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

from .naming import sample_code_from_filename, unique_station_sample_code
from .station import StationClient, StationError   # StationError re-export: cli.py và
                                                   # test cũ import nó từ đây

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


class Esp32CaptureSource:
    """Chụp N khung từ firmware aqua_scope_station (chế độ CLI --from-board).

    Chỉ còn giữ phần "vòng lặp đếm khung": mọi thứ liên quan tới HTTP nằm ở
    StationClient (ml/infer/station.py), dùng chung với runner của backend web.

    Hỏng NGAY ở /device: nếu không đọc được danh tính board thì mọi mẫu thu
    được sau đó cũng không truy nguyên được — thà dừng còn hơn ghi vào sổ audit
    những dòng không biết đến từ đâu.

    Ngược lại, một khung ảnh hỏng chỉ làm mất khung đó. Brownout khi WiFi TX
    trùng lúc chụp UXGA là chuyện thường ngày trên board này; để nó giết cả
    lượt đo là sai.
    """

    def __init__(self, host, *, count=1, interval_s=2.0, timeout_s=20, retries=3):
        self.client = StationClient(host, timeout_s=timeout_s, retries=retries)
        self.base_url = self.client.base_url
        self.count = int(count)
        self.interval_s = float(interval_s)
        # Mã đã phát ra trong lượt đo này (xem naming.unique_station_sample_code).
        self._used_sample_codes = set()
        # Số khung đã bỏ vì hỏng cả retries lần thử. cli.py đọc thuộc tính này
        # SAU KHI đã tiêu thụ hết source.frames() để cộng vào Summary và quyết
        # định exit code — nếu không, một lượt đo mà board brownout hết mọi
        # khung sẽ báo "0 failed" và RC=0 dù không mẫu nào được ghi vào sổ audit.
        self.skipped = 0
        self.device_info = self.client.read_device()

    @property
    def device_id(self):
        return self.client.device_id

    def frames(self):
        for i in range(self.count):
            if i > 0 and self.interval_s > 0:
                time.sleep(self.interval_s)
            try:
                body = self.client.capture_once()
            except (StationError, requests.RequestException) as exc:
                self.skipped += 1
                print(f"[warn] khung {i + 1}/{self.count} hỏng, bỏ qua: {exc}")
                continue

            captured_at = datetime.now(timezone.utc)
            yield Frame(
                image_bytes=body,
                sample_code=unique_station_sample_code(
                    captured_at, self._used_sample_codes),
                captured_at=captured_at,
                source_name=f"{self.base_url}/capture#{i + 1}",
            )
