import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from ml.infer.source import Esp32CaptureSource, FolderSource, Frame, StationError


def _write_jpeg(path):
    Image.new("RGB", (32, 32), (128, 128, 128)).save(path, format="JPEG")


def _write_png(path):
    Image.new("RGB", (32, 32), (128, 128, 128)).save(path, format="PNG")


def test_folder_source_yields_image_frames_only(tmp_path):
    _write_jpeg(tmp_path / "a.jpg")
    _write_png(tmp_path / "b.png")
    (tmp_path / "notes.txt").write_text("ignore me")

    frames = list(FolderSource(tmp_path).frames())

    assert len(frames) == 2
    assert {f.source_name for f in frames} == {"a.jpg", "b.png"}
    for f in frames:
        assert isinstance(f, Frame)
        assert f.image_bytes[:2] in (b"\xff\xd8", b"\x89P")  # jpeg / png magic
        assert f.captured_at.tzinfo is not None
        assert f.sample_code in ("a", "b")


def test_folder_source_accepts_single_file(tmp_path):
    _write_jpeg(tmp_path / "solo.jpg")
    frames = list(FolderSource(tmp_path / "solo.jpg").frames())
    assert len(frames) == 1
    assert frames[0].sample_code == "solo"


_DEVICE_JSON = {
    "device_id": "aqua-cam-a1b2c3",
    "firmware": "aqua_scope_station/1.0.0",
    "uptime_s": 42,
    "wifi": {"ssid": "test", "rssi": -55, "ip": "127.0.0.1"},
    "psram": True,
    "sensor": "OV2640",
    "camera": {"framesize": 13, "width": 1600, "height": 1200, "quality": 10,
               "aec": 0, "aec2": 0, "agc": 0, "gain": 0, "exposure": 100},
    "captures": 7,
    "prefs_saved": True,
}


def _jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


class _FakeBoard:
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

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


def test_reads_device_info_then_yields_frames():
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=2, interval_s=0)
        assert src.device_info["device_id"] == "aqua-cam-a1b2c3"

        frames = list(src.frames())

    assert len(frames) == 2
    for f in frames:
        assert f.image_bytes[:2] == b"\xff\xd8"       # JPEG magic
        assert f.captured_at.tzinfo is not None        # ingest đòi có offset
        assert f.sample_code.startswith("S")
    # sample_code phải khác nhau, nếu không ingest coi khung sau là trùng
    assert frames[0].sample_code != frames[1].sample_code


def test_unreachable_board_raises_immediately():
    # Cổng đóng: phải hỏng NGAY ở /device, không âm thầm chụp tiếp.
    with pytest.raises(StationError) as exc:
        Esp32CaptureSource("127.0.0.1:1", count=1, timeout_s=1, retries=1)
    assert "/device" in str(exc.value)


def test_device_json_missing_keys_does_not_crash():
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", {"device_id": "x"})) as board:
        src = Esp32CaptureSource(board.host, count=1, interval_s=0)
        assert src.device_info["device_id"] == "x"
        assert list(src.frames())


def test_html_with_http_200_is_rejected_not_treated_as_image():
    with _FakeBoard([("html200", None)],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=1, interval_s=0, retries=2)
        assert list(src.frames()) == []      # bỏ qua khung, không đẩy rác đi
        assert board.capture_hits == 2       # đã thử lại đủ số lần


def test_503_frame_is_skipped_and_run_continues():
    with _FakeBoard([("503", None), ("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=2, interval_s=0, retries=1)
        frames = list(src.frames())
    # khung 1 hỏng và bị bỏ; khung 2 vẫn tới nơi — một lỗi không giết cả lượt
    assert len(frames) == 1


def test_server_dies_midway_yields_earlier_frames():
    """Brownout giữa burst: khung đã lấy được phải giữ nguyên, và vòng lặp
    phải KẾT THÚC bình thường thay vì ném ngoại lệ ra ngoài."""
    board = _FakeBoard([("jpeg", _jpeg_bytes())],
                       device_response=("json", _DEVICE_JSON))
    with board:
        src = Esp32CaptureSource(board.host, count=3, interval_s=0, retries=1)
        frames = []
        for i, frame in enumerate(src.frames()):
            frames.append(frame)
            if i == 0:
                board._server.shutdown()   # board chết ngay sau khung đầu

    # Đúng 1 khung: khung đầu tới nơi, hai khung sau hỏng vì board đã chết.
    # (Nếu chỉ khẳng định >= 1 thì test không bao giờ fail được — khung đầu
    # luôn được append trước khi shutdown.)
    assert len(frames) == 1
    assert frames[0].image_bytes[:2] == b"\xff\xd8"
