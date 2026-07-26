"""Operational settings the OPERATOR changes from the dashboard.

Deliberately separate from ml/config.toml, which holds what a *developer*
configures (inference backend, API keys, weights). Two files, two audiences,
no overlap — see the spec's §4 precedence table:

  * station_host / px_per_mm : this file wins; empty falls back to ml/config.toml
  * mode                     : the start request wins; this only remembers the
                               last choice so the dashboard pre-selects it

Never raises on a corrupt file: the dashboard must still open so the operator
can fix the bad value from the UI.
"""

import json
import os
import re
import tempfile

from . import config

SETTINGS_PATH = config.DATA_DIR / "settings.json"

DEFAULTS = {
    "station_host": "",        # empty -> fall back to ml/config.toml [station].host
    "mode": "preview",         # remembered UI default, not the runtime authority
    "batch_lot": None,
    "capture_delay_ms": 800,   # after the SETTLING edge, before capturing
    "px_per_mm": None,         # None -> ml/config.toml, then the placeholder default
}

ALLOWED_MODES = ("preview", "measure")
MAX_CAPTURE_DELAY_MS = 60_000

# Host only — no scheme, no path, no query. /api/station/control turns this into
# a URL it calls, so accepting a full URL here would turn that endpoint into an
# arbitrary-request tool. Public on purpose: control.py validates the probe host
# with the SAME rule, and one host rule beats two that can drift apart.
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,253}(:\d{1,5})?$")


class SettingsError(ValueError):
    """A rejected settings value, with a message meant for the operator."""


def load(path=None):
    path = SETTINGS_PATH if path is None else path
    data = dict(DEFAULTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in DEFAULTS:
        if key in raw:
            data[key] = raw[key]
    return data


def save(patch, path=None):
    path = SETTINGS_PATH if path is None else path
    unknown = set(patch) - set(DEFAULTS)
    if unknown:
        raise SettingsError(
            f"khoá không hợp lệ: {', '.join(sorted(unknown))}. "
            f"Chỉ nhận: {', '.join(sorted(DEFAULTS))}.")

    data = load(path)
    data.update(patch)
    _validate(data)

    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))
    return data


def _validate(data):
    host = data["station_host"]
    if host is None:
        data["station_host"] = ""
    else:
        if not isinstance(host, str):
            raise SettingsError("station_host phải là chuỗi.")
        host = host.strip()
        if host and not HOST_RE.match(host):
            raise SettingsError(
                f"station_host {host!r} không hợp lệ. Nhập IP hoặc tên máy "
                "(ví dụ 192.168.1.50 hoặc aqua-scope.local), không kèm "
                "http:// hay đường dẫn.")
        data["station_host"] = host

    if data["mode"] not in ALLOWED_MODES:
        raise SettingsError(
            f"mode phải là một trong {ALLOWED_MODES}, nhận được {data['mode']!r}.")

    lot = data["batch_lot"]
    if lot is not None:
        if not isinstance(lot, str):
            raise SettingsError("batch_lot phải là chuỗi hoặc để trống.")
        lot = lot.strip()
        data["batch_lot"] = lot or None

    delay = data["capture_delay_ms"]
    if not isinstance(delay, int) or isinstance(delay, bool):
        raise SettingsError("capture_delay_ms phải là số nguyên (mili-giây).")
    if not 0 <= delay <= MAX_CAPTURE_DELAY_MS:
        raise SettingsError(
            f"capture_delay_ms phải trong khoảng 0–{MAX_CAPTURE_DELAY_MS} ms.")

    px = data["px_per_mm"]
    if px is not None:
        if isinstance(px, bool) or not isinstance(px, (int, float)):
            raise SettingsError("px_per_mm phải là số hoặc để trống.")
        if px <= 0:
            # <= 0 không phải tỉ lệ vật lý hợp lệ và sẽ chảy thẳng vào size_mm
            # của mọi hạt.
            raise SettingsError("px_per_mm phải lớn hơn 0 (hoặc để trống).")
        data["px_per_mm"] = float(px)


def _write_atomic(path, text):
    """Ghi qua file tạm rồi os.replace — mất điện giữa chừng không để lại
    file JSON cụt mà lần mở sau phải đoán."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
