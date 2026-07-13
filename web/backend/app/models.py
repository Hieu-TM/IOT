"""SQLModel table models + API validation models.

Two DB tables (`sample`, `particle`, §3 web_plan.md) plus the Pydantic
input models (`IngestPayload`, `ParticleIn`) that Module 2's ingest router
validates incoming `metadata` JSON against (§2.1).

Intentionally imports nothing from `database`/`config` to keep the metadata
registry free of circular imports — `database.py` imports *this* module.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel


# --- DB tables ----------------------------------------------------------


class Sample(SQLModel, table=True):
    """One measurement cycle: metadata + the backlit image it produced.

    Append-only audit record; there is no update/delete path anywhere in the
    API (§2.2). `raw_metadata_json` keeps the verbatim payload so the record
    stays auditable even if this normalized schema changes later (§3).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    sample_code: str = Field(index=True, unique=True)
    batch_lot: Optional[str] = Field(default=None, index=True)
    device_id: str
    captured_at: datetime
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    # Denormalized len(particles) for fast sort/list (§2.1).
    particle_count: int = 0
    # Relative path under data/images/, e.g. "images/S....jpg".
    image_path: str
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    px_per_mm: Optional[float] = None
    # Verbatim original metadata JSON — the real audit-proof record.
    raw_metadata_json: str

    particles: List["Particle"] = Relationship(back_populates="sample")


class Particle(SQLModel, table=True):
    """One detected blob within a sample's frame.

    `label` is a free string (not a DB enum) because the classifier's class
    list is not finalized (§3, §10).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    sample_id: int = Field(foreign_key="sample.id", index=True)
    blob_index: int
    centroid_x: float
    centroid_y: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    area_px: float
    size_mm: float
    label: str
    confidence: float

    sample: Optional[Sample] = Relationship(back_populates="particles")


# --- API input validation (used by Module 2's ingest router) ------------


class ParticleIn(BaseModel):
    """A particle as sent in the `metadata` JSON (§2.1)."""

    blob_index: int
    centroid_x: float
    centroid_y: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    area_px: float
    size_mm: float
    label: str
    confidence: float


class IngestPayload(BaseModel):
    """The `metadata` form field of `POST /api/ingest` (§2.1).

    `sample_code` is optional — the server generates one when missing. Count
    and size distribution are never accepted from input; they are derived.
    """

    device_id: str
    sample_code: Optional[str] = None
    batch_lot: Optional[str] = None
    captured_at: datetime
    px_per_mm: Optional[float] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    particles: List[ParticleIn] = []
