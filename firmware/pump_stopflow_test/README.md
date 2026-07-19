# Pump Stop-Flow Test — Firmware

> **Công cụ test bơm độc lập** — không phải firmware của trạm. Firmware chính
> thức là [`firmware/aqua_scope_station/`](../aqua_scope_station/).

Firmware **test độc lập**, chỉ để kiểm tra relay + bơm RS365 12V chạy đúng chu
trình **Stop-Flow** trước khi ráp vào khay thật. Không đụng tới camera/CV.

## Phần cứng

- Board: **ESP32-CAM (AI-Thinker)** hoặc bất kỳ board ESP32 nào có GPIO13 rảnh.
  **Cấp nguồn riêng cho ESP32** (5V qua USB/FTDI) — không rút 5V từ nguồn 12V bơm.
- Module relay 1 kênh, opto-cách ly, **active-LOW** (theo BOM đã chốt trong dự án).
- Bơm màng **RS365 12V** + adapter **12V/2A**.
- Tụ gốm **0.1µF** hàn ngang 2 cực bơm (chống nhiễu chổi than — bắt buộc).

## Đấu nối

| Relay | Nối tới |
|---|---|
| IN | **GPIO13** |
| VCC | 5V (ESP32-CAM) |
| GND | GND chung (ESP32 **+** nguồn 12V bơm) |
| COM | 12V+ (adapter) |
| NO | Bơm (+) |

Bơm (−) → GND 12V. **GND phải chung** giữa ESP32 và nguồn 12V.

> **Vì sao GPIO13?** Trên AI-Thinker, GPIO13 không trùng chân camera (xem
> `camera_pins.h` trong `firmware/Esp32 cam/CameraWebServer/`). Nó chỉ trùng
> SD card 4-bit (`HS2_DATA3`) — không dùng khe SD trong bài test này thì dùng
> thoải mái.

> **An toàn active-LOW:** relay đóng (bơm chạy) khi GPIO ở mức LOW. Firmware
> kéo chân lên HIGH (tắt) **ngay dòng đầu tiên của `setup()`**, trước khi làm
> gì khác, để bơm không tự chạy lúc boot/nạp code.

## Cài đặt & nạp

1. Arduino IDE + gói board **esp32 by Espressif**.
2. Board: **AI Thinker ESP32-CAM** (hoặc board ESP32 tương ứng).
3. Mở `pump_stopflow_test.ino`, chọn đúng Port, **Upload**.

## Chu trình mặc định (chỉnh được qua Serial, không cần nạp lại)

```
FILLING (bơm ON, 5s) → SETTLING (bơm OFF, 2s) → FLUSHING (bơm ON mạnh, 5s)
→ COOLDOWN (bơm OFF, 3s) → lặp lại
```

Mở **Serial Monitor 115200 baud** để xem log chuyển pha và gõ lệnh:

| Lệnh | Ý nghĩa |
|---|---|
| `p` | in trạng thái hiện tại |
| `0` / `1` | tạm dừng auto, ép bơm tắt/bật (test tay) |
| `a` | chạy lại auto Stop-Flow |
| `f3000` / `s1500` / `x8000` / `c5000` | chỉnh thời gian fill/settle/flush/cooldown (ms) |
| `r` | khôi phục timing mặc định |
| `?` | in lại menu |

## Sau khi test xong

Nếu relay/bơm chạy đúng nhịp, bước tiếp theo là gộp state machine này vào
`aqua_scope_cam.ino` (thêm điều khiển đèn nền + gọi chụp ảnh ở pha `SETTLING`,
đúng theo chu trình Stop-Flow trong `README.md`/`CLAUDE.md` gốc của dự án).
