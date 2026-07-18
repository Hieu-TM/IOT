import io

import numpy as np
import pytest
from PIL import Image

from ml.infer import detector_roboflow as rfmod
from ml.infer.detector import Detection, DetectionResult


def _jpeg_bytes(w=64, h=48):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _detector(**kw):
    kw.setdefault("api_key", "k")
    kw.setdefault("workspace", "ws")
    kw.setdefault("workflow_id", "wf")
    return rfmod.RoboflowWorkflowDetector(**kw)


class _Resp:
    def __init__(self, payload, code=200):
        self._payload = payload
        self.status_code = code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise rfmod.requests.HTTPError(f"status {self.status_code}", response=self)


# --- construction / validation -------------------------------------------

def test_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        _detector(api_key="")


def test_requires_workspace():
    with pytest.raises(ValueError, match="workspace"):
        _detector(workspace="")


def test_requires_workflow_id():
    with pytest.raises(ValueError, match="workflow_id"):
        _detector(workflow_id="")


def test_url_is_endpoint_workspace_workflows_id():
    det = _detector(workspace="my-ws", workflow_id="my-wf")
    assert det.url == "https://serverless.roboflow.com/my-ws/workflows/my-wf"


# --- request envelope ----------------------------------------------------

def test_run_posts_workflow_envelope(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp([{}])

    monkeypatch.setattr(rfmod.requests, "post", fake_post)

    det = _detector(image_input_name="photo")
    det.run(_jpeg_bytes())

    assert captured["url"] == det.url
    assert captured["json"]["api_key"] == "k"
    image_input = captured["json"]["inputs"]["photo"]
    assert image_input["type"] == "base64"
    assert isinstance(image_input["value"], str) and image_input["value"]


# --- prediction extraction (output names are NOT hard-coded) -------------

def test_extract_with_explicit_key():
    entry = {"my_out": {"predictions": [{"x": 1, "y": 1, "width": 2, "height": 2}]}}
    assert len(rfmod.extract_predictions(entry, "my_out")) == 1


def test_extract_with_dotted_key():
    entry = {"a": {"b": [{"x": 1, "y": 1, "width": 2, "height": 2}]}}
    assert len(rfmod.extract_predictions(entry, "a.b")) == 1


def test_extract_autodetects_nested_predictions():
    entry = {"model_predictions": {"predictions": [
        {"x": 1, "y": 1, "width": 2, "height": 2}]}}
    assert len(rfmod.extract_predictions(entry)) == 1


def test_extract_autodetects_arbitrary_output_name():
    entry = {"whatever_the_user_named_it": [
        {"x": 1, "y": 1, "width": 2, "height": 2}]}
    assert len(rfmod.extract_predictions(entry)) == 1


def test_extract_returns_empty_when_nothing_matches():
    assert rfmod.extract_predictions({"stats": {"count": 3}}) == []
    assert rfmod.extract_predictions({}) == []


# --- bbox conversion -----------------------------------------------------

def test_run_converts_center_bbox_to_top_left(monkeypatch):
    payload = [{"model_predictions": {"predictions": [
        # center (100, 200), size 40x60 -> top-left (80, 170)
        {"x": 100, "y": 200, "width": 40, "height": 60,
         "class": "fragment", "confidence": 0.87}]}}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))

    result = _detector().run(_jpeg_bytes(w=640, h=480))

    assert isinstance(result, DetectionResult)
    assert result.image_width == 640 and result.image_height == 480
    assert len(result.detections) == 1
    d = result.detections[0]
    assert isinstance(d, Detection)
    assert d.bbox_xywh == (80, 170, 40, 60)
    assert d.class_name == "fragment"
    assert d.confidence == 0.87


def test_run_handles_multiple_predictions(monkeypatch):
    payload = [{"out": [
        {"x": 10, "y": 10, "width": 4, "height": 4, "class": "fiber", "confidence": 0.5},
        # Both boxes must lie INSIDE the 64x48 test image: an out-of-frame box is
        # dropped by design (see test_run_drops_box_entirely_outside_image), which
        # is not what this test is about.
        {"x": 50, "y": 30, "width": 10, "height": 20, "class": "film", "confidence": 0.9}]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))

    result = _detector().run(_jpeg_bytes())

    assert [d.bbox_xywh for d in result.detections] == [(8, 8, 4, 4), (45, 20, 10, 20)]
    assert [d.class_name for d in result.detections] == ["fiber", "film"]


def test_run_returns_empty_detections_when_workflow_found_none(monkeypatch):
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp([{"out": []}]))
    result = _detector().run(_jpeg_bytes(w=32, h=32))
    assert result.detections == []
    assert result.image_width == 32 and result.image_height == 32


def test_run_array_encodes_and_delegates(monkeypatch):
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp([{}]))
    result = _detector().run_array(np.zeros((32, 48, 3), dtype=np.uint8))
    assert isinstance(result, DetectionResult)
    assert result.image_width == 48 and result.image_height == 32


# --- retries -------------------------------------------------------------

def test_run_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    payload = [{"out": [{"x": 5, "y": 5, "width": 2, "height": 2}]}]

    def flaky(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise rfmod.requests.ConnectionError("boom")
        return _Resp(payload)

    monkeypatch.setattr(rfmod.requests, "post", flaky)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    result = _detector(retries=2).run(_jpeg_bytes())

    assert calls["n"] == 2
    assert len(result.detections) == 1


def test_run_raises_after_retries_exhausted(monkeypatch):
    def always_fail(url, json=None, timeout=None):
        raise rfmod.requests.ConnectionError("down")

    monkeypatch.setattr(rfmod.requests, "post", always_fail)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    with pytest.raises(rfmod.requests.ConnectionError):
        _detector(retries=1).run(_jpeg_bytes())


def test_run_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp({}, code=403))
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)
    with pytest.raises(rfmod.requests.HTTPError):
        _detector(retries=0).run(_jpeg_bytes())


def test_run_does_not_retry_client_error(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _Resp({}, code=403)

    monkeypatch.setattr(rfmod.requests, "post", fake_post)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    with pytest.raises(rfmod.requests.HTTPError):
        _detector(retries=3).run(_jpeg_bytes())

    assert calls["n"] == 1   # a bad api_key fails fast, no retries


def test_run_retries_server_error(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _Resp({}, code=500)

    monkeypatch.setattr(rfmod.requests, "post", fake_post)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    with pytest.raises(rfmod.requests.HTTPError):
        _detector(retries=2).run(_jpeg_bytes())

    assert calls["n"] == 3   # 5xx is transient -> retried


def test_run_retries_rate_limit(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _Resp({}, code=429)

    monkeypatch.setattr(rfmod.requests, "post", fake_post)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    with pytest.raises(rfmod.requests.HTTPError):
        _detector(retries=1).run(_jpeg_bytes())

    assert calls["n"] == 2   # 429 IS worth backing off on


def test_run_clamps_edge_touching_box_to_non_negative_origin(monkeypatch):
    # center x=6 width=20 -> raw x0 = -4, must clamp to 0 with width shrunk to 16
    payload = [{"out": [{"x": 6, "y": 30, "width": 20, "height": 20,
                         "class": "fiber", "confidence": 0.5}]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))
    result = _detector().run(_jpeg_bytes(w=64, h=48))
    assert result.detections[0].bbox_xywh == (0, 20, 16, 20)


def test_run_clamps_box_overflowing_right_and_bottom(monkeypatch):
    # image is 64x48; center (60,44) size 20x20 -> x1=70 -> clamp 64, y1=54 -> clamp 48
    payload = [{"out": [{"x": 60, "y": 44, "width": 20, "height": 20,
                         "class": "film", "confidence": 0.5}]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))
    result = _detector().run(_jpeg_bytes(w=64, h=48))
    assert result.detections[0].bbox_xywh == (50, 34, 14, 14)


def test_run_drops_box_entirely_outside_image(monkeypatch):
    payload = [{"out": [{"x": -50, "y": -50, "width": 10, "height": 10,
                         "class": "ghost", "confidence": 0.5}]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))
    result = _detector().run(_jpeg_bytes(w=64, h=48))
    assert result.detections == []


def test_run_never_emits_negative_origin(monkeypatch):
    payload = [{"out": [
        {"x": 1, "y": 1, "width": 30, "height": 30, "class": "a", "confidence": 0.5},
        {"x": 63, "y": 47, "width": 30, "height": 30, "class": "b", "confidence": 0.5},
    ]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))
    result = _detector().run(_jpeg_bytes(w=64, h=48))
    assert result.detections, "expected boxes to survive clamping"
    for d in result.detections:
        assert d.bbox_xywh[0] >= 0 and d.bbox_xywh[1] >= 0   # ingest schema requires ge=0
        assert d.bbox_xywh[2] > 0 and d.bbox_xywh[3] > 0


def test_run_warns_once_when_no_predictions_resolved(monkeypatch, capsys):
    payload = [{"some_other_output": {"count": 0}}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))
    det = _detector()
    det.run(_jpeg_bytes())
    det.run(_jpeg_bytes())
    out = capsys.readouterr().out
    assert "no predictions resolved" in out
    assert out.count("no predictions resolved") == 1   # warn once, not per frame


def test_run_skips_malformed_predictions(monkeypatch):
    payload = [{"out": [
        {"x": 10, "y": 10, "width": 4, "height": 4, "class": "fiber", "confidence": 0.5},
        {"not": "a bbox"},
    ]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))

    result = _detector().run(_jpeg_bytes())

    assert len(result.detections) == 1
    assert result.detections[0].class_name == "fiber"


# --- probe summariser (must never emit blobs) ----------------------------

def test_summarize_elides_large_blobs():
    out = rfmod.summarize_response({"visualization": "A" * 5000})
    assert "A" * 100 not in out
    assert "elided" in out


def test_summarize_reports_keys_and_types():
    out = rfmod.summarize_response({"count": 3, "preds": [{"x": 1}]})
    assert "count" in out
    assert "preds" in out
