import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.models import Particle, Sample
from app.routers.pages import router

def _make_client(seed=True):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    if seed:
        with Session(engine) as s:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # Batch A samples
            s.add(Sample(
                sample_code="S-LOT-A-1",
                batch_lot="LOT-A",
                device_id="aquascope-01",
                captured_at=now,
                particle_count=2,
                image_path="images/S-LOT-A-1.jpg",
                raw_metadata_json='{}'
            ))
            s.add(Sample(
                sample_code="S-LOT-A-2",
                batch_lot="LOT-A",
                device_id="aquascope-01",
                captured_at=now,
                particle_count=3,
                image_path="images/S-LOT-A-2.jpg",
                raw_metadata_json='{}'
            ))
            
            # Batch B samples (no particles, so no warning)
            s.add(Sample(
                sample_code="S-LOT-B-1",
                batch_lot="LOT-B",
                device_id="aquascope-01",
                captured_at=now,
                particle_count=0,
                image_path="images/S-LOT-B-1.jpg",
                raw_metadata_json='{}'
            ))
            
            # No-lot samples
            s.add(Sample(
                sample_code="S-NOLOT-1",
                batch_lot=None,
                device_id="aquascope-02",
                captured_at=now,
                particle_count=1,
                image_path="images/S-NOLOT-1.jpg",
                raw_metadata_json='{}'
            ))
            
            s.commit()
            
            # Add particles to get dominant label
            # LOT-A sample 1 has 2 plastic particles
            s.add(Particle(sample_id=1, blob_index=0, centroid_x=0, centroid_y=0, bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0, area_px=10, size_mm=1.0, label="fiber", confidence=0.9))
            s.add(Particle(sample_id=1, blob_index=1, centroid_x=0, centroid_y=0, bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0, area_px=10, size_mm=1.0, label="fiber", confidence=0.9))
            
            # LOT-A sample 2 has 3 film particles
            s.add(Particle(sample_id=2, blob_index=0, centroid_x=0, centroid_y=0, bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0, area_px=10, size_mm=1.0, label="film", confidence=0.9))
            s.add(Particle(sample_id=2, blob_index=1, centroid_x=0, centroid_y=0, bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0, area_px=10, size_mm=1.0, label="film", confidence=0.9))
            s.add(Particle(sample_id=2, blob_index=2, centroid_x=0, centroid_y=0, bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0, area_px=10, size_mm=1.0, label="film", confidence=0.9))
            
            # NOLOT sample 1 has 1 bubble/legacy type
            s.add(Particle(sample_id=4, blob_index=0, centroid_x=0, centroid_y=0, bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0, area_px=10, size_mm=1.0, label="bubble", confidence=0.9))
            
            s.commit()

    app = FastAPI()
    app.include_router(router)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)
    client._engine = engine
    return client

def test_batches_page_empty():
    with _make_client(seed=False) as client:
        r = client.get("/batches")
        assert r.status_code == 200
        assert "Chưa có lô nào" in r.text

def test_batches_page_populated():
    with _make_client(seed=True) as client:
        r = client.get("/batches")
        assert r.status_code == 200
        assert "LOT-A" in r.text
        assert "LOT-B" in r.text
        assert "Chưa gán lô" in r.text
        
        # LOT-A details check
        # LOT-A has 2 samples, 5 total particles, 2 warning samples (both have particles > 0)
        assert "LOT-A" in r.text
        assert "5" in r.text  # total particles
        
        # Test dominant label logic: LOT-A has 3 film and 2 fiber -> film (Màng) is dominant
        assert "Màng" in r.text
        
        # NOLOT dominant is bubble (Bọt khí)
        assert "Bọt khí" in r.text

def test_batches_page_links():
    with _make_client(seed=True) as client:
        r = client.get("/batches")
        assert 'href="/history?batch_lot=LOT-A"' in r.text
        assert 'href="/history?batch_lot=LOT-B"' in r.text
        assert 'href="/history?batch_lot=__unassigned__"' in r.text
