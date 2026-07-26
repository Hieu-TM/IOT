"""Central configuration for the Aqua Scope backend.

Single source of paths + constants shared across modules. Everything else
(routers, database, mock sender integration) imports from here so there is
exactly one place that decides where the DB / images live and what the
domain constants are (§4 web_plan.md).
"""

import os
from pathlib import Path

# --- Paths --------------------------------------------------------------
# This file lives at web/backend/app/config.py
APP_DIR = Path(__file__).resolve().parent          # web/backend/app
BACKEND_DIR = APP_DIR.parent                        # web/backend
DATA_DIR = BACKEND_DIR / "data"                     # web/backend/data (runtime, git-ignored)
IMAGES_DIR = DATA_DIR / "images"                    # captured JPEGs
# Production data is stored in SQL Server. Connection uses SQL Server
# Authentication so any teammate can run the app after setting env vars.
# Override AQUA_SCOPE_DATABASE_URL for a completely custom connection string.
_DB_USER = os.getenv("AQUA_SCOPE_DB_USER", "sa")
_DB_PASSWORD = os.getenv("AQUA_SCOPE_DB_PASSWORD", "")
DATABASE_URL = os.getenv(
    "AQUA_SCOPE_DATABASE_URL",
    f"mssql+pyodbc://{_DB_USER}:{_DB_PASSWORD}@localhost\\SQLEXPRESS/AquaScope"
    f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes",
)
SQLITE_SOURCE_PATH = Path(
    os.getenv("AQUA_SCOPE_SQLITE_SOURCE", BACKEND_DIR / "data" / "aqua_scope.db")
)

# Authentication secrets are configured at deployment. A temporary fallback is
# intentionally not provided: restarting with a random key would silently log
# everyone out and a checked-in key would compromise every installation.
SESSION_SECRET = os.getenv("AQUA_SCOPE_SESSION_SECRET", "")
ADMIN_USERNAME = os.getenv("AQUA_SCOPE_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("AQUA_SCOPE_ADMIN_PASSWORD", "")
COOKIE_SECURE = os.getenv("AQUA_SCOPE_COOKIE_SECURE", "false").lower() == "true"
INGEST_TOKEN = os.getenv("AQUA_SCOPE_INGEST_TOKEN", "")

# --- Domain constants ---------------------------------------------------
# Default calibration (~14 px/mm at VGA, ~40mm working distance — CLAUDE.md).
PX_PER_MM_DEFAULT = 14.0

# The deployed detector's classes. All four are microplastic MORPHOLOGIES - the model
# has no non-plastic class, so it cannot distinguish plastic from bubbles/organics.
CLASS_LIST = ["fiber", "film", "fragment", "pallet", "unknown"]

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

# Time window in minutes within which a device is considered "online"
DEVICE_ONLINE_WINDOW_MINUTES = 10
