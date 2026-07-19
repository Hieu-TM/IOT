import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

import ml.infer.cli as cli
from ml.infer.detector import Detection, DetectionResult
from ml.tests.test_source import _DEVICE_JSON, _FakeBoard, _jpeg_bytes

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _jpeg(path):
    Image.new("RGB", (32, 32), (120, 120, 120)).save(path, format="JPEG")


class _FakeDetector:
    def __init__(self, weights):
        pass

    def run(self, image_bytes):
        return DetectionResult(
            detections=[Detection((1, 2, 3, 4), "fiber", 0.8)],
            image_width=32,
            image_height=32,
        )


def test_cli_posts_and_tallies(tmp_path, monkeypatch, capsys):
    _jpeg(tmp_path / "a.jpg")
    _jpeg(tmp_path / "b.jpg")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    posted = []

    def fake_post(api_url, metadata, image_bytes, image_name):
        posted.append(metadata)

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--weights", "x", "--px-per-mm", "10",
                   "--api-url", "http://x"])

    assert rc == 0
    assert len(posted) == 2
    assert "2 created" in capsys.readouterr().out


def test_cli_dry_run_does_not_post(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    called = {"n": 0}

    def fake_post(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--dry-run", "--px-per-mm", "10"])
    assert rc == 0 and called["n"] == 0


def test_cli_counts_failures(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    def fake_post(*a, **k):
        class R:
            status = "failed"
            http_status = 422
            detail = "bad"

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--px-per-mm", "10"])
    assert rc == 1


def test_cli_warns_on_sample_code_collision(tmp_path, monkeypatch, capsys):
    # a.jpg and a.png both sanitize to sample_code "a"
    _jpeg(tmp_path / "a.jpg")
    _jpeg(tmp_path / "a.png")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    posted = []

    def fake_post(api_url, metadata, image_bytes, image_name):
        posted.append(metadata)

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--px-per-mm", "10"])
    out = capsys.readouterr().out

    assert len(posted) == 1          # only the first file is sent; the collision is skipped
    assert "collision" in out
    assert rc == 1                   # a not-stored sample makes the run non-zero


def test_cli_warns_when_px_per_mm_omitted(tmp_path, monkeypatch, capsys):
    _jpeg(tmp_path / "a.jpg")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    def fake_post(api_url, metadata, image_bytes, image_name):
        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path)])   # no --px-per-mm
    out = capsys.readouterr().out
    assert "PLACEHOLDER" in out
    assert rc == 0


def test_cli_uses_config_defaults_when_flags_omitted(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[ingest]\napi_url = "http://from-config:1234"\n'
        'device_id = "dev-from-config"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    seen = {}

    def fake_post(api_url, metadata, image_bytes, image_name):
        seen["api_url"] = api_url
        seen["device_id"] = metadata["device_id"]

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--config", str(cfg_file), "--px-per-mm", "10"])

    assert rc == 0
    assert seen["api_url"] == "http://from-config:1234"
    assert seen["device_id"] == "dev-from-config"


def test_cli_flag_overrides_config(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[ingest]\napi_url = "http://from-config:1234"\n',
                        encoding="utf-8")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    seen = {}

    def fake_post(api_url, metadata, image_bytes, image_name):
        seen["api_url"] = api_url

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--config", str(cfg_file),
                   "--api-url", "http://from-flag:9999", "--px-per-mm", "10"])

    assert rc == 0
    assert seen["api_url"] == "http://from-flag:9999"   # flag beats config


def test_cli_config_px_per_mm_suppresses_placeholder_warning(tmp_path, monkeypatch, capsys):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[calibration]\npx_per_mm = 20.0\n', encoding="utf-8")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    def fake_post(api_url, metadata, image_bytes, image_name):
        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--config", str(cfg_file)])  # no --px-per-mm
    out = capsys.readouterr().out

    assert rc == 0
    assert "PLACEHOLDER" not in out   # a configured calibration is a deliberate choice


def test_check_config_reports_ok_for_local_with_weights(tmp_path, capsys):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fake")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f'[local]\nweights = "{weights.as_posix()}"\n',
                        encoding="utf-8")

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "OK" in out


def test_check_config_reports_missing_roboflow_key(tmp_path, capsys):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[general]\nbackend = "roboflow"\n', encoding="utf-8")

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "api_key" in out


def test_check_config_never_prints_the_api_key(tmp_path, capsys):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[general]\nbackend = "roboflow"\n'
        '[roboflow]\napi_key = "SUPERSECRET123"\nworkspace = "ws"\n'
        'workflow_id = "wf"\n',
        encoding="utf-8",
    )

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "SUPERSECRET123" not in out   # secrets must never be echoed


def test_backend_roboflow_builds_workflow_detector(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[roboflow]\napi_key = "k"\nworkspace = "ws"\nworkflow_id = "wf"\n'
        'predictions_key = "out"\n',
        encoding="utf-8",
    )

    built = {}

    class _FakeWorkflowDetector:
        def __init__(self, **kwargs):
            built.update(kwargs)

        def run(self, image_bytes):
            return DetectionResult(
                detections=[Detection((1, 2, 3, 4), "fiber", 0.8)],
                image_width=32, image_height=32,
            )

    monkeypatch.setattr(cli, "RoboflowWorkflowDetector", _FakeWorkflowDetector)
    monkeypatch.setattr(
        cli, "post",
        lambda *a, **k: type("R", (), {"status": "created",
                                       "http_status": 201, "detail": ""})(),
    )

    rc = cli.main([str(tmp_path), "--config", str(cfg_file),
                   "--backend", "roboflow", "--px-per-mm", "10"])

    assert rc == 0
    assert built["api_key"] == "k"
    assert built["workspace"] == "ws"
    assert built["workflow_id"] == "wf"
    assert built["predictions_key"] == "out"


def test_cli_reports_actionable_error_when_roboflow_unconfigured(tmp_path, capsys):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[general]\nbackend = "roboflow"\n', encoding="utf-8")

    rc = cli.main([str(tmp_path), "--config", str(cfg_file), "--px-per-mm", "10"])
    out = capsys.readouterr().out

    assert rc == 2
    assert "cannot start backend" in out
    assert "api_key" in out
    assert "--check-config" in out


def test_from_board_and_folder_together_is_rejected(tmp_path, capsys):
    rc = cli.main([str(tmp_path), "--from-board", "192.168.1.50"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "--from-board" in out


def test_no_input_and_no_station_host_reports_both_options(capsys):
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 2
    assert "--from-board" in out


# --- Important #1: --check-config --from-board tự mâu thuẫn (đã sửa) -------

def test_check_config_from_board_flag_is_not_reported_missing(tmp_path, capsys):
    # Trước khi sửa: station_host tới từ --from-board nhưng
    # cfg.missing_for("station") chỉ đọc cfg.station.host (rỗng) nên vẫn báo
    # thiếu, dù dòng "station = 10.0.0.5" ngay phía trên đã in ra host hợp lệ.
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fake")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f'[local]\nweights = "{weights.as_posix()}"\n',
                        encoding="utf-8")

    rc = cli.main(["--config", str(cfg_file), "--check-config",
                   "--from-board", "10.0.0.5"])
    out = capsys.readouterr().out

    assert "station = 10.0.0.5" in out
    assert "chưa đặt" not in out
    assert rc == 0
    assert "OK" in out


def test_check_config_still_flags_missing_station_host_without_from_board(tmp_path, capsys):
    # Đối chứng: host thật sự chưa đặt ở đâu cả (không --from-board, không
    # [station].host trong config) thì không tự ý bật kiểm tra station - hành
    # vi cũ, không được phá khi sửa Important #1 (nguồn ảnh trực giao với
    # backend; ai chạy thư mục ảnh không bị bắt khai host).
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fake")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f'[local]\nweights = "{weights.as_posix()}"\n',
                        encoding="utf-8")

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert "station" not in out
    assert rc == 0


def test_check_config_reports_missing_station_host_when_configured_host_is_empty(tmp_path, capsys):
    # Host đến từ [station].host trong config (không phải cờ) mà vẫn rỗng ->
    # phải giữ nguyên hành vi báo thiếu khi người dùng CÓ mở mục [station]
    # nhưng bỏ trống host.
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fake")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        f'[local]\nweights = "{weights.as_posix()}"\n'
        '[station]\nhost = "10.0.0.9"\n',
        encoding="utf-8",
    )

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert "station = 10.0.0.9" in out
    assert "chưa đặt" not in out
    assert rc == 0


# --- Important #2: UnicodeEncodeError khi in StationError (đã sửa) ---------

def test_station_error_at_init_exits_gracefully(tmp_path, monkeypatch, capsys):
    # Yêu cầu #5 (khoảng trống test): StationError lúc khởi tạo Esp32CaptureSource
    # phải làm CLI thoát tử tế (mã lỗi đúng, thông báo dùng được), không traceback.
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("", encoding="utf-8")

    # Cổng 1 trên localhost: không ai lắng nghe -> ECONNREFUSED ngay, không
    # cần chờ hết timeout thật.
    rc = cli.main(["--config", str(cfg_file), "--from-board", "127.0.0.1:1",
                   "--px-per-mm", "10"])
    out = capsys.readouterr().out

    assert rc == 2
    assert "[error]" in out
    assert "Traceback" not in out


def test_from_board_station_error_does_not_crash_under_cp1252_console(tmp_path):
    """Khóa lại Important #2 đúng kiểu bắt được lỗi: chạy CLI thật trong tiến
    trình con với PYTHONIOENCODING=cp1252 (console Windows mặc định), rồi
    khẳng định nó thoát bằng mã lỗi tử tế chứ không phải UnicodeEncodeError.
    capsys của pytest không đi qua encoding của console nên không bắt được ca
    này - phải chạy subprocess thật (giống cách dataset_collector đã làm).
    """
    cfg_file = tmp_path / "config.toml"
    # backend=roboflow với key giả: build_detector() không đụng mạng lúc khởi
    # tạo (chỉ validate có mặt các trường), nên chạy được tới bước tạo
    # Esp32CaptureSource mà không cần ultralytics/weights thật.
    cfg_file.write_text(
        '[general]\nbackend = "roboflow"\n'
        '[roboflow]\napi_key = "k"\nworkspace = "ws"\nworkflow_id = "wf"\n',
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"

    # QUAN TRỌNG: force_utf8_output() ép stdout của TIẾN TRÌNH CON sang UTF-8
    # bất kể PYTHONIOENCODING=cp1252 mô phỏng console Windows - đó chính là
    # cách nó tránh UnicodeEncodeError. Vì vậy phía cha (subprocess.run) phải
    # tự giải mã bằng UTF-8, KHÔNG dùng locale mặc định của máy (ở đây cũng
    # là cp1252) - nếu không luồng đọc pipe của subprocess sẽ tự
    # UnicodeDecodeError và proc.stdout/proc.stderr về None, che mất phép thử
    # thật (xem lỗi encoding của chính máy cha nếu bỏ encoding="utf-8" ở đây).
    proc = subprocess.run(
        [sys.executable, "-m", "ml.infer", "--config", str(cfg_file),
         "--from-board", "127.0.0.1:1", "--px-per-mm", "10"],
        cwd=str(_REPO_ROOT), env=env, capture_output=True,
        encoding="utf-8", errors="replace", timeout=60,
    )

    assert proc.returncode == 2, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "UnicodeEncodeError" not in proc.stderr
    assert "Traceback" not in proc.stderr
    assert "[error]" in proc.stdout


# --- Khoảng trống #3: thứ tự ưu tiên device_id (--from-board) --------------

def _fake_post_recorder(monkeypatch, posted):
    def fake_post(api_url, metadata, image_bytes, image_name):
        posted.append(metadata)

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)


def test_device_id_flag_wins_over_board_and_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[ingest]\ndevice_id = "cfg-device"\n', encoding="utf-8")
    posted = []
    _fake_post_recorder(monkeypatch, posted)

    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        rc = cli.main(["--config", str(cfg_file), "--from-board", board.host,
                       "--device-id", "flag-device", "--px-per-mm", "10"])

    assert rc == 0
    assert len(posted) == 1
    assert posted[0]["device_id"] == "flag-device"


def test_device_id_board_wins_over_config_when_flag_omitted(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[ingest]\ndevice_id = "cfg-device"\n', encoding="utf-8")
    posted = []
    _fake_post_recorder(monkeypatch, posted)

    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        rc = cli.main(["--config", str(cfg_file), "--from-board", board.host,
                       "--px-per-mm", "10"])

    assert rc == 0
    assert len(posted) == 1
    assert posted[0]["device_id"] == _DEVICE_JSON["device_id"]


def test_device_block_reaches_the_posted_payload(tmp_path, monkeypatch):
    """Khối /device phải đi hết đường tới payload gửi đi, không chỉ tới mapper.

    test_mapper.py kiểm build_metadata() một mình bằng dict tay, nên nếu ai đó
    refactor cli.py làm rơi mất dòng truyền device_info thì mọi test vẫn xanh
    trong khi khối /device âm thầm biến mất khỏi sổ audit ở môi trường thật —
    đúng thứ duy nhất mà Task 9 sinh ra để bảo đảm. Test này khoá đường đi đó.
    """
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    posted = []
    _fake_post_recorder(monkeypatch, posted)

    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        rc = cli.main(["--from-board", board.host, "--px-per-mm", "10"])

    assert rc == 0
    assert len(posted) == 1
    device = posted[0].get("device")
    assert device is not None, "khối /device không tới được payload"
    assert device["firmware"] == _DEVICE_JSON["firmware"]
    assert device["camera"]["exposure"] == _DEVICE_JSON["camera"]["exposure"]
    assert device["prefs_saved"] == _DEVICE_JSON["prefs_saved"]


def test_device_block_absent_when_reading_a_folder(tmp_path, monkeypatch):
    """Chạy từ thư mục ảnh thì không có board nào — metadata không được có
    khóa `device` (đừng nhét null vào sổ audit)."""
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    posted = []
    _fake_post_recorder(monkeypatch, posted)
    _jpeg(tmp_path / "a.jpg")

    rc = cli.main([str(tmp_path), "--px-per-mm", "10"])

    assert rc == 0
    assert len(posted) == 1
    assert "device" not in posted[0]


def test_device_id_falls_back_to_config_when_board_does_not_report_one(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[ingest]\ndevice_id = "cfg-device"\n', encoding="utf-8")
    posted = []
    _fake_post_recorder(monkeypatch, posted)

    device_json_without_id = dict(_DEVICE_JSON)
    del device_json_without_id["device_id"]

    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", device_json_without_id)) as board:
        rc = cli.main(["--config", str(cfg_file), "--from-board", board.host,
                       "--px-per-mm", "10"])

    assert rc == 0
    assert len(posted) == 1
    assert posted[0]["device_id"] == "cfg-device"


# --- Khoảng trống #4: --dry-run + --from-board không được POST -------------

def test_dry_run_with_from_board_makes_no_post_request(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "Detector", _FakeDetector)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("", encoding="utf-8")
    called = {"n": 0}

    def fake_post(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(cli, "post", fake_post)

    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        rc = cli.main(["--config", str(cfg_file), "--from-board", board.host,
                       "--dry-run", "--px-per-mm", "10"])

    assert rc == 0
    assert called["n"] == 0   # DB là sổ audit, mỗi bản ghi là vĩnh viễn - dry-run
                              # không được tạo bất kỳ request POST nào.
