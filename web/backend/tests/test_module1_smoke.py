"""Module 1 acceptance test (web_plan.md §9).

Verifies the backend core boots, creates the DB with exactly the two tables,
and serves `GET /` without crashing. Run from web/backend/:  pytest -q
"""

from sqlalchemy import inspect

from app.config import DB_PATH
from app.database import create_db_and_tables, engine
from app.main import app


def test_create_db_and_tables_makes_exactly_two_tables():
    create_db_and_tables()
    assert DB_PATH.exists(), "aqua_scope.db was not created"
    tables = set(inspect(engine).get_table_names())
    assert tables == {"sample", "particle"}, f"unexpected tables: {tables}"


def test_root_endpoint_does_not_crash():
    from fastapi.testclient import TestClient

    with TestClient(app) as client:  # triggers lifespan startup too
        resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_particle_has_sample_foreign_key():
    fks = inspect(engine).get_foreign_keys("particle")
    assert any(
        fk["referred_table"] == "sample" for fk in fks
    ), "particle.sample_id FK to sample missing"
