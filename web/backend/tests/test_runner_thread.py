"""Vòng đời thread của Runner. Máy trạng thái đã được test riêng ở
test_runner.py — ở đây chỉ hỏi: thread có chạy, có dừng, và có từ chối chạy
hai lần không.
"""

import time

import pytest

from app.runner import Runner, RunnerBusy, RunnerConfig, RunnerConfigError
from tests.fakes_runner import FakeDetector, FakePoster, FakeStation


def make_cfg(host="board.local", mode="preview"):
    return RunnerConfig(
        mode=mode,
        station_host=host,
        capture_delay_s=0.0,
        px_per_mm=14.0,
        batch_lot=None,
        api_url="http://localhost:8000",
    )


def make_runner(station):
    return Runner(
        station_factory=lambda host: station,
        detector_factory=FakeDetector,
        poster=FakePoster(),
    )


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_start_runs_ticks_in_background_then_stop_ends_them():
    station = FakeStation(phase="SETTLING")
    runner = make_runner(station)

    runner.start(make_cfg(), poll_interval_s=0.01)
    assert wait_until(lambda: station.captures >= 1), "thread không chạy tick"
    runner.stop()

    assert runner.snapshot()["running"] is False
    settled = station.captures
    time.sleep(0.1)
    assert station.captures == settled, "thread vẫn chạy sau khi stop"


def test_start_twice_raises_busy():
    station = FakeStation()
    runner = make_runner(station)
    runner.start(make_cfg(), poll_interval_s=0.01)
    try:
        with pytest.raises(RunnerBusy):
            runner.start(make_cfg(), poll_interval_s=0.01)
    finally:
        runner.stop()


def test_stop_when_idle_is_a_no_op():
    runner = make_runner(FakeStation())
    runner.stop()      # không được ném
    assert runner.snapshot()["running"] is False


def test_start_without_host_raises_config_error():
    runner = make_runner(FakeStation())
    with pytest.raises(RunnerConfigError):
        runner.start(make_cfg(host=""), poll_interval_s=0.01)


def test_start_again_after_stop_works():
    station = FakeStation(phase="SETTLING")
    runner = make_runner(station)

    runner.start(make_cfg(), poll_interval_s=0.01)
    wait_until(lambda: station.captures >= 1)
    runner.stop()
    first = station.captures

    runner.start(make_cfg(), poll_interval_s=0.01)
    assert wait_until(lambda: station.captures > first)
    runner.stop()


def test_thread_stops_itself_when_the_board_dies():
    station = FakeStation()
    station.device_error = OSError("board rút điện")
    runner = make_runner(station)

    runner.start(make_cfg(), poll_interval_s=0.01)

    assert wait_until(lambda: runner.snapshot()["running"] is False), \
        "runner phải tự dừng khi board chết, không quay vô tận"
    runner.stop()
    assert "board rút điện" in runner.snapshot()["error"]
