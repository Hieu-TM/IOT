"""Test collect_dataset.py với một HTTP server thật chạy trên localhost.

Không mock `requests` — server giả này cho phép mô phỏng đúng những kiểu hỏng
mà ESP32-CAM hay gây ra ngoài đời: body cụt, trả HTML lỗi, HTTP 500, chậm quá
timeout. Mock sẽ bỏ lọt đúng những ca đó.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collect_dataset import (  # noqa: E402
    CaptureError,
    capture_once,
    collect,
    main,
    make_filename,
    save_image,
    serve,
)

# JPEG hợp lệ tối thiểu: SOI ... EOI
GOOD_JPEG = b"\xff\xd8" + b"\x00" * 128 + b"\xff\xd9"


class FakeCam:
    """ESP32-CAM giả. `script` quyết định mỗi request trả về cái gì."""

    def __init__(self, script):
        self.script = script  # list[callable(handler)] hoặc callable
        self.hits = 0
        self._server = None
        self._thread = None

    def _next_action(self):
        i = self.hits
        self.hits += 1
        if callable(self.script):
            return self.script
        # Hết kịch bản thì lặp lại hành vi cuối cùng.
        return self.script[min(i, len(self.script) - 1)]

    def __enter__(self):
        cam = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cam._next_action()(self)

            def log_message(self, *args):
                pass  # im lặng, không rác ra output test

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    @property
    def host(self) -> str:
        return "127.0.0.1"

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/capture"


# --- Các hành vi server -------------------------------------------------------


def serve_jpeg(h, payload=GOOD_JPEG):
    h.send_response(200)
    h.send_header("Content-Type", "image/jpeg")
    h.send_header("Content-Length", str(len(payload)))
    h.end_headers()
    h.wfile.write(payload)


def serve_truncated(h):
    """Board sập giữa chừng: có SOI nhưng không có EOI."""
    serve_jpeg(h, b"\xff\xd8" + b"\x00" * 64)


def serve_html_error(h):
    """Trả HTML với HTTP 200 — kiểu hỏng âm thầm, nguy hiểm nhất."""
    body = b"<html><body>Camera capture failed</body></html>"
    h.send_response(200)
    h.send_header("Content-Type", "text/html")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def serve_500(h):
    h.send_error(500, "capture failed")


def serve_slow(h):
    time.sleep(2.0)
    serve_jpeg(h)


# --- capture_once -------------------------------------------------------------


def test_capture_once_returns_jpeg_bytes():
    with FakeCam(serve_jpeg) as cam:
        data = capture_once(requests.Session(), cam.url, timeout=5)
    assert data == GOOD_JPEG


def test_capture_once_rejects_truncated_jpeg():
    with FakeCam(serve_truncated) as cam:
        with pytest.raises(CaptureError, match="cụt"):
            capture_once(requests.Session(), cam.url, timeout=5)


def test_capture_once_accepts_jpeg_with_trailing_null_padding():
    """Một số driver đệm \\x00 sau EOI. Ảnh này HỢP LỆ, không được loại."""
    padded = GOOD_JPEG + b"\x00" * 8
    with FakeCam(lambda h: serve_jpeg(h, padded)) as cam:
        assert capture_once(requests.Session(), cam.url, timeout=5) == padded


def test_capture_once_rejects_html_body_with_http_200():
    with FakeCam(serve_html_error) as cam:
        with pytest.raises(CaptureError, match="không phải JPEG"):
            capture_once(requests.Session(), cam.url, timeout=5)


def test_capture_once_rejects_http_error():
    with FakeCam(serve_500) as cam:
        with pytest.raises(CaptureError, match="HTTP 500"):
            capture_once(requests.Session(), cam.url, timeout=5)


def test_capture_once_times_out():
    with FakeCam(serve_slow) as cam:
        with pytest.raises(CaptureError, match="lỗi mạng"):
            capture_once(requests.Session(), cam.url, timeout=0.3)


def test_capture_once_reports_unreachable_host():
    # Cổng 1 gần như chắc chắn không có gì lắng nghe.
    with pytest.raises(CaptureError, match="lỗi mạng"):
        capture_once(requests.Session(), "http://127.0.0.1:1/capture", timeout=1)


# --- save_image / make_filename ----------------------------------------------


def test_make_filename_has_millisecond_precision():
    now = datetime(2026, 7, 19, 14, 30, 52, 417_000)
    assert make_filename(now) == "20260719-143052-417.jpg"


def test_save_image_creates_missing_directory(tmp_path):
    out = tmp_path / "khong" / "ton" / "tai"
    path = save_image(GOOD_JPEG, out)
    assert path.exists()
    assert path.read_bytes() == GOOD_JPEG


def test_save_image_never_overwrites_on_timestamp_collision(tmp_path):
    now = datetime(2026, 7, 19, 14, 30, 52, 417_000)
    first = save_image(b"\xff\xd8AAA\xff\xd9", tmp_path, now)
    second = save_image(b"\xff\xd8BBB\xff\xd9", tmp_path, now)

    assert first != second
    assert first.read_bytes() == b"\xff\xd8AAA\xff\xd9"  # ảnh cũ còn nguyên
    assert second.name == "20260719-143052-417-1.jpg"


# --- collect ------------------------------------------------------------------


def test_collect_saves_requested_number_of_images(tmp_path):
    with FakeCam(serve_jpeg) as cam:
        ok, failed, total = collect(
            host=cam.host, port=cam.port, count=3, interval=0, out_dir=tmp_path
        )

    assert (ok, failed) == (3, 0)
    assert total == len(GOOD_JPEG) * 3
    assert len(list(tmp_path.glob("*.jpg"))) == 3


def test_collect_retries_then_succeeds(tmp_path):
    # 2 lần đầu hỏng, lần 3 ngon — vẫn phải ra đúng 1 ảnh, 0 lỗi.
    with FakeCam([serve_500, serve_500, serve_jpeg]) as cam:
        ok, failed, _ = collect(
            host=cam.host, port=cam.port, count=1, interval=0,
            out_dir=tmp_path, retries=3,
        )

    assert (ok, failed) == (1, 0)
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_collect_skips_bad_image_and_keeps_going(tmp_path):
    # Ảnh 1 hỏng hết lượt retry (2 lần), ảnh 2 và 3 ngon.
    with FakeCam([serve_500, serve_500, serve_jpeg]) as cam:
        ok, failed, _ = collect(
            host=cam.host, port=cam.port, count=3, interval=0,
            out_dir=tmp_path, retries=2,
        )

    assert (ok, failed) == (2, 1)  # không dừng cả phiên vì 1 ảnh hỏng
    assert len(list(tmp_path.glob("*.jpg"))) == 2


def test_collect_writes_nothing_when_every_capture_fails(tmp_path):
    with FakeCam(serve_500) as cam:
        ok, failed, total = collect(
            host=cam.host, port=cam.port, count=2, interval=0,
            out_dir=tmp_path, retries=1,
        )

    assert (ok, failed, total) == (0, 2, 0)
    assert list(tmp_path.glob("*.jpg")) == []


# --- main / CLI ---------------------------------------------------------------


def test_main_returns_zero_on_success(tmp_path, capsys):
    with FakeCam(serve_jpeg) as cam:
        code = main([
            "--host", cam.host, "--port", str(cam.port),
            "--count", "2", "--interval", "0", "--out", str(tmp_path),
        ])
    assert code == 0
    assert "2 ảnh OK, 0 lỗi" in capsys.readouterr().out


def test_main_returns_nonzero_when_nothing_collected(tmp_path):
    with FakeCam(serve_500) as cam:
        code = main([
            "--host", cam.host, "--port", str(cam.port),
            "--count", "1", "--interval", "0", "--retries", "1",
            "--out", str(tmp_path),
        ])
    assert code == 1


@pytest.mark.parametrize("bad_args", [["--count", "0"], ["--interval", "-1"]])
def test_main_rejects_invalid_arguments(bad_args, tmp_path):
    assert main(["--host", "127.0.0.1", "--out", str(tmp_path)] + bad_args) == 2


def test_cli_runs_on_a_legacy_codepage_console(tmp_path):
    """Chạy thật trong tiến trình con với stdout cp1252 (console Windows mặc định).

    capsys của pytest KHÔNG bắt được ca này — nó thu output mà không đi qua
    encoding của console, nên bug chỉ lộ ra khi người dùng chạy trong PowerShell.
    """
    import os
    import subprocess

    with FakeCam(serve_jpeg) as cam:
        env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "collect_dataset.py"),
             "--host", cam.host, "--port", str(cam.port),
             "--count", "1", "--interval", "0", "--out", str(tmp_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )

    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert "UnicodeEncodeError" not in proc.stderr
    assert len(list(tmp_path.glob("*.jpg"))) == 1


# --- Chế độ nhận (--serve) ----------------------------------------------------


@pytest.fixture
def receiver(tmp_path):
    """Server nhận đang chạy, trả về (base_url, thư mục lưu, counter)."""
    server, counter = serve(tmp_path, port=0, bind="127.0.0.1")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path, counter
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_receiver_saves_posted_jpeg(receiver):
    url, out_dir, counter = receiver
    resp = requests.post(f"{url}/upload", data=GOOD_JPEG,
                         headers={"Content-Type": "image/jpeg"}, timeout=5)

    assert resp.status_code == 201
    assert counter["n"] == 1
    saved = list(out_dir.glob("*.jpg"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == GOOD_JPEG
    assert resp.json()["saved"] == saved[0].name


def test_receiver_answers_cors_preflight(receiver):
    """Thiếu nhánh OPTIONS thì nút trên web im lặng không chạy.

    Content-Type image/jpeg KHÔNG nằm trong danh sách an toàn của CORS, nên
    trình duyệt luôn gửi OPTIONS trước. Test này khóa hành vi đó lại.
    """
    url, _, _ = receiver
    resp = requests.options(
        f"{url}/upload",
        headers={
            "Origin": "http://192.168.1.50",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=5,
    )

    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in resp.headers["Access-Control-Allow-Headers"]


def test_receiver_sends_cors_header_on_upload(receiver):
    url, _, _ = receiver
    resp = requests.post(f"{url}/upload", data=GOOD_JPEG,
                         headers={"Content-Type": "image/jpeg"}, timeout=5)
    assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_receiver_refuses_corrupt_image_without_writing_it(receiver):
    url, out_dir, counter = receiver
    resp = requests.post(f"{url}/upload", data=b"\xff\xd8 thieu EOI",
                         headers={"Content-Type": "image/jpeg"}, timeout=5)

    assert resp.status_code == 400
    assert "cụt" in resp.json()["error"]
    assert list(out_dir.glob("*.jpg")) == []  # không để ảnh hỏng lọt vào dataset
    assert counter["n"] == 0


def test_receiver_refuses_html_masquerading_as_image(receiver):
    url, out_dir, _ = receiver
    resp = requests.post(f"{url}/upload", data=b"<html>capture failed</html>",
                         headers={"Content-Type": "image/jpeg"}, timeout=5)
    assert resp.status_code == 400
    assert list(out_dir.glob("*.jpg")) == []


def test_receiver_rejects_oversized_upload_before_reading_it(receiver):
    """Server phải từ chối dựa trên header, KHÔNG nuốt 99MB vào RAM trước đã.

    Phải dùng socket thô: `requests` tự tính lại Content-Length nên không gửi
    được header nói dối.
    """
    import socket as sk
    from urllib.parse import urlparse

    url, out_dir, _ = receiver
    parsed = urlparse(url)

    request = (
        "POST /upload HTTP/1.1\r\n"
        f"Host: {parsed.hostname}:{parsed.port}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {99 * 1024 * 1024}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")

    with sk.create_connection((parsed.hostname, parsed.port), timeout=5) as conn:
        conn.sendall(request)          # gửi header rồi im — không gửi 99MB thật
        status_line = conn.makefile("rb").readline().decode("ascii", "replace")

    assert "413" in status_line, status_line
    assert list(out_dir.glob("*.jpg")) == []


def test_receiver_health_reports_progress(receiver):
    url, out_dir, _ = receiver
    assert requests.get(f"{url}/health", timeout=5).json()["saved"] == 0

    requests.post(f"{url}/upload", data=GOOD_JPEG,
                  headers={"Content-Type": "image/jpeg"}, timeout=5)

    health = requests.get(f"{url}/health", timeout=5).json()
    assert health["ok"] is True
    assert health["saved"] == 1
    assert health["out_dir"] == str(out_dir)


def test_receiver_404s_unknown_paths(receiver):
    url, _, _ = receiver
    assert requests.get(f"{url}/nothing", timeout=5).status_code == 404
    assert requests.post(f"{url}/nothing", data=b"x", timeout=5).status_code == 404


def test_receiver_keeps_every_image_in_a_rapid_burst(receiver):
    """Burst nhanh từ nút Dataset: 10 ảnh liên tiếp, không được mất/ghi đè cái nào."""
    url, out_dir, counter = receiver
    for _ in range(10):
        resp = requests.post(f"{url}/upload", data=GOOD_JPEG,
                             headers={"Content-Type": "image/jpeg"}, timeout=5)
        assert resp.status_code == 201

    assert counter["n"] == 10
    assert len(list(out_dir.glob("*.jpg"))) == 10


def test_serve_mode_does_not_require_host_argument(tmp_path):
    """`--serve` phải chạy được mà không cần --host (không có ESP32 nào để kéo)."""
    parser_args = ["--serve", "--out", str(tmp_path)]
    from collect_dataset import build_parser

    args = build_parser().parse_args(parser_args)
    assert args.serve is True
    assert args.host is None


def test_pull_mode_still_requires_host(tmp_path, capsys):
    assert main(["--out", str(tmp_path)]) == 2
    assert "--host" in capsys.readouterr().err


def test_main_does_not_default_to_the_web_sample_images_dir():
    """Chốt quyết định thiết kế: ảnh thô KHÔNG được rơi vào data/images/.

    Thư mục đó mỗi file khớp 1 dòng Sample trong DB; đổ ảnh thô vào sẽ tạo file
    mồ côi lẫn với ảnh MOCK-* của mock_sender.
    """
    from collect_dataset import DEFAULT_OUT_DIR

    assert DEFAULT_OUT_DIR.name == "dataset"
    assert DEFAULT_OUT_DIR.parent.name == "data"
    assert not (DEFAULT_OUT_DIR.parent / "images") == DEFAULT_OUT_DIR
