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

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import Session, select

from . import config
from .auth import get_current_user, hash_password, router as auth_router
from .database import create_db_and_tables, engine
from .models import User
from .routers import control, ingest, pages, samples


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SESSION_SECRET:
        raise RuntimeError("AQUA_SCOPE_SESSION_SECRET must be configured")
    create_db_and_tables()
    with Session(engine) as session:
        admin = session.exec(
            select(User).where(User.username == config.ADMIN_USERNAME)
        ).first()
        if admin is None:
            if not config.ADMIN_PASSWORD:
                raise RuntimeError(
                    "AQUA_SCOPE_ADMIN_PASSWORD is required to create the first administrator"
                )
            session.add(
                User(
                    username=config.ADMIN_USERNAME,
                    password_hash=hash_password(config.ADMIN_PASSWORD),
                    role="admin",
                )
            )
            session.commit()
    yield
    # Stop the capture worker on shutdown; with --reload the process is
    # replaced repeatedly and an orphaned thread would keep polling the board.
    from .runner import RUNNER

    RUNNER.stop()


app = FastAPI(title="Aqua Scope Traceability API", lifespan=lifespan)


@app.middleware("http")
async def load_authenticated_user(request: Request, call_next):
    # The station remains a machine-to-machine client of the legacy ingest
    # contract; browser access to its stored data is session-protected.
    public_paths = ("/login", "/api/ingest", "/static", "/docs", "/openapi.json")
    if request.url.path.startswith(public_paths):
        return await call_next(request)

    user_id = request.session.get("user_id")
    if user_id is None:
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            return RedirectResponse("/login", status_code=303)
        return JSONResponse(status_code=401, content={"detail": "authentication required"})

    with Session(engine) as session:
        user = session.get(User, user_id)
    if user is None:
        request.session.clear()
        return JSONResponse(status_code=401, content={"detail": "authentication required"})
    request.state.user = user
    return await call_next(request)


# Add this after the function middleware so SessionMiddleware is the outer
# layer and request.session is available to the authentication middleware.
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET or "startup-validation-will-reject-this",
    same_site="lax",
    https_only=config.COOKIE_SECURE,
)

# API routers (both already carry their own /api prefix).
app.include_router(auth_router)
app.include_router(ingest.router)
app.include_router(samples.router, dependencies=[Depends(get_current_user)])
app.include_router(control.router)
# Server-rendered dashboard pages (/, /history, /samples/{id}, /stream).
app.include_router(pages.router, dependencies=[Depends(get_current_user)])

# Static assets. app/static is committed. StaticFiles validates its directory
# at import time, before lifespan can run, so ensure the runtime images folder
# exists here as well as in create_db_and_tables().
config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=config.APP_DIR / "static"), name="static")
config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=config.IMAGES_DIR), name="images")
