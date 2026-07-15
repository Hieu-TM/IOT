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

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

from .. import config
from ..database import get_session
from ..models import Particle, Sample
from .samples import BIN_WIDTH_MM, _apply_filters, _build_histogram

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(config.APP_DIR / "templates"))

# --- Label vocabulary (single source, mirrors static/css + static/js) ---
LABEL_ORDER = ["plastic", "bubble", "organic", "fiber", "unknown"]
LABEL_VI = {
    "plastic": "Nhựa",
    "bubble": "Bọt khí",
    "organic": "Hữu cơ",
    "fiber": "Sợi",
    "unknown": "Không xác định",
}

HISTORY_PAGE_SIZE = 10


def _label_vi(label: str) -> str:
    return LABEL_VI.get(label, label)


def _label_color(label: str) -> str:
    """CSS custom-property reference for a label's color (unknown for strays)."""
    return f"var(--p-{label})" if label in LABEL_VI else "var(--p-unknown)"


def _is_warn(particle_count: int) -> bool:
    return particle_count > config.WARN_PARTICLE_COUNT


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
    chips = []
    for label in LABEL_ORDER:
        if dist.get(label):
            chips.append(
                {"vi": _label_vi(label), "color": _label_color(label), "count": dist[label]}
            )
    # Any classifier label outside the canonical order still shows up.
    for label, count in dist.items():
        if label not in LABEL_ORDER and count:
            chips.append(
                {"vi": _label_vi(label), "color": _label_color(label), "count": count}
            )
    return chips


# --- pages ----------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    today = datetime.now().astimezone().date()

    all_samples = session.exec(
        select(Sample).order_by(Sample.captured_at.desc(), Sample.id.desc())
    ).all()

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
    plastic_count = today_dist.get("plastic", 0)
    plastic_pct = round(plastic_count / today_total * 100) if today_total else 0
    warn_count = sum(1 for s in today_samples if _is_warn(s.particle_count))

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
            "label": "Tỉ lệ nhựa",
            "value": f"{plastic_pct}%",
            "hint": f"{plastic_count} / {today_total} hạt",
            "icon": "plus",
            "value_class": "teal",
            "warn": False,
        },
        {
            "label": "Cảnh báo",
            "value": warn_count,
            "hint": "mẫu có ≥1 hạt" if warn_count else "không có",
            "icon": "warn",
            "value_class": "amber" if warn_count else "",
            "warn": bool(warn_count),
        },
    ]

    donut_entries = [
        {"color": _label_color(l), "count": today_dist[l]}
        for l in LABEL_ORDER
        if today_dist.get(l)
    ]
    donut_legend = [
        {
            "vi": _label_vi(l),
            "color": _label_color(l),
            "pct": f"{round(today_dist[l] / today_total * 100)}%",
        }
        for l in LABEL_ORDER
        if today_dist.get(l)
    ]

    latest = all_samples[0]
    latest_particles = _sample_particles(session, latest.id)

    recent5 = [
        {
            "id": s.id,
            "code": s.sample_code,
            "lot": s.batch_lot or "—",
            "time": _fmt_dt(s.captured_at),
            "count": s.particle_count,
            "warn": _is_warn(s.particle_count),
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
            "warn": _is_warn(latest.particle_count),
            "image_url": "/" + latest.image_path.lstrip("/"),
            "image_width": latest.image_width or 640,
            "image_height": latest.image_height or 480,
            "particles_json": _json_for_script(_overlay_particles(latest_particles)),
        },
        "recent5": recent5,
    }
    return templates.TemplateResponse(request, "index.html", ctx)


@router.get("/history", response_class=HTMLResponse)
def history(
    request: Request,
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    batch_lot: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
):
    # Date inputs are yyyy-mm-dd (local). Turn them into a local-aware
    # [start-of-day, end-of-day] range so _apply_filters converts to UTC.
    from_dt = _parse_local_day(date_from, end=False)
    to_dt = _parse_local_day(date_to, end=True)
    lot = batch_lot or None

    total = session.exec(
        _apply_filters(select(func.count(Sample.id)), lot, from_dt, to_dt)
    ).one()
    total_pages = max(1, math.ceil(total / HISTORY_PAGE_SIZE))
    page = min(page, total_pages)

    samples = session.exec(
        _apply_filters(select(Sample), lot, from_dt, to_dt)
        .order_by(Sample.captured_at.desc(), Sample.id.desc())
        .offset((page - 1) * HISTORY_PAGE_SIZE)
        .limit(HISTORY_PAGE_SIZE)
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
            "warn": _is_warn(s.particle_count),
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
    export_qs = _query_string({"batch_lot": lot, "from": date_from, "to": date_to})

    ctx = {
        "screen": "history",
        "title": "Lịch sử · audit",
        "filters": {"from": date_from or "", "to": date_to or "", "lot": lot or ""},
        "lot_options": lot_values,
        "rows": page_rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "summary": f"{total} mẫu khớp bộ lọc · trang {page}/{total_pages}",
        "export_qs": export_qs,
        "prev_qs": _query_string(
            {"batch_lot": lot, "from": date_from, "to": date_to, "page": page - 1}
        ),
        "next_qs": _query_string(
            {"batch_lot": lot, "from": date_from, "to": date_to, "page": page + 1}
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
    dist = _label_distribution(particles)
    total = len(particles)
    size_histogram = _build_histogram(particles)

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

    label_rows = [
        {
            "vi": _label_vi(l),
            "color": _label_color(l),
            "count": dist[l],
            "pct": f"{round(dist[l] / total * 100)}%" if total else "0%",
        }
        for l in LABEL_ORDER
        if dist.get(l)
    ]
    legend = [
        {"vi": _label_vi(l), "color": _label_color(l)}
        for l in LABEL_ORDER
        if dist.get(l)
    ]

    ctx = {
        "screen": "detail",
        "title": "Chi tiết mẫu",
        "notfound": False,
        "sample": {
            "id": sample.id,
            "code": sample.sample_code,
            "warn": _is_warn(sample.particle_count),
            "image_url": "/" + sample.image_path.lstrip("/"),
            "image_width": sample.image_width or 640,
            "image_height": sample.image_height or 480,
            "dim_label": f"{sample.image_width}×{sample.image_height} px"
            if sample.image_width
            else "",
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


@router.get("/stream", response_class=HTMLResponse)
def stream(request: Request):
    # Pure-frontend demo — no DB access, no new endpoint (frontend design §2.4).
    return templates.TemplateResponse(
        request, "stream.html", {"screen": "stream", "title": "Stream demo"}
    )


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
