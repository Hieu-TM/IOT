"""POST /api/ingest — receive one measurement (metadata JSON + JPEG).

Implements the ingest contract in web_plan.md §2.1:
  * multipart/form-data with a `metadata` JSON string field and an `image` file
  * server-generated `sample_code` when absent
  * idempotent retry keyed on `sample_code`
  * atomic write: sample row + particle rows + image file all land, or none do

Module 2 owns this file only. Wiring it into `main.py` is Module 6's job.
"""

import io
import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .. import config
from ..database import get_session
from ..models import IngestPayload, Particle, Sample

router = APIRouter(prefix="/api", tags=["ingest"])


def _generate_sample_code() -> str:
    """`S{yyyyMMdd}-{HHmmss}-{4 hex}` per §2.1 when the device sends none.

    DATA-1 (SPEC §6): must be UTC, not local time — captured_at/received_at
    are stored naive-UTC, so a local-time code would disagree with the audit
    columns it summarizes by exactly the machine's UTC offset.
    """
    now = datetime.now(timezone.utc)
    return f"S{now:%Y%m%d}-{now:%H%M%S}-{secrets.token_hex(2)}"


def _already_exists_response(sample: Sample) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "id": sample.id,
            "sample_code": sample.sample_code,
            "particle_count": sample.particle_count,
            "status": "already_exists",
        },
    )


@router.post("/ingest")
async def ingest(
    metadata: str = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    # --- 1. Validate metadata JSON (§2.1: 422 on bad/missing) -----------
    try:
        raw = json.loads(metadata)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=422, detail="metadata is not valid JSON")
    try:
        payload = IngestPayload.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json()))

    # --- 2. Validate image (SEC-3 SPEC §6: 413 before 400 on unopenable) --
    # Prefer the multipart-provided size (set by Starlette while parsing the
    # form, before this handler runs) so an oversized upload is rejected
    # without an extra full-body read into app memory.
    # NOTE: this is a 413 *contract* (correct status code + no huge row/file
    # written), not a DoS control — Starlette has already buffered the whole
    # multipart body into memory before this handler ever runs. A real
    # request-body-size cap belongs in ASGI middleware or the reverse proxy,
    # in front of that buffering.
    if image.size is not None and image.size > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image exceeds upload size limit")
    contents = await image.read()
    if len(contents) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image exceeds upload size limit")
    if not contents:
        raise HTTPException(status_code=400, detail="image part is empty")
    try:
        with Image.open(io.BytesIO(contents)) as im:
            im.verify()  # sanity-check; consumes the object
        with Image.open(io.BytesIO(contents)) as im2:
            img_w, img_h = im2.size
    except Exception:
        raise HTTPException(status_code=400, detail="image is not a readable picture")

    # --- 3. Resolve sample_code + idempotent short-circuit --------------
    sample_code = payload.sample_code or _generate_sample_code()
    existing = session.exec(
        select(Sample).where(Sample.sample_code == sample_code)
    ).first()
    if existing is not None:
        return _already_exists_response(existing)

    # --- 4. Persist image, then sample + particles atomically -----------
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    image_file = config.IMAGES_DIR / f"{sample_code}.jpg"
    image_file.write_bytes(contents)

    sample = Sample(
        sample_code=sample_code,
        batch_lot=payload.batch_lot,
        device_id=payload.device_id,
        captured_at=payload.captured_at,
        particle_count=len(payload.particles),
        image_path=f"images/{sample_code}.jpg",
        image_width=payload.image_width or img_w,
        image_height=payload.image_height or img_h,
        px_per_mm=payload.px_per_mm if payload.px_per_mm is not None
        else config.PX_PER_MM_DEFAULT,
        raw_metadata_json=metadata,
    )
    session.add(sample)
    try:
        session.flush()  # assign sample.id without committing yet
        for p in payload.particles:
            session.add(Particle(sample_id=sample.id, **p.model_dump()))
        session.commit()
    except IntegrityError:
        # Concurrent duplicate slipped past the pre-check — treat as retry.
        session.rollback()
        existing = session.exec(
            select(Sample).where(Sample.sample_code == sample_code)
        ).first()
        if existing is not None:
            return _already_exists_response(existing)
        _remove_quietly(image_file)
        raise HTTPException(status_code=500, detail="database integrity error")
    except Exception:
        # Nothing partial survives: DB rolled back, orphan image removed.
        session.rollback()
        _remove_quietly(image_file)
        raise HTTPException(status_code=500, detail="failed to store sample")

    return JSONResponse(
        status_code=201,
        content={
            "id": sample.id,
            "sample_code": sample.sample_code,
            "particle_count": sample.particle_count,
            "status": "created",
        },
    )


def _remove_quietly(path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
