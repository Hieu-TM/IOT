"""Central configuration for the Aqua Scope backend.

Single source of paths + constants shared across modules. Everything else
(routers, database, mock sender integration) imports from here so there is
exactly one place that decides where the DB / images live and what the
domain constants are (§4 web_plan.md).
"""

from pathlib import Path

# --- Paths --------------------------------------------------------------
# This file lives at web/backend/app/config.py
APP_DIR = Path(__file__).resolve().parent          # web/backend/app
BACKEND_DIR = APP_DIR.parent                        # web/backend
DATA_DIR = BACKEND_DIR / "data"                     # web/backend/data (runtime, git-ignored)
IMAGES_DIR = DATA_DIR / "images"                    # captured JPEGs
DB_PATH = DATA_DIR / "aqua_scope.db"                # SQLite file

# SQLite URL for SQLModel/SQLAlchemy engine.
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# --- Domain constants ---------------------------------------------------
# Default calibration (~14 px/mm at VGA, ~40mm working distance — CLAUDE.md).
PX_PER_MM_DEFAULT = 14.0

# Provisional class list from ai_model_plan.md — NOT enforced as a DB enum
# so the list can change without a schema migration (§2.1, §3, §10).
CLASS_LIST = ["plastic", "bubble", "organic", "fiber", "unknown"]

# Below this confidence the device/mock relabels a particle as "unknown"
# (backend only stores the final label — §2.1).
CONFIDENCE_THRESHOLD = 0.5

# QC warning threshold (frontend design §1.4): a sample shows the amber
# "Cảnh báo" status when particle_count > this value. Default 0 → any detected
# particle is a warning (the agreed default when no QC criterion is fixed yet,
# frontend-design §8). One place to change, never hard-coded in a template.
WARN_PARTICLE_COUNT = 0

# SEC-3 (SPEC §6): reject uploads above this size (413) before buffering the
# whole body into RAM.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MiB
