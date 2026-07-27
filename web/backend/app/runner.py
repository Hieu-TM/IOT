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


def _repo_root():
    """The one place this file derives where the repo root is.

    Everything that needs a repo-root-relative path (sys.path, ml/config.toml,
    a relative local.weights) must call this instead of re-deriving it, so
    there is exactly one definition to keep correct.
    """
    return Path(__file__).resolve().parents[3]


def _ensure_repo_on_path():
    """Put the repo root on sys.path so `import ml.infer...` works.

    The backend normally runs with cwd=web/backend, where `ml` is not
    importable. start.bat launches uvicorn from the repo root so both paths
    resolve, but the tests (and anyone starting the server their own way) do
    not - so fix it here rather than making the import order depend on how the
    process was launched.
    """
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_on_path()

from ml.infer.mapper import build_metadata          # noqa: E402
from ml.infer.naming import unique_station_sample_code  # noqa: E402

POLL_INTERVAL_S = 0.5
# default_station_factory gives StationClient timeout_s=8, retries=2, so one
# read_device()/capture_once() call has a worst case of
# 2 * 8s + one CAPTURE_RETRY_BACKOFF_S (0.3s) backoff ~= 16.3s. At the default
# poll interval, 10 consecutive failures is therefore up to
# ~10 * 16.3s = 163s of silence before a dead board is reported - not the ~5s
# this comment used to claim (true only before the station client grew
# timeout_s=8, retries=2). Kept at 10 anyway: a WiFi hiccup that outlasts a
# couple of retries can still outlast several ticks, and reporting "dead"
# too eagerly is worse than waiting a few minutes for a truly dead board.
MAX_CONSECUTIVE_ERRORS = 10
SETTLING = "SETTLING"

# Ceiling for stop()'s thread.join(), not a typical wait — the loop spends
# almost all its time in stop_event.wait(), where the join returns within
# milliseconds of the event being set. This only gets exercised when the
# worker is blocked inside tick() at the moment Stop is pressed, and a single
# tick() can serially perform: read_device() (<=16.3s, see
# MAX_CONSECUTIVE_ERRORS above) + capture_once() (<=16.3s) +
# detector.run() (local CPU, treated as ~0) + _post(), which calls
# ml/infer/ingest_client.post(..., timeout=30) by default. Worst case for one
# tick is therefore ~16.3 + 16.3 + 30 = ~62.6s - not the
# "2 * 8s + 0.3s ≈ 16.3s for one station call" this used to claim, which
# ignored _post() entirely. 70s sits just above that 62.6s worst case, so an
# ordinary Stop issued mid-tick still joins cleanly; it may just take up to
# that long against a station/backend that is slow but alive rather than
# actually hung.
STOP_JOIN_TIMEOUT_S = 70.0


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
        # Published as ONE tuple, rebound in a single statement, never as two
        # separate attributes: rebinding one name is atomic under the GIL, so
        # any HTTP-thread read either sees the previous complete pair or the
        # new complete pair - never a mix of this cycle's metadata with the
        # last cycle's JPEG (or vice versa). Do NOT split this back into
        # `self._preview_jpeg` / `self._preview_metadata` "for clarity" - that
        # reintroduces the exact race keep() was written to avoid: the worker
        # could publish a new frame between two independent reads on the HTTP
        # thread, and keep() would post a mismatched image+metadata pair
        # straight into the append-only audit trail with no way to detect it
        # afterwards.
        self._preview = None

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

    def start(self, cfg, poll_interval_s=POLL_INTERVAL_S):
        """arm() plus a background thread that calls tick() until stop()."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RunnerBusy("runner đang chạy rồi.")
            self.arm(cfg)                       # raises RunnerConfigError if host is missing
            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(self._stop_event, poll_interval_s),
                name="aqua-runner",
                daemon=True,                    # don't keep the process alive on shutdown
            )
            self._thread.start()

    def stop(self, timeout=STOP_JOIN_TIMEOUT_S):
        """Idempotent: calling this while idle is a no-op.

        Only forgets the thread once the join actually confirms it has
        stopped. Clearing the handles before joining would let a station
        call that hangs past the join timeout hide the still-live worker
        from start()'s busy-check (which looks at self._thread) — the next
        Start would then spawn a second thread against the same station,
        and both would mutate the same unlocked counters/audit state.
        """
        with self._lock:
            thread, event = self._thread, self._stop_event
        if event is not None:
            event.set()
        self.disarm()
        if thread is None:
            return
        thread.join(timeout=timeout)
        if thread.is_alive():
            # Still blocked inside a station HTTP call past the join
            # ceiling. Leave the handles in place so a retried start() still
            # sees this worker as alive instead of doubling it up.
            self._error = (
                f"chưa dừng được worker sau {timeout:.0f}s — board có thể "
                "đang treo giữa một lệnh HTTP. Thử bấm Dừng lại.")
            return
        with self._lock:
            # Identity check: a concurrent start() may already have
            # installed a new thread while we were joining the old one.
            if self._thread is thread:
                self._thread = self._stop_event = None

    def _run_loop(self, stop_event, poll_interval_s):
        while not stop_event.is_set():
            try:
                self.tick()
            except Exception as exc:   # noqa: BLE001 - last line of defense: tick()
                # already handles its own per-cycle failures, so anything that
                # reaches here is a bug. Record it and keep the thread alive
                # rather than dying silently and leaving the dashboard stuck
                # showing "running" forever.
                self._error = f"lỗi không lường trước trong vòng lặp: {exc}"
            if not self._running:
                # tick() already stopped itself (board died for too long) — exit
                # instead of looping on a station that is no longer usable.
                break
            stop_event.wait(poll_interval_s)

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

        # Hold in RAM for the browser's live view ("Khung vừa chụp") in both modes.
        self._preview = (jpeg, metadata)
        if self._cfg.mode == "measure":
            written = self._post(metadata, jpeg, code)
        else:
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
        frame = self._preview
        return frame[0] if frame is not None else None

    def keep(self):
        """Write the held preview frame to the audit trail (the "Keep this sample" dashboard button).

        Reads `self._preview` exactly once into a local so the jpeg/metadata
        pair posted below is always the pair from a single worker cycle, even
        if the worker publishes a newer frame the instant after this line
        runs.
        """
        frame = self._preview
        if frame is None:
            raise RuntimeError("chưa có khung nào để lưu.")
        jpeg, metadata = frame
        code = metadata["sample_code"]
        written = self._post(metadata, jpeg, code)
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
            "has_preview": self._preview is not None,
        })


def _label_counts(particles):
    counts = {}
    for p in particles:
        counts[p["label"]] = counts.get(p["label"], 0) + 1
    return counts


# --- real wiring -----------------------------------------------------------


def default_station_factory(host):
    from ml.infer.station import StationClient

    # Tighter than StationClient's own defaults (timeout_s=20, retries=3),
    # which suit a one-shot CLI batch run. A worker that must stay
    # responsive to a dashboard Stop button needs a bounded worst case:
    # 2 * 8s + one CAPTURE_RETRY_BACKOFF_S (0.3s) backoff ~= 16.3s per call,
    # which is what STOP_JOIN_TIMEOUT_S is sized against.
    return StationClient(host, timeout_s=8, retries=2)


def default_detector_factory():
    """Build the configured detector, lazily.

    Called on Start, never at import: with backend="local" this pulls
    ultralytics + torch in, which would add tens of seconds to every server
    start even for someone who only wanted to read history.
    """
    from ml.infer import config as ml_config
    from ml.infer.cli import build_detector

    cfg = ml_config.load(_repo_root() / "ml" / "config.toml")
    backend = cfg.get("general", "backend")

    # config.toml documents `local.weights` as repo-root-relative
    # ("ml/models/best.pt"), but ml.infer.config.Config.missing_for() and
    # build_detector() both resolve it against the process's CWD via
    # Path.is_file(). That is correct for the CLI (always invoked from the
    # repo root) but not for this server, which _ensure_repo_on_path()
    # already lets run from any CWD - resolve a relative path against the
    # same repo root before either sees it, so Start doesn't depend on how
    # uvicorn was launched. Leave an absolute path (e.g. an operator-supplied
    # override) untouched. Mutated in place on `cfg` (not just a local
    # variable) so missing_for()'s own weights check below - which re-reads
    # cfg.get("local", "weights") itself - sees the same resolved path
    # instead of independently failing on the original relative one.
    weights = cfg.get("local", "weights")
    if backend == "local" and weights and not Path(weights).is_absolute():
        cfg._data["local"]["weights"] = str(_repo_root() / weights)

    problems = cfg.missing_for(backend)
    if problems:
        raise RunnerConfigError(
            f"backend suy luận {backend!r} chưa chạy được: " + " | ".join(problems))
    try:
        return build_detector(cfg, backend, cfg.get("local", "weights"))
    except Exception as exc:       # noqa: BLE001
        raise RunnerConfigError(
            f"không dựng được backend {backend!r}: {exc}") from exc


def default_poster(api_url, metadata, image_bytes, image_name):
    from ml.infer.ingest_client import post

    return post(api_url, metadata, image_bytes, image_name)


def build_config_from_settings(mode=None):
    """Merge data/settings.json with ml/config.toml per the spec's precedence.

    settings.json wins for station_host / px_per_mm; empty falls back to
    ml/config.toml. `mode` passed by the caller (the start request) always
    wins over the remembered UI default.
    """
    from ml.infer import config as ml_config

    from . import settings_store

    s = settings_store.load()
    ml = ml_config.load(_repo_root() / "ml" / "config.toml")

    host = s["station_host"] or (ml.get("station", "host") or "")
    px = s["px_per_mm"]
    if px is None:
        px = ml.get("calibration", "px_per_mm")
    if px is None or float(px) <= 0:
        # Same honesty rule as the CLI: size_mm is a PLACEHOLDER until a real
        # px/mm is measured on the rig.
        from ml.infer.naming import DEFAULT_PX_PER_MM

        px = DEFAULT_PX_PER_MM

    return RunnerConfig(
        mode=mode or s["mode"],
        station_host=host,
        capture_delay_s=s["capture_delay_ms"] / 1000.0,
        px_per_mm=float(px),
        batch_lot=s["batch_lot"],
        api_url=ml.get("ingest", "api_url") or "http://localhost:8000",
    )


RUNNER = Runner(
    station_factory=default_station_factory,
    detector_factory=default_detector_factory,
    poster=default_poster,
)


def get_runner():
    """Seam for tests: FastAPI dependency override swaps in a fake Runner."""
    return RUNNER
