"""Runner + station control endpoints (spec 2026-07-26 §5).

These are the first POST routes outside /api/ingest. They do NOT mutate stored
samples — append-only still holds for the audit data; what they mutate is
runtime state (a worker thread, an operational settings file) and the board's
own camera/pump settings.

`/api/station/control` deliberately does NOT take a host from the request: it
always targets the configured station. Otherwise it would be a general-purpose
"make the server fetch this URL" tool for anyone on the LAN. The `var`
allowlist exists for the same reason at the parameter level.

`/api/station/probe` DOES take a host from the request and has the server
fetch it — that property is not avoided here, only narrowed: HOST_RE (the
same rule settings_store uses for station_host) constrains the request to
`http://<host[:port]>/device`, so a caller on the LAN can steer the server's
probe at an arbitrary LAN/internet host of their choosing but cannot inject a
different scheme, path, or query. Acceptable for this LAN threat model; do not
read this as "the server never fetches attacker-influenced URLs".
"""

import re

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .. import settings_store
from ..runner import (RunnerBusy, RunnerConfigError, build_config_from_settings,
                      get_runner)

router = APIRouter(prefix="/api", tags=["control"])

# Every var the dashboard needs, and nothing else. Adding one here is a
# deliberate act — see the module docstring.
CONTROL_VARS = frozenset({
    "darkmode", "save", "reset", "device_id",
    "pump_auto", "pump_fill_ms", "pump_settle_ms", "pump_flush_ms",
    "pump_cooldown_ms", "pump_fill_duty", "pump_flush_duty",
    "pump_ramp_up_ms", "pump_ramp_down_ms",
})

# Board's own device_id rule (firmware README): [A-Za-z0-9._-], 1–64 chars.
# Also blocks `&`/`?`, which would smuggle a second var into the query string.
_VAL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Same host rule as the settings store — a probe host that settings_store would
# reject must not sneak in through the query string instead.
HOST_RE = settings_store.HOST_RE


class StartBody(BaseModel):
    mode: str = Field(pattern="^(preview|measure)$")


class ControlBody(BaseModel):
    var: str
    val: str


class SettingsBody(BaseModel):
    station_host: str | None = None
    mode: str | None = None
    batch_lot: str | None = None
    capture_delay_ms: int | None = None
    px_per_mm: float | None = None
    # Distinguishing "not sent" from "sent as null" matters for batch_lot and
    # px_per_mm, both of which are legitimately clearable.
    model_config = {"extra": "forbid"}


# --- runner ---------------------------------------------------------------


@router.get("/runner/status")
def runner_status(runner=Depends(get_runner)):
    return runner.snapshot()


@router.post("/runner/start")
def runner_start(body: StartBody, runner=Depends(get_runner)):
    cfg = build_config_from_settings(mode=body.mode)
    try:
        runner.start(cfg)
    except RunnerBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RunnerConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Remember the choice so the dashboard pre-selects it next time.
    settings_store.save({"mode": body.mode})
    return runner.snapshot()


@router.post("/runner/stop")
def runner_stop(runner=Depends(get_runner)):
    runner.stop()
    return runner.snapshot()


@router.get("/runner/preview.jpg")
def runner_preview(runner=Depends(get_runner)):
    jpeg = runner.preview_jpeg()
    if not jpeg:
        raise HTTPException(status_code=404, detail="chưa có khung xem nào.")
    # no-store: the frame changes every pump cycle and must never be cached.
    return Response(content=jpeg, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.post("/runner/keep")
def runner_keep(runner=Depends(get_runner)):
    try:
        return runner.keep()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# --- settings -------------------------------------------------------------


@router.get("/settings")
def settings_get():
    return settings_store.load()


@router.post("/settings")
def settings_post(body: SettingsBody):
    patch = body.model_dump(exclude_unset=True)
    try:
        return settings_store.save(patch)
    except settings_store.SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- station --------------------------------------------------------------


@router.get("/station/probe")
def station_probe(host: str = Query(...)):
    host = host.strip()
    if not HOST_RE.match(host):
        raise HTTPException(
            status_code=400,
            detail=f"host {host!r} không hợp lệ. Nhập IP hoặc tên máy, không "
                   "kèm http:// hay đường dẫn.")
    try:
        return _probe_host(host)
    except Exception as exc:       # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"không tới được board: {exc}")


@router.post("/station/control")
def station_control(body: ControlBody):
    if body.var not in CONTROL_VARS:
        raise HTTPException(
            status_code=400,
            detail=f"tham số {body.var!r} không nằm trong danh sách cho phép.")
    if not _VAL_RE.match(body.val):
        raise HTTPException(
            status_code=422,
            detail="giá trị chỉ được chứa chữ, số và . _ - (1–64 ký tự).")

    host = settings_store.load()["station_host"]
    if not host:
        raise HTTPException(
            status_code=400,
            detail="chưa có địa chỉ board. Nhập IP hoặc bấm Dò trước.")

    url = f"http://{host}/control?var={body.var}&val={body.val}"
    try:
        text = _board_get(url)
    except Exception as exc:       # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"board không nhận lệnh: {exc}")
    return JSONResponse({"ok": True, "var": body.var, "val": body.val,
                         "board_response": text})


# --- seams (monkeypatched in tests; the only places that touch the network) --


def _board_get(url, timeout=5):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text[:200]


def _probe_host(host):
    from ml.infer.station import StationClient

    return StationClient(host, timeout_s=5, retries=1).read_device()
