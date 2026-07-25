# Kế hoạch: rà soát & sửa lỗi phần gộp bơm L298N vào firmware trạm

**Spec:** [`2026-07-25-pump-integration-station-firmware-design.md`](../specs/2026-07-25-pump-integration-station-firmware-design.md)

**Bối cảnh:** code đã được một agent khác viết trước (`aqua_pump.cpp/h` mới; sửa `app_httpd.cpp`, `aqua_prefs.*`, `aqua_scope_station.ino`; xoá `firmware/pump_l298n_xiao/`). Kế hoạch này **không viết lại từ đầu** — chỉ đối chiếu với spec, sửa chỗ sai, giữ nguyên chỗ đúng.

**Đánh giá tổng thể:** phần khung đúng — module hoá đúng pattern, state machine port chính xác, NVS namespace riêng, `/device` có object pump, `autoRunning` mặc định TẮT. Lỗi tập trung ở **thứ tự khởi tạo**, **xử lý lỗi bị bỏ qua**, và **đồng thời giữa task HTTP và task loop**.

---

## Bảng lỗi

| # | Mức | Vi phạm | Mô tả |
|---|---|---|---|
| F1 | 🔴 Cao | A1 | GPIO13 chỉ được ép LOW ở cuối `setup()` |
| F2 | 🔴 Cao | A2 | Kết quả `ledcAttach()` bị bỏ qua |
| F3 | 🔴 Cao | A5 | Handler HTTP tự chạy ramp/đổi pha → tranh chấp với `aquaPumpTick()` |
| F4 | 🟠 Vừa | A6 | `/control` giá trị ngoài miền bị im lặng bỏ qua, vẫn trả 200 |
| F5 | 🟡 Thấp | A3, A10 | Nhiều comment mô tả sai code |
| F6 | 🟡 Thấp | A11 | `HUONG_DAN_LAP_RAP.md` còn trỏ tới firmware đã xoá |

---

### F1 — GPIO13 thả nổi gần hết `setup()` 🔴

`aquaPumpInit()` được gọi ở **cuối** `setup()`, sau `initCamera()`, sau `connectWiFi()` (timeout tới **20 giây**), và thậm chí sau `startCameraServer()`.

Suốt thời gian đó GPIO13 chưa hề được lái. ENA thả nổi có thể được L298N đọc là HIGH → **bơm chạy hết tốc ~20+ giây mỗi lần cấp điện**.

Nặng hơn: `setup()` có nhánh thoát sớm khi camera lỗi —

```cpp
if (!initCamera()) { Serial.println("Dừng lại: ..."); return; }
```

→ camera hỏng thì `aquaPumpInit()` **không bao giờ chạy**, GPIO13 không bao giờ được lái, bơm chạy vô thời hạn.

**Sửa:** tách phần ép chân an toàn ra thành `aquaPumpPreInit()` và gọi ở **dòng đầu tiên** của `setup()`, trước cả `Serial.begin()`. Phần gắn LEDC vẫn ở `aquaPumpInit()` giữ nguyên vị trí cuối `setup()` (nó cần chạy sau camera init).

- [x] Thêm `aquaPumpPreInit()` vào `aqua_pump.h`/`.cpp`: chỉ `pinMode(OUTPUT)` + `digitalWrite(LOW)`.
- [x] Gọi nó ở dòng đầu `setup()` trong `.ino`.
- [x] Cập nhật comment `aqua_pump.h` cho khớp mô hình hai giai đoạn.

---

### F2 — `ledcAttach()` thất bại trong im lặng 🔴

```cpp
ledcAttach(PUMP_PIN, PWM_FREQ, PWM_BITS);   // trả bool — bị bỏ qua
pumpDuty(0);
```

Nếu gắn thất bại (hết timer, hoặc chân đã thuộc bus khác), mọi `ledcWrite()` sau đó **không làm gì cả**. Bơm không bao giờ chạy, Serial không báo gì, `/device` vẫn hồn nhiên báo `duty: 55`. Đây đúng là kiểu hỏng khó truy nhất mà spec §4.1 cấm.

**Sửa:** kiểm tra giá trị trả về, in lỗi rõ ràng, và giữ một cờ `g_pwmReady` để `/device` phản ánh trung thực.

- [x] `aquaPumpInit()` kiểm tra kết quả gắn LEDC, in `[pump][LỖI]` nếu thất bại.
- [x] Thêm `g_pwmReady`; `pumpDuty()` không ghi khi chưa sẵn sàng.
- [x] `/device` thêm trường `pwm_ready`.

---

### F3 — Tranh chấp giữa task HTTP và task `loop()` 🔴

`/control?var=pump_auto&val=1` chạy trong **task httpd**, gọi thẳng `aquaPumpSetAuto()` → `enterPhase()` → `rampDuty()` (blocking 250–350ms, có `delay()`).

Cùng lúc đó `aquaPumpTick()` chạy trong **task `loop()`** và cũng có thể gọi `enterPhase()` → `rampDuty()`.

Hai task cùng ghi `g_phase`, `g_curDuty`, `g_phaseStart` và cùng gọi `ledcWrite` → duty kết thúc sai mức, hoặc đồng hồ pha bị đặt lại giữa chừng. Ngoài ra ramp blocking chặn task httpd 350ms.

**Sửa:** đường HTTP chỉ **đặt yêu cầu**, không thực thi. Mọi ramp/đổi pha xảy ra trong `aquaPumpTick()` — một điểm ghi duy nhất, không cần mutex.

- [x] Thêm `aquaPumpRequestAuto(bool)` — chỉ ghi một `volatile bool g_autoRequest` + cờ `g_autoRequestPending`.
- [x] `aquaPumpTick()` xử lý yêu cầu đang chờ ở đầu mỗi lần gọi.
- [x] `app_httpd.cpp` gọi `aquaPumpRequestAuto()` thay vì `aquaPumpSetAuto()`.
- [x] Serial (chạy trong `loop()`, cùng task với tick) vẫn được gọi trực tiếp — an toàn.

---

### F4 — Giá trị ngoài miền trả 200 OK 🟠

```cpp
} else if (!strcmp(variable, "pump_fill_duty")) {
  if (val >= 0 && val <= 100) aquaPumpTiming()->fillDuty = (uint8_t)val;
}
```

`pump_fill_duty=150` → không đặt gì, **vẫn trả 200**. Người dùng tin là đã đặt được. Nhánh `framesize` ngay phía trên xử lý đúng (`res = -1` → HTTP 500); nhánh pump thì không — thiếu nhất quán ngay trong cùng một handler.

- [x] Mọi nhánh `pump_*` đặt `res = -1` khi giá trị ngoài miền.

---

### F5 — Comment mô tả sai code 🟡

| Chỗ | Comment nói | Thực tế |
|---|---|---|
| `aqua_pump.cpp` đầu file | "dùng LEDC_CHANNEL_7 (channel 0 đã bị camera chiếm)" | Code gọi `ledcAttach()` — cấp phát tự động, và nó chọn **đúng channel 0** |
| `.ino` chỗ gọi `aquaPumpInit()` | "ledcAttach tự chọn channel khác" | Sai — `ledcAttach` chọn channel 0 |
| `aqua_pump.cpp` đầu file | "Port từ `pump_pwm_test.ino`" | Port từ `pump_l298n_xiao.ino` (bản L298N) |
| `aqua_pump.h` | "Gọi TRƯỚC khi gắn bất cứ gì vào GPIO13" | `.ino` gọi sau camera init |

Lý do thật khiến nó chạy được: Arduino channel 0 thuộc nhóm **HIGH-speed**, còn `esp32-camera` tạo XCLK ở nhóm **LOW-speed** — hai khối timer tách rời. Đây là sự trùng hợp, không phải thiết kế, và comment hiện tại dạy sai cho người đọc sau.

- [x] Viết lại các comment trên cho khớp code và ghi đúng lý do HS/LS.

---

### F6 — Tài liệu trỏ tới firmware đã xoá 🟡

`firmware/pump_l298n_xiao/` đã bị xoá nhưng `HUONG_DAN_LAP_RAP.md` còn 3 chỗ trỏ tới (dòng ~12, ~150, ~211), trong đó có câu "✅ Điều khiển bơm — đã có firmware" chỉ vào file không còn tồn tại.

- [x] Cập nhật 3 chỗ đó sang `firmware/aqua_scope_station/` + bộ lệnh mới.

---

## Nghiệm thu

- [x] Biên dịch sạch: `arduino-cli compile --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app`
      → 1089937 byte (34% flash), 70624 byte RAM. Không warning.
- [x] Rà lại A1–A11 trong spec (đọc code, không phải chạy thử).
- [ ] **A12 — nghiệm thu trên board thật: CHƯA LÀM.** Không có test tự động cho
      firmware này; phải chạy tay checklist trong `firmware/aqua_scope_station/README.md`.
      Mục quan trọng nhất: **mục 9** — cấp điện mà chưa gõ lệnh nào, bơm phải đứng
      im tuyệt đối (kiểm tra chân ENA không thả nổi). Biên dịch sạch **không**
      chứng minh được điều này.
- [ ] Dò lại `fillDuty` thực nghiệm bằng lệnh `d` (55% hiện tại chỉ là ước lượng).
