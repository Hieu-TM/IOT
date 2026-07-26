"""The capture/inference worker that drives one measurement per pump cycle.

Why this lives inside the web app instead of staying a CLI: the operator needs
Start/Stop buttons and a live view, and a second process controlled from a
second terminal is exactly the friction this replaces.

Two deliberate shapes here:

  * `tick()` is ONE poll iteration and does no sleeping. The thread (start/stop)
    is a thin wrapper around it. The state machine is the part that is easy to
    get wrong - capture four times per pump cycle, or never - so it is testable
    on its own with a fake clock.
  * results are POSTed back into this app's own /api/ingest rather than written
    to the DB directly. Ingest already owns validation, sample_code generation,
    idempotency and the atomic image+rows write; duplicating that here would
    mean every future fix has to land in two places, and the audit trail is the
    one thing that must not drift.
"""

import copy
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _ensure_repo_on_path():
    """Put the repo root on sys.path so `import ml.infer...` works.

    The backend normally runs with cwd=web/backend, where `ml` is not
    importable. start.bat launches uvicorn from the repo root so both paths
    resolve, but the tests (and anyone starting the server their own way) do
    not - so fix it here rather than making the import order depend on how the
    process was launched.
    """
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_on_path()

from ml.infer.mapper import build_metadata          # noqa: E402
from ml.infer.naming import unique_station_sample_code  # noqa: E402

POLL_INTERVAL_S = 0.5
# ~5s of silence at the default poll interval. Long enough to ride out a WiFi
# hiccup, short enough that a dead board is reported instead of spun on.
MAX_CONSECUTIVE_ERRORS = 10
SETTLING = "SETTLING"


class RunnerBusy(RuntimeError):
    """Start requested while a run is already in progress."""


class RunnerConfigError(RuntimeError):
    """The runner cannot start: missing host, unusable detector config, ..."""


@dataclass
class RunnerConfig:
    mode: str                 # "preview" | "measure"
    station_host: str
    capture_delay_s: float
    px_per_mm: float
    batch_lot: Optional[str]
    api_url: str
    device_id_override: Optional[str] = None


def _utcnow():
    return datetime.now(timezone.utc)


class Runner:
    def __init__(self, *, station_factory, detector_factory, poster,
                 monotonic=time.monotonic, utcnow=_utcnow):
        self._station_factory = station_factory
        self._detector_factory = detector_factory
        self._poster = poster
        self._monotonic = monotonic
        self._utcnow = utcnow

        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = None

        self._station = None
        self._detector = None
        self._cfg = None
        self._reset_state()

    # --- lifecycle (thread-free half) ------------------------------------

    def _reset_state(self):
        self._running = False
        self._device = None
        self._prev_phase = None
        self._pending_capture_at = None
        self._consecutive_errors = 0
        self._error = None
        self._warnings = []
        self._counters = {"cycles": 0, "captured": 0, "written": 0, "failed": 0}
        self._last = None
        self._used_codes = set()
        self._preview_jpeg = None
        self._preview_metadata = None

    def arm(self, cfg):
        """Build the station + detector and mark the runner live.

        Separate from start() so the state machine can be exercised without a
        thread. start() (below) is arm() + a thread that calls tick().
        """
        if self._running:
            raise RunnerBusy("runner đang chạy rồi.")
        if not cfg.station_host:
            raise RunnerConfigError(
                "chưa có địa chỉ board. Nhập IP hoặc bấm Dò trên dashboard.")
        self._reset_state()
        self._cfg = cfg
        self._station = self._station_factory(cfg.station_host)
        self._detector = self._detector_factory()
        self._running = True

    def disarm(self):
        self._running = False

    # --- one poll iteration ----------------------------------------------

    def tick(self):
        try:
            device = self._station.read_device()
        except Exception as exc:       # noqa: BLE001 - any board failure is the same here
            self._consecutive_errors += 1
            self._error = f"không đọc được /device: {exc}"
            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self._running = False
                self._error = (
                    f"đã dừng: {MAX_CONSECUTIVE_ERRORS} lần liên tiếp không đọc "
                    f"được /device ({exc}). Kiểm tra board còn điện và còn trong mạng.")
            return

        self._consecutive_errors = 0
        self._error = None
        self._device = device
        self._warnings = self._compute_warnings(device)

        phase = (device.get("pump") or {}).get("phase")
        # CẠNH, không phải trạng thái: pha SETTLING kéo dài nhiều lần poll, bắt
        # trạng thái sẽ chụp nhiều lần cho cùng một lần lấy nước.
        if phase == SETTLING and self._prev_phase != SETTLING:
            self._counters["cycles"] += 1
            self._pending_capture_at = self._monotonic() + self._cfg.capture_delay_s
        self._prev_phase = phase

        if (self._pending_capture_at is not None
                and self._monotonic() >= self._pending_capture_at):
            self._pending_capture_at = None
            self._capture_and_process(device)

    def _capture_and_process(self, device):
        try:
            jpeg = self._station.capture_once()
        except Exception as exc:       # noqa: BLE001
            self._counters["failed"] += 1
            self._error = f"chụp hỏng: {exc}"
            return
        self._counters["captured"] += 1

        try:
            result = self._detector.run(jpeg)
        except Exception as exc:       # noqa: BLE001
            self._counters["failed"] += 1
            self._error = f"suy luận hỏng: {exc}"
            return

        captured_at = self._utcnow()
        code = unique_station_sample_code(captured_at, self._used_codes)
        metadata = build_metadata(
            detections=result.detections,
            image_width=result.image_width,
            image_height=result.image_height,
            sample_code=code,
            captured_at=captured_at,
            device_id=self._resolve_device_id(device),
            px_per_mm=self._cfg.px_per_mm,
            batch_lot=self._cfg.batch_lot,
            device_info=device,
        )

        if self._cfg.mode == "measure":
            written = self._post(metadata, jpeg, code)
        else:
            # Preview: hold in RAM for the browser to view, don't touch disk.
            self._preview_jpeg = jpeg
            self._preview_metadata = metadata
            written = False

        self._last = {
            "sample_code": code,
            "particle_count": len(metadata["particles"]),
            "labels": _label_counts(metadata["particles"]),
            "at": captured_at.isoformat(),
            "written": written,
        }

    def _post(self, metadata, jpeg, code):
        res = self._poster(self._cfg.api_url, metadata, jpeg, f"{code}.jpg")
        if res.status in ("created", "already_exists"):
            self._counters["written"] += 1
            return True
        self._counters["failed"] += 1
        self._error = f"ghi sổ hỏng ({res.http_status}): {res.detail}"
        return False

    def _resolve_device_id(self, device):
        """The board's self-reported name beats the config constant; the manual override flag beats both."""
        if self._cfg.device_id_override:
            return self._cfg.device_id_override
        board_id = device.get("device_id")
        return board_id if isinstance(board_id, str) and board_id else "pc-infer"

    def _compute_warnings(self, device):
        out = []
        pump = device.get("pump") or {}
        cam = device.get("camera") or {}

        if pump.get("auto") is False:
            out.append("Bơm chưa ở chế độ auto — sẽ không có khung nào được chụp.")
        if pump.get("pwm_ready") is False:
            out.append("Bơm báo pwm_ready=false — firmware không gắn được PWM, "
                       "bơm sẽ không chạy.")
        if cam.get("aec") or cam.get("agc"):
            out.append("AEC/AGC đang bật — nền sẽ cháy trắng và nuốt mất hạt. "
                       "Bấm 'Canh sáng buồng tối' trước khi đo.")
        settle_ms = pump.get("settle_ms")
        delay_ms = int(self._cfg.capture_delay_s * 1000)
        if isinstance(settle_ms, int) and delay_ms >= settle_ms:
            out.append(f"Độ trễ chụp ({delay_ms}ms) ≥ thời gian lắng ({settle_ms}ms) "
                       "— khung sẽ rơi sang pha FLUSHING lúc nước đang chảy.")
        return out

    # --- preview ----------------------------------------------------------

    def preview_jpeg(self):
        return self._preview_jpeg

    def keep(self):
        """Write the held preview frame to the audit trail (the "Keep this sample" dashboard button)."""
        if self._preview_metadata is None or self._preview_jpeg is None:
            raise RuntimeError("chưa có khung nào để lưu.")
        metadata = self._preview_metadata
        code = metadata["sample_code"]
        written = self._post(metadata, self._preview_jpeg, code)
        if self._last is not None and self._last["sample_code"] == code:
            self._last["written"] = written
        return {"sample_code": code, "written": written}

    # --- read model -------------------------------------------------------

    def snapshot(self):
        """A deep copy: HTTP handlers read this while the worker writes."""
        return copy.deepcopy({
            "running": self._running,
            "mode": self._cfg.mode if self._cfg else None,
            "station_host": self._cfg.station_host if self._cfg else "",
            "device": self._device,
            "phase": self._prev_phase,
            "counters": self._counters,
            "last": self._last,
            "error": self._error,
            "warnings": self._warnings,
            "has_preview": self._preview_jpeg is not None,
        })


def _label_counts(particles):
    counts = {}
    for p in particles:
        counts[p["label"]] = counts.get(p["label"], 0) + 1
    return counts
