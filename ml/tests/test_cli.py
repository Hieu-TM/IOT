from PIL import Image

import ml.infer.cli as cli
from ml.infer.detector import Detection, DetectionResult


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
