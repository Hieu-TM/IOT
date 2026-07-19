"""Image sources for the inference CLI.

FolderSource reads image files from disk; Esp32CaptureSource pulls them
straight off the board over HTTP. Both expose the same .frames() interface, so
cli.py / mapper.py / ingest_client.py never learn which one they got.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .naming import sample_code_from_filename

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


@dataclass
class Frame:
    image_bytes: bytes
    sample_code: str
    captured_at: datetime  # timezone-aware (web ingest requires an offset)
    source_name: str       # original filename, for logging


class FolderSource:
    """Yield Frames from a folder of images, or a single image file."""

    def __init__(self, path):
        self.path = Path(path)

    def frames(self):
        if self.path.is_file():
            paths = [self.path]
        else:
            paths = sorted(
                p for p in self.path.iterdir()
                if p.suffix.lower() in _IMAGE_EXTS
            )
        for p in paths:
            captured_at = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            yield Frame(
                image_bytes=p.read_bytes(),
                sample_code=sample_code_from_filename(p.name),
                captured_at=captured_at,
                source_name=p.name,
            )


class StationError(RuntimeError):
    """Board không dùng được (không tới được, hoặc /device không hợp lệ)."""


class Esp32CaptureSource:
    """Chụp ảnh trực tiếp từ firmware aqua_scope_station qua HTTP.

    Hỏng NGAY ở /device: nếu không đọc được danh tính board thì mọi mẫu thu
    được sau đó cũng không truy nguyên được — thà dừng còn hơn ghi vào sổ audit
    những dòng không biết đến từ đâu.

    Ngược lại, một khung ảnh hỏng chỉ làm mất khung đó. Brownout khi WiFi TX
    trùng lúc chụp UXGA là chuyện thường ngày trên board này; để nó giết cả
    lượt đo là sai.
    """

    def __init__(self, host, *, count=1, interval_s=2.0, timeout_s=20, retries=3):
        self.base_url = host if "://" in host else f"http://{host}"
        self.count = int(count)
        self.interval_s = float(interval_s)
        self.timeout_s = float(timeout_s)
        self.retries = max(1, int(retries))
        self.device_info = self._read_device()

    def _read_device(self):
        url = f"{self.base_url}/device"
        try:
            resp = requests.get(url, timeout=self.timeout_s)
            resp.raise_for_status()
            info = resp.json()
        except Exception as exc:
            raise StationError(
                f"không đọc được {url}: {exc}. Kiểm tra board đã bật, đúng IP, "
                f"và đã nạp firmware/aqua_scope_station."
            ) from exc
        if not isinstance(info, dict):
            raise StationError(f"{url} trả về JSON không phải object: {info!r}")
        return info

    @property
    def device_id(self):
        """device_id board tự báo, hoặc None nếu firmware không khai."""
        value = self.device_info.get("device_id")
        return value if isinstance(value, str) and value else None

    def _capture_once(self):
        """Trả về bytes JPEG, hoặc raise nếu khung này hỏng."""
        url = f"{self.base_url}/capture"
        resp = requests.get(url, timeout=self.timeout_s)
        if resp.status_code != 200:
            raise StationError(
                f"HTTP {resp.status_code}: {resp.text[:120]}")
        body = resp.content
        # Kiểm tra magic, KHÔNG tin Content-Type: một captive portal của router
        # trả HTML kèm HTTP 200 và đủ loại header. Đẩy HTML vào detector sẽ ra
        # lỗi khó hiểu ở tận cuối pipeline.
        if not body.startswith(b"\xff\xd8"):
            raise StationError(
                f"phản hồi không phải JPEG (bắt đầu bằng {body[:8]!r})")
        if not body.rstrip().endswith(b"\xff\xd9"):
            raise StationError("JPEG cụt (thiếu marker kết thúc)")
        return body

    def frames(self):
        for i in range(self.count):
            if i > 0 and self.interval_s > 0:
                time.sleep(self.interval_s)

            body = None
            last_error = None
            for attempt in range(self.retries):
                try:
                    body = self._capture_once()
                    break
                except Exception as exc:
                    last_error = exc

            if body is None:
                print(f"[warn] khung {i + 1}/{self.count} hỏng, bỏ qua: {last_error}")
                continue

            captured_at = datetime.now(timezone.utc)
            yield Frame(
                image_bytes=body,
                sample_code=_station_sample_code(captured_at),
                captured_at=captured_at,
                source_name=f"{self.base_url}/capture#{i + 1}",
            )


def _station_sample_code(captured_at):
    """`S{yyyyMMdd}-{HHmmss}-{mmm}` — đủ mịn để hai khung liền nhau không trùng.

    Cùng dạng với mã do server sinh (web/backend/app/routers/ingest.py), và
    khớp sẵn ^[A-Za-z0-9._-]{1,64}$ nên không cần làm sạch thêm.
    """
    return (f"S{captured_at:%Y%m%d}-{captured_at:%H%M%S}-"
            f"{captured_at.microsecond // 1000:03d}")
