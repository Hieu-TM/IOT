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
