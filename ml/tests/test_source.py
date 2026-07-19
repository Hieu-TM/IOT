import io
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

import ml.infer.source as source_module
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


def test_all_frames_503_are_counted_as_skipped():
    # Ca CRITICAL đã tái hiện thật: board brownout, trả 503 cho MỌI khung.
    # Trước khi sửa, source.skipped không tồn tại và cli.py không có cách nào
    # biết 3 khung đã mất - Summary báo "0 failed" và RC=0 dù không mẫu nào
    # được ghi. .skipped phải phản ánh đúng số khung mất để cli.py cộng vào
    # Summary và trả RC khác 0 (xem test_cli.py::
    # test_all_frames_failing_from_board_reports_skipped_and_nonzero_exit).
    with _FakeBoard([("503", None)], device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=3, interval_s=0, retries=1)
        frames = list(src.frames())

    assert frames == []
    assert src.skipped == 3


def test_partial_failure_increments_skipped_by_exactly_one():
    with _FakeBoard([("503", None), ("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=2, interval_s=0, retries=1)
        frames = list(src.frames())

    assert len(frames) == 1
    assert src.skipped == 1


def test_server_dies_midway_yields_earlier_frames():
    """Brownout giữa burst: khung đã lấy được phải giữ nguyên, và vòng lặp
    phải KẾT THÚC bình thường thay vì ném ngoại lệ ra ngoài."""
    board = _FakeBoard([("jpeg", _jpeg_bytes())],
                       device_response=("json", _DEVICE_JSON))
    with board:
        # timeout_s=1 (thay vì mặc định 20s): hai khung sau khi board chết
        # đều phải chờ hết ReadTimeout mới bị bỏ qua; 20s x 2 khung sẽ làm
        # riêng test này tốn ~40s. Giá trị nhỏ vẫn chứng minh đúng hành vi.
        src = Esp32CaptureSource(board.host, count=3, interval_s=0, retries=1,
                                 timeout_s=1)
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


def test_truncated_jpeg_frame_is_skipped():
    # Ca thứ ba mà docstring _FakeBoard tự khai ("body cụt") nhưng trước đây
    # chưa có test nào tái hiện: JPEG có magic mở đầu đúng nhưng thiếu marker
    # kết thúc \xff\xd9 — nhánh "JPEG cụt" trong _capture_once() phải chạy.
    with _FakeBoard([("jpeg_truncated", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=1, interval_s=0, retries=2)
        assert list(src.frames()) == []      # khung cụt không được lọt qua
        assert board.capture_hits == 2       # đã thử lại đủ số lần


def test_device_html_body_raises_station_error():
    # /device trả HTML (không parse được thành JSON) — phải dừng cả lượt,
    # không được coi như board tới được rồi lặng lẽ tiếp tục.
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("html200", None)) as board:
        with pytest.raises(StationError) as exc:
            Esp32CaptureSource(board.host, count=1, interval_s=0, retries=1)
        assert "/device" in str(exc.value)


def test_device_json_array_is_rejected_not_a_dict():
    # /device trả JSON hợp lệ nhưng không phải object (một mảng) — nhánh
    # `isinstance(info, dict)` trước đây chưa từng được test chạy tới.
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", [1, 2, 3])) as board:
        with pytest.raises(StationError) as exc:
            Esp32CaptureSource(board.host, count=1, interval_s=0, retries=1)
        assert "không phải object" in str(exc.value)


def test_device_json_number_is_rejected_not_a_dict():
    # Cùng nhánh như trên nhưng với một kiểu JSON hợp lệ khác không phải dict.
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", 42)) as board:
        with pytest.raises(StationError) as exc:
            Esp32CaptureSource(board.host, count=1, interval_s=0, retries=1)
        assert "không phải object" in str(exc.value)


def test_device_http_error_status_raises_station_error():
    # /device trả HTTP lỗi (500) — board tới được nhưng nó tự báo hỏng.
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("500", None)) as board:
        with pytest.raises(StationError) as exc:
            Esp32CaptureSource(board.host, count=1, interval_s=0, retries=1)
        assert "/device" in str(exc.value)


def test_sample_code_does_not_collide_when_clock_stands_still(monkeypatch):
    # Ép đồng hồ hệ thống đứng yên (nhiều khung liền nhau rơi vào cùng một
    # mili-giây, đúng ca interval_s=0 hoặc máy đủ nhanh). Nếu code cũ
    # (_station_sample_code() dùng thẳng, không chống trùng) thì test này
    # FAIL thật: cả hai frame sẽ có cùng sample_code, và ingest sẽ coi khung
    # thứ hai là bản retry rồi âm thầm bỏ nó đi.
    frozen = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr(source_module, "datetime", _FrozenDatetime)

    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=3, interval_s=0)
        frames = list(src.frames())

    assert len(frames) == 3
    codes = [f.sample_code for f in frames]
    assert len(set(codes)) == 3, f"sample_code trùng nhau: {codes}"
    for code in codes:
        assert 1 <= len(code) <= 64
        assert all(c.isalnum() or c in "._-" for c in code)
