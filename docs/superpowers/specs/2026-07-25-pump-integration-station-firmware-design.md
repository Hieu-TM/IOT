# Gộp điều khiển bơm L298N vào firmware trạm ESP32-CAM — Thiết kế

**Ngày:** 2026-07-25
**Trạng thái:** đã chốt thiết kế; code đã được viết trước bởi một agent khác → tài liệu này đồng thời là **hợp đồng để rà soát lại code đó**.

## 1. Vấn đề

Trước thay đổi này, hai chức năng nằm ở hai firmware trên hai board khác nhau:

| Chức năng | Firmware | Board |
|---|---|---|
| Phục vụ ảnh backlit (`/capture`) cho pipeline Roboflow trên PC | `firmware/aqua_scope_station/` | ESP32-CAM AI-Thinker |
| Chu trình bơm Stop-Flow qua L298N | `firmware/pump_l298n_xiao/` | XIAO ESP32-S3 Sense |

Trạm thật chỉ có **một** MCU (ESP32-CAM). Hai firmware trên hai board là trạng thái tạm của giai đoạn thử nghiệm, không phải thiết kế cuối. Mục tiêu: gộp state machine bơm vào firmware trạm, chạy trên đúng board ESP32-CAM.

## 2. Phạm vi

**Trong phạm vi:** module bơm mới trong firmware trạm; điều khiển qua HTTP + Serial; lưu cấu hình vào flash; báo trạng thái bơm trong `/device`.

**Ngoài phạm vi (cố ý):**
- Firmware **không** tự chụp ảnh theo pha bơm. `/capture` giữ nguyên hành vi hiện tại — PC chủ động pull.
- Không suy luận on-device. Roboflow/YOLO vẫn chạy trên PC (`ml/infer`).
- Không điều khiển đèn nền (đèn cắm thẳng, luôn sáng).
- Không viết script PC tự động bám pha SETTLING — chỉ *lộ* thông tin pha để sau này làm được.

## 3. Kiến trúc

Module mới `aqua_pump.h` / `aqua_pump.cpp`, theo đúng pattern module hoá đã có trong thư mục (`aqua_device.*`, `aqua_prefs.*`) — không nhét thẳng vào `.ino`.

**Ranh giới:** `aqua_pump` chỉ biết điều khiển bơm. Không biết camera, WiFi hay HTTP. Tích hợp HTTP nằm ở `app_httpd.cpp`, Serial ở `.ino`, lưu flash ở `aqua_prefs.cpp`.

State machine port từ `pump_l298n_xiao.ino` (đã kiểm chứng thực nghiệm về ramp chống búa nước):

```
FILLING (bơm chạy fillDuty) → SETTLING (bơm tắt, chụp ảnh)
   → FLUSHING (bơm chạy flushDuty) → COOLDOWN (bơm tắt) → lặp
```

Đồng hồ pha bắt đầu **sau** khi ramp xong, để trọn `fillMs`/`flushMs` thực sự ở mức cruise.

## 4. Phần cứng

| Hạng mục | Giá trị |
|---|---|
| Chân PWM → ENA của L298N | **GPIO13** |
| PWM | 20 kHz, 10-bit (duty 0..1023) |
| IN1 / IN2 | cố định 3.3V / GND — một chiều, không đảo |
| Nguồn L298N + bơm | adapter **12V/2A riêng**, GND chung với ESP32-CAM |

GPIO13 trên AI-Thinker không trùng chân camera (camera dùng 32, 0, 26, 27, 35, 34, 39, 36, 21, 19, 18, 5, 25, 23, 22; LED flash 4). GPIO13 chỉ trùng HS2_DATA3 của khe SD — firmware này không dùng khe SD.

### 4.1 Ràng buộc LEDC (quan trọng)

Camera driver `esp32-camera` tạo XCLK 20 MHz bằng LEDC, cấu hình **trực tiếp qua ESP-IDF** (`ledc_timer_config`/`ledc_channel_config`), nên **không** đăng ký vào Peripheral Manager của Arduino. Hệ quả: `ledcAttach()` của Arduino tin rằng mọi kênh đều rảnh và luôn cấp phát kênh 0.

Trên ESP32 classic điều này *tình cờ* không xung đột, vì Arduino kênh 0 thuộc nhóm **HIGH-speed** còn camera dùng nhóm **LOW-speed** — hai khối timer tách rời về phần cứng. Nhưng đây là **sự trùng hợp không có gì bảo đảm**, không phải thiết kế.

**Yêu cầu:** không được phụ thuộc vào sự trùng hợp đó một cách ngầm định. Kết quả `ledcAttach`/`ledcAttachChannel` **phải được kiểm tra** và báo lỗi rõ ràng nếu thất bại — nếu không, `ledcWrite` sẽ im lặng không làm gì và bơm không bao giờ chạy mà không có bất kỳ thông báo nào.

## 5. An toàn

| Yêu cầu | Lý do |
|---|---|
| GPIO13 bị ép LOW **ở dòng đầu tiên của `setup()`** | ENA thả nổi có thể được L298N đọc là HIGH → bơm chạy hết tốc suốt thời gian còn lại của `setup()` (camera init + WiFi timeout tới 20s). Ép LOW muộn là để hở đúng cửa sổ nguy hiểm đó. |
| `autoRunning` mặc định **TẮT** | Giai đoạn đang lắp/kiểm tra phần cứng mới: cắm điện không được tự xịt nước. Đổi sang tự chạy sau khi nghiệm thu trên board thật. |
| Ramp xuống trước khi tắt bơm | Cắt đột ngột gây búa nước. |

## 6. Giao diện điều khiển

### 6.1 HTTP — mở rộng `/control?var=…&val=…` sẵn có

| `var` | Miền giá trị | Ý nghĩa |
|---|---|---|
| `pump_auto` | 0 / 1 | tắt/bật chu trình auto |
| `pump_fill_ms` | > 0 | thời gian FILLING |
| `pump_settle_ms` | > 0 | thời gian SETTLING |
| `pump_flush_ms` | > 0 | thời gian FLUSHING |
| `pump_cooldown_ms` | > 0 | thời gian COOLDOWN |
| `pump_fill_duty` | 0..100 | duty cruise pha FILL |
| `pump_flush_duty` | 0..100 | duty pha FLUSH |
| `pump_ramp_up_ms` | ≥ 0 | thời gian vuốt lên |
| `pump_ramp_down_ms` | ≥ 0 | thời gian vuốt xuống |

**Giá trị ngoài miền phải bị từ chối rõ ràng (HTTP 500, giống nhánh `framesize`), không được im lặng bỏ qua rồi trả 200.** Trả 200 cho một lệnh không có hiệu lực chính là kiểu hỏng khó truy nhất — người dùng tin là đã đặt được.

### 6.2 Serial (115200)

Bộ lệnh 1 ký tự giữ nguyên từ `pump_l298n_xiao.ino`: `p ? 0 1 a f s x c u w d X r`.

Firmware trạm hiện **không** có bộ lệnh Serial camera nào, nên không có xung đột ký tự.

### 6.3 `/device` JSON

Thêm object `pump`: `auto`, `phase`, `duty`, `cycle_count`, `fill_ms`, `settle_ms`, `flush_ms`, `cooldown_ms`, `ramp_up_ms`, `ramp_down_ms`, `fill_duty`, `flush_duty`.

Trường `phase` để script PC sau này tự biết lúc nào là SETTLING mà gọi `/capture` đúng lúc nước đứng yên. Bản thân firmware không dùng trường này.

## 7. Lưu cấu hình

Mở rộng `aqua_prefs.*`: một nút `?var=save` lưu **cả** cấu hình camera lẫn cấu hình bơm; `?var=reset` xoá cả hai và đưa timing bơm về mặc định. Dùng NVS namespace riêng (`aquapump`) để không va khoá với namespace camera (`aquacam`).

## 8. Đồng thời (concurrency)

Đây là điểm rủi ro nhất của thiết kế và phải xử lý tường minh.

`aquaPumpTick()` chạy trong task `loop()`. Nhưng handler HTTP chạy trong **task httpd riêng**. Nghĩa là `/control?var=pump_auto` có thể gọi vào state machine **đồng thời** với `aquaPumpTick()`.

Nếu cả hai cùng vào `enterPhase()` → `rampDuty()`, hai task sẽ cùng ghi `ledcWrite`, cùng sửa `g_curDuty`/`g_phase`/`g_phaseStart` → duty cuối cùng sai, hoặc đồng hồ pha hỏng. Ngoài ra `rampDuty()` blocking ~350ms sẽ chặn task httpd.

**Yêu cầu:** đường HTTP **không được** tự chạy state machine hay ramp. Nó chỉ được đặt cờ/ghi tham số; mọi thay đổi pha và mọi lần ramp phải xảy ra trong `aquaPumpTick()` ở task `loop()`. Một điểm ghi duy nhất, không cần mutex.

Ghi tham số `PumpTiming` (uint32/uint8) từ task httpd là ghi nguyên tử trên ESP32 — chấp nhận được, không cần khoá.

## 9. Ảnh hưởng tới `loop()`

`loop()` cũ nghỉ 10s mỗi vòng (chia 10 lát 1s). State machine bơm cần độ phân giải cao hơn nhiều, nên `loop()` chuyển sang nhịp ngắn (~50ms) và in trạng thái WiFi theo mốc thời gian (`millis()`) thay vì theo số vòng lặp. Watchdog 30s/5s không bị chạm.

## 10. Tiêu chí nghiệm thu

Đây là checklist để rà soát code hiện có:

- [ ] A1. GPIO13 ép LOW ngay dòng đầu `setup()`, trước camera init và WiFi.
- [ ] A2. Kết quả gắn LEDC được kiểm tra; thất bại thì báo lỗi rõ ràng ra Serial.
- [ ] A3. Kênh LEDC không phụ thuộc ngầm vào sự trùng hợp HS/LS; lý do chọn được ghi đúng trong comment.
- [ ] A4. `autoRunning` mặc định false.
- [ ] A5. Đường HTTP không gọi ramp/đổi pha trực tiếp — chỉ đặt cờ, `aquaPumpTick()` thực thi.
- [ ] A6. Giá trị `/control` ngoài miền → HTTP 500, không phải 200.
- [ ] A7. `?var=save` lưu cả camera + bơm; `?var=reset` xoá cả hai.
- [ ] A8. `/device` chứa object `pump` đầy đủ, JSON hợp lệ, không tràn buffer.
- [ ] A9. Bộ lệnh Serial hoạt động, không xung đột.
- [ ] A10. Comment trong code mô tả đúng code (không còn dẫn chiếu sai file nguồn/kênh LEDC).
- [ ] A11. Không còn tham chiếu treo tới `firmware/pump_l298n_xiao/` đã xoá trong tài liệu.
- [ ] A12. Biên dịch sạch bằng `arduino-cli` cho board AI Thinker ESP32-CAM.

## 11. Rủi ro còn lại (không xử lý trong phạm vi này)

- `fillDuty = 55%` là **giá trị ước lượng khởi điểm, không phải kết quả đo**. Phải dò lại trên bơm thật bằng lệnh `d`. L298N sụt ~1.8–2.5V nên bơm chỉ nhận ~9.5–10V.
- Nghiệm thu thực tế trên board vẫn cần làm tay; không có test tự động cho firmware này.
