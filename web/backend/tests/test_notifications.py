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
from app.models import User, Notification
from app.auth import hash_password

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
    # Unauthenticated GET /notifications -> redirect to /login
    r = client.get("/notifications", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

    # Unauthenticated POST /notifications/1/ack -> returns 401
    r = client.post("/notifications/1/ack", follow_redirects=False)
    assert r.status_code == 401

def test_user_can_access_and_ack_notifications(client):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(client._engine) as session:
        # Create a notification
        session.add(Notification(
            sample_id=1,
            batch_lot="LOT-A",
            message="LOT-A: sample S001 has too many particles",
            created_at=now
        ))
        session.commit()

    # Log in as operator
    login_res = client.post("/login", data={"username": "operator", "password": "operatorpass"})
    assert login_res.status_code == 200

    # GET /notifications should succeed and display the alert
    r = client.get("/notifications")
    assert r.status_code == 200
    assert "LOT-A: sample S001 has too many particles" in r.text
    assert "Cảnh báo chưa xác nhận" in r.text
    assert "Xác nhận" in r.text

    # Ack the notification
    r = client.post(
        "/notifications/1/ack",
        data={"note": "Retested with clean tray"},
        follow_redirects=False,
        headers={"referer": "https://evil.example/phish"},
    )
    assert r.status_code == 303 # redirects back to referrer or default /notifications
    assert r.headers["location"] == "/notifications"

    # Verify database was updated
    with Session(client._engine) as session:
        notice = session.get(Notification, 1)
        assert notice is not None
        assert notice.acknowledged_at is not None
        # should match the operator's ID (which is 2)
        assert notice.acknowledged_by == 2
        assert notice.acknowledgement_note == "Retested with clean tray"

    # GET /notifications should now show it under resolved list
    r = client.get("/notifications")
    assert r.status_code == 200
    assert "operator" in r.text
    assert "Retested with clean tray" in r.text
    assert "Lịch sử cảnh báo đã xác nhận" in r.text
    assert "Đã xác nhận bởi <strong style=\"color:var(--text);\">operator</strong>" in r.text
