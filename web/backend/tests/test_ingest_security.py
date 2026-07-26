import pytest
import io
import json
import tempfile
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from PIL import Image

from app import config
from app.database import get_session
from app.routers import ingest as ingest_module

@pytest.fixture()
def secure_client(monkeypatch):
    # Create temp directory inside workspace tests dir to avoid OS temp folder locks
    tests_dir = Path(__file__).parent.resolve()
    tmp_workspace_dir = tests_dir / "tmp_test_ingest"
    tmp_workspace_dir.mkdir(exist_ok=True)
    
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    images_dir = tmp_workspace_dir / "images"
    images_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(config, "IMAGES_DIR", images_dir)
    monkeypatch.setattr(config, "INGEST_TOKEN", "secure-token-12345")

    app = FastAPI()
    app.include_router(ingest_module.router)
    app.dependency_overrides[get_session] = override_get_session

    test_client = TestClient(app)
    test_client._engine = engine
    test_client._images_dir = images_dir
    yield test_client
    
    # Cleanup workspace temp directory
    try:
        import shutil
        shutil.rmtree(tmp_workspace_dir, ignore_errors=True)
    except Exception:
        pass

def _metadata():
    return {
        "sample_code": "S-TOKEN-TEST",
        "device_id": "aquascope-01",
        "captured_at": "2026-07-26T15:17:00Z",
        "particles": []
    }

def _image():
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), "white").save(buf, format="JPEG")
    buf.seek(0)
    return ("image.jpg", buf, "image/jpeg")

def test_ingest_without_token_returns_401(secure_client):
    r = secure_client.post(
        "/api/ingest",
        data={"metadata": json.dumps(_metadata())},
        files={"image": _image()}
    )
    assert r.status_code == 401
    assert "Unauthorized" in r.text

def test_ingest_with_invalid_token_returns_401(secure_client):
    r = secure_client.post(
        "/api/ingest",
        data={"metadata": json.dumps(_metadata())},
        files={"image": _image()},
        headers={"X-Ingest-Token": "wrong-token"}
    )
    assert r.status_code == 401

def test_ingest_with_valid_x_ingest_token_header_succeeds(secure_client):
    r = secure_client.post(
        "/api/ingest",
        data={"metadata": json.dumps(_metadata())},
        files={"image": _image()},
        headers={"X-Ingest-Token": "secure-token-12345"}
    )
    assert r.status_code == 201
    assert r.json()["status"] == "created"

def test_ingest_with_valid_bearer_token_succeeds(secure_client):
    metadata = _metadata()
    metadata["sample_code"] = "S-BEARER-TEST"
    r = secure_client.post(
        "/api/ingest",
        data={"metadata": json.dumps(metadata)},
        files={"image": _image()},
        headers={"Authorization": "Bearer secure-token-12345"}
    )
    assert r.status_code == 201
    assert r.json()["status"] == "created"
