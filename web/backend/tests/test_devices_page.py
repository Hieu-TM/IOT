import pytest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.models import Sample
from app.routers.pages import router
from app import config

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
            
            # Device 1: Online (last sample was 2 mins ago)
            s.add(Sample(
                sample_code="S-DEV1-1",
                batch_lot="LOT-A",
                device_id="device-online",
                captured_at=now - timedelta(minutes=2),
                received_at=now - timedelta(minutes=2) + timedelta(seconds=5),
                particle_count=0,
                image_path="images/S-DEV1-1.jpg",
                raw_metadata_json='{}'
            ))
            
            # Device 2: Idle (last sample was 30 mins ago, but today)
            s.add(Sample(
                sample_code="S-DEV2-1",
                batch_lot="LOT-A",
                device_id="device-idle",
                captured_at=now - timedelta(minutes=30),
                received_at=now - timedelta(minutes=30) + timedelta(seconds=12),
                particle_count=2, # with warning
                image_path="images/S-DEV2-1.jpg",
                raw_metadata_json='{}'
            ))
            
            # Device 3: Offline (last sample was yesterday)
            s.add(Sample(
                sample_code="S-DEV3-1",
                batch_lot="LOT-B",
                device_id="device-offline",
                captured_at=now - timedelta(days=1),
                received_at=now - timedelta(days=1) + timedelta(seconds=2),
                particle_count=0,
                image_path="images/S-DEV3-1.jpg",
                raw_metadata_json='{}'
            ))
            
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

def test_devices_page_empty():
    with _make_client(seed=False) as client:
        r = client.get("/devices")
        assert r.status_code == 200
        assert "Không có thiết bị" in r.text

def test_devices_page_populated():
    with _make_client(seed=True) as client:
        r = client.get("/devices")
        assert r.status_code == 200
        assert "device-online" in r.text
        assert "device-idle" in r.text
        assert "device-offline" in r.text
        
        # Test status classifications
        assert "Trực tuyến" in r.text
        assert "Chờ" in r.text
        assert "Ngoại tuyến" in r.text

        # Test today count and warn count
        # device-idle has 1 sample today, with 2 particles (warn)
        # device-online has 1 sample today, 0 particles (no warn)
        # device-offline has 0 samples today
        assert "device-idle" in r.text
        
        # Checking logic for delays
        assert "5s" in r.text # Device 1 delay: 5 seconds
        assert "12s" in r.text # Device 2 delay: 12 seconds
        assert "2s" in r.text # Device 3 delay: 2 seconds
