"""FastAPI application entry point — Module 1 skeleton.

Deliberately minimal (§9): creates the app, ensures the DB + tables exist at
startup, and exposes a trivial root. Routers (ingest/samples/pages) and the
static/images mounts are wired in by Module 6, not here.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create data/aqua_scope.db and both tables before serving requests.
    create_db_and_tables()
    yield


app = FastAPI(title="Aqua Scope Traceability API", lifespan=lifespan)


@app.get("/")
def root():
    """Placeholder root until Module 5/6 mount the dashboard pages."""
    return {
        "service": "aqua-scope-backend",
        "status": "ok",
        "note": "Module 1 skeleton — routers not yet wired (see web_plan.md §9).",
    }
