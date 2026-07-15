"""FastAPI application entry point + wiring (Module 6, web_plan.md §9).

Creates the app, ensures the DB + tables exist at startup, wires the three
routers (ingest / samples read API / server-rendered pages) and mounts the two
static trees:

  /static  → app/static           (css/js assets, committed)
  /images  → data/images          (captured JPEGs, runtime, git-ignored)

Append-only is enforced at the routing layer: none of the wired routers expose
a PUT/PATCH/DELETE path (§2.2).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .database import create_db_and_tables
from .routers import ingest, pages, samples


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create data/aqua_scope.db + data/images/ and both tables before serving.
    create_db_and_tables()
    yield


app = FastAPI(title="Aqua Scope Traceability API", lifespan=lifespan)

# API routers (both already carry their own /api prefix).
app.include_router(ingest.router)
app.include_router(samples.router)
# Server-rendered dashboard pages (/, /history, /samples/{id}, /stream).
app.include_router(pages.router)

# Static assets. app/static is committed; data/images is created at startup by
# create_db_and_tables(), so it always exists by the time this mount is hit.
app.mount("/static", StaticFiles(directory=config.APP_DIR / "static"), name="static")
app.mount("/images", StaticFiles(directory=config.IMAGES_DIR), name="images")
