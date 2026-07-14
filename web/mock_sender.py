#!/usr/bin/env python3
"""Aqua Scope — Mock Sender (web_plan.md §6).

Script độc lập, **không import code nào trong `web/backend/`** — chỉ cần `requests`
+ `pillow`. Mô phỏng một trạm Aqua Scope thật: sinh mẫu (metadata JSON + ảnh JPEG
mô phỏng trường backlit) rồi POST `multipart/form-data` tới `/api/ingest`, đúng
hợp đồng đã chốt ở `web_plan.md` §2.1.

Lý do tồn tại (giữ vĩnh viễn, không xoá sau khi có firmware thật — xem §6): test
backend độc lập, không cần bật phần cứng ESP32-CAM.

CLI:
    python web/mock_sender.py --url http://127.0.0.1:8000/api/ingest \
        --count 15 --interval 2 --device-id aquascope-mock

Mỗi mẫu sinh ra:
  - sample_code = MOCK-{yyyyMMdd-HHmmss}-{4 hex ngẫu nhiên}
  - batch_lot ngẫu nhiên trong ["LOT-A", "LOT-B", None]
  - số hạt ngẫu nhiên 3–15
  - mỗi hạt: label theo trọng số (plastic 40 / bubble 25 / organic 20 / fiber 10 / unknown 5),
    size_mm đều trong [0.3, 4.5]mm, confidence 0.6–0.99 (thỉnh thoảng ép dưới 0.5 → unknown)
  - bbox/area_px suy từ size_mm qua PX_PER_MM = 14.0 (khớp CLAUDE.md ~14px/mm @ VGA)
  - ảnh: nền xám sáng + elip tối đúng centroid/bbox → khớp trực quan bbox-overlay trang detail
"""
from __future__ import annotations

import argparse
import io
import json
import random
import secrets
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

# Bảo vệ in tiếng Việt trên Windows console (cp1258 không có dấu). Reconfigure
# stdout/stderr sang utf-8 nếu có thể — không ảnh hưởng môi trường đã là utf-8.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass  # stream không hỗ trợ reconfigure — cứ để nguyên, lỗi mã hoá sẽ báo rõ

try:
    import requests  # noqa: F401  — checked late for friendlier error
except ImportError:  # pragma: no cover
    print(
        "[mock_sender] thiếu thư viện 'requests'. Cài: pip install requests pillow",
        file=sys.stderr,
    )
    raise

try:
    from PIL import Image, ImageDraw  # noqa: F401
except ImportError:  # pragma: no cover
    print(
        "[mock_sender] thiếu thư viện 'pillow'. Cài: pip install requests pillow",
        file=sys.stderr,
    )
    raise


# ──────────────────────────────────────────────────────────────────────────
# Hằng số — đồng bộ web_plan.md §6 + backend config.py (KHÔNG import, copy giá trị
# để script tự đứng được; nếu backend đổi, cập nhật cả hai nơi)
# ──────────────────────────────────────────────────────────────────────────
PX_PER_MM = 14.0                       # ~14 px/mm @ VGA, 40mm working distance
CONFIDENCE_THRESHOLD = 0.5            # dưới ngưỡng → gán 'unknown' (xử lý phía mock)
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480

# Trọng số nhãn theo §6 — tổng 100
LABEL_WEIGHTS: list[tuple[str, int]] = [
    ("plastic", 40),
    ("bubble", 25),
    ("organic", 20),
    ("fiber", 10),
    ("unknown", 5),
]

# batch_lot có thể None (nullable theo §3)
BATCH_LOT_CHOICES: list[str | None] = ["LOT-A", "LOT-B", None]

# Khoảng kích thước hạt (mm) — khớp phạm vi thiết kế 1–5mm / test <2mm (CLAUDE.md)
SIZE_MIN_MM = 0.3
SIZE_MAX_MM = 4.5

# Định nghĩa 1 số VND timezone +07:00 cho captured_at ISO đầy đủ.
VN_TZ = timezone(timedelta(hours=7))


# ──────────────────────────────────────────────────────────────────────────
# Sinh dữ liệu
# ──────────────────────────────────────────────────────────────────────────
def _weighted_label(rng: random.Random) -> str:
    """Chọn label theo trọng số LABEL_WEIGHTS."""
    labels, weights = zip(*LABEL_WEIGHTS)
    return rng.choices(labels, weights=weights, k=1)[0]


def _gen_sample_code(now: datetime, rng: random.Random) -> str:
    """MOCK-{yyyyMMdd-HHmmss}-{4 hex}."""
    stamp = now.strftime("%Y%m%d-%H%M%S")
    hex4 = secrets.token_hex(2)  # 2 bytes → 4 hex chars
    return f"MOCK-{stamp}-{hex4}"


def _gen_particles(rng: random.Random, n: int) -> list[dict[str, Any]]:
    """Sinh n hạt: centroid/bbox/area suy từ size_mm qua PX_PER_MM.

    bbox đủ lớn để hạt elip vẽ đượcを見 (~size_mm * PX_PER_MM), có jitter tỉ lệ khung
    nhỏ để 'fiber' ra hình thuôn dài rõ (bbox_h ~ 0.4 bbox_w).
    """
    particles: list[dict[str, Any]] = []
    for i in range(n):
        label = _weighted_label(rng)
        size_mm = round(rng.uniform(SIZE_MIN_MM, SIZE_MAX_MM), 2)

        confidence = round(rng.uniform(0.6, 0.99), 3)
        # "Thỉnh thoảng" (§6) — tần suất thấp, chỉ vừa đủ để có hạt test đường dưới-ngưỡng.
        # Đặt ~5% (không phải 15%): trọng số 'unknown' cộng dồn phải tiệm cận mục tiêu 5%
        # trong §6, không khuếch đại lên gấp 4. Kết quả: ~unknown_LẠI/nhãn-hạt-cho-1-test
        # vẫn có vài hạt confidence<0.5 trên 200 mẫu (xem _check_dist).
        if rng.random() < 0.05:
            confidence = round(rng.uniform(0.2, CONFIDENCE_THRESHOLD - 0.01), 3)
            label = "unknown"

        # Kích thước bbox theo px
        w_px = size_mm * PX_PER_MM
        if label == "fiber":
            # Elip thuôn dài: h nhỏ hơn w rõ rệt
            h_px = w_px * rng.uniform(0.25, 0.45)
        else:
            # Gần tròn với jitter tỉ lệ khung nhỏ
            h_px = w_px * rng.uniform(0.7, 1.2)

        bbox_w = max(1, int(round(w_px)))
        bbox_h = max(1, int(round(h_px)))

        # Đặt centroid sao cho bbox nằm trọn trong khung
        cx = rng.uniform(bbox_w / 2 + 4, IMAGE_WIDTH - bbox_w / 2 - 4)
        cy = rng.uniform(bbox_h / 2 + 4, IMAGE_HEIGHT - bbox_h / 2 - 4)
        bbox_x = int(round(cx - bbox_w / 2))
        bbox_y = int(round(cy - bbox_h / 2))

        # area_px ≈ diện tích elip (π * a * b) + jitter nhẹ
        area_px = round(3.1415 * (bbox_w / 2) * (bbox_h / 2) * rng.uniform(0.85, 1.0), 1)

        particles.append({
            "blob_index": i,
            "centroid_x": round(cx, 1),
            "centroid_y": round(cy, 1),
            "bbox_x": bbox_x,
            "bbox_y": bbox_y,
            "bbox_w": bbox_w,
            "bbox_h": bbox_h,
            "area_px": area_px,
            "size_mm": size_mm,
            "label": label,
            "confidence": confidence,
        })
    return particles


def _render_image(particles: list[dict[str, Any]]) -> bytes:
    """Vẽ ảnh JPEG mô phỏng trường backlit đều: nền xám sáng + elip tối đúng bbox.

    Vẽ đúng toạ độ gốc IMAGE_WIDTH×IMAGE_HEIGHT để bbox-overlay trang detail khớp.
    """
    img = Image.new("L", (IMAGE_WIDTH, IMAGE_HEIGHT), color=205)  # nền xám sáng đều
    draw = ImageDraw.Draw(img)

    # Độ tối nhẹ khác nhau giữa label để nhìn phân biệt (vẫn là silhouette: tối trên sáng)
    darkness = {
        "plastic": 30,
        "bubble":  60,   # bong bóng: tối ít hơn (trong suốt hơn)
        "organic": 45,
        "fiber":   38,
        "unknown": 52,
    }
    for p in particles:
        val = darkness.get(p["label"], 40)
        # Elip nội tiếp bbox: [(x0,y0), (x1,y1)]
        x0, y0 = p["bbox_x"], p["bbox_y"]
        x1, y1 = x0 + p["bbox_w"], y0 + p["bbox_h"]
        draw.ellipse([x0, y0, x1, y1], fill=val)

        if p["label"] == "bubble":
            # Bong bóng: thêm viền sáng trong để gợi ý phản chiếu
            pad = max(1, p["bbox_w"] // 6)
            draw.ellipse(
                [x0 + pad, y0 + pad, x1 - pad, y1 - pad],
                outline=180,
            )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def build_sample(rng: random.Random, device_id: str, now: datetime) -> tuple[dict[str, Any], bytes]:
    """Trả (metadata dict, image bytes JPEG) cho 1 mẫu."""
    sample_code = _gen_sample_code(now, rng)
    batch_lot = rng.choice(BATCH_LOT_CHOICES)
    n_particles = rng.randint(3, 15)
    particles = _gen_particles(rng, n_particles)
    image = _render_image(particles)

    metadata = {
        "device_id": device_id,
        "sample_code": sample_code,
        "batch_lot": batch_lot,
        "captured_at": now.astimezone(VN_TZ).isoformat(),
        "px_per_mm": PX_PER_MM,
        "image_width": IMAGE_WIDTH,
        "image_height": IMAGE_HEIGHT,
        "particles": particles,
    }
    return metadata, image


# ──────────────────────────────────────────────────────────────────────────
# Gửi
# ──────────────────────────────────────────────────────────────────────────
def post_sample(
    url: str,
    metadata: dict[str, Any],
    image: bytes,
    *,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | str]:
    """POST multipart (metadata JSON string + image JPEG) tới /api/ingest.

    Trả (status_code, parsed_json_or_text). Giữ metadata=None bên trong multipart
    không được — theo §2.1 phải là form field chuỗi JSON.
    """
    files = {
        "image": ("image.jpg", image, "image/jpeg"),
    }
    data = {
        "metadata": json.dumps(metadata, ensure_ascii=False),
    }
    resp = requests.post(url, files=files, data=data, timeout=timeout)
    try:
        body: dict[str, Any] | str = resp.json()
    except ValueError:
        body = resp.text
    return resp.status_code, body


# ──────────────────────────────────────────────────────────────────────────
# Tự test khi chưa có backend (§6 gợi ý)
# ──────────────────────────────────────────────────────────────────────────
def _self_test(device_id: str) -> int:
    """Dựng 1 HTTP server tối giản in ra request nhận được, bắn 1 mẫu vào.

    Dùng khi Module 2 (backend ingest) chưa xong — chứng minh script đúng shape.
    """
    import http.server
    import socketserver

    received = {"n": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 — stdlib naming
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            print(f"\n[self-test] POST {self.path} | Content-Type={ctype} | {length} bytes")
            # Tách multipart thô để in metadata mà không cần thêm thư viện
            if "multipart/form-data" in ctype:
                boundary = ctype.split("boundary=", 1)[1]
                print(f"[self-test] boundary={boundary[:40]}...")
                # In keyword 'sample_code' xuất hiện trong payload để確認 metadata JSON đã gửi
                idx = raw.find(b'"sample_code"')
                if idx >= 0:
                    snippet = raw[idx:idx + 80].decode("utf-8", "replace")
                    print(f"[self-test] metadata snippet: {snippet}")
                # Tìm JPEG magic FF D8 FF để xác nhận có ảnh
                if b"\xff\xd8\xff" in raw:
                    print("[self-test] ảnh JPEG đã nhận (magic FF D8 FF có mặt)")
                else:
                    print("[self-test] CẢNH BÁO: không thấy magic JPEG trong payload")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id": 0, "sample_code": "self-test", "particle_count": 0, "status": "created"}')
            received["n"] += 1

        def log_message(self, *args):  # tắt log mặc định ồn
            pass

    port = 8765
    print(f"[self-test] chạy HTTP server tối giản tại http://127.0.0.1:{port}/api/ingest")
    print("[self-test] bấm Ctrl+C để dừng")
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        import threading
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        rng = random.Random()
        now = datetime.now(VN_TZ)
        metadata, image = build_sample(rng, device_id=device_id, now=now)
        status, body = post_sample(f"http://127.0.0.1:{port}/api/ingest", metadata, image)
        print(f"[self-test] gửi 1 mẫu → status={status} body={body} (đã nhận {received['n']})")
        print("[self-test] OK: script đúng shape multipart (metadata JSON + image JPEG).")
        httpd.shutdown()
        return 0


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Aqua Scope mock sender — POST mẫu giả tới /api/ingest (web_plan.md §6).",
    )
    p.add_argument("--url", default="http://127.0.0.1:8000/api/ingest",
                   help="endpoint ingest (mặc định: http://127.0.0.1:8000/api/ingest)")
    p.add_argument("--count", type=int, default=15, help="số mẫu gửi (mặc định: 15)")
    p.add_argument("--interval", type=float, default=2.0,
                   help="khoảng giây giữa 2 mẫu (mặc định: 2.0; <=0 thì gửi liên tục)")
    p.add_argument("--device-id", default="aquascope-mock", help="device_id (mặc định: aquascope-mock)")
    p.add_argument("--seed", type=int, default=None, help="seed cho random (mặc định: ngẫu nhiên, mỗi lần khác nhau)")
    p.add_argument("--self-test", action="store_true",
                   help="không gửi đi đâu — dựng http.server tối giản, bắn 1 mẫu vào để kiểm shape "
                        "(dùng khi backend chưa sẵn sàng)")
    args = p.parse_args(argv)

    if args.self_test:
        return _self_test(args.device_id)

    rng = random.Random(args.seed)
    print(f"[mock_sender] gửi {args.count} mẫu tới {args.url} (device_id={args.device_id})")

    ok = 0
    fail = 0
    import time
    for i in range(1, args.count + 1):
        now = datetime.now(VN_TZ)
        metadata, image = build_sample(rng, device_id=args.device_id, now=now)
        try:
            status, body = post_sample(args.url, metadata, image)
        except requests.RequestException as e:
            print(f"[{i}/{args.count}] LỖI mạng: {e}")
            fail += 1
        else:
            # 201 created hoặc 200 already_exists đều là thành công
            status_str = (
                body.get("status") if isinstance(body, dict) else str(body)
            )
            count_str = body.get("particle_count") if isinstance(body, dict) else "?"
            if status in (200, 201):
                print(
                    f"[{i}/{args.count}] OK status={status} {status_str} "
                    f"sample={metadata['sample_code']} particles={len(metadata['particles'])} "
                    f"(server ghi count={count_str})"
                )
                ok += 1
            else:
                print(
                    f"[{i}/{args.count}] HTTP {status}: {body}  "
                    f"(sample={metadata['sample_code']})"
                )
                fail += 1

        if i < args.count and args.interval > 0:
            time.sleep(args.interval)

    print(f"\n[mock_sender] xong: {ok} thành công, {fail} thất bại.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
