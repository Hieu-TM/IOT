"""Chẩn đoán ảnh trắng xóa / hỏng trên ESP32-CAM.

Chạy một lần, trả lời dứt điểm câu hỏi: cảm biến có PHẢN ỨNG với phơi sáng không?

    python diagnose.py --host 192.168.1.50

Nếu ảnh tối dần khi giảm exposure  -> chỉ là canh sáng, có số liệu để canh.
Nếu ảnh trắng ở MỌI mức exposure   -> cảm biến không nhìn thấy cảnh; chỉnh
                                       thông số bao nhiêu cũng vô ích, phải
                                       soi phần cứng/ánh sáng.

Công cụ này KHÔNG sửa gì trên board ngoài các thông số nó đang thử.
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
import time

import requests
from PIL import Image

# Dải exposure quét: từ tối nhất tới sáng nhất mà OV2640 nhận.
EXPOSURE_SWEEP = [0, 25, 50, 100, 200, 400, 800, 1200]

# Ngưỡng coi là "cháy trắng": >98% điểm ảnh nằm sát trần.
SATURATED_PCT = 98.0
NEAR_WHITE = 250


def _force_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


class Board:
    """Bọc các endpoint của firmware. Mọi lỗi mạng thành RuntimeError có ngữ cảnh."""

    def __init__(self, host: str, port: int = 80, timeout: float = 15.0):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout
        self.session = requests.Session()

    def status(self) -> dict:
        r = self.session.get(f"{self.base}/status", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def control(self, var: str, val) -> None:
        r = self.session.get(f"{self.base}/control", params={"var": var, "val": val},
                             timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError(f"đặt {var}={val} thất bại: HTTP {r.status_code}")

    def capture(self) -> Image.Image:
        r = self.session.get(f"{self.base}/capture", params={"_cb": time.time()},
                             timeout=self.timeout)
        r.raise_for_status()
        if not r.content.startswith(b"\xff\xd8"):
            raise RuntimeError(f"/capture không trả JPEG (bắt đầu {r.content[:4]!r})")
        return Image.open(io.BytesIO(r.content))


def measure(img: Image.Image) -> dict:
    """Thống kê độ sáng của một ảnh, tính trên kênh xám."""
    gray = img.convert("L")
    hist = gray.histogram()
    total = sum(hist)

    mean = sum(i * n for i, n in enumerate(hist)) / total
    saturated = sum(hist[NEAR_WHITE:]) / total * 100
    black = sum(hist[:6]) / total * 100

    # Độ lệch chuẩn: ảnh trắng phẳng có stdev ~0. Còn dấu vết cấu trúc thì > 0.
    var = sum(n * (i - mean) ** 2 for i, n in enumerate(hist)) / total
    return {
        "mean": mean,
        "stdev": var ** 0.5,
        "sat_pct": saturated,
        "black_pct": black,
        "size": img.size,
    }


def fmt(row: dict) -> str:
    return (f"mean={row['mean']:6.1f}  stdev={row['stdev']:5.1f}  "
            f"cháy trắng={row['sat_pct']:5.1f}%  đen={row['black_pct']:5.1f}%")


def run(board: Board) -> int:
    print("=" * 72)
    print("1. TRẠNG THÁI HIỆN TẠI")
    print("=" * 72)
    st = board.status()
    keys = ["framesize", "quality", "aec", "aec2", "agc", "aec_value", "agc_gain",
            "gainceiling", "brightness", "contrast", "special_effect",
            "lamp", "autolamp", "xclk", "cam_name"]
    for k in keys:
        if k in st:
            print(f"   {k:<15} = {st[k]}")

    lamp = st.get("lamp", -1)
    autolamp = st.get("autolamp", 0)
    lamp_suspect = lamp not in (-1, 0) or autolamp
    if lamp_suspect:
        print()
        print(f"   >>> ĐÈN GPIO4: lamp={lamp}, autolamp={autolamp}")
        print("   >>> Đèn flood nằm NGAY CẠNH ống kính. Trong ống chụp kín nó bật")
        print("   >>> là trắng xóa mọi khung hình. Bước 2 sẽ tắt hẳn để kiểm chứng.")

    print()
    print("=" * 72)
    print("2. TẮT ĐÈN GPIO4 + TẮT MỌI CHẾ ĐỘ TỰ ĐỘNG")
    print("=" * 72)
    for var, val in [("autolamp", 0), ("lamp", 0), ("aec", 0), ("aec2", 0),
                     ("agc", 0), ("agc_gain", 0), ("gainceiling", 0),
                     ("brightness", 0), ("contrast", 0), ("special_effect", 0)]:
        try:
            board.control(var, val)
        except RuntimeError as exc:
            print(f"   (bỏ qua {var}: {exc})")
    time.sleep(0.5)
    print("   Xong. Giờ mọi thay đổi độ sáng chỉ còn do exposure.")

    print()
    print("=" * 72)
    print("3. QUÉT EXPOSURE (đây là phép đo quyết định)")
    print("=" * 72)
    rows = []
    for value in EXPOSURE_SWEEP:
        board.control("aec_value", value)
        time.sleep(0.6)          # cho sensor kịp áp giá trị mới
        board.capture()          # bỏ 1 khung: khung đầu thường còn thông số cũ
        time.sleep(0.2)
        row = measure(board.capture())
        rows.append((value, row))
        print(f"   exposure={value:5d}  {fmt(row)}")

    print()
    print("=" * 72)
    print("4. KẾT LUẬN")
    print("=" * 72)

    means = [r["mean"] for _, r in rows]
    spread = max(means) - min(means)
    darkest_val, darkest = min(rows, key=lambda kv: kv[1]["mean"])
    all_blown = all(r["sat_pct"] > SATURATED_PCT for _, r in rows)

    if spread < 5 and all_blown:
        print("   ✗ Ảnh cháy trắng ở MỌI mức exposure, độ sáng gần như không đổi")
        print(f"     (chênh lệch mean chỉ {spread:.1f} mức xám).")
        print()
        print("   => Cảm biến KHÔNG phản ứng với exposure. Đây KHÔNG phải lỗi canh sáng.")
        print("      Nguyên nhân nằm ở một trong các chỗ sau, xếp theo khả năng:")
        print("      1. Ánh sáng lọt vào quá mạnh (đèn nền chiếu thẳng ống kính,")
        print("         hoặc ống chụp hở sáng). Thử che hẳn ống kính rồi chạy lại")
        print("         lệnh này — nếu vẫn trắng thì loại bỏ hẳn nguyên nhân ánh sáng.")
        print("      2. Cáp ribbon camera lỏng/bẩn — rút ra cắm lại, gạt khóa nâu.")
        print("      3. Module camera hỏng.")
        return 1

    if spread < 5:
        print(f"   ? Độ sáng gần như không đổi (chênh {spread:.1f}) nhưng không cháy trắng.")
        print("     Bất thường — gửi lại toàn bộ output này.")
        return 1

    print(f"   ✓ Cảm biến CÓ phản ứng với exposure (mean chạy từ "
          f"{min(means):.0f} đến {max(means):.0f}).")
    print("   => Đây chỉ là bài toán canh sáng, phần cứng bình thường.")
    print()

    # Ảnh backlit tốt: nền sáng đều nhưng CHƯA cháy, còn chỗ cho hạt tối nổi lên.
    good = [(v, r) for v, r in rows if 120 <= r["mean"] <= 210 and r["sat_pct"] < 50]
    if good:
        value, row = good[-1]
        print(f"   Mức nên dùng: exposure = {value}   ({fmt(row)})")
        print("   Nền sáng đều mà chưa cháy — hạt tối còn chỗ để nổi lên.")
    else:
        print(f"   Chưa mức nào cho nền lý tưởng. Tối nhất là exposure={darkest_val}")
        print(f"   ({fmt(darkest)}).")
        if darkest["mean"] > 210:
            print("   Vẫn quá sáng ở mức thấp nhất => ĐÈN NỀN quá mạnh.")
            print("   Giảm dòng LED, hoặc thêm lớp khuếch tán/giấy can.")
        else:
            print("   Chỉnh quanh mức đó bằng slider Exposure trên web.")

    if lamp_suspect:
        print()
        print("   LƯU Ý: đèn GPIO4 đang bật lúc bắt đầu đo. Lệnh này đã tắt nó,")
        print("   nhưng nó sẽ bật lại nếu bạn kéo slider Light. Giữ Light = 0.")
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    p = argparse.ArgumentParser(description="Chẩn đoán ảnh trắng xóa trên ESP32-CAM.")
    p.add_argument("--host", required=True, help="IP của ESP32-CAM")
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--timeout", type=float, default=15.0)
    args = p.parse_args(argv)

    board = Board(args.host, args.port, args.timeout)
    try:
        return run(board)
    except requests.RequestException as exc:
        print(f"Không nối được tới board: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
