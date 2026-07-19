# Branch-1 PC Inference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PC-side CLI that runs a Roboflow-trained YOLO detector on images and POSTs count/size/label results to the existing `/api/ingest` endpoint, so Aqua Scope gets end-to-end debris detection without on-device inference.

**Architecture:** A layered package `ml/infer/` with one responsibility per file — image source, detector wrapper, detection→schema mapper, ingest HTTP client, CLI orchestrator, plus a separate visualization-only live preview. Folder source now; ESP32 `/capture` source drops in later behind the same interface. Output conforms to the already-built `POST /api/ingest` contract; the web backend is not touched.

**Tech Stack:** Python 3, Ultralytics YOLO, Pillow + NumPy (image decode), `requests` (HTTP), OpenCV (preview only), pytest.

## Global Constraints

- Do **not** modify the web backend or change the `particles`/`Sample` schema. Produce the payload it already accepts (`web/backend/app/models.py` `IngestPayload`/`ParticleIn`).
- `sample_code` must match `^[A-Za-z0-9._-]{1,64}$` verbatim (web SEC-1). Derive it from the source filename, sanitized.
- `captured_at` must be timezone-aware ISO 8601 (web rejects offset-less values with 422).
- Honesty rules baked into code + comments: warn when `px_per_mm` is defaulted (`size_mm` is then a placeholder, not real calibration); `area_px = w*h` is bbox area, **not** true blob area; `label` is a free string.
- Model weights live at `ml/models/best.pt` (gitignored; source recorded in `ml/README.md`).
- `ml/infer/preview.py` must **not** import `ingest_client` — the preview path can never write to the DB.
- Mirror `web/backend/app/config.py` `PX_PER_MM_DEFAULT = 14.0` as a local constant (do not import across packages); keep in sync via comment.
- Run tests with `python -m pytest ml/tests/ -v` from the repo root (puts cwd on `sys.path` so `import ml.infer...` resolves).

---

### Task 1: Package scaffold + pure naming helpers

**Files:**
- Create: `ml/__init__.py` (empty), `ml/infer/__init__.py` (empty), `ml/tests/__init__.py` (empty)
- Create: `ml/infer/naming.py`
- Test: `ml/tests/test_naming.py`

**Interfaces:**
- Produces: `sample_code_from_filename(filename: str) -> str`; `resolve_px_per_mm(value: float | None) -> tuple[float, bool]`; `DEFAULT_PX_PER_MM: float`.

- [ ] **Step 1: Write the failing test**

`ml/tests/test_naming.py`:
```python
from ml.infer.naming import (
    sample_code_from_filename,
    resolve_px_per_mm,
    DEFAULT_PX_PER_MM,
)


def test_sample_code_strips_unsafe_chars():
    assert sample_code_from_filename("my photo (1).JPG") == "my-photo--1"


def test_sample_code_handles_path_and_traversal():
    assert sample_code_from_filename("../../etc/passwd.png") == "passwd"


def test_sample_code_truncates_to_64():
    long_name = "a" * 100 + ".jpg"
    assert len(sample_code_from_filename(long_name)) == 64


def test_sample_code_never_empty():
    assert sample_code_from_filename("---.jpg") == "sample"


def test_resolve_px_per_mm_default():
    assert resolve_px_per_mm(None) == (DEFAULT_PX_PER_MM, True)


def test_resolve_px_per_mm_explicit():
    assert resolve_px_per_mm(20.0) == (20.0, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.naming'`

- [ ] **Step 3: Create the empty package markers**

Create `ml/__init__.py`, `ml/infer/__init__.py`, `ml/tests/__init__.py` — all empty files.

- [ ] **Step 4: Write minimal implementation**

`ml/infer/naming.py`:
```python
"""Pure helpers shared across the inference package (no I/O, no heavy deps)."""

import re
from pathlib import Path

# Mirror of web/backend/app/config.py PX_PER_MM_DEFAULT. Duplicated (not
# imported) to keep ml/ decoupled from the web package's import path. Keep in
# sync if the web default changes.
DEFAULT_PX_PER_MM = 14.0

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def sample_code_from_filename(filename: str) -> str:
    """Derive a filename-safe sample_code from an image filename.

    The web ingest contract requires sample_code to match
    ^[A-Za-z0-9._-]{1,64}$ (web/backend/app/models.py SAMPLE_CODE_PATTERN),
    because the server uses it verbatim as an image filename. Deriving a stable
    code from the source filename makes re-running the same folder idempotent
    (server returns already_exists instead of duplicating the sample).
    """
    stem = Path(filename).stem
    safe = _UNSAFE.sub("-", stem).strip("-") or "sample"
    return safe[:64]


def resolve_px_per_mm(value):
    """Return (px_per_mm, used_default).

    When the caller passes None, fall back to DEFAULT_PX_PER_MM and flag it so
    the CLI can warn that size_mm is a placeholder, not a real calibration.
    """
    if value is None:
        return DEFAULT_PX_PER_MM, True
    return float(value), False
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_naming.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add ml/__init__.py ml/infer/__init__.py ml/tests/__init__.py ml/infer/naming.py ml/tests/test_naming.py
git commit -m "feat(ml): naming helpers (sample_code + px_per_mm resolve)"
```

---

### Task 2: Folder image source

**Files:**
- Create: `ml/infer/source.py`
- Test: `ml/tests/test_source.py`

**Interfaces:**
- Consumes: `naming.sample_code_from_filename`.
- Produces: `Frame` dataclass (`image_bytes: bytes`, `sample_code: str`, `captured_at: datetime`, `source_name: str`); `FolderSource(path)` with `.frames() -> Iterator[Frame]`.

- [ ] **Step 1: Write the failing test**

`ml/tests/test_source.py`:
```python
from PIL import Image

from ml.infer.source import FolderSource, Frame


def _write_jpeg(path):
    Image.new("RGB", (32, 32), (128, 128, 128)).save(path, format="JPEG")


def _write_png(path):
    Image.new("RGB", (32, 32), (128, 128, 128)).save(path, format="PNG")


def test_folder_source_yields_image_frames_only(tmp_path):
    _write_jpeg(tmp_path / "a.jpg")
    _write_png(tmp_path / "b.png")
    (tmp_path / "notes.txt").write_text("ignore me")

    frames = list(FolderSource(tmp_path).frames())

    assert len(frames) == 2
    assert {f.source_name for f in frames} == {"a.jpg", "b.png"}
    for f in frames:
        assert isinstance(f, Frame)
        assert f.image_bytes[:2] in (b"\xff\xd8", b"\x89P")  # jpeg / png magic
        assert f.captured_at.tzinfo is not None
        assert f.sample_code in ("a", "b")


def test_folder_source_accepts_single_file(tmp_path):
    _write_jpeg(tmp_path / "solo.jpg")
    frames = list(FolderSource(tmp_path / "solo.jpg").frames())
    assert len(frames) == 1
    assert frames[0].sample_code == "solo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.source'`

- [ ] **Step 3: Write minimal implementation**

`ml/infer/source.py`:
```python
"""Image sources for the inference CLI.

FolderSource reads image files now; an Esp32CaptureSource (GET /capture) will
implement the same .frames() interface later without touching downstream code.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .naming import sample_code_from_filename

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


@dataclass
class Frame:
    image_bytes: bytes
    sample_code: str
    captured_at: datetime  # timezone-aware (web ingest requires an offset)
    source_name: str       # original filename, for logging


class FolderSource:
    """Yield Frames from a folder of images, or a single image file."""

    def __init__(self, path):
        self.path = Path(path)

    def frames(self):
        if self.path.is_file():
            paths = [self.path]
        else:
            paths = sorted(
                p for p in self.path.iterdir()
                if p.suffix.lower() in _IMAGE_EXTS
            )
        for p in paths:
            captured_at = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            yield Frame(
                image_bytes=p.read_bytes(),
                sample_code=sample_code_from_filename(p.name),
                captured_at=captured_at,
                source_name=p.name,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_source.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add ml/infer/source.py ml/tests/test_source.py
git commit -m "feat(ml): FolderSource yields tz-aware image frames"
```

---

### Task 3: Detector wrapper (Ultralytics)

**Files:**
- Create: `ml/infer/detector.py`
- Test: `ml/tests/test_detector_smoke.py`

**Interfaces:**
- Produces: `Detection` dataclass (`bbox_xywh: tuple[int,int,int,int]`, `class_name: str`, `confidence: float`); `DetectionResult` dataclass (`detections: list[Detection]`, `image_width: int`, `image_height: int`); `Detector(weights)` with `.run(image_bytes) -> DetectionResult` and `.run_array(rgb_array, width=None, height=None) -> DetectionResult`.

- [ ] **Step 1: Write the failing test**

`ml/tests/test_detector_smoke.py` (skips cleanly when weights/ultralytics are absent — this is the only task that needs the real model):
```python
import io
import os

import pytest


WEIGHTS = os.environ.get("AQUA_TEST_WEIGHTS", "ml/models/best.pt")


@pytest.mark.skipif(not os.path.exists(WEIGHTS), reason="no weights at ml/models/best.pt")
def test_detector_runs_on_blank_image():
    pytest.importorskip("ultralytics")
    from PIL import Image

    from ml.infer.detector import Detector, DetectionResult

    buf = io.BytesIO()
    Image.new("RGB", (320, 320), (128, 128, 128)).save(buf, format="JPEG")

    result = Detector(WEIGHTS).run(buf.getvalue())

    assert isinstance(result, DetectionResult)
    assert result.image_width == 320 and result.image_height == 320
    for d in result.detections:
        assert len(d.bbox_xywh) == 4
        assert 0.0 <= d.confidence <= 1.0
```

- [ ] **Step 2: Run test to verify it fails (or skips)**

Run: `python -m pytest ml/tests/test_detector_smoke.py -v`
Expected: SKIPPED (no weights) — that is the acceptable "fails to run for lack of dependency" state; the implementation still must import cleanly. If you have weights locally, expect PASS after Step 3.

- [ ] **Step 3: Write minimal implementation**

`ml/infer/detector.py`:
```python
"""Ultralytics YOLO wrapper. This is the ONLY module that imports ultralytics."""

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image


@dataclass
class Detection:
    bbox_xywh: tuple  # (x, y, w, h), ints, top-left origin
    class_name: str
    confidence: float


@dataclass
class DetectionResult:
    detections: list
    image_width: int
    image_height: int


def _class_name(names, class_id):
    try:
        return names[class_id]
    except (KeyError, IndexError, TypeError):
        return str(class_id)


class Detector:
    def __init__(self, weights):
        from ultralytics import YOLO  # lazy: keep the heavy/optional dep here

        self.model = YOLO(str(weights))

    def run(self, image_bytes):
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = img.size
        return self.run_array(np.asarray(img), width, height)

    def run_array(self, rgb_array, width=None, height=None):
        if width is None or height is None:
            height, width = rgb_array.shape[:2]
        results = self.model.predict(rgb_array, verbose=False)
        names = self.model.names
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append(
                    Detection(
                        bbox_xywh=(x1, y1, x2 - x1, y2 - y1),
                        class_name=_class_name(names, int(box.cls[0].item())),
                        confidence=float(box.conf[0].item()),
                    )
                )
        return DetectionResult(detections=detections, image_width=width, image_height=height)
```

- [ ] **Step 4: Run test to verify it passes (or still skips)**

Run: `python -m pytest ml/tests/test_detector_smoke.py -v`
Expected: PASS if `ml/models/best.pt` present; SKIPPED otherwise. Either is acceptable to proceed.

- [ ] **Step 5: Commit**

```bash
git add ml/infer/detector.py ml/tests/test_detector_smoke.py
git commit -m "feat(ml): Detector wraps YOLO, returns bbox+class+conf"
```

---

### Task 4: Detection → ingest metadata mapper

**Files:**
- Create: `ml/infer/mapper.py`
- Test: `ml/tests/test_mapper.py`

**Interfaces:**
- Consumes: `naming.resolve_px_per_mm`; objects with `.bbox_xywh`, `.class_name`, `.confidence` (i.e. `Detection`).
- Produces: `build_metadata(*, detections, image_width, image_height, sample_code, captured_at, device_id, px_per_mm, batch_lot=None) -> dict` shaped exactly like the web `IngestPayload` (keys: `device_id, sample_code, batch_lot, captured_at, px_per_mm, image_width, image_height, particles[]`).

- [ ] **Step 1: Write the failing test**

`ml/tests/test_mapper.py`:
```python
from datetime import datetime, timezone

from ml.infer.detector import Detection
from ml.infer.mapper import build_metadata
from ml.infer.naming import DEFAULT_PX_PER_MM


def _dets():
    return [
        Detection(bbox_xywh=(10, 20, 30, 40), class_name="fiber", confidence=0.9),
        Detection(bbox_xywh=(0, 0, 8, 8), class_name="film", confidence=0.5),
    ]


def test_build_metadata_maps_particles():
    md = build_metadata(
        detections=_dets(),
        image_width=640,
        image_height=480,
        sample_code="S1",
        captured_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        device_id="pc-infer",
        px_per_mm=10.0,
        batch_lot="L1",
    )

    assert md["device_id"] == "pc-infer"
    assert md["sample_code"] == "S1"
    assert md["batch_lot"] == "L1"
    assert md["px_per_mm"] == 10.0
    assert md["image_width"] == 640
    assert md["captured_at"].endswith("+00:00")
    assert len(md["particles"]) == 2

    p0 = md["particles"][0]
    assert p0["blob_index"] == 0
    assert p0["bbox_x"] == 10 and p0["bbox_w"] == 30
    assert p0["centroid_x"] == 25.0 and p0["centroid_y"] == 40.0
    assert p0["area_px"] == 1200.0        # bbox area (documented approximation)
    assert p0["size_mm"] == 4.0           # max(30, 40) / 10
    assert p0["label"] == "fiber"
    assert p0["confidence"] == 0.9


def test_build_metadata_defaults_px_per_mm_when_missing():
    md = build_metadata(
        detections=_dets(),
        image_width=64,
        image_height=64,
        sample_code="S2",
        captured_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        device_id="pc-infer",
        px_per_mm=None,
    )
    assert md["px_per_mm"] == DEFAULT_PX_PER_MM
    assert md["particles"][0]["size_mm"] == 40 / DEFAULT_PX_PER_MM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_mapper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.mapper'`

- [ ] **Step 3: Write minimal implementation**

`ml/infer/mapper.py`:
```python
"""Map detector output to the /api/ingest `metadata` dict (IngestPayload shape).

Honesty notes carried in the values themselves:
  * size_mm = max(w, h) / px_per_mm  — approx Feret diameter via calibration.
  * area_px = w * h                  — BBOX area, NOT true blob area (a plain
    detector has no mask). Documented approximation; replace with real blob
    area only if a CV/segmentation stage is added later.
"""

from .naming import resolve_px_per_mm


def build_metadata(*, detections, image_width, image_height, sample_code,
                   captured_at, device_id, px_per_mm, batch_lot=None):
    px, _ = resolve_px_per_mm(px_per_mm)  # tolerate None; CLI resolves+warns first
    particles = []
    for i, d in enumerate(detections):
        x, y, w, h = d.bbox_xywh
        particles.append({
            "blob_index": i,
            "centroid_x": x + w / 2,
            "centroid_y": y + h / 2,
            "bbox_x": int(x),
            "bbox_y": int(y),
            "bbox_w": int(w),
            "bbox_h": int(h),
            "area_px": float(w * h),
            "size_mm": (max(w, h) / px) if px else 0.0,
            "label": d.class_name,
            "confidence": float(d.confidence),
        })
    return {
        "device_id": device_id,
        "sample_code": sample_code,
        "batch_lot": batch_lot,
        "captured_at": captured_at.isoformat(),
        "px_per_mm": px,
        "image_width": image_width,
        "image_height": image_height,
        "particles": particles,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_mapper.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add ml/infer/mapper.py ml/tests/test_mapper.py
git commit -m "feat(ml): map detections to ingest metadata payload"
```

---

### Task 5: Ingest HTTP client

**Files:**
- Create: `ml/infer/ingest_client.py`
- Modify: `ml/requirements.txt` (add `requests`)
- Test: `ml/tests/test_ingest_client.py`

**Interfaces:**
- Produces: `IngestResult` dataclass (`status: str` in `{"created","already_exists","failed"}`, `http_status: int`, `detail: str`); `post(api_url, metadata, image_bytes, image_name, timeout=30) -> IngestResult`.

- [ ] **Step 1: Add the dependency**

Append `requests` to `ml/requirements.txt` so the module and its test can import it. Resulting file:
```
ultralytics>=8.3.0
tensorflow>=2.15.0
numpy
requests
```
Then: `pip install requests`

- [ ] **Step 2: Write the failing test**

`ml/tests/test_ingest_client.py`:
```python
import json

from ml.infer import ingest_client


class _Resp:
    def __init__(self, code, payload=None, text=""):
        self.status_code = code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _patch(monkeypatch, resp=None, exc=None):
    calls = {}

    def fake_post(url, files=None, data=None, timeout=None):
        calls["url"] = url
        calls["files"] = files
        calls["data"] = data
        if exc:
            raise exc
        return resp

    monkeypatch.setattr(ingest_client.requests, "post", fake_post)
    return calls


def test_post_created(monkeypatch):
    calls = _patch(monkeypatch, _Resp(201, {"status": "created"}))
    r = ingest_client.post("http://x", {"a": 1}, b"jpeg", "a.jpg")
    assert r.status == "created" and r.http_status == 201
    assert calls["url"] == "http://x/api/ingest"
    assert json.loads(calls["data"]["metadata"]) == {"a": 1}


def test_post_already_exists(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"status": "already_exists"}))
    r = ingest_client.post("http://x/", {}, b"j", "a.jpg")
    assert r.status == "already_exists"


def test_post_validation_error(monkeypatch):
    _patch(monkeypatch, _Resp(422, {"detail": "bad"}))
    r = ingest_client.post("http://x", {}, b"j", "a.jpg")
    assert r.status == "failed" and r.http_status == 422 and "bad" in r.detail


def test_post_network_error(monkeypatch):
    _patch(monkeypatch, exc=ingest_client.requests.RequestException("boom"))
    r = ingest_client.post("http://x", {}, b"j", "a.jpg")
    assert r.status == "failed" and r.http_status == 0 and "boom" in r.detail
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_ingest_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.ingest_client'`

- [ ] **Step 4: Write minimal implementation**

`ml/infer/ingest_client.py`:
```python
"""POST one measurement to the web backend's /api/ingest contract.

Builds the multipart form the endpoint expects (a `metadata` JSON string field
+ an `image` file) and classifies the response. Never raises on HTTP/network
failure — returns a `failed` IngestResult so the CLI can tally and continue.
"""

import json
from dataclasses import dataclass

import requests


@dataclass
class IngestResult:
    status: str        # "created" | "already_exists" | "failed"
    http_status: int
    detail: str = ""


def post(api_url, metadata, image_bytes, image_name, timeout=30):
    url = api_url.rstrip("/") + "/api/ingest"
    files = {"image": (image_name, image_bytes, "image/jpeg")}
    data = {"metadata": json.dumps(metadata)}
    try:
        resp = requests.post(url, files=files, data=data, timeout=timeout)
    except requests.RequestException as exc:
        return IngestResult(status="failed", http_status=0, detail=str(exc))

    if resp.status_code == 201:
        return IngestResult(status="created", http_status=201)
    if resp.status_code == 200:
        return IngestResult(status="already_exists", http_status=200)
    return IngestResult(
        status="failed", http_status=resp.status_code, detail=_safe_detail(resp)
    )


def _safe_detail(resp):
    try:
        return json.dumps(resp.json())
    except ValueError:
        return resp.text[:500]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_ingest_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add ml/infer/ingest_client.py ml/requirements.txt ml/tests/test_ingest_client.py
git commit -m "feat(ml): ingest client posts multipart to /api/ingest"
```

---

### Task 6: CLI orchestrator + module entry point

**Files:**
- Create: `ml/infer/cli.py`, `ml/infer/__main__.py`
- Test: `ml/tests/test_cli.py`

**Interfaces:**
- Consumes: `Detector` (Task 3), `build_metadata` (Task 4), `resolve_px_per_mm` (Task 1), `post` (Task 5), `FolderSource` (Task 2).
- Produces: `build_arg_parser() -> argparse.ArgumentParser`; `main(argv=None) -> int` (0 on full success, 1 if any image failed). `Detector` and `post` are referenced as module attributes `cli.Detector` / `cli.post` so tests can monkeypatch them.

- [ ] **Step 1: Write the failing test**

`ml/tests/test_cli.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.cli'`

- [ ] **Step 3: Write minimal implementation**

`ml/infer/cli.py`:
```python
"""CLI: run the detector over a folder/file and POST results to /api/ingest.

Usage:
    python -m ml.infer <image|folder> --weights ml/models/best.pt \
        --api-url http://localhost:8000 --device-id pc-infer --px-per-mm <n>
"""

import argparse
import sys

from .detector import Detector
from .ingest_client import post
from .mapper import build_metadata
from .naming import resolve_px_per_mm
from .source import FolderSource


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="python -m ml.infer",
        description="Run the Roboflow-trained detector on images and POST "
                    "count/size/label to /api/ingest.",
    )
    p.add_argument("input", help="Image file or folder of images")
    p.add_argument("--weights", default="ml/models/best.pt")
    p.add_argument("--api-url", default="http://localhost:8000")
    p.add_argument("--device-id", default="pc-infer")
    p.add_argument("--px-per-mm", type=float, default=None)
    p.add_argument("--batch-lot", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Detect and print only; do not POST to the API")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    px, used_default = resolve_px_per_mm(args.px_per_mm)
    if used_default:
        print(f"[warn] --px-per-mm not set; using default {px} px/mm. "
              "size_mm is a PLACEHOLDER, not a real calibration.")

    detector = Detector(args.weights)
    source = FolderSource(args.input)

    created = already = failed = 0
    failed_names = []
    for frame in source.frames():
        try:
            result = detector.run(frame.image_bytes)
            metadata = build_metadata(
                detections=result.detections,
                image_width=result.image_width,
                image_height=result.image_height,
                sample_code=frame.sample_code,
                captured_at=frame.captured_at,
                device_id=args.device_id,
                px_per_mm=px,
                batch_lot=args.batch_lot,
            )
            if args.dry_run:
                print(f"[dry-run] {frame.source_name}: "
                      f"{len(metadata['particles'])} particles")
                continue
            res = post(args.api_url, metadata, frame.image_bytes,
                       f"{frame.sample_code}.jpg")
            if res.status == "created":
                created += 1
            elif res.status == "already_exists":
                already += 1
            else:
                failed += 1
                failed_names.append(
                    f"{frame.source_name} ({res.http_status}: {res.detail})")
            print(f"[{res.status}] {frame.source_name} -> {frame.sample_code}")
        except Exception as exc:  # one image must never abort the whole batch
            failed += 1
            failed_names.append(f"{frame.source_name} ({exc})")
            print(f"[failed] {frame.source_name}: {exc}")

    print(f"\nSummary: {created} created, {already} already_exists, {failed} failed")
    if failed_names:
        print("Failed:")
        for n in failed_names:
            print(f"  - {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

`ml/infer/__main__.py`:
```python
import sys

from .cli import main

sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add ml/infer/cli.py ml/infer/__main__.py ml/tests/test_cli.py
git commit -m "feat(ml): CLI orchestrates source->detect->map->ingest with tally"
```

---

### Task 7: Live annotated preview (visualization only)

**Files:**
- Create: `ml/infer/preview.py`
- Modify: `ml/requirements.txt` (add `opencv-python`)
- Test: `ml/tests/test_preview.py`

**Interfaces:**
- Consumes: `Detector.run_array` (Task 3), `Detection` (Task 3).
- Produces: `annotate_frame(frame_bgr, detections) -> frame_bgr`; `main(argv=None)` for `python -m ml.infer.preview`.
- **Constraint:** must NOT import `ingest_client` (structurally cannot write to the DB).

- [ ] **Step 1: Add the dependency**

Append `opencv-python` to `ml/requirements.txt`:
```
ultralytics>=8.3.0
tensorflow>=2.15.0
numpy
requests
opencv-python
```
Then: `pip install opencv-python`

- [ ] **Step 2: Write the failing test**

`ml/tests/test_preview.py`:
```python
import numpy as np
import pytest

from ml.infer.detector import Detection


def test_annotate_frame_draws_without_error():
    pytest.importorskip("cv2")
    from ml.infer.preview import annotate_frame

    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    out = annotate_frame(frame, [Detection((5, 5, 10, 10), "film", 0.7)])

    assert out.shape == (64, 64, 3)
    assert out.sum() > 0  # boxes/labels were drawn onto the black frame


def test_preview_never_imports_ingest_client():
    import ml.infer.preview as preview
    import inspect

    src = inspect.getsource(preview)
    assert "ingest_client" not in src
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_preview.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.preview'`

- [ ] **Step 4: Write minimal implementation**

`ml/infer/preview.py`:
```python
"""Live annotated preview — VISUALIZATION ONLY. Never writes to the DB.

Why streaming is not the counting path: /stream is low-res MJPEG (particles
<2mm vanish) over flowing water (a moving particle would be double-counted
across frames). Counting/sizing is a single high-res still in the Stop-Flow
pump-off window (that is the /capture path). This tool only draws boxes for a
human to eyeball during a demo; the on-screen count is transient, not audited.

Deliberately does NOT import ingest_client, so it structurally cannot log.

Usage:
    python -m ml.infer.preview --source webcam:0 --weights ml/models/best.pt --fps 2
    python -m ml.infer.preview --source http://<esp32-ip>/stream --weights ml/models/best.pt
    python -m ml.infer.preview --source path/to/video.mp4 --weights ml/models/best.pt
"""

import argparse
import sys
import time

from .detector import Detector


def annotate_frame(frame_bgr, detections):
    import cv2

    for d in detections:
        x, y, w, h = d.bbox_xywh
        cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame_bgr, f"{d.class_name} {d.confidence:.2f}",
                    (x, max(0, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 1)
    cv2.putText(frame_bgr, "PREVIEW - not logged", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame_bgr


def _open_capture(source):
    import cv2

    if source.startswith("webcam:"):
        return cv2.VideoCapture(int(source.split(":", 1)[1]))
    return cv2.VideoCapture(source)


def main(argv=None):
    import cv2

    p = argparse.ArgumentParser(prog="python -m ml.infer.preview")
    p.add_argument("--source", required=True,
                   help="webcam:<n> | <stream-url> | <video-file>")
    p.add_argument("--weights", default="ml/models/best.pt")
    p.add_argument("--fps", type=float, default=2.0,
                   help="Max detector passes per second (throttle)")
    args = p.parse_args(argv)

    detector = Detector(args.weights)
    cap = _open_capture(args.source)
    if not cap.isOpened():
        print(f"[error] cannot open source: {args.source}")
        return 1

    min_interval = 1.0 / args.fps if args.fps > 0 else 0.0
    last = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            now = time.time()
            if now - last >= min_interval:
                last = now
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = detector.run_array(rgb)
                annotate_frame(frame, result.detections)
            cv2.imshow("Aqua Scope preview (not logged)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_preview.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add ml/infer/preview.py ml/requirements.txt ml/tests/test_preview.py
git commit -m "feat(ml): visualization-only live preview (no DB writes)"
```

---

### Task 8: Full test sweep + README run docs + end-to-end verification

**Files:**
- Modify: `ml/README.md` (add a "Nhánh 1 — chạy inference trên PC" run section)

- [ ] **Step 1: Run the whole ml test suite**

Run: `python -m pytest ml/tests/ -v`
Expected: all tests PASS except `test_detector_smoke.py` which PASSES or SKIPS depending on whether `ml/models/best.pt` exists.

- [ ] **Step 2: Document how to run it**

Add this section to `ml/README.md` (after the Phase C section):
````markdown
## Nhánh 1 — chạy inference trên PC (offload)

Chạy detector đã train trên ảnh (folder/1 ảnh) rồi đẩy kết quả vào dashboard đã có.

```bash
pip install -r ml/requirements.txt
# đặt weights tải từ Roboflow tại ml/models/best.pt
python -m ml.infer <ảnh|folder> --weights ml/models/best.pt \
    --api-url http://localhost:8000 --device-id pc-infer --px-per-mm <n>
```
- `--px-per-mm`: bỏ trống → dùng mặc định 14.0 kèm cảnh báo (size_mm chỉ là placeholder cho ảnh dataset).
- `--dry-run`: chỉ detect + in số hạt, không POST.
- Chạy lại cùng folder là idempotent (sample_code suy từ tên file) → server trả `already_exists`.

Preview trực quan (chỉ để xem, KHÔNG ghi DB):
```bash
python -m ml.infer.preview --source webcam:0 --weights ml/models/best.pt --fps 2
# hoặc --source http://<esp32-ip>/stream  |  --source video.mp4
```
````

- [ ] **Step 3: End-to-end verification (real stack, manual)**

Follow these and confirm each observation before claiming done:
1. Start the web backend:
   ```bash
   cd web/backend && python -m uvicorn app.main:app --reload
   ```
2. Ensure `ml/models/best.pt` exists (download from Roboflow) and put 2–3 test images in a folder, e.g. `ml/_e2e/`.
3. From the repo root, run:
   ```bash
   python -m ml.infer ml/_e2e --weights ml/models/best.pt \
       --api-url http://localhost:8000 --device-id pc-infer --px-per-mm 14
   ```
   Expected: a `[created] ... -> <code>` line per image and `Summary: N created, 0 already_exists, 0 failed`.
4. Open the dashboard (`http://localhost:8000/`) and confirm the new samples appear with count/label/size and viewable images.
5. **Re-run the exact same command.** Expected: every line now `[already_exists]`, `Summary: 0 created, N already_exists, 0 failed`, and the dashboard shows **no** duplicates.

- [ ] **Step 4: Commit the docs**

```bash
git add ml/README.md
git commit -m "docs(ml): document Branch-1 PC inference CLI + preview usage"
```

---

## Notes for the implementer

- The `_e2e/` folder and `ml/models/` are gitignored (see `ml/.gitignore`) — they are local-only.
- Do not add `Esp32CaptureSource` now; it is intentionally deferred (Phase D, when the rig captures sharp frames). The `FolderSource` interface is what it will mirror.
- If `python -m ml.infer` can't find the `ml` package, confirm you're running from the repo root (`C:\University\Semester 4\IOT102\project`).
