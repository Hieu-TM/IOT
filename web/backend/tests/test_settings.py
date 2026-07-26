import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

from app.main import app as fastapi_app
import app.main as app_main
import app.database as app_database
import app.auth as app_auth
from app.database import get_session
from app.models import User, QcSetting
from app.auth import hash_password
from app.qc_helpers import get_warn_particle_count

@pytest.fixture()
def client(monkeypatch):
    # Create isolated in-memory database
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Seed users
    with Session(engine) as s:
        s.add(User(
            username="admin",
            password_hash=hash_password("adminpass1234"),
            role="admin"
        ))
        s.add(User(
            username="operator",
            password_hash=hash_password("operatorpass"),
            role="operator"
        ))
        s.commit()

    # Monkeypatch the engine inside database and main/auth modules
    monkeypatch.setattr(app_database, "engine", engine)
    monkeypatch.setattr(app_main, "engine", engine)

    # Override session dependency on the global app
    def override_get_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    
    c = TestClient(fastapi_app)
    c._engine = engine
    yield c
    fastapi_app.dependency_overrides.clear()

def test_unauthenticated_user_redirects_to_login(client):
    # Unauthenticated GET /settings -> redirect to /login
    r = client.get("/settings", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

    # Unauthenticated POST /settings/qc -> returns 401 (since it's POST and not GET HTML)
    r = client.post("/settings/qc", data={"warn_particle_count": 5}, follow_redirects=False)
    assert r.status_code == 401

def test_operator_blocked_from_settings(client):
    # Log in as operator
    login_res = client.post("/login", data={"username": "operator", "password": "operatorpass"})
    assert login_res.status_code == 200 # redirects by default in testclient unless follow_redirects=False, but it executes login post handler

    # GET /settings should return 403 Forbidden
    r = client.get("/settings")
    assert r.status_code == 403
    assert "administrator role required" in r.text

    # POST /settings/qc should return 403 Forbidden
    r = client.post("/settings/qc", data={"warn_particle_count": 5})
    assert r.status_code == 403

def test_admin_can_access_and_change_settings(client):
    # Log in as admin
    login_res = client.post("/login", data={"username": "admin", "password": "adminpass1234"})
    assert login_res.status_code == 200

    # GET /settings should succeed
    r = client.get("/settings")
    assert r.status_code == 200
    assert "Thiết lập ngưỡng chất lượng (QC)" in r.text

    # POST /settings/qc should update setting and redirect
    r = client.post("/settings/qc", data={"warn_particle_count": 12}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/settings"

    # Verify database update
    with Session(client._engine) as session:
        setting = session.exec(
            select(QcSetting).where(QcSetting.key == "warn_particle_count")
        ).first()
        assert setting is not None
        assert setting.value == "12"

    # Verify settings page displays the updated value
    r = client.get("/settings")
    assert r.status_code == 200
    assert 'value="12"' in r.text


def test_admin_cannot_save_negative_warning_threshold(client):
    client.post("/login", data={"username": "admin", "password": "adminpass1234"})

    r = client.post(
        "/settings/qc",
        data={"warn_particle_count": -1},
        follow_redirects=False,
    )
    assert r.status_code == 422

    with Session(client._engine) as session:
        setting = session.exec(
            select(QcSetting).where(QcSetting.key == "warn_particle_count")
        ).first()
        assert setting is None


def test_invalid_persisted_warning_threshold_fails_loudly(client):
    with Session(client._engine) as session:
        session.add(QcSetting(key="warn_particle_count", value="not-an-int"))
        session.commit()

        with pytest.raises(RuntimeError, match="must be an integer"):
            get_warn_particle_count(session)
