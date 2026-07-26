"""FastAPI application entry point + wiring (Module 6, web_plan.md §9).

Creates the app, ensures the DB + tables exist at startup, wires the three
routers (ingest / samples read API / server-rendered pages) and mounts the two
static trees:

  /static  → app/static           (css/js assets, committed)
  /images  → data/images          (captured JPEGs, runtime, git-ignored)

Append-only applies to the SAMPLE DATA: no route anywhere exposes PUT/PATCH/
DELETE, so a stored sample can never be edited or removed. The control router
does add POST routes (start/stop the capture worker, write operational
settings, forward a command to the board) — those mutate runtime state and the
board's own config, never a stored row (spec 2026-07-26 §5.1).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .database import create_db_and_tables
from .routers import control, ingest, pages, samples


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create data/aqua_scope.db + data/images/ and both tables before serving.
    create_db_and_tables()
    yield
    # Stop the capture worker on shutdown; with --reload the process is
    # replaced repeatedly and an orphaned thread would keep polling the board.
    from .runner import RUNNER

    RUNNER.stop()


app = FastAPI(title="Aqua Scope Traceability API", lifespan=lifespan)

# API routers (both already carry their own /api prefix).
app.include_router(ingest.router)
app.include_router(samples.router)
app.include_router(control.router)
# Server-rendered dashboard pages (/, /history, /samples/{id}, /stream).
app.include_router(pages.router)

# Static assets. app/static is committed. StaticFiles validates its directory
# at import time, before lifespan can run, so ensure the runtime images folder
# exists here as well as in create_db_and_tables().
config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=config.APP_DIR / "static"), name="static")
app.mount("/images", StaticFiles(directory=config.IMAGES_DIR), name="images")
