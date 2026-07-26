"""Database engine, session dependency, and table creation.

Imports `models` (side-effect: registers both tables on SQLModel.metadata)
so `create_db_and_tables()` sees them. `models` must not import this module,
or table registration would deadlock on a circular import.
"""

from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401 — registers Sample/Particle on metadata
from .config import DATABASE_URL, IMAGES_DIR

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


def create_db_and_tables() -> None:
    """Ensure the image directory and SQL Server tables exist (idempotent)."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency yielding a scoped Session."""
    with Session(engine) as session:
        yield session
