"""SQLModel table models + API validation models.

Two DB tables (`sample`, `particle`, §3 web_plan.md) plus the Pydantic
input models (`IngestPayload`, `ParticleIn`) that Module 2's ingest router
validates incoming `metadata` JSON against (§2.1).

Intentionally imports nothing from `database`/`config` to keep the metadata
registry free of circular imports — `database.py` imports *this* module.
"""

import re
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, field_validator
from pydantic import Field as PydanticField
from sqlmodel import Field, Relationship, SQLModel

# Allowlist for client-supplied sample_code: it becomes a filename verbatim
# (data/images/{sample_code}.jpg), so `/ \ ..` must never reach it (SEC-1,
# SPEC §6, §5.1).
SAMPLE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


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
    # Naive-UTC (DATA-1, SPEC §6) to match captured_at — SQLite drops tzinfo
    # anyway, so mixing aware/naive would skew received_at - captured_at by
    # the dropped offset.
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
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
    """A particle as sent in the `metadata` JSON (§2.1).

    Bounds are loose-but-meaningful sanity checks, not domain limits (SEC-4,
    SPEC §5.1) — they only reject nonsensical values (negative sizes, an
    out-of-[0,1] confidence). `label` stays a free string (class list not
    finalized — §3, §10).
    """

    blob_index: int
    centroid_x: float
    centroid_y: float
    bbox_x: int = PydanticField(ge=0)
    bbox_y: int = PydanticField(ge=0)
    bbox_w: int = PydanticField(ge=0)
    bbox_h: int = PydanticField(ge=0)
    area_px: float = PydanticField(ge=0)
    size_mm: float = PydanticField(ge=0)
    label: str
    confidence: float = PydanticField(ge=0, le=1)


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

    @field_validator("sample_code")
    @classmethod
    def _sample_code_must_be_filename_safe(cls, v: Optional[str]) -> Optional[str]:
        # SEC-1 (SPEC §6, §5.1): sample_code is used verbatim as an image
        # filename, so `/ \ ..` must never reach the filesystem. Missing
        # sample_code stays valid — the server generates one.
        # fullmatch, not match: `^...$` + match would accept a trailing "\n"
        # (that `\n` then reaches write_bytes and crashes) — SEC-1 requires
        # the whole string to be filename-safe.
        if v is not None and not SAMPLE_CODE_PATTERN.fullmatch(v):
            raise ValueError(
                "sample_code must match ^[A-Za-z0-9._-]{1,64}$"
            )
        return v

    @field_validator("captured_at")
    @classmethod
    def _captured_at_must_carry_offset(cls, v: datetime) -> datetime:
        # DATA-1 (SPEC §6, §5.1): captured_at must carry a UTC offset so the
        # server can convert it unambiguously — an offset-less value is
        # rejected rather than silently assumed to be UTC or local time.
        # Accepted values are normalized to naive-UTC here so every stored
        # datetime (this + Sample.received_at) is naive-UTC consistently.
        if v.tzinfo is None:
            raise ValueError("captured_at must include a UTC offset (ISO 8601)")
        return v.astimezone(timezone.utc).replace(tzinfo=None)
