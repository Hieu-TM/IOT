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


def station_sample_code(captured_at):
    """`S{yyyyMMdd}-{HHmmss}-{mmm}` từ thời điểm chụp.

    CHỈ định dạng theo giờ chụp — KHÔNG tự đảm bảo duy nhất giữa hai lần gọi
    liên tiếp (xem unique_station_sample_code()). Cùng dạng với mã do server
    sinh (web/backend/app/routers/ingest.py), và khớp sẵn
    ^[A-Za-z0-9._-]{1,64}$ nên hậu tố "-N" nếu có cũng không cần làm sạch thêm.
    """
    return (f"S{captured_at:%Y%m%d}-{captured_at:%H%M%S}-"
            f"{captured_at.microsecond // 1000:03d}")


def unique_station_sample_code(captured_at, used):
    """Mã cho một khung, đảm bảo KHÔNG trùng bất kỳ mã nào trong `used`.

    `used` là một set bị THAY ĐỔI TẠI CHỖ (mã mới được thêm vào).

    QUAN TRỌNG — vì sao không dùng thẳng station_sample_code():
    web/backend/app/routers/ingest.py coi sample_code trùng là một bản RETRY
    và trả về already_exists — KHÔNG báo lỗi. Nếu hai khung liên tiếp sinh
    trùng mã, khung thứ hai bị ingest âm thầm bỏ qua như thể nó là bản gửi lại
    của khung đầu, và dữ liệu mất khỏi sổ audit mà không ai biết. Độ phân giải
    mili-giây của đồng hồ hệ thống KHÔNG đủ đảm bảo khác nhau khi interval_s=0
    hoặc máy chạy đủ nhanh — nên phải chống trùng bằng cấu trúc dữ liệu ở đây,
    không dựa vào may mắn của đồng hồ.
    """
    base = station_sample_code(captured_at)
    code = base
    suffix = 2
    while code in used:
        code = f"{base}-{suffix}"
        suffix += 1
    used.add(code)
    return code
