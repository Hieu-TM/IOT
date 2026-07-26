"""Authentication and role-boundary tests."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from starlette.middleware.sessions import SessionMiddleware

from app.auth import hash_password, require_admin, router as auth_router
from app.database import get_session
from app.models import User


def _client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret", https_only=False)
    app.include_router(auth_router)

    @app.get("/admin", dependencies=[Depends(require_admin)])
    def admin_page():
        return {"ok": True}

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    client._engine = engine
    return client


def test_login_creates_session_and_operator_cannot_access_admin_route():
    client = _client()
    with Session(client._engine) as session:
        session.add(User(username="operator", password_hash=hash_password("correct horse"), role="operator"))
        session.commit()

    response = client.post(
        "/login",
        data={"username": "operator", "password": "correct horse"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    denied = client.get("/admin")
    assert denied.status_code == 403


def test_invalid_login_does_not_create_session():
    client = _client()
    response = client.post(
        "/login", data={"username": "nobody", "password": "bad"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"
    assert client.get("/admin").status_code == 401
