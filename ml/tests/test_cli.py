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
