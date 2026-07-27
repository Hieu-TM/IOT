"""Tầng nói chuyện HTTP với firmware aqua_scope_station.

Tách khỏi source.py vì có HAI người dùng với nhu cầu khác nhau:
  * Esp32CaptureSource — chụp N khung rồi dừng (CLI `--count`)
  * Runner của backend web — chụp MỘT khung theo yêu cầu, lặp vô hạn

Trước đây hai việc này dính vào nhau trong một class, nên cái thứ hai không
làm được: vòng `for i in range(count)` là thứ duy nhất biết cách gọi /capture.
"""

import time

import requests

# Nghỉ giữa các lần thử lại /capture trong cùng một khung. Brownout WiFi (lý
# do phổ biến nhất khiến /capture hỏng) cần vài trăm ms mới hồi; thử lại liền
# tay trong vài mili-giây nhiều khả năng đụng đúng lúc nguồn còn sụt và hỏng
# cả retries lần liên tiếp.
CAPTURE_RETRY_BACKOFF_S = 0.3


class StationError(RuntimeError):
    """Board không dùng được (không tới được, hoặc trả về thứ không hợp lệ)."""


class StationClient:
    """Client HTTP tới một board aqua_scope_station.

    Không giữ trạng thái vòng lặp nào — mỗi phương thức là một lần gọi độc lập.
    """

    def __init__(self, host, *, timeout_s=20, retries=3):
        self.base_url = host if "://" in host else f"http://{host}"
        self.timeout_s = float(timeout_s)
        self.retries = max(1, int(retries))
        self._device_info = None

    # --- /device ---------------------------------------------------------

    def read_device(self):
        """Đọc /device, thử lại tối đa self.retries lần trước khi bỏ cuộc.

        Cùng một brownout WiFi lúc board mới cấp nguồn có thể làm /device
        timeout HOẶC trả JSON cụt — cùng một nguyên nhân, nên cùng một nhánh
        retry. Ngược lại, JSON hợp lệ nhưng SAI HÌNH DẠNG (không phải object)
        là firmware trả sai: thử lại không giúp gì nên raise ngay.
        """
        url = f"{self.base_url}/device"
        last_exc = None
        for _attempt in range(self.retries):
            try:
                resp = requests.get(url, timeout=self.timeout_s)
                resp.raise_for_status()
                info = resp.json()
            except (StationError, requests.RequestException) as exc:
                # Chỉ nuốt lỗi mạng/board (requests.exceptions.JSONDecodeError
                # là subclass của RequestException từ requests>=2.27). Lỗi lập
                # trình thật (AttributeError, TypeError, ...) phải nổi lên.
                last_exc = exc
                continue
            if not isinstance(info, dict):
                raise StationError(f"{url} trả về JSON không phải object: {info!r}")
            self._device_info = info
            return info
        raise StationError(
            f"không đọc được {url}: {last_exc}. Kiểm tra board đã bật, đúng IP, "
            f"và đã nạp firmware/aqua_scope_station."
        ) from last_exc

    @property
    def device_info(self):
        """Khối /device gần nhất; đọc lười ở lần gọi đầu."""
        if self._device_info is None:
            self.read_device()
        return self._device_info

    @property
    def device_id(self):
        """device_id board tự báo, hoặc None nếu firmware không khai."""
        value = self.device_info.get("device_id")
        return value if isinstance(value, str) and value else None

    # --- /capture --------------------------------------------------------

    def capture_once(self):
        """Một khung JPEG. Thử lại self.retries lần; hỏng hết thì raise."""
        last_error = None
        for attempt in range(self.retries):
            if attempt > 0:
                time.sleep(CAPTURE_RETRY_BACKOFF_S)
            try:
                return self._capture_attempt()
            except (StationError, requests.RequestException) as exc:
                last_error = exc
        raise StationError(f"chụp hỏng sau {self.retries} lần thử: {last_error}")

    def _capture_attempt(self):
        url = f"{self.base_url}/capture"
        resp = requests.get(url, timeout=self.timeout_s)
        if resp.status_code != 200:
            raise StationError(f"HTTP {resp.status_code}: {resp.text[:120]}")
        body = resp.content
        # Kiểm tra magic, KHÔNG tin Content-Type: captive portal của router trả
        # HTML kèm HTTP 200 và đủ loại header.
        if not body.startswith(b"\xff\xd8"):
            raise StationError(
                f"phản hồi không phải JPEG (bắt đầu bằng {body[:8]!r})")
        if not body.rstrip().endswith(b"\xff\xd9"):
            raise StationError("JPEG cụt (thiếu marker kết thúc)")
        return body
