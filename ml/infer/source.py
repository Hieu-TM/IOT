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
        # Mã đã phát ra trong lượt đo này, để _next_sample_code() chống trùng
        # (xem docstring của hàm đó vì sao không thể dựa vào đồng hồ hệ thống).
        self._used_sample_codes = set()
        self.device_info = self._read_device()

    def _read_device(self):
        """Đọc /device, thử lại tối đa self.retries lần trước khi bỏ cuộc.

        Cố ý dùng `retries` ở đây (không phải chỉ để dành riêng cho
        /capture): cùng một brownout WiFi lúc board mới cấp nguồn có thể làm
        /device timeout hoặc trả JSON cụt, y hệt lý do /capture cần thử lại.
        Không tách lỗi mạng và lỗi JSON parse thành hai nhánh retry khác nhau
        — cùng một nguyên nhân (mất gói giữa chừng) có thể biểu hiện thành cả
        hai, và cả hai đều đáng thử lại như nhau. Ngược lại, JSON hợp lệ
        nhưng SAI HÌNH DẠNG (không phải object) không phải lỗi thoáng qua —
        đó là firmware trả sai, thử lại không giúp gì nên raise ngay, không
        đếm vào vòng lặp retry.
        """
        url = f"{self.base_url}/device"
        last_exc = None
        for _attempt in range(self.retries):
            try:
                resp = requests.get(url, timeout=self.timeout_s)
                resp.raise_for_status()
                info = resp.json()
            except Exception as exc:
                last_exc = exc
                continue
            if not isinstance(info, dict):
                raise StationError(f"{url} trả về JSON không phải object: {info!r}")
            return info
        raise StationError(
            f"không đọc được {url}: {last_exc}. Kiểm tra board đã bật, đúng IP, "
            f"và đã nạp firmware/aqua_scope_station."
        ) from last_exc

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
                except (StationError, requests.RequestException) as exc:
                    # Chỉ nuốt lỗi mạng/board — lỗi lập trình thật (AttributeError,
                    # TypeError, ...) phải nổi lên chứ không được báo chung chung
                    # là "khung hỏng, bỏ qua".
                    last_error = exc

            if body is None:
                print(f"[warn] khung {i + 1}/{self.count} hỏng, bỏ qua: {last_error}")
                continue

            captured_at = datetime.now(timezone.utc)
            yield Frame(
                image_bytes=body,
                sample_code=self._next_sample_code(captured_at),
                captured_at=captured_at,
                source_name=f"{self.base_url}/capture#{i + 1}",
            )

    def _next_sample_code(self, captured_at):
        """Sinh sample_code cho một khung, đảm bảo KHÔNG trùng với bất kỳ mã
        nào đã phát ra trong cùng lượt đo (self._used_sample_codes).

        QUAN TRỌNG — vì sao không được rút gọn về `_station_sample_code()`
        đơn thuần: web/backend/app/routers/ingest.py coi sample_code trùng
        là một bản RETRY và trả về already_exists — KHÔNG báo lỗi. Nếu hai
        khung liên tiếp sinh trùng mã, khung thứ hai sẽ bị ingest âm thầm bỏ
        qua như thể nó là bản gửi lại của khung đầu, và dữ liệu mất khỏi sổ
        audit mà không ai biết. Độ phân giải mili-giây của đồng hồ hệ thống
        KHÔNG đủ đảm bảo khác nhau khi interval_s=0, máy chạy đủ nhanh, hoặc
        ai đó hạ interval_s mặc định sau này — nên phải chống trùng bằng cấu
        trúc dữ liệu ở đây, không dựa vào may mắn của đồng hồ.
        """
        base = _station_sample_code(captured_at)
        code = base
        suffix = 2
        while code in self._used_sample_codes:
            code = f"{base}-{suffix}"
            suffix += 1
        self._used_sample_codes.add(code)
        return code


def _station_sample_code(captured_at):
    """`S{yyyyMMdd}-{HHmmss}-{mmm}` từ thời điểm chụp.

    CHỈ định dạng theo giờ chụp — KHÔNG tự đảm bảo duy nhất giữa hai lần gọi
    liên tiếp (xem Esp32CaptureSource._next_sample_code(), nơi chống trùng
    thật sự xảy ra). Cùng dạng với mã do server sinh
    (web/backend/app/routers/ingest.py), và khớp sẵn
    ^[A-Za-z0-9._-]{1,64}$ nên hậu tố "-N" nếu có cũng không cần làm sạch thêm.
    """
    return (f"S{captured_at:%Y%m%d}-{captured_at:%H%M%S}-"
            f"{captured_at.microsecond // 1000:03d}")
