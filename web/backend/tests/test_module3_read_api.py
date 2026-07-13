"""Module 3 acceptance test (web_plan.md §9, contract §2.2).

Exercises the Read API in isolation: a fresh in-memory SQLite DB is seeded
directly with Sample/Particle rows (no dependency on Module 2's ingest), the
samples router is mounted on a throwaway FastAPI app, and get_session is
overridden to the test DB. Run from web/backend/:  pytest -q

Seed fixture (captured_at ascending):
  s1  LOT-A  2026-07-10  2 particles (plastic, bubble)
  s2  LOT-B  2026-07-11  3 particles (plastic x2, organic) spanning size bins
  s3  None   2026-07-13  0 particles
"""

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.models import Particle, Sample
from app.routers.samples import router


def _mk_particle(blob_index, size_mm, label):
    return Particle(
        blob_index=blob_index,
        centroid_x=100.0 + blob_index,
        centroid_y=50.0 + blob_index,
        bbox_x=90,
        bbox_y=40,
        bbox_w=20,
        bbox_h=20,
        area_px=size_mm * 100.0,
        size_mm=size_mm,
        label=label,
        confidence=0.9,
    )


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across connections
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as s:
        s1 = Sample(
            sample_code="S-001", batch_lot="LOT-A", device_id="dev1",
            captured_at=datetime(2026, 7, 10, 8, 0, 0), particle_count=2,
            image_path="images/S-001.jpg", image_width=640, image_height=480,
            px_per_mm=14.0, raw_metadata_json='{"sample_code":"S-001"}',
        )
        s2 = Sample(
            sample_code="S-002", batch_lot="LOT-B", device_id="dev1",
            captured_at=datetime(2026, 7, 11, 9, 0, 0), particle_count=3,
            image_path="images/S-002.jpg", image_width=640, image_height=480,
            px_per_mm=14.0, raw_metadata_json='{"sample_code":"S-002"}',
        )
        s3 = Sample(
            sample_code="S-003", batch_lot=None, device_id="dev1",
            captured_at=datetime(2026, 7, 13, 10, 0, 0), particle_count=0,
            image_path="images/S-003.jpg", image_width=640, image_height=480,
            px_per_mm=14.0, raw_metadata_json='{"sample_code":"S-003"}',
        )
        s.add_all([s1, s2, s3])
        s.commit()
        s.refresh(s1)
        s.refresh(s2)

        p_s1 = [_mk_particle(0, 0.5, "plastic"), _mk_particle(1, 1.2, "bubble")]
        p_s2 = [
            _mk_particle(0, 0.4, "plastic"),
            _mk_particle(1, 1.9, "plastic"),
            _mk_particle(2, 3.1, "organic"),
        ]
        for p in p_s1:
            p.sample_id = s1.id
        for p in p_s2:
            p.sample_id = s2.id
        s.add_all(p_s1 + p_s2)
        s.commit()

    app = FastAPI()
    app.include_router(router)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c


def test_list_returns_all_summaries_newest_first(client):
    r = client.get("/api/samples")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    codes = [it["sample_code"] for it in body["items"]]
    assert codes == ["S-003", "S-002", "S-001"]  # captured_at desc
    # summary rows must not carry particles / raw metadata
    assert "particles" not in body["items"][0]
    assert "raw_metadata_json" not in body["items"][0]


def test_list_filter_by_batch_lot(client):
    r = client.get("/api/samples", params={"batch_lot": "LOT-A"})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["sample_code"] == "S-001"


def test_list_filter_by_date_range(client):
    r = client.get("/api/samples", params={"from": "2026-07-11T00:00:00"})
    body = r.json()
    assert body["total"] == 2
    assert {it["sample_code"] for it in body["items"]} == {"S-002", "S-003"}


def test_list_pagination(client):
    r = client.get("/api/samples", params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    r2 = client.get("/api/samples", params={"page": 2, "page_size": 2})
    body2 = r2.json()
    assert len(body2["items"]) == 1


def test_list_no_match_returns_empty_not_error(client):
    r = client.get("/api/samples", params={"batch_lot": "NOPE"})
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_detail_includes_particles_histogram_and_labels(client):
    lst = client.get("/api/samples", params={"batch_lot": "LOT-B"}).json()
    sid = lst["items"][0]["id"]
    r = client.get(f"/api/samples/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["sample_code"] == "S-002"
    assert len(body["particles"]) == 3
    assert body["particles"][0]["blob_index"] == 0  # ordered
    assert body["raw_metadata_json"]  # detail carries the audit blob
    # histogram bins sum to the particle count
    hist = body["size_histogram"]
    assert abs(hist["bin_width_mm"] - 0.3) < 1e-9
    assert sum(b["count"] for b in hist["bins"]) == 3
    # sizes 0.4, 1.9, 3.1 land in distinct bins
    nonzero = [b for b in hist["bins"] if b["count"] > 0]
    assert len(nonzero) == 3
    assert body["label_distribution"] == {"plastic": 2, "organic": 1}


def test_detail_404_for_missing_id(client):
    r = client.get("/api/samples/9999")
    assert r.status_code == 404


def test_export_csv_one_row_per_particle(client):
    r = client.get("/api/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "")
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    # 1 header + 5 particle rows (s1:2, s2:3) + 1 zero-particle row (s3)
    assert len(lines) == 1 + 5 + 1
    assert lines[0].startswith("sample_code,")


def test_export_csv_respects_filter(client):
    r = client.get("/api/export.csv", params={"batch_lot": "LOT-A"})
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    # header + 2 particles of S-001 only
    assert len(lines) == 1 + 2
