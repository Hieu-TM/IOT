"""Server-rendered dashboard pages (Module 5, web_plan.md §5 + frontend design).

Four Jinja2 pages, all read-only (append-only is enforced by there being no
mutating route anywhere):

  GET /              Dashboard — today's shift summary + latest sample
  GET /history       Audit table — paginated + date/lot filters + CSV export
  GET /samples/{id}  Sample detail — image + bbox overlay + particles + charts
  GET /stream        Stream demo — pure-frontend backlit-flow simulation

Data is queried straight from the DB and prepared into template-ready view
models here (charts are hand-built inline SVG rendered from these values — no
client charting library, so the dashboard stays fully offline on the LAN).

Datetimes are stored naive-UTC (DATA-1); every value shown to the user is
converted to the server's local time here before formatting (frontend build
prompt: "Frontend phải đổi sang giờ địa phương khi hiển thị").

Module 5 owns this file. It reuses two read helpers from the Module 3 read API
(`_apply_filters`, `_build_histogram`) rather than duplicating the filter/bin
logic — importing is not modifying.
"""

import json
import math
from datetime import date, datetime, time, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

from .. import config
from ..database import get_session
from ..models import Notification, Particle, Sample, QcSetting, User
from .samples import BIN_WIDTH_MM, UNASSIGNED_BATCH_LOT, _apply_filters, _build_histogram
from ..qc_helpers import get_warn_particle_count
from ..auth import require_admin, get_current_user

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(config.APP_DIR / "templates"))

# --- Label vocabulary (single source, mirrors static/css + static/js) ---
# Current detector vocabulary (all four are plastic morphologies).
LABEL_ORDER = ["fiber", "film", "fragment", "pallet", "unknown"]
LABEL_VI = {
    "fiber": "Sợi",
    "film": "Màng",
    "fragment": "Mảnh",
    "pallet": "Viên",
    "pellet": "Viên",      # dataset spells it "pallet"; accept the correct spelling too
    "unknown": "Không xác định",
    # Legacy vocabulary from the earlier hybrid design - kept so historical rows
    # already stored in the database still render with a Vietnamese name.
    "plastic": "Nhựa",
    "bubble": "Bọt khí",
    "organic": "Hữu cơ",
}


def _label_vi(label: str) -> str:
    return LABEL_VI.get(label, label)


def _label_color(label: str) -> str:
    """CSS custom-property reference for a label's color (unknown for strays)."""
    return f"var(--p-{label})" if label in LABEL_VI else "var(--p-unknown)"


def _is_warn(particle_count: int, threshold: int) -> bool:
    return particle_count > threshold


# --- datetime → local, formatted -----------------------------------------


def _local(dt: datetime) -> datetime:
    """Stored naive-UTC → timezone-aware local time for display (DATA-1)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _fmt_dt(dt: datetime) -> str:
    """`dd/mm · HH:MM` — the compact stamp used in tables/cards."""
    lt = _local(dt)
    return f"{lt:%d/%m · %H:%M}"


def _json_for_script(obj) -> str:
    """JSON safe to embed in a `<script type="application/json">` block.

    `json.dumps` does not escape `<` `>` `&`, so a value containing
    `</script>` — and particle `label` is free-form ingest input (models.py),
    not a fixed enum — would close the script element early and inject markup
    (stored XSS). Escaping those three to `\\uXXXX` keeps the payload valid
    JSON while making a `</script>` breakout impossible. Mirrors the SEC-2
    output-encoding approach used for the CSV export.
    """
    return (
        json.dumps(obj)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


# --- chart geometry (hand-built inline SVG, no charting lib) --------------


def _donut(entries: List[dict], total: int, size: int = 132) -> dict:
    """Stroke-dasharray ring segments for the label-distribution donut.

    `entries` is [{"color": <css var>, "count": int}, ...]; mirrors the design
    reference's donut() math so the server-rendered SVG matches it exactly.
    """
    r = size / 2
    sw = size * 0.14
    rr = r - sw / 2
    circ = 2 * math.pi * rr
    segs = []
    offset = 0.0
    for e in entries:
        if e["count"] <= 0 or total <= 0:
            continue
        seg_len = e["count"] / total * circ
        segs.append(
            {
                "color": e["color"],
                "len": round(seg_len, 3),
                "gap": round(circ - seg_len, 3),
                "offset": round(-offset, 3),
            }
        )
        offset += seg_len
    return {
        "size": size,
        "c": round(r, 3),
        "rr": round(rr, 3),
        "sw": round(sw, 3),
        "segs": segs,
    }


def _histogram_svg(size_histogram) -> dict:
    """Bar + tick geometry for the size histogram (0.3mm bins, 0–5mm)."""
    W, H = 360, 150
    pad_l, pad_r, pad_b, pad_t = 6, 6, 26, 8
    counts = [b.count for b in size_histogram.bins]
    n = len(counts)
    max_c = max([1, *counts])
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    bw = plot_w / n
    bars = []
    for i, v in enumerate(counts):
        bh = v / max_c * plot_h
        x = pad_l + i * bw
        y = pad_t + plot_h - bh
        bars.append(
            {
                "x": round(x + 1.5, 3),
                "y": round(y, 3),
                "w": round(bw - 3, 3),
                "h": round(bh, 3),
                "count": v,
                "tx": round(x + bw / 2, 3),
                "ty": round(y - 3, 3),
            }
        )
    ticks = []
    span_mm = n * BIN_WIDTH_MM
    for mm in range(6):
        x = pad_l + (mm / span_mm) * plot_w
        ticks.append({"x": round(x, 3), "mm": mm})
    return {
        "W": W,
        "H": H,
        "baseline_y": pad_t + plot_h,
        "bars": bars,
        "ticks": ticks,
    }


# --- particle / sample view models ---------------------------------------


def _sample_particles(session: Session, sample_id: int) -> List[Particle]:
    return session.exec(
        select(Particle)
        .where(Particle.sample_id == sample_id)
        .order_by(Particle.blob_index)
    ).all()


def _overlay_particles(particles: List[Particle]) -> List[dict]:
    """Minimal per-particle payload the bbox overlay + hover JS reads."""
    return [
        {
            "i": idx,
            "x": p.bbox_x,
            "y": p.bbox_y,
            "w": p.bbox_w,
            "h": p.bbox_h,
            "cx": p.centroid_x,
            "cy": p.centroid_y,
            "label": p.label,
            "vi": _label_vi(p.label),
            "color": _label_color(p.label),
            "size_mm": p.size_mm,
            "conf_pct": round(p.confidence * 100),
            "dashed": p.label not in LABEL_VI or p.label == "unknown",
        }
        for idx, p in enumerate(particles)
    ]


def _label_distribution(particles: List[Particle]) -> Dict[str, int]:
    dist: Dict[str, int] = {}
    for p in particles:
        dist[p.label] = dist.get(p.label, 0) + 1
    return dist


def _dist_chips(dist: Dict[str, int]) -> List[dict]:
    """Ordered colored count-chips for a sample's label distribution."""
    return [
        {"vi": _label_vi(label), "color": _label_color(label), "count": dist[label]}
        for label in _ordered_labels(dist)
    ]


def _ordered_labels(dist: Dict[str, int]) -> List[str]:
    """Canonical labels first, then every non-canonical label present in data."""
    labels = [label for label in LABEL_ORDER if dist.get(label)]
    labels.extend(
        label
        for label in sorted(dist)
        if label not in LABEL_ORDER and dist.get(label)
    )
    return labels


# --- pages ----------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    today = datetime.now().astimezone().date()
    threshold = get_warn_particle_count(session)

    all_samples = session.exec(
        select(Sample).order_by(Sample.captured_at.desc(), Sample.id.desc())
    ).all()
    notifications = session.exec(
        select(Notification)
        .where(Notification.acknowledged_at == None)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(8)
    ).all()
    notification_rows = [
        {
            "id": item.id,
            "lot": item.batch_lot or "Unassigned batch lot",
            "message": item.message,
            "time": _fmt_dt(item.created_at),
            "sample_id": item.sample_id,
        }
        for item in notifications
    ]

    if not all_samples:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"screen": "dashboard", "title": "Bảng điều khiển QC", "empty": True},
        )

    today_samples = [s for s in all_samples if _local(s.captured_at).date() == today]
    today_ids = [s.id for s in today_samples]

    # Today's aggregate label distribution (one grouped query, not N).
    today_dist: Dict[str, int] = {}
    if today_ids:
        rows = session.exec(
            select(Particle.label, func.count(Particle.id))
            .where(Particle.sample_id.in_(today_ids))
            .group_by(Particle.label)
        ).all()
        today_dist = {label: count for label, count in rows}
    today_total = sum(today_dist.values())
    # No plastic-ratio metric: every class the detector can emit is a plastic
    # morphology, and it has no non-plastic class - so a "% plastic" figure would
    # assert something the model cannot determine. Show the dominant type instead.
    dominant_label, dominant_count = ("", 0)
    if today_dist:
        dominant_label, dominant_count = max(today_dist.items(), key=lambda kv: kv[1])
    dominant_pct = round(dominant_count / today_total * 100) if today_total else 0
    warn_count = sum(1 for s in today_samples if _is_warn(s.particle_count, threshold))

    metric_tiles = [
        {
            "label": "Mẫu hôm nay",
            "value": len(today_samples),
            "hint": "trong ca hôm nay",
            "icon": "grid",
            "warn": False,
        },
        {
            "label": "Tổng hạt hôm nay",
            "value": today_total,
            "hint": "trên tất cả mẫu",
            "icon": "dots",
            "warn": False,
        },
        {
            "label": "Loại nhiều nhất",
            "value": _label_vi(dominant_label) if dominant_label else "—",
            "hint": (f"{dominant_count}/{today_total} hạt · {dominant_pct}%"
                     if today_total else "chưa có hạt"),
            "icon": "plus",
            "value_class": "teal",
            "warn": False,
        },
        {
            "label": "Cảnh báo",
            "value": warn_count,
            "hint": f"mẫu có >{threshold} hạt" if warn_count else "không có",
            "icon": "warn",
            "value_class": "amber" if warn_count else "",
            "warn": bool(warn_count),
        },
    ]

    today_labels = _ordered_labels(today_dist)
    donut_entries = [
        {"color": _label_color(l), "count": today_dist[l]}
        for l in today_labels
    ]

    donut_legend = [
        {
            "vi": _label_vi(l),
            "color": _label_color(l),
            "pct": f"{round(today_dist[l] / today_total * 100)}%",
        }
        for l in today_labels
    ]

    latest = all_samples[0]
    latest_particles = _sample_particles(session, latest.id)
    latest_image_available = (config.IMAGES_DIR / f"{latest.sample_code}.jpg").is_file()

    recent5 = [
        {
            "id": s.id,
            "code": s.sample_code,
            "lot": s.batch_lot or "—",
            "time": _fmt_dt(s.captured_at),
            "count": s.particle_count,
            "warn": _is_warn(s.particle_count, threshold),
        }
        for s in today_samples[:5]
    ]

    ctx = {
        "screen": "dashboard",
        "title": "Bảng điều khiển QC",
        "empty": False,
        "metric_tiles": metric_tiles,
        "donut": _donut(donut_entries, today_total),
        "donut_total": today_total,
        "donut_legend": donut_legend,
        "latest": {
            "id": latest.id,
            "code": latest.sample_code,
            "lot": latest.batch_lot or "—",
            "time": _fmt_dt(latest.captured_at),
            "count": latest.particle_count,
            "warn": _is_warn(latest.particle_count, threshold),
            "image_url": "/" + latest.image_path.lstrip("/"),
            "image_available": latest_image_available,
            "image_width": latest.image_width or 640,
            "image_height": latest.image_height or 480,
            "particles_json": _json_for_script(_overlay_particles(latest_particles)),
        },
        "recent5": recent5,
        "notifications": notification_rows,
    }
    return templates.TemplateResponse(request, "index.html", ctx)


@router.get("/batches", response_class=HTMLResponse)
def batches(request: Request, session: Session = Depends(get_session)):
    """Batch summary page — aggregates samples by batch_lot."""
    from collections import defaultdict
    from urllib.parse import urlencode
    threshold = get_warn_particle_count(session)

    all_samples = session.exec(
        select(Sample).order_by(Sample.captured_at.desc(), Sample.id.desc())
    ).all()

    if not all_samples:
        return templates.TemplateResponse(
            request,
            "batches.html",
            {"screen": "batches", "title": "Lô sản xuất", "empty": True,
             "batches": [], "total_batches": 0},
        )

    # Group samples by batch_lot
    lots: dict = defaultdict(list)
    for s in all_samples:
        lots[s.batch_lot].append(s)

    # Get label distribution across all samples (one query)
    sample_ids = [s.id for s in all_samples]
    label_rows = session.exec(
        select(Particle.sample_id, Particle.label, func.count(Particle.id))
        .where(Particle.sample_id.in_(sample_ids))
        .group_by(Particle.sample_id, Particle.label)
    ).all()
    # Build: lot -> {label: count}
    sample_to_lot = {s.id: s.batch_lot for s in all_samples}
    lot_labels: dict = defaultdict(lambda: defaultdict(int))
    for sid, label, count in label_rows:
        lot_key = sample_to_lot.get(sid)
        lot_labels[lot_key][label] += count

    batch_rows = []
    for lot_key, samples_in_lot in lots.items():
        sample_count = len(samples_in_lot)
        total_particles = sum(s.particle_count for s in samples_in_lot)
        warn_count = sum(1 for s in samples_in_lot if _is_warn(s.particle_count, threshold))
        first_dt = min(s.captured_at for s in samples_in_lot)
        last_dt = max(s.captured_at for s in samples_in_lot)

        dist = lot_labels.get(lot_key, {})
        dominant_label = ""
        dominant_count = 0
        if dist:
            dominant_label, dominant_count = max(dist.items(), key=lambda kv: kv[1])
        total_label_count = sum(dist.values())
        dominant_pct = round(dominant_count / total_label_count * 100) if total_label_count else 0

        qs = "?" + urlencode(
            {"batch_lot": lot_key if lot_key else UNASSIGNED_BATCH_LOT}
        )
        batch_rows.append({
            "lot_key": lot_key,
            "lot_display": lot_key or "Chưa gán lô",
            "sample_count": sample_count,
            "total_particles": total_particles,
            "warn_count": warn_count,
            "dominant_label": dominant_label,
            "dominant_vi": _label_vi(dominant_label) if dominant_label else "",
            "dominant_color": _label_color(dominant_label) if dominant_label else "",
            "dominant_pct": dominant_pct,
            "first_time": _fmt_dt(first_dt),
            "last_time": _fmt_dt(last_dt),
            "history_qs": qs,
        })

    # Sort: lots with warnings first, then alphabetically
    batch_rows.sort(key=lambda b: (-b["warn_count"], b["lot_display"]))

    ctx = {
        "screen": "batches",
        "title": "Lô sản xuất",
        "empty": False,
        "batches": batch_rows,
        "total_batches": len(batch_rows),
    }
    return templates.TemplateResponse(request, "batches.html", ctx)


@router.get("/devices", response_class=HTMLResponse)
def devices(request: Request, session: Session = Depends(get_session)):
    """Device status page — details for each active device/station."""
    today = datetime.now().astimezone().date()
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    threshold = get_warn_particle_count(session)

    all_samples = session.exec(
        select(Sample).order_by(Sample.captured_at.desc(), Sample.id.desc())
    ).all()

    if not all_samples:
        return templates.TemplateResponse(
            request,
            "devices.html",
            {"screen": "devices", "title": "Thiết bị", "empty": True, "devices": []},
        )

    # Group samples by device_id
    from collections import defaultdict
    device_samples = defaultdict(list)
    for s in all_samples:
        device_samples[s.device_id].append(s)

    device_rows = []
    for dev_id, samples in device_samples.items():
        latest_sample = samples[0] # ordered descending
        
        # Today's samples for this device
        today_dev_samples = [s for s in samples if _local(s.captured_at).date() == today]
        today_count = len(today_dev_samples)
        today_warn_count = sum(1 for s in today_dev_samples if _is_warn(s.particle_count, threshold))
        
        # Calculate delay
        delay_seconds = (latest_sample.received_at - latest_sample.captured_at).total_seconds()
        # format delay nicely
        if delay_seconds < 60:
            delay_str = f"{int(max(0, delay_seconds))}s"
        else:
            delay_str = f"{int(delay_seconds // 60)}m {int(delay_seconds % 60)}s"

        # Determine status
        diff_minutes = (now_utc - latest_sample.captured_at).total_seconds() / 60.0
        
        if diff_minutes <= config.DEVICE_ONLINE_WINDOW_MINUTES:
            status = "online"
            status_vi = "Trực tuyến"
        elif _local(latest_sample.captured_at).date() == today:
            status = "idle"
            status_vi = "Chờ"
        else:
            status = "offline"
            status_vi = "Ngoại tuyến"

        device_rows.append({
            "device_id": dev_id,
            "latest_code": latest_sample.sample_code,
            "latest_sample_id": latest_sample.id,
            "captured_at": _fmt_dt(latest_sample.captured_at),
            "received_at": _fmt_dt(latest_sample.received_at),
            "delay_str": delay_str,
            "today_count": today_count,
            "today_warn_count": today_warn_count,
            "status": status,
            "status_vi": status_vi,
        })

    # Sort: online first, then idle, then offline
    status_order = {"online": 0, "idle": 1, "offline": 2}
    device_rows.sort(key=lambda d: (status_order[d["status"]], d["device_id"]))

    ctx = {
        "screen": "devices",
        "title": "Thiết bị",
        "empty": False,
        "devices": device_rows,
    }
    return templates.TemplateResponse(request, "devices.html", ctx)


@router.get("/history", response_class=HTMLResponse)
def history(
    request: Request,
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    batch_lot: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    q: Optional[str] = Query(None),
):
    # Date inputs are yyyy-mm-dd (local). Turn them into a local-aware
    # [start-of-day, end-of-day] range so _apply_filters converts to UTC.
    from_dt = _parse_local_day(date_from, end=False)
    to_dt = _parse_local_day(date_to, end=True)
    lot = batch_lot or None
    threshold = get_warn_particle_count(session)

    total = session.exec(
        _apply_filters(select(func.count(Sample.id)), lot, from_dt, to_dt, q)
    ).one()
    # The audit view is the complete traceability record: never truncate it to
    # a dashboard-sized subset. Filters still narrow the exported/displayed set.
    page = 1
    total_pages = 1
    samples = session.exec(
        _apply_filters(select(Sample), lot, from_dt, to_dt, q)
        .order_by(Sample.captured_at.desc(), Sample.id.desc())
    ).all()

    # Label distributions for just this page's samples (one grouped query).
    page_ids = [s.id for s in samples]
    dist_by_sample: Dict[int, Dict[str, int]] = {sid: {} for sid in page_ids}
    if page_ids:
        rows = session.exec(
            select(Particle.sample_id, Particle.label, func.count(Particle.id))
            .where(Particle.sample_id.in_(page_ids))
            .group_by(Particle.sample_id, Particle.label)
        ).all()
        for sid, label, count in rows:
            dist_by_sample[sid][label] = count

    page_rows = [
        {
            "id": s.id,
            "code": s.sample_code,
            "lot": s.batch_lot or "—",
            "time": _fmt_dt(s.captured_at),
            "count": s.particle_count,
            "dist": _dist_chips(dist_by_sample.get(s.id, {})),
            "warn": _is_warn(s.particle_count, threshold),
        }
        for s in samples
    ]

    lot_values = session.exec(
        select(Sample.batch_lot)
        .where(Sample.batch_lot.is_not(None))
        .distinct()
        .order_by(Sample.batch_lot)
    ).all()

    # Preserve the active filter on the CSV-export link + pagination links.
    export_qs = _query_string({"batch_lot": lot, "from": date_from, "to": date_to, "q": q})

    ctx = {
        "screen": "history",
        "title": "Lịch sử · audit",
        "filters": {
            "from": date_from or "",
            "to": date_to or "",
            "lot": lot or "",
            "q": q or "",
            "unassigned_lot": UNASSIGNED_BATCH_LOT,
        },
        "lot_options": lot_values,
        "rows": page_rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "summary": f"{total} mẫu khớp bộ lọc · trang {page}/{total_pages}",
        "export_qs": export_qs,
        "prev_qs": _query_string(
            {"batch_lot": lot, "from": date_from, "to": date_to, "q": q, "page": page - 1}
        ),
        "next_qs": _query_string(
            {"batch_lot": lot, "from": date_from, "to": date_to, "q": q, "page": page + 1}
        ),
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "empty": total == 0,
    }
    return templates.TemplateResponse(request, "history.html", ctx)


@router.get("/samples/{sample_id}", response_class=HTMLResponse)
def sample_detail(
    request: Request, sample_id: int, session: Session = Depends(get_session)
):
    sample = session.get(Sample, sample_id)
    if sample is None:
        return templates.TemplateResponse(
            request,
            "sample_detail.html",
            {"screen": "detail", "title": "Chi tiết mẫu", "notfound": True},
            status_code=404,
        )

    particles = _sample_particles(session, sample_id)
    image_available = (config.IMAGES_DIR / f"{sample.sample_code}.jpg").is_file()
    dist = _label_distribution(particles)
    total = len(particles)
    size_histogram = _build_histogram(particles)
    threshold = get_warn_particle_count(session)

    meta = [
        {"k": "Mã lô", "v": sample.batch_lot or "—", "mono": True},
        {"k": "Thiết bị", "v": sample.device_id, "mono": True},
        {"k": "Giờ chụp", "v": _fmt_dt(sample.captured_at), "mono": False},
        {"k": "Giờ nhận", "v": _fmt_dt(sample.received_at), "mono": False},
        {
            "k": "Hiệu chuẩn",
            "v": f"{sample.px_per_mm:g} px/mm" if sample.px_per_mm else "—",
            "mono": False,
        },
        {
            "k": "Kích thước ảnh",
            "v": f"{sample.image_width}×{sample.image_height}"
            if sample.image_width
            else "—",
            "mono": False,
        },
    ]

    particle_rows = [
        {
            "i": idx,
            "vi": _label_vi(p.label),
            "color": _label_color(p.label),
            "conf": f"{round(p.confidence * 100)}%",
            "conf_low": p.confidence < config.CONFIDENCE_THRESHOLD,
            "size": f"{p.size_mm:g} mm",
            "area": f"{p.area_px:g} px²",
            "centroid": f"{p.centroid_x:g}, {p.centroid_y:g}",
        }
        for idx, p in enumerate(particles)
    ]

    sample_labels = _ordered_labels(dist)
    label_rows = [
        {
            "vi": _label_vi(l),
            "color": _label_color(l),
            "count": dist[l],
            "pct": f"{round(dist[l] / total * 100)}%" if total else "0%",
        }
        for l in sample_labels
    ]
    legend = [
        {"vi": _label_vi(l), "color": _label_color(l)}
        for l in sample_labels
    ]

    ctx = {
        "screen": "detail",
        "title": "Chi tiết mẫu",
        "notfound": False,
        "sample": {
            "id": sample.id,
            "code": sample.sample_code,
            "warn": _is_warn(sample.particle_count, threshold),
            "image_url": "/" + sample.image_path.lstrip("/"),
            "image_available": image_available,
            "image_width": sample.image_width or 640,
            "image_height": sample.image_height or 480,
            "dim_label": f"{sample.image_width}×{sample.image_height} px" if sample.image_width else "",
        },
        "count": total,
        "meta": meta,
        "legend": legend,
        "particles_json": _json_for_script(_overlay_particles(particles)),
        "particle_rows": particle_rows,
        "histogram": _histogram_svg(size_histogram),
        "label_rows": label_rows,
        "raw_json": _pretty_json(sample.raw_metadata_json),
    }
    return templates.TemplateResponse(request, "sample_detail.html", ctx)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
):
    """Admin-only settings page."""
    threshold = get_warn_particle_count(session)
    ctx = {
        "screen": "settings",
        "title": "Cài đặt hệ thống",
        "warn_particle_count": threshold,
    }
    return templates.TemplateResponse(request, "settings.html", ctx)


@router.post("/settings/qc")
def update_qc_settings(
    request: Request,
    warn_particle_count: int = Form(...),
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
):
    """Update QC threshold setting in the database."""
    if warn_particle_count < 0:
        raise HTTPException(status_code=422, detail="warn_particle_count must be >= 0")
    # Find existing or create new setting
    setting = session.exec(
        select(QcSetting).where(QcSetting.key == "warn_particle_count")
    ).first()
    if setting is None:
        setting = QcSetting(
            key="warn_particle_count",
            value=str(warn_particle_count),
            updated_by=admin_user.id
        )
        session.add(setting)
    else:
        setting.value = str(warn_particle_count)
        setting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        setting.updated_by = admin_user.id
        session.add(setting)
    session.commit()
    # Redirect back to settings page
    return RedirectResponse("/settings", status_code=303)


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """View active and historical notifications."""
    # Active/unacknowledged
    active_notices = session.exec(
        select(Notification)
        .where(Notification.acknowledged_at == None)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    ).all()

    # Resolved/acknowledged (joined with User to display who acknowledged it)
    resolved_notices = session.exec(
        select(Notification)
        .where(Notification.acknowledged_at != None)
        .order_by(Notification.acknowledged_at.desc(), Notification.id.desc())
    ).all()

    # Fetch users in resolved notices to avoid query-in-loop
    user_ids = {n.acknowledged_by for n in resolved_notices if n.acknowledged_by is not None}
    users_dict = {}
    if user_ids:
        users = session.exec(select(User).where(User.id.in_(list(user_ids)))).all()
        users_dict = {u.id: u.username for u in users}

    active_rows = [
        {
            "id": n.id,
            "lot": n.batch_lot or "—",
            "message": n.message,
            "time": _fmt_dt(n.created_at),
            "sample_id": n.sample_id,
        }
        for n in active_notices
    ]

    resolved_rows = [
        {
            "id": n.id,
            "lot": n.batch_lot or "—",
            "message": n.message,
            "time": _fmt_dt(n.created_at),
            "sample_id": n.sample_id,
            "ack_by": users_dict.get(n.acknowledged_by, "—"),
            "ack_at": _fmt_dt(n.acknowledged_at) if n.acknowledged_at else "—",
            "ack_note": n.acknowledgement_note or "",
        }
        for n in resolved_notices
    ]

    ctx = {
        "screen": "notifications",
        "title": "Cảnh báo",
        "active": active_rows,
        "resolved": resolved_rows,
    }
    return templates.TemplateResponse(request, "notifications.html", ctx)


@router.post("/notifications/{id}/ack")
def acknowledge_notification(
    id: int,
    request: Request,
    note: str = Form("", max_length=500),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as acknowledged."""
    notice = session.get(Notification, id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notice.acknowledged_at is None:
        notice.acknowledged_at = datetime.now(timezone.utc).replace(tzinfo=None)
        notice.acknowledged_by = current_user.id
        notice.acknowledgement_note = note.strip() or None
        session.add(notice)
        session.commit()
    
    # Redirect back to request's referrer (often dashboard or /notifications)
    referrer = _safe_local_redirect(request.headers.get("referer"), request)
    return RedirectResponse(referrer, status_code=303)


@router.get("/stream", response_class=HTMLResponse)
def stream(request: Request):
    # Pure-frontend demo — no DB access, no new endpoint (frontend design §2.4).
    return templates.TemplateResponse(
        request, "stream.html", {"screen": "stream", "title": "Stream demo"}
    )


def _safe_local_redirect(referrer: Optional[str], request: Request) -> str:
    """Return an internal redirect target; reject external/malformed referrers."""
    if not referrer:
        return "/notifications"
    from urllib.parse import urlsplit

    parts = urlsplit(referrer)
    if parts.netloc:
        request_netloc = request.url.netloc
        if parts.scheme in {"http", "https"} and parts.netloc == request_netloc:
            target = parts.path or "/"
            return target + (f"?{parts.query}" if parts.query else "")
        return "/notifications"
    if parts.path.startswith("/") and not parts.path.startswith("//"):
        return parts.path + (f"?{parts.query}" if parts.query else "")
    return "/notifications"


# --- small helpers --------------------------------------------------------


def _parse_local_day(value: Optional[str], end: bool) -> Optional[datetime]:
    """`yyyy-mm-dd` (local) → local-aware datetime at day start/end, or None."""
    if not value:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return None
    t = time(23, 59, 59) if end else time(0, 0, 0)
    return datetime.combine(d, t).astimezone()


def _query_string(params: dict) -> str:
    """Build a `?a=b&...` string from non-empty params (values are escaped)."""
    from urllib.parse import urlencode

    clean = {k: v for k, v in params.items() if v not in (None, "")}
    return ("?" + urlencode(clean)) if clean else ""


def _pretty_json(raw: str) -> str:
    try:
        return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return raw
