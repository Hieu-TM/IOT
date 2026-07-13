"""Database engine, session dependency, and table creation.

Imports `models` (side-effect: registers both tables on SQLModel.metadata)
so `create_db_and_tables()` sees them. `models` must not import this module,
or table registration would deadlock on a circular import.
"""

from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401 — registers Sample/Particle on metadata
from .config import DATABASE_URL, DATA_DIR, IMAGES_DIR

# check_same_thread=False: FastAPI may touch the session from a different
# thread than the one that created it; safe here given SQLite single-writer
# and the low, batched write rate of this station (§3).
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def create_db_and_tables() -> None:
    """Ensure the data dirs exist and both tables are created (idempotent)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency yielding a scoped Session."""
    with Session(engine) as session:
        yield session
