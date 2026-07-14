"""Module 2 acceptance tests — POST /api/ingest (web_plan.md §2.1).

Router is tested in isolation (its own FastAPI app + temp DB + temp images
dir) so it does not depend on Module 6 wiring `main.py`, nor touch the real
`data/` directory.
"""

import io
import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine, select

from app import config
from app.database import get_session
from app.models import Particle, Sample
from app.routers import ingest as ingest_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolated file-backed SQLite so each test starts empty.
    engine = create_engine(
        f"sqlite:///{tmp_path/'test.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    # Redirect image writes to a temp dir (router reads config.IMAGES_DIR live).
    images_dir = tmp_path / "images"
    monkeypatch.setattr(config, "IMAGES_DIR", images_dir)

    app = FastAPI()
    app.include_router(ingest_module.router)
    app.dependency_overrides[get_session] = override_get_session

    test_client = TestClient(app)
    test_client._engine = engine  # expose for assertions
    test_client._images_dir = images_dir
    return test_client


def _jpeg_bytes(color=(128, 128, 128), size=(640, 480)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _metadata(sample_code="S-TEST-0001", particles=1, **overrides):
    parts = [
        {
            "blob_index": i,
            "centroid_x": 210.5,
            "centroid_y": 133.2,
            "bbox_x": 198,
            "bbox_y": 120,
            "bbox_w": 26,
            "bbox_h": 24,
            "area_px": 312.0,
            "size_mm": 1.8,
            "label": "plastic",
            "confidence": 0.91,
        }
        for i in range(particles)
    ]
    data = {
        "device_id": "aquascope-test",
        "sample_code": sample_code,
        "batch_lot": "LOT-TEST",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "px_per_mm": 14.0,
        "image_width": 640,
        "image_height": 480,
        "particles": parts,
    }
    data.update(overrides)
    return data


def _post(client, metadata_dict, image=None):
    return client.post(
        "/api/ingest",
        data={"metadata": json.dumps(metadata_dict)},
        files={"image": ("frame.jpg", image or _jpeg_bytes(), "image/jpeg")},
    )


def test_valid_ingest_returns_201_and_persists(client):
    resp = _post(client, _metadata(sample_code="S-A", particles=3))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "created"
    assert body["particle_count"] == 3
    assert body["sample_code"] == "S-A"

    with Session(client._engine) as s:
        sample = s.exec(select(Sample).where(Sample.sample_code == "S-A")).one()
        assert sample.particle_count == 3
        assert sample.image_path == "images/S-A.jpg"
        parts = s.exec(select(Particle).where(Particle.sample_id == sample.id)).all()
        assert len(parts) == 3
    assert (client._images_dir / "S-A.jpg").exists()


def test_duplicate_sample_code_is_idempotent_200(client):
    first = _post(client, _metadata(sample_code="S-DUP", particles=2))
    assert first.status_code == 201
    second = _post(client, _metadata(sample_code="S-DUP", particles=5))
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "already_exists"
    # Original wins — not overwritten by the retry's different particle count.
    assert body["particle_count"] == 2

    with Session(client._engine) as s:
        rows = s.exec(select(Sample).where(Sample.sample_code == "S-DUP")).all()
        assert len(rows) == 1


def test_missing_sample_code_is_server_generated(client):
    md = _metadata()
    del md["sample_code"]
    resp = _post(client, md)
    assert resp.status_code == 201
    code = resp.json()["sample_code"]
    assert code.startswith("S") and len(code) >= 15  # S{yyyyMMdd}-{HHmmss}-{hex}


def test_invalid_metadata_json_returns_422(client):
    resp = client.post(
        "/api/ingest",
        data={"metadata": "{not valid json"},
        files={"image": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 422


def test_missing_required_field_returns_422(client):
    md = _metadata()
    del md["device_id"]  # required
    resp = _post(client, md)
    assert resp.status_code == 422


def test_unreadable_image_returns_400(client):
    resp = _post(client, _metadata(sample_code="S-BAD"), image=b"this is not a jpeg")
    assert resp.status_code == 400
    # Failed ingest leaves nothing behind.
    with Session(client._engine) as s:
        assert s.exec(select(Sample).where(Sample.sample_code == "S-BAD")).first() is None
    assert not (client._images_dir / "S-BAD.jpg").exists()


# --- SEC-1: sample_code path traversal (SPEC §6, §5.1) -------------------


def test_path_traversal_sample_code_returns_422_and_writes_nothing(client, tmp_path):
    resp = _post(client, _metadata(sample_code="../../evil"))
    assert resp.status_code == 422
    # No file escaped anywhere under tmp_path, and nothing landed in images/.
    assert not any(tmp_path.rglob("evil.jpg"))
    assert not (client._images_dir / "evil.jpg").exists()
    with Session(client._engine) as s:
        assert s.exec(select(Sample)).all() == []


def test_sample_code_allowed_edge_value_returns_201(client):
    resp = _post(client, _metadata(sample_code="S_20260713.v2-01"))
    assert resp.status_code == 201


# --- SEC-3: oversized upload rejected (SPEC §6) ---------------------------


def test_oversized_image_returns_413(client, monkeypatch):
    # Keep the test fast: shrink the limit rather than generate 8MiB+ bytes.
    # Router reads config.MAX_UPLOAD_BYTES live, same pattern as IMAGES_DIR.
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 100)
    oversized = b"\xff\xd8\xff" + b"\x00" * 200
    resp = _post(client, _metadata(sample_code="S-BIG"), image=oversized)
    assert resp.status_code == 413


# --- DATA-1: naive-UTC datetimes (SPEC §6) --------------------------------


def test_captured_at_with_offset_stored_as_naive_utc(client):
    resp = _post(
        client,
        _metadata(sample_code="S-TZ", captured_at="2026-07-13T14:32:05+07:00"),
    )
    assert resp.status_code == 201
    with Session(client._engine) as s:
        sample = s.exec(select(Sample).where(Sample.sample_code == "S-TZ")).one()
        assert sample.captured_at == datetime(2026, 7, 13, 7, 32, 5)
        assert sample.captured_at.tzinfo is None
        assert sample.received_at.tzinfo is None


def test_captured_at_without_offset_returns_422(client):
    resp = _post(
        client,
        _metadata(sample_code="S-NOTZ", captured_at="2026-07-13T14:32:05"),
    )
    assert resp.status_code == 422


# --- SEC-4 / §5.1: particle field bounds ----------------------------------


def test_particle_confidence_out_of_range_returns_422(client):
    md = _metadata(sample_code="S-CONF")
    md["particles"][0]["confidence"] = 1.5
    resp = _post(client, md)
    assert resp.status_code == 422


def test_particle_negative_size_mm_returns_422(client):
    md = _metadata(sample_code="S-NEG")
    md["particles"][0]["size_mm"] = -1
    resp = _post(client, md)
    assert resp.status_code == 422
