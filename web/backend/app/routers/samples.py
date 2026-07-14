"""Read API — list, detail, and CSV export (web_plan.md §2.2).

Serves the frontend and the audit export. Three read-only endpoints, no
PUT/PATCH/DELETE anywhere: append-only is enforced at the routing layer, not
just by UI convention (§2.2).

  GET /api/samples      paginated summary list + batch_lot/date filters
  GET /api/samples/{id} full sample + particles + size histogram
  GET /api/export.csv   one CSV row per particle, same filters

Module 3 owns this file only. Wiring it into `main.py` is Module 6's job.
"""

import csv
import io
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlmodel import Session, select

from ..database import get_session
from ..models import Particle, Sample

router = APIRouter(prefix="/api", tags=["samples"])

# Size histogram: fixed 0.3mm bins across the 0–5mm design range (CLAUDE.md).
# Computed at read time (not stored) so bin size can change later without
# touching persisted data (§2.1). 5.0 / 0.3 rounds up to 17 bins → 0–5.1mm.
BIN_WIDTH_MM = 0.3
HIST_MAX_MM = 5.0
_N_BINS = math.ceil(HIST_MAX_MM / BIN_WIDTH_MM)


# --- Response schemas (owned here; models.py is Module 1's) -------------


class SampleSummary(BaseModel):
    """One row in the history/list view — no particles, no raw metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sample_code: str
    batch_lot: Optional[str]
    device_id: str
    captured_at: datetime
    received_at: datetime
    particle_count: int
    image_path: str


class SampleListResponse(BaseModel):
    items: List[SampleSummary]
    total: int
    page: int
    page_size: int


class ParticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class HistogramBin(BaseModel):
    start: float
    end: float
    count: int


class SizeHistogram(BaseModel):
    bin_width_mm: float
    max_mm: float
    bins: List[HistogramBin]


class SampleDetail(BaseModel):
    id: int
    sample_code: str
    batch_lot: Optional[str]
    device_id: str
    captured_at: datetime
    received_at: datetime
    particle_count: int
    image_path: str
    image_width: Optional[int]
    image_height: Optional[int]
    px_per_mm: Optional[float]
    raw_metadata_json: str
    particles: List[ParticleOut]
    size_histogram: SizeHistogram
    label_distribution: Dict[str, int]


# --- Shared filtering ---------------------------------------------------


def _apply_filters(stmt, batch_lot, date_from, date_to):
    """Apply the batch_lot + captured_at range filters shared by list/export."""
    if batch_lot is not None:
        stmt = stmt.where(Sample.batch_lot == batch_lot)
    if date_from is not None:
        stmt = stmt.where(Sample.captured_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Sample.captured_at <= date_to)
    return stmt


def _build_histogram(particles: List[Particle]) -> SizeHistogram:
    counts = [0] * _N_BINS
    for p in particles:
        idx = int(p.size_mm // BIN_WIDTH_MM)
        idx = max(0, min(idx, _N_BINS - 1))  # clamp under/over-range into ends
        counts[idx] += 1
    bins = [
        HistogramBin(
            start=round(i * BIN_WIDTH_MM, 4),
            end=round((i + 1) * BIN_WIDTH_MM, 4),
            count=counts[i],
        )
        for i in range(_N_BINS)
    ]
    return SizeHistogram(
        bin_width_mm=BIN_WIDTH_MM,
        max_mm=round(_N_BINS * BIN_WIDTH_MM, 4),
        bins=bins,
    )


# --- Endpoints ----------------------------------------------------------


@router.get("/samples", response_model=SampleListResponse)
def list_samples(
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    batch_lot: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None, alias="from"),
    date_to: Optional[datetime] = Query(None, alias="to"),
):
    """Paginated summary list, newest capture first (§2.2)."""
    total = session.exec(
        _apply_filters(select(func.count(Sample.id)), batch_lot, date_from, date_to)
    ).one()

    rows = session.exec(
        _apply_filters(select(Sample), batch_lot, date_from, date_to)
        .order_by(Sample.captured_at.desc(), Sample.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return SampleListResponse(
        items=[SampleSummary.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/samples/{sample_id}", response_model=SampleDetail)
def get_sample(sample_id: int, session: Session = Depends(get_session)):
    """Full sample + its particles + a pre-computed size histogram (§2.2)."""
    sample = session.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="sample not found")

    particles = session.exec(
        select(Particle)
        .where(Particle.sample_id == sample_id)
        .order_by(Particle.blob_index)
    ).all()

    label_distribution: Dict[str, int] = {}
    for p in particles:
        label_distribution[p.label] = label_distribution.get(p.label, 0) + 1

    return SampleDetail(
        id=sample.id,
        sample_code=sample.sample_code,
        batch_lot=sample.batch_lot,
        device_id=sample.device_id,
        captured_at=sample.captured_at,
        received_at=sample.received_at,
        particle_count=sample.particle_count,
        image_path=sample.image_path,
        image_width=sample.image_width,
        image_height=sample.image_height,
        px_per_mm=sample.px_per_mm,
        raw_metadata_json=sample.raw_metadata_json,
        particles=[ParticleOut.model_validate(p) for p in particles],
        size_histogram=_build_histogram(particles),
        label_distribution=label_distribution,
    )


# Column order for the audit CSV: parent-sample fields, then per-particle.
_CSV_SAMPLE_COLS = [
    "sample_code",
    "batch_lot",
    "device_id",
    "captured_at",
    "received_at",
    "particle_count",
    "image_path",
    "px_per_mm",
]
_CSV_PARTICLE_COLS = [
    "blob_index",
    "centroid_x",
    "centroid_y",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "area_px",
    "size_mm",
    "label",
    "confidence",
]

# SEC-2 (SPEC docs/superpowers/specs/2026-07-14-web-system-design.md §6, §4
# FR-3): a spreadsheet treats a cell starting with any of these as a live
# formula/command, not text.
_DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value):
    """Neutralize CSV formula injection (SEC-2) at the CSV boundary only.

    Prefixes a literal single quote onto any string cell whose first
    character is `= + - @` (or a leading TAB/CR), forcing spreadsheet apps to
    render it as text instead of executing it as a formula/command. A no-op
    for non-str values (numeric cells, None) and for strings that don't start
    with a dangerous character — it never touches what's stored in the DB.
    """
    if isinstance(value, str) and value.startswith(_DANGEROUS_CSV_PREFIXES):
        return "'" + value
    return value


@router.get("/export.csv")
def export_csv(
    session: Session = Depends(get_session),
    batch_lot: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None, alias="from"),
    date_to: Optional[datetime] = Query(None, alias="to"),
):
    """Audit export: one row per particle, plus one row for zero-particle
    samples so every matched sample is represented (§2.2, §5). Same filters as
    the list view.

    PERF-1 (SPEC §6): particles for every matched sample are fetched in a
    single query and grouped by sample_id in memory, instead of one query per
    sample.
    """
    samples = session.exec(
        _apply_filters(select(Sample), batch_lot, date_from, date_to)
        .order_by(Sample.captured_at.asc(), Sample.id.asc())
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_SAMPLE_COLS + _CSV_PARTICLE_COLS)

    # One IN() query for all matched samples' particles (PERF-1) — short-
    # circuit when there are no samples so we never issue `IN ()`, which some
    # drivers reject.
    particles_by_sample: Dict[int, List[Particle]] = {}
    if samples:
        sample_ids = [s.id for s in samples]
        all_particles = session.exec(
            select(Particle)
            .where(Particle.sample_id.in_(sample_ids))
            .order_by(Particle.sample_id, Particle.blob_index)
        ).all()
        for p in all_particles:
            particles_by_sample.setdefault(p.sample_id, []).append(p)

    for s in samples:
        sample_cells = [_csv_safe(getattr(s, col)) for col in _CSV_SAMPLE_COLS]
        particles = particles_by_sample.get(s.id, [])
        if not particles:
            writer.writerow(sample_cells + [""] * len(_CSV_PARTICLE_COLS))
        else:
            for p in particles:
                writer.writerow(
                    sample_cells
                    + [_csv_safe(getattr(p, col)) for col in _CSV_PARTICLE_COLS]
                )

    filename = f"aqua_scope_export_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
