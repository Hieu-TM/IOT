"""Core schema smoke tests for the SQL Server-backed backend."""

from sqlmodel import SQLModel

from app.config import DATABASE_URL
from app.main import app


def test_runtime_configuration_targets_sql_server():
    assert DATABASE_URL.startswith("mssql+pyodbc://")
    assert {"sample", "particle", "user", "notification"} <= set(SQLModel.metadata.tables)


def test_application_is_configured_as_traceability_api():
    assert app.title == "Aqua Scope Traceability API"


def test_particle_and_notification_reference_samples():
    particle = SQLModel.metadata.tables["particle"]
    notification = SQLModel.metadata.tables["notification"]
    assert any(fk.column.table.name == "sample" for fk in particle.foreign_keys)
    assert any(fk.column.table.name == "sample" for fk in notification.foreign_keys)
