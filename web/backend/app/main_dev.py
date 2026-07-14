"""
main_dev.py — điểm chạy ĐỘC LẬP cho Module 5 (frontend only).

Mục đích: dựng & kiểm tra UI dựa trên fixture JSON, KHÔNG cần Module 1/2/3/6
(plan §9: Module 5 không phụ thuộc backend thật). Mount:
  /static  ← app/static     (css, js, js/vendor, fixtures)
  /images  ← app/static/images  (ảnh mẫu — để fixture /images/... resolve đúng)
Include router pages (/, /history, /samples/{id}).

Chạy từ backend/:   uvicorn app.main_dev:app --reload --port 8000

NOTE: file này sẽ bị thay/supersede bởi app/main.py khi Module 6 ráp router thật.
Chỉ giữ làm cách dev nhanh cho UI.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import pages

_APP_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _APP_DIR / "static"
_IMAGES_DIR = _STATIC_DIR / "images"          # fixture ảnh nằm trong static/images

app = FastAPI(title="Aqua Scope · Module 5 (dev)", version="0.5-dev")

# /static → css/js/vendor/fixtures ; /images → ảnh mẫu
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.mount("/images", StaticFiles(directory=str(_IMAGES_DIR)),
          name="images")
app.include_router(pages.router)
