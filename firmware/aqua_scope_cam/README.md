# Aqua Scope Cam — Firmware

Firmware camera tùy chỉnh cho **XIAO ESP32-S3 Sense** (cảm biến **OV3660**, 3MP), thay cho firmware
Matchboxscope (vốn dành cho kính hiển vi). Tối ưu cho **ảnh backlit silhouette**:
nền sáng đều, hạt rác 1–5mm hiện lên thành **bóng đen** để đếm & đo kích thước.

## Vì sao không dùng firmware Matchboxscope?

Firmware Matchboxscope để auto-exposure và tối ưu cho vật soi gần dưới kính hiển
vi. Với đèn nền (backlight) của ta, auto-exposure sẽ **kéo nền cháy trắng** và mất
hạt. Firmware này **ép phơi sáng thủ công** và **lưu cứng** thông số vào flash.

## Tính năng

- **Ép phơi sáng thủ công**: TẮT AEC / AEC-DSP / AGC; đặt Gain=0 + Exposure thấp
  → nền không cháy trắng (đúng theo `CLAUDE.md`).
- **Lưu cứng cấu hình** vào flash (NVS/`Preferences`): cắm điện là chạy đúng thông
  số đã chỉnh, không phải canh lại mỗi lần.
- **Chọn độ phân giải tự do**: một dropdown QVGA→QXGA (dùng chung cho stream và
  chụp), đổi ngay khi test để so sánh — không khóa cứng vào 2 chế độ.
- Chỉnh qua **Web UI** (slider trực quan) **hoặc Serial**.
- Có sẵn **hook `runVision()`** để nhúng computer vision on-device về sau.

## Cài đặt (Arduino IDE)

1. Cài **Arduino IDE** + gói board **esp32 by Espressif** (Boards Manager, ≥ 3.0).
2. Mở `aqua_scope_cam.ino` (giữ nguyên `camera_pins.h` cùng thư mục).
3. Trong **Tools**:
   - Board: **XIAO_ESP32S3**
   - **PSRAM: OPI PSRAM**  ← *bắt buộc*, không bật thì camera không init được
   - Partition Scheme: **Huge APP (3MB No OTA/1MB SPIFFS)**
4. Cắm board qua USB-C, chọn đúng Port, bấm **Upload**.
   - Nếu upload lỗi: giữ nút **BOOT** khi cắm để vào bootloader.

## Cách dùng

### Qua WiFi (khuyến nghị — canh sáng bằng mắt)
1. Mặc định board phát WiFi **`AquaScope`** (mật khẩu `aquascope`).
2. Nối điện thoại/laptop vào WiFi đó → mở trình duyệt tới **http://192.168.4.1**
3. Bật đèn nền, kéo slider **Exposure/Gain** đến khi nền **xám đều**, hạt = **bóng
   đen rõ nét** (không có đốm sáng chói, camera không thấy đèn LED trần).
4. Chọn **Độ phân giải** trong dropdown (QVGA→QXGA) để so sánh khi test; bấm
   **Chụp 1 ảnh** để xem ảnh ở đúng độ phân giải đang chọn.
5. Ưng ý → bấm **LƯU CỨNG vào flash**. Lần sau cắm điện tự chạy đúng thông số
   (kể cả độ phân giải đã chọn).
6. Lỡ chỉnh nhầm → bấm **Khôi phục mặc định** (có hỏi xác nhận): mọi thông số về
   giá trị gốc và cấu hình đã lưu trong flash bị xóa, giao diện tự làm mới.

> Muốn nối vào router nhà thay vì AP: sửa `USE_STA = true` và điền `STA_SSID/STA_PASS`.

### Qua Serial (115200 baud)
| Lệnh | Ý nghĩa |
|------|---------|
| `t100` | đặt exposure = 100 |
| `g0`   | đặt gain = 0 |
| `b0` / `c1` | brightness / contrast |
| `q12`  | JPEG quality |
| `y1`   | grayscale on (0 = màu) |
| `f12`  | đổi độ phân giải (5=QVGA, 8=VGA, 9=SVGA, 10=XGA, 12=SXGA, 13=UXGA, 17=QXGA) |
| `p`    | in cấu hình hiện tại |
| `s`    | **lưu cứng** vào flash |
| `r`    | **khôi phục mặc định** (về giá trị gốc + xóa cấu hình đã lưu) |
| `x`    | chụp 1 frame analysis (chạy `runVision`) |

### Endpoint HTTP (để PC lấy ảnh chạy CV)
- `GET /stream`  — MJPEG preview (ở độ phân giải đang chọn)
- `GET /capture` — chụp **1 ảnh JPEG** ở độ phân giải hiện tại (đây là ảnh để chạy CV)
- `GET /control?var=framesize&val=12` — đổi độ phân giải (giá trị enum như bảng serial)
- `GET /control?var=exposure&val=100` — chỉnh runtime
- `GET /control?var=save&val=1` — lưu cứng
- `GET /control?var=reset&val=1` — khôi phục mặc định + xóa cấu hình đã lưu
- `GET /status`  — JSON cấu hình

## Firmware có ảnh hưởng tới computer vision sau này không?

**Có — theo hướng tích cực, và có hai đường đi:**

**Đường A — CV chạy trên PC (dễ, nên làm trước):**
Firmware này đã phục vụ sẵn `GET /capture` trả ảnh **SXGA JPEG chất lượng cao**.
Script Python/OpenCV trên máy tính chỉ việc `requests.get(".../capture")` → threshold
→ `connectedComponentsWithStats` → đếm + đo diện tích hạt. **Không cần sửa firmware.**

**Đường B — CV chạy on-device trên ESP32-S3 (đúng mục tiêu cuối trong `CLAUDE.md`):**
Có sẵn hàm `runVision(camera_fb_t* fb)` — mỗi lần chụp analysis firmware gọi hàm này.
Chỉ cần điền phần xử lý vào đó. Vài lưu ý firmware giúp việc này:
- Ảnh đã ép **grayscale** (`grayscale=1`) → threshold trực tiếp, đỡ 1 bước.
- Frame trả về là **JPEG**; để làm CV trên chip cần **giải nén sang buffer thô**
  bằng `jpg2rgb565`/`fmt2rgb888` (có trong `esp32-camera`) hoặc chuyển
  `pixel_format` sang `PIXFORMAT_GRAYSCALE` khi chụp analysis.
- **PSRAM** (đã bật) là chỗ chứa buffer ảnh lớn để chạy connected-components — đây
  là lý do bật OPI PSRAM là bắt buộc.

Tóm lại: firmware này **được thiết kế để không chặn CV** — hook và endpoint đã có,
độ phân giải analysis đủ cao (~14 px/mm ở 40mm), ảnh xám sẵn sàng. Firmware
Matchboxscope thì ngược lại: auto-exposure của nó sẽ phá dữ liệu đầu vào của CV.

## Quản lý nhiệt & nguồn — PROTOTYPE (chưa nhúng vào `.ino`)

> **Trạng thái:** đây là *bản phác thảo phần mềm*, chưa có trong `aqua_scope_cam.ino`.
> Firmware hiện tại chạy **stream MJPEG liên tục** (port 81) + WiFi luôn bật → đây
> chính là nguyên nhân **board nóng và có thể sập** khi vận hành lâu. Mục này gom
> các cách khắc phục **thuần phần mềm** để triển khai ở bước sau.

### Chẩn đoán gốc rễ
| Nguồn nhiệt/tải | Mức | Vì sao |
|---|---|---|
| WiFi radio phát liên tục (stream) | 🔴 lớn nhất | dòng đỉnh 300–500mA, sinh nhiệt nhiều nhất trên board |
| Camera grab frame không nghỉ (vòng `while` trong `stream_handler`) | 🟠 vừa | XCLK 20MHz + DMA + JPEG encoder chạy liên tục |
| CPU 240MHz + nhiệt bị nhốt trong ống Imaging Tube kín | 🟡 | ống đục kín chặn sáng cũng nhốt nhiệt |

> "Sập" thường là **brownout** (WiFi TX + capture cùng lúc làm sụt 3.3V → reset),
> chứ không phải nhiệt trực tiếp. Fix phần cứng (tụ bulk + nguồn 5V ≥2A) nằm ngoài
> phạm vi mục này; ở đây chỉ xử lý phần mềm.

### Ý tưởng cốt lõi: bám chu trình Stop-Flow, KHÔNG stream liên tục
Vận hành thật chỉ cần **1 ảnh/chu kỳ** (lúc nước đứng yên). Giữa các chu kỳ là thời
gian nghỉ để hạ nhiệt. Chuyển từ "stream mãi mãi" sang **máy trạng thái duty-cycle**:

```cpp
// PROTOTYPE — máy trạng thái Stop-Flow thay cho stream liên tục
enum Phase { FILLING, SETTLING, CAPTURING, DRAINING, COOLDOWN };
Phase phase = FILLING;
uint32_t tPhase = 0;
bool streamOnDemand = false;   // stream CHỈ bật khi đang canh sáng qua web

void loopCycle() {
  handleSerial();
  uint32_t now = millis();
  switch (phase) {
    case SETTLING:                       // nước đã đứng yên
      if (now - tPhase > 1500) {         // chờ lắng 1.5s
        camera_fb_t* fb = esp_camera_fb_get();   // <-- CHỤP ĐÚNG 1 FRAME
        if (fb) { runVision(fb); esp_camera_fb_return(fb); }
        phase = DRAINING; tPhase = now;
      }
      break;
    case COOLDOWN:                       // nghỉ giữa chu kỳ: đây là lúc hạ nhiệt
      if (now - tPhase > COOLDOWN_MS) { phase = FILLING; tPhase = now; }
      break;
    // ... FILLING / CAPTURING / DRAINING điều khiển bơm & van
  }
}
```

### Các đòn bẩy phần mềm (xếp theo hiệu quả)
1. **Tắt stream ở chế độ production.** Chỉ chạy `stream_handler` khi `streamOnDemand`
   bật (lúc canh sáng); vận hành thật thì **không đăng ký server port 81**, hoặc dừng
   nó sau khi đã lưu cấu hình. Đây là đòn giảm nhiệt lớn nhất.
2. **WiFi modem-sleep / tắt giữa chu kỳ.**
   ```cpp
   WiFi.setSleep(WIFI_PS_MAX_MODEM);        // luôn cho radio ngủ khi rảnh
   // hoặc quyết liệt hơn: WiFi.mode(WIFI_OFF) ở COOLDOWN, bật lại + gửi kết quả rồi tắt
   WiFi.setTxPower(WIFI_POWER_11dBm);        // hạ công suất phát nếu router/điện thoại ở gần
   ```
   Vì CV chạy on-device chỉ xuất **con số đếm + phân bố kích thước** (vài chục byte),
   WiFi chỉ cần bật burst ngắn mỗi chu kỳ — hoặc bỏ hẳn, gửi qua Serial/USB.
3. **Hạ XCLK 20MHz → 10MHz** trong `initCamera()` (`c.xclk_freq_hz = 10000000;`) —
   giảm nhiệt sensor rõ, đổi lại chụp chậm hơn chút (chấp nhận được với Stop-Flow).
4. **Giữ camera đã init, chỉ grab khi cần** — KHÔNG `esp_camera_deinit()/init()` lặp
   mỗi vòng (reinit chậm + phải ổn định lại sensor). Camera idle giữa các lần chụp.
5. **Giám sát nhiệt nội + thermal throttle** (ESP32-S3 có cảm biến nhiệt on-chip):
   ```cpp
   #include "driver/temperature_sensor.h"
   // nếu t > ~75°C thì kéo dài COOLDOWN_MS / bỏ 1 chu kỳ cho hạ nhiệt
   ```
6. **Task Watchdog để tự phục hồi khi treo** (`esp_task_wdt_init()` + `..._reset()`
   trong vòng lặp) → treo thì reset lại thay vì đơ cứng.
7. **Xử lý `esp_camera_fb_get()` trả NULL có kiểm soát** (retry giới hạn) để một lần
   chụp lỗi không làm kẹt vòng lặp — hiện `stream_handler` gặp NULL là `break` cả stream.

### Ranh giới phạm vi
- **Phần mềm (mục này):** duty-cycle, tắt stream, WiFi sleep, XCLK, throttle, watchdog.
- **Phần cứng (làm riêng, không thuộc firmware):** tụ bulk 470–1000µF, nguồn 5V ≥2A,
  heatsink lên chip, **lỗ thông gió bẫy-sáng ở top cap** (sẽ thêm hằng số vào OpenSCAD).

## Thông số mặc định (chỉnh trong `.ino`, biến `cfg`)

| Tham số | Mặc định | Ghi chú |
|---------|----------|---------|
| exposure | 100 | slider chính, tăng nếu ảnh tối |
| gain | 0 | backlit nên để 0 |
| contrast | 1 | tách bóng hạt |
| grayscale | 1 | 1 = xám (tốt cho CV) |
| framesize | VGA (640×480) | độ phân giải dùng chung, đổi tự do tới **QXGA 2048×1536** khi test |
| vflip | 1 | OV3660 mặc định ảnh lật ngược → để 1 cho đúng chiều |

## Ghi chú riêng cho OV3660 (khác OV2640)

- OV3660 là **3MP**, phân giải tối đa **QXGA 2048×1536** (OV2640 chỉ UXGA 1600×1200).
  Buffer camera đã cấp phát ở QXGA nên dropdown có thể chọn lên tới QXGA để đo
  hạt 1mm nét hơn (đổi lại CV nặng hơn, RAM/thời gian nhiều hơn).
- Driver `esp32-camera` **tự nhận diện** OV3660 qua SCCB — không cần đổi code init.
- OV3660 trả ảnh **lật ngược mặc định**, nên firmware để `vflip=1`. Với đếm hạt thì
  chiều ảnh không ảnh hưởng kết quả CV, nhưng để đúng chiều khi xem preview.
