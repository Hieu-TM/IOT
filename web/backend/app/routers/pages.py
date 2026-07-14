"""
routers/pages.py — Module 5 · Frontend pages (Jinja2 server-rendered)

Phục vụ 3 trang theo web_plan.md §5:
  GET /                → dashboard (mẫu gần nhất + KPI + 5 mẫu gần)
  GET /history         → bảng audit phân trang + filter + nút xuất CSV
  GET /samples/{id}    → chi tiết: ảnh + bbox overlay canvas + 2 chart + bảng hạt + raw JSON

Theo §9, Module 5 KHÔNG phụ thuộc backend thật (Module 1/3) lúc dựng UI — đọc dữ
liệu mẫu tĩnh (fixture JSON) khớp đúng shape §2.2. Khi Module 6 ráp dây, chỉ cần
thay lời gọi fixture bằng query thật tới routers/samples.py; signature hàm giữ nguyên
để template không phải sửa.

Router này dùng Jinja2Templates + StaticFiles DO FASTAPI INSTANCE CHA MOUNT. Để
chạy độc lập verify (chưa cần Module 1/6), chạy:  uvicorn app.main_dev:app --reload
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# ── Paths ──────────────────────────────────────────────────────────────────
# app/ = backend/app → templates/ & static/ nằm ngang hàng
_APP_DIR = Path(__file__).resolve().parent.parent          # .../backend/app
_TEMPLATES_DIR = _APP_DIR / "templates"
_FIXTURES_DIR = _APP_DIR / "static" / "fixtures"

router = APIRouter()
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── Fixture loader (Module 5 stand-in cho Module 3 read API) ────────────────
_FIXTURES_CACHE: dict[str, Any] = {}

def _load_fixture(name: str) -> Any | None:
    if name in _FIXTURES_CACHE:
        return _FIXTURES_CACHE[name]
    path = _FIXTURES_DIR / name
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    _FIXTURES_CACHE[name] = data
    return data


def _samples_list() -> list[dict]:
    """Toàn bộ mẫu từ fixture samples_list.json (list view, không particles)."""
    data = _load_fixture("samples_list.json") or {"items": []}
    return data.get("items", [])


def _sample_detail(sample_id: int) -> dict | None:
    """Chi tiết mẫu từ fixture sample_detail.json."""
    data = _load_fixture("sample_detail.json")
    if not data:
        return None
    if int(data.get("id", -1)) == int(sample_id):
        return data
    return None


# ── Dev compute helpers (khi Module 3 chưa sẵn sàng) ───────────────────────
def _today_str() -> str:
    return date.today().isoformat()


def _captured_date(s: dict) -> str | None:
    raw = s.get("captured_at") or ""
    return raw[:10] if len(raw) >= 10 else None


def _filter_samples(items: list[dict], frm: str | None, to: str | None,
                    batch_lot: str | None) -> list[dict]:
    out = items
    if frm:
        out = [s for s in out if (_captured_date(s) or "") >= frm]
    if to:
        out = [s for s in out if (_captured_date(s) or "") <= to]
    if batch_lot:
        out = [s for s in out if (s.get("batch_lot") or "") == batch_lot]
    return out


# ── Routes ─────────────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    items = _samples_list()
    items_sorted = sorted(items, key=lambda s: s.get("captured_at", ""), reverse=True)
    recent = items_sorted[0] if items_sorted else None
    recent_items = items_sorted[:5]

    today_iso = _today_str()
    samples_today = sum(1 for s in items_sorted if _captured_date(s) == today_iso)
    particles_today = sum(s.get("particle_count", 0) for s in items_sorted
                          if _captured_date(s) == today_iso)

    return templates.TemplateResponse(request, "index.html", {
        "recent_sample": recent,
        "recent_items": recent_items,
        "stats": {
            "samples_today": samples_today,
            "particles_today": particles_today,
            "total_samples": len(items),
        },
    })


@router.get("/history", response_class=HTMLResponse)
async def history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    batch_lot: str | None = None,
):
    items = _samples_list()
    items_sorted = sorted(items, key=lambda s: s.get("captured_at", ""), reverse=True)
    filtered = _filter_samples(items_sorted, from_, to, batch_lot)

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start:start + page_size]

    return templates.TemplateResponse(request, "history.html", {
        "page_data": {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "query": {
            "from": from_ or "",
            "to": to or "",
            "batch_lot": batch_lot or "",
        },
    })


@router.get("/samples/{sample_id}", response_class=HTMLResponse)
async def sample_detail(request: Request, sample_id: int):
    sample = _sample_detail(sample_id)
    if not sample:
        # Khi chưa có backend thật: fixture chỉ có 1 id; báo情形 rõ ràng
        return templates.TemplateResponse(request, "index.html", {
            "recent_sample": None,
            "recent_items": _samples_list()[:5],
            "stats": {"samples_today": 0, "particles_today": 0,
                      "total_samples": len(_samples_list())},
            "error": f"Chưa có dữ liệu chi tiết cho mẫu #{sample_id} (fixture chỉ sẵn sàng #42).",
        }, status_code=404)
    return templates.TemplateResponse(request, "sample_detail.html", {"sample": sample})
