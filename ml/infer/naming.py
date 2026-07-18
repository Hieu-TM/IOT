"""Pure helpers shared across the inference package (no I/O, no heavy deps)."""

import re
from pathlib import Path

# Mirror of web/backend/app/config.py PX_PER_MM_DEFAULT. Duplicated (not
# imported) to keep ml/ decoupled from the web package's import path. Keep in
# sync if the web default changes.
DEFAULT_PX_PER_MM = 14.0

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def sample_code_from_filename(filename: str) -> str:
    """Derive a filename-safe sample_code from an image filename.

    The web ingest contract requires sample_code to match
    ^[A-Za-z0-9._-]{1,64}$ (web/backend/app/models.py SAMPLE_CODE_PATTERN),
    because the server uses it verbatim as an image filename. Deriving a stable
    code from the source filename makes re-running the same folder idempotent
    (server returns already_exists instead of duplicating the sample).
    """
    stem = Path(filename).stem
    safe = _UNSAFE.sub("-", stem).strip("-") or "sample"
    return safe[:64]


def resolve_px_per_mm(value):
    """Return (px_per_mm, used_default).

    When the caller passes None, or a non-positive value (0 or negative - not a
    physically valid scale), fall back to DEFAULT_PX_PER_MM and flag it so the
    CLI can warn that size_mm is a placeholder, not a real calibration. A silent
    0.0 would otherwise flow straight into every particle's size_mm.
    """
    if value is None or float(value) <= 0:
        return DEFAULT_PX_PER_MM, True
    return float(value), False
