"""ESP32-CAM giả bằng HTTP server THẬT, dùng chung cho test của source + station.

Dùng server thật chứ không mock `requests`: các ca hỏng ngoài đời quan trọng
nhất (body cụt, HTML kèm HTTP 200, server chết giữa burst) chỉ tái hiện được ở
tầng socket. Mock sẽ bỏ lọt đúng những ca đó.
"""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image


DEVICE_JSON = {
    "device_id": "aqua-cam-a1b2c3",
    "firmware": "aqua_scope_station/1.0.0",
    "uptime_s": 42,
    "wifi": {"ssid": "test", "rssi": -55, "ip": "127.0.0.1"},
    "psram": True,
    "sensor": "OV2640",
    "camera": {"framesize": 13, "width": 1600, "height": 1200, "quality": 10,
               "aec": 0, "aec2": 0, "agc": 0, "gain": 0, "exposure": 100},
    "pump": {"pwm_ready": True, "auto": True, "phase": "SETTLING", "duty": 0,
             "cycle_count": 3, "fill_ms": 5000, "settle_ms": 2000,
             "flush_ms": 5000, "cooldown_ms": 3000, "ramp_up_ms": 250,
             "ramp_down_ms": 350, "fill_duty": 55, "flush_duty": 100},
    "captures": 7,
    "prefs_saved": True,
}


def jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


class FakeBoard:
    """ESP32-CAM giả bằng HTTP server THẬT.

    Dùng server thật chứ không mock `requests`: các ca hỏng ngoài đời quan
    trọng nhất (body cụt, HTML kèm HTTP 200, server chết giữa burst) chỉ tái
    hiện được ở tầng socket. Mock sẽ bỏ lọt đúng những ca đó.
    """

    def __init__(self, capture_responses, device_response=None):
        self._captures = list(capture_responses)
        self._device = device_response
        self.capture_hits = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/device":
                    kind, payload = outer._device
                    outer._respond(self, kind, payload)
                elif self.path == "/capture":
                    idx = min(outer.capture_hits, len(outer._captures) - 1)
                    outer.capture_hits += 1
                    kind, payload = outer._captures[idx]
                    outer._respond(self, kind, payload)
                else:
                    self.send_response(404)
                    self.end_headers()

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.host = f"127.0.0.1:{self._server.server_port}"

    @staticmethod
    def _respond(handler, kind, payload):
        if kind == "json":
            body = json.dumps(payload).encode()
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
        elif kind == "jpeg":
            handler.send_response(200)
            handler.send_header("Content-Type", "image/jpeg")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
        elif kind == "html200":
            body = b"<html>captive portal</html>"
            handler.send_response(200)
            handler.send_header("Content-Type", "text/html")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
        elif kind == "503":
            body = b"camera capture failed"
            handler.send_response(503)
            handler.send_header("Content-Type", "text/plain")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
        elif kind == "500":
            body = b"internal server error"
            handler.send_response(500)
            handler.send_header("Content-Type", "text/plain")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
        elif kind == "jpeg_truncated":
            # JPEG hợp lệ nhưng bị cắt mất đuôi: có magic \xff\xd8 mở đầu,
            # không có marker \xff\xd9 kết thúc — mô phỏng kết nối đứt giữa
            # chừng lúc board đang gửi ảnh.
            body = payload[:-10]
            handler.send_response(200)
            handler.send_header("Content-Type", "image/jpeg")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
