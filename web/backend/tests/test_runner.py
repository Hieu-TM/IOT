"""Runner — máy trạng thái chụp theo cạnh pha bơm.

Gọi tick() trực tiếp với đồng hồ giả: máy trạng thái phải xác định, không phụ
thuộc thread timing. Vòng đời thread nằm ở test_runner_thread.py.
"""

import pytest

from app.runner import MAX_CONSECUTIVE_ERRORS, Runner, RunnerConfig
from tests.fakes_runner import (FakeClock, FakeDetector, FakePoster,
                                FakeStation)


def make_runner(station, detector=None, poster=None, clock=None, mode="measure",
                capture_delay_s=0.8):
    clock = clock or FakeClock()
    poster = poster or FakePoster()
    runner = Runner(
        station_factory=lambda host: station,
        detector_factory=lambda: detector or FakeDetector(),
        poster=poster,
        monotonic=clock,
    )
    cfg = RunnerConfig(
        mode=mode,
        station_host="board.local",
        capture_delay_s=capture_delay_s,
        px_per_mm=14.0,
        batch_lot="LOT-1",
        api_url="http://localhost:8000",
    )
    runner.arm(cfg)
    return runner, clock, poster


def drive_one_cycle(runner, station, clock, settle_ticks=4):
    """Một chu kỳ bơm: FILLING -> SETTLING (nhiều tick) -> FLUSHING."""
    station.phase = "FILLING"
    runner.tick()
    station.phase = "SETTLING"
    for _ in range(settle_ticks):
        runner.tick()
        clock.advance(0.5)
    station.phase = "FLUSHING"
    runner.tick()


def test_one_capture_per_settling_cycle():
    # TEST QUAN TRỌNG NHẤT của plan này. Pha SETTLING kéo dài nhiều lần poll;
    # bắt TRẠNG THÁI thay vì CẠNH sẽ chụp 4 lần cho một chu kỳ bơm và nhồi sổ
    # audit toàn mẫu trùng của cùng một lần lấy nước.
    station = FakeStation()
    runner, clock, poster = make_runner(station)

    drive_one_cycle(runner, station, clock)

    assert station.captures == 1
    assert len(poster.calls) == 1
    assert runner.snapshot()["counters"]["cycles"] == 1


def test_three_cycles_give_three_samples():
    station = FakeStation()
    runner, clock, poster = make_runner(station)

    for _ in range(3):
        drive_one_cycle(runner, station, clock)

    assert station.captures == 3
    assert runner.snapshot()["counters"]["written"] == 3
    # Mã mẫu phải khác nhau, nếu không ingest coi các khung sau là bản retry
    codes = [call[1]["sample_code"] for call in poster.calls]
    assert len(set(codes)) == 3


def test_no_capture_before_the_delay_elapses():
    station = FakeStation()
    runner, clock, poster = make_runner(station, capture_delay_s=0.8)

    station.phase = "FILLING"
    runner.tick()
    station.phase = "SETTLING"
    runner.tick()              # cạnh: mới hẹn giờ, chưa tới lúc chụp

    assert station.captures == 0

    clock.advance(0.9)
    runner.tick()

    assert station.captures == 1


def test_preview_mode_never_posts():
    station = FakeStation()
    runner, clock, poster = make_runner(station, mode="preview")

    drive_one_cycle(runner, station, clock)

    assert station.captures == 1          # vẫn chụp và suy luận
    assert poster.calls == []             # nhưng KHÔNG ghi gì
    assert runner.snapshot()["counters"]["written"] == 0
    assert runner.snapshot()["last"]["written"] is False


def test_preview_frame_is_kept_in_memory_for_the_browser():
    station = FakeStation()
    runner, clock, _ = make_runner(station, mode="preview")

    drive_one_cycle(runner, station, clock)

    assert runner.preview_jpeg() == b"\xff\xd8fake-jpeg\xff\xd9"


def test_keep_writes_the_held_preview_frame():
    station = FakeStation()
    runner, clock, poster = make_runner(station, mode="preview")
    drive_one_cycle(runner, station, clock)

    out = runner.keep()

    assert len(poster.calls) == 1
    assert out["sample_code"] == poster.calls[0][1]["sample_code"]
    assert runner.snapshot()["counters"]["written"] == 1


def test_keep_without_a_preview_frame_raises():
    station = FakeStation()
    runner, _, _ = make_runner(station, mode="preview")

    with pytest.raises(RuntimeError):
        runner.keep()


def test_metadata_carries_lot_calibration_and_board_identity():
    station = FakeStation()
    runner, clock, poster = make_runner(station)

    drive_one_cycle(runner, station, clock)

    meta = poster.calls[0][1]
    assert meta["batch_lot"] == "LOT-1"
    assert meta["px_per_mm"] == 14.0
    assert meta["device_id"] == "aqua-cam-test"   # tên board tự báo, không phải hằng
    assert meta["device"]["firmware"] == "aqua_scope_station/1.0.0"
    assert len(meta["particles"]) == 2


def test_device_errors_stop_the_runner_after_the_limit():
    # Quay vô tận trong im lặng là kiểu hỏng tệ nhất cho một trạm QC.
    station = FakeStation()
    station.device_error = OSError("mạng chết")
    runner, _, _ = make_runner(station)

    for _ in range(MAX_CONSECUTIVE_ERRORS - 1):
        runner.tick()
        assert runner.snapshot()["running"] is True

    runner.tick()

    snap = runner.snapshot()
    assert snap["running"] is False
    assert "mạng chết" in snap["error"]


def test_one_good_read_resets_the_error_streak():
    station = FakeStation()
    runner, _, _ = make_runner(station)

    station.device_error = OSError("chớp mạng")
    for _ in range(MAX_CONSECUTIVE_ERRORS - 1):
        runner.tick()
    station.device_error = None
    runner.tick()

    for _ in range(MAX_CONSECUTIVE_ERRORS - 1):
        station.device_error = OSError("chớp mạng")
        runner.tick()

    assert runner.snapshot()["running"] is True


def test_capture_failure_counts_and_keeps_running():
    station = FakeStation()
    station.capture_error = RuntimeError("JPEG cụt")
    runner, clock, poster = make_runner(station)

    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    assert snap["counters"]["failed"] == 1
    assert snap["running"] is True        # một khung hỏng không giết lượt đo
    assert poster.calls == []


def test_detector_failure_counts_and_keeps_running():
    station = FakeStation()
    runner, clock, poster = make_runner(station, detector=FakeDetector(raises=True))

    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    assert snap["counters"]["failed"] == 1
    assert snap["running"] is True
    assert poster.calls == []


def test_failed_post_counts_as_failed_not_written():
    station = FakeStation()
    poster = FakePoster(status="failed")
    runner, clock, _ = make_runner(station, poster=poster)

    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    assert snap["counters"]["written"] == 0
    assert snap["counters"]["failed"] == 1


def test_already_exists_counts_as_written():
    station = FakeStation()
    poster = FakePoster(status="already_exists")
    runner, clock, _ = make_runner(station, poster=poster)

    drive_one_cycle(runner, station, clock)

    assert runner.snapshot()["counters"]["written"] == 1


def test_warns_when_pump_is_not_in_auto():
    # Bơm không auto -> pha không đổi -> không khung nào được chụp. Đúng, nhưng
    # nếu để im thì trông y hệt "hệ thống treo".
    station = FakeStation(auto=False)
    runner, _, _ = make_runner(station)

    runner.tick()

    assert any("auto" in w for w in runner.snapshot()["warnings"])


def test_warns_when_aec_or_agc_still_on():
    station = FakeStation(aec=1)
    runner, _, _ = make_runner(station)

    runner.tick()

    assert any("AEC" in w for w in runner.snapshot()["warnings"])


def test_warns_when_capture_delay_exceeds_settle_window():
    station = FakeStation(settle_ms=500)
    runner, _, _ = make_runner(station, capture_delay_s=0.8)

    runner.tick()

    assert any("FLUSHING" in w for w in runner.snapshot()["warnings"])


def test_no_warnings_on_a_healthy_board():
    station = FakeStation()
    runner, _, _ = make_runner(station)

    runner.tick()

    assert runner.snapshot()["warnings"] == []


def test_snapshot_is_a_copy_not_live_state():
    # Handler HTTP đọc snapshot trong khi worker đang ghi; trả về tham chiếu
    # sống là mở đường cho dữ liệu đọc dở.
    station = FakeStation()
    runner, clock, _ = make_runner(station)
    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    snap["counters"]["written"] = 999

    assert runner.snapshot()["counters"]["written"] == 1
