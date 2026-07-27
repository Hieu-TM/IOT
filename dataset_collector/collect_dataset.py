"""Thu thập dataset: kéo ảnh từ ESP32-CAM về máy.

Firmware chỉ phục vụ `GET /capture` (1 ảnh JPEG). Toàn bộ logic burst, đặt tên
file, retry và lưu trữ nằm ở đây — sửa cách thu dataset không cần nạp lại
firmware.

Ảnh lưu vào `web/backend/data/dataset/` (KHÔNG phải `data/images/` — thư mục đó
là ảnh của các Sample trong DB, mỗi file khớp 1 dòng; đổ ảnh thô vào đấy sẽ tạo
file mồ côi lẫn với ảnh MOCK-* của mock_sender).

Ví dụ:
    # chụp 1 ảnh (thủ công)
    python collect_dataset.py --host 192.168.1.50 --count 1

    # burst 200 ảnh, cách nhau 1.5s
    python collect_dataset.py --host 192.168.1.50 --count 200 --interval 1.5
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

# --- Đường dẫn ---------------------------------------------------------------
# File này ở dataset_collector/collect_dataset.py
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "web" / "backend" / "data" / "dataset"

# JPEG luôn bắt đầu bằng SOI marker FF D8. ESP32-CAM khi quá tải/brownout có thể
# trả về HTML lỗi hoặc body cụt với HTTP 200 — không kiểm thì dataset lẫn file
# hỏng mà mãi sau lúc train mới phát hiện.
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


class CaptureError(Exception):
    """Một lần chụp thất bại (mạng lỗi, HTTP lỗi, hoặc ảnh không hợp lệ)."""


def validate_jpeg(data: bytes) -> None:
    """Raise CaptureError nếu `data` không phải JPEG nguyên vẹn.

    Dùng chung cho cả hai chiều (laptop kéo, và nút trên web đẩy sang) để một
    ảnh hỏng không bao giờ lọt vào dataset qua đường nào cả.
    """
    if not data:
        raise CaptureError("body rỗng")
    if not data.startswith(JPEG_SOI):
        raise CaptureError(f"không phải JPEG (bắt đầu bằng {data[:4]!r})")
    # rstrip cả byte 0: một số driver camera đệm thêm \x00 sau EOI. Chỉ dùng
    # rstrip() trơn sẽ loại nhầm ảnh HỢP LỆ — mất ảnh thật còn tệ hơn lọt ảnh hỏng.
    if not data.rstrip(b"\x00\r\n\t ").endswith(JPEG_EOI):
        raise CaptureError(f"JPEG cụt ({len(data)} bytes, thiếu EOI)")


def capture_once(session: requests.Session, url: str, timeout: float) -> bytes:
    """Gọi /capture một lần, trả về bytes JPEG đã kiểm tra.

    Raise CaptureError nếu request lỗi hoặc dữ liệu trả về không phải JPEG
    nguyên vẹn.
    """
    try:
        resp = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise CaptureError(f"lỗi mạng: {exc}") from exc

    if resp.status_code != 200:
        raise CaptureError(f"HTTP {resp.status_code}")

    data = resp.content
    validate_jpeg(data)
    return data


def make_filename(now: datetime) -> str:
    """`YYYYmmdd-HHMMSS-mmm.jpg` — mili giây để burst nhanh không trùng tên."""
    return f"{now:%Y%m%d-%H%M%S}-{now.microsecond // 1000:03d}.jpg"


def save_image(data: bytes, out_dir: Path, now: datetime | None = None) -> Path:
    """Ghi ảnh vào out_dir, trả về đường dẫn file.

    Nếu tên đã tồn tại (2 ảnh trong cùng 1 mili giây) thì thêm hậu tố -1, -2...
    để không bao giờ ghi đè ảnh đã thu.
    """
    now = now or datetime.now()
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / make_filename(now)
    if path.exists():
        stem, suffix = path.stem, path.suffix
        n = 1
        while path.exists():
            path = out_dir / f"{stem}-{n}{suffix}"
            n += 1

    path.write_bytes(data)
    return path


def collect(
    host: str,
    count: int,
    interval: float,
    out_dir: Path,
    port: int = 80,
    timeout: float = 15.0,
    retries: int = 3,
    session: requests.Session | None = None,
) -> tuple[int, int, int]:
    """Kéo `count` ảnh về `out_dir`. Trả về (số ảnh OK, số ảnh lỗi, tổng bytes).

    Một ảnh lỗi (sau khi hết lượt retry) bị bỏ qua chứ không dừng cả phiên —
    thu 200 ảnh mà hỏng vì 1 lần timeout thì quá phí.
    """
    url = f"http://{host}:{port}/capture"
    session = session or requests.Session()

    ok = failed = total_bytes = 0

    for i in range(1, count + 1):
        data = None
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                data = capture_once(session, url, timeout)
                break
            except CaptureError as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(0.5 * attempt)  # lùi dần, cho board kịp hồi

        if data is None:
            failed += 1
            print(f"[{i}/{count}] LỖI sau {retries} lần thử: {last_error}")
            continue

        path = save_image(data, out_dir)
        ok += 1
        total_bytes += len(data)
        print(f"[{i}/{count}] {path.name}  ({len(data) / 1024:.0f} KB)")

        if i < count and interval > 0:
            time.sleep(interval)

    return ok, failed, total_bytes


# ============================================================================
# Chế độ nhận (--serve): nút "Dataset" trên web UI của ESP32 đẩy ảnh sang đây.
#
# Vì sao cần: trang web chạy trong trình duyệt KHÔNG ghi được vào thư mục tùy ý
# trên ổ đĩa. Script này là cầu nối duy nhất đưa ảnh về đúng data/dataset/.
# ============================================================================

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # chặn Content-Length vô lý trước khi đọc vào RAM


def make_upload_handler(out_dir: Path, counter: dict):
    """Tạo lớp handler gắn với `out_dir`. `counter` để đếm qua các request."""

    class UploadHandler(BaseHTTPRequestHandler):
        server_version = "AquaScopeCollector/1"

        def _cors(self) -> None:
            # Trang gọi tới chạy ở origin của ESP32 (http://192.168.x.x), còn
            # server này ở origin khác -> mọi phản hồi phải có CORS header.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            # Preflight. BẮT BUỘC phải có: Content-Type image/jpeg không nằm
            # trong danh sách an toàn của CORS, nên trình duyệt luôn hỏi trước
            # bằng OPTIONS. Thiếu nhánh này thì nút trên web im lặng không chạy.
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if self.path.split("?")[0] == "/health":
                self._json(200, {"ok": True, "saved": counter["n"],
                                 "out_dir": str(out_dir)})
            else:
                self._json(404, {"error": "chỉ có /health và /upload"})

        def do_POST(self):
            if self.path.split("?")[0] != "/upload":
                self._json(404, {"error": "chỉ có /upload"})
                return

            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                self._json(400, {"error": "Content-Length không hợp lệ"})
                return
            if length <= 0:
                self._json(400, {"error": "thiếu Content-Length"})
                return
            if length > MAX_UPLOAD_BYTES:
                self._json(413, {"error": f"ảnh quá lớn ({length} bytes)"})
                return

            data = self.rfile.read(length)
            try:
                validate_jpeg(data)
            except CaptureError as exc:
                # Không ghi ảnh hỏng ra đĩa — báo lỗi để hiện ngay trên web UI.
                print(f"  TỪ CHỐI ảnh hỏng: {exc}")
                self._json(400, {"error": str(exc)})
                return

            path = save_image(data, out_dir)
            counter["n"] += 1
            print(f"[{counter['n']}] {path.name}  ({len(data) / 1024:.0f} KB)")
            self._json(201, {"saved": path.name, "count": counter["n"]})

        def log_message(self, *args):
            pass  # tự in dòng gọn hơn ở trên

    return UploadHandler


def serve(out_dir: Path, port: int = 8765, bind: str = "0.0.0.0"):
    """Chạy server nhận ảnh. Trả về (server, counter) — dùng được trong test."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counter = {"n": 0}
    server = ThreadingHTTPServer((bind, port), make_upload_handler(out_dir, counter))
    return server, counter


def run_server(out_dir: Path, port: int, bind: str = "0.0.0.0") -> int:
    server, _ = serve(out_dir, port, bind)
    actual_port = server.server_address[1]

    print(f"Đang chờ ảnh ở cổng {actual_port}, lưu vào: {out_dir}")
    print("Trên web UI của ESP32, điền ô \"Dataset PC\":")
    for addr in _local_addresses():
        print(f"    {addr}:{actual_port}")
    print("Ctrl+C để dừng.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    finally:
        server.shutdown()
        server.server_close()
    return 0


def _local_addresses() -> list[str]:
    """IP LAN của máy này, để khỏi phải tự đi tra ipconfig."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Không thực sự gửi gói nào; chỉ để OS chọn interface ra ngoài.
            s.connect(("8.8.8.8", 80))
            return [s.getsockname()[0]]
    except OSError:
        return ["<IP-cua-may-nay>"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kéo ảnh từ ESP32-CAM về để thu thập dataset.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--serve", action="store_true",
                   help="chế độ NHẬN: nằm chờ nút Dataset trên web UI của ESP32 đẩy ảnh sang")
    p.add_argument("--listen-port", type=int, default=8765,
                   help="cổng lắng nghe ở chế độ --serve")
    p.add_argument("--host", help="IP của ESP32-CAM (xem ở Serial Monitor). Bắt buộc khi KHÔNG dùng --serve")
    p.add_argument("--port", type=int, default=80, help="cổng HTTP của board")
    p.add_argument("--count", type=int, default=1, help="số ảnh cần chụp")
    p.add_argument("--interval", type=float, default=1.5, help="giây nghỉ giữa 2 ảnh")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="thư mục lưu ảnh")
    p.add_argument("--timeout", type=float, default=15.0, help="timeout mỗi request (giây)")
    p.add_argument("--retries", type=int, default=3, help="số lần thử lại mỗi ảnh")
    return p


def _force_utf8_output() -> None:
    """Ép stdout/stderr sang UTF-8.

    Console Windows mặc định là cp1252, không mã hóa được tiếng Việt: chỉ cần
    in "Nguồn" là UnicodeEncodeError và script chết trước khi chụp được ảnh nào.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # stream đã bị thay thế/đóng — không đáng để chết vì chuyện này


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(argv)

    out_dir = args.out.resolve()

    if args.serve:
        return run_server(out_dir, args.listen_port)

    if not args.host:
        print("Cần --host <IP của ESP32>, hoặc dùng --serve để nằm chờ.", file=sys.stderr)
        return 2
    if args.count < 1:
        print("--count phải >= 1", file=sys.stderr)
        return 2
    if args.interval < 0:
        print("--interval không được âm", file=sys.stderr)
        return 2
    print(f"Nguồn : http://{args.host}:{args.port}/capture")
    print(f"Lưu về: {out_dir}")
    print(f"Kế hoạch: {args.count} ảnh, cách nhau {args.interval}s\n")

    start = time.time()
    try:
        ok, failed, total_bytes = collect(
            host=args.host,
            count=args.count,
            interval=args.interval,
            out_dir=out_dir,
            port=args.port,
            timeout=args.timeout,
            retries=args.retries,
        )
    except KeyboardInterrupt:
        print("\nĐã dừng theo yêu cầu. Ảnh đã lưu vẫn còn nguyên.")
        return 130

    elapsed = time.time() - start
    print(
        f"\nXong sau {elapsed:.0f}s — {ok} ảnh OK, {failed} lỗi, "
        f"tổng {total_bytes / 1024 / 1024:.1f} MB"
    )
    if failed:
        print(
            "Có ảnh lỗi. Hay gặp nhất: ESP32-CAM brownout khi WiFi TX + chụp UXGA\n"
            "cùng lúc — thử tăng --interval, hoặc dùng nguồn 5V >= 2A."
        )
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
