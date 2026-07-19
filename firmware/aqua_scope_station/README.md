# Aqua Scope — Firmware chính thức (ESP32-CAM AI-Thinker)

**Đây là bản duy nhất cần nạp.** Các thư mục firmware khác trong repo là thử
nghiệm hoặc tiền đề, giữ lại để tham khảo.

Vai trò: cung cấp ảnh backlit chất lượng đúng, ổn định, kèm đủ thông tin để
truy xuất nguồn gốc. Firmware **không** đếm hạt, không lưu trữ, không suy luận
— việc đó do `ml.infer` trên máy tính làm.

## Endpoint

| Endpoint | Dùng để |
|---|---|
| `GET /` | Web UI canh sáng (slider) |
| `GET /stream` | MJPEG xem trực tiếp — chỉ dùng lúc canh sáng |
| `GET /capture` | Một ảnh JPEG. Chụp lỗi → **503** kèm lý do |
| `GET /device` | JSON danh tính + thiết lập camera (khối audit) |
| `GET /status` | JSON cấu hình cho slider (bản gốc Espressif) |
| `GET /control?var=save&val=1` | Ghi cứng cấu hình vào flash |
| `GET /control?var=reset&val=1` | Xóa cấu hình, về mặc định backlit |
| `GET /control?var=device_id&val=<tên>` | Đổi device_id (khớp `[A-Za-z0-9._-]`, 1–64 ký tự) |

## Nạp firmware

Arduino IDE, cần gói board **esp32 by Espressif ≥ 3.0**:

| Mục | Chọn |
|---|---|
| Board | **AI Thinker ESP32-CAM** |
| Partition Scheme | **Huge APP (3MB No OTA/1MB SPIFFS)** |

Sửa WiFi ở đầu `aqua_scope_station.ino`, nối **IO0 → GND**, cấp nguồn, Upload,
rút IO0, reset. Mở Serial Monitor 115200 để lấy IP và `device_id`.

## Khác gì bản CameraWebServer gốc

1. **Mặc định backlit** — tắt AEC / AEC-DSP / AGC, gain 0, exposure 100. Bản
   gốc để auto, và auto-exposure sẽ kéo nền cháy trắng nuốt mất hạt.
2. **Không bật đèn flash khi chụp.** Bản gốc bật GPIO4 150ms trước mỗi lần
   chụp. Rig này chiếu sáng **từ dưới** — thêm đèn từ trên làm nhạt bóng hạt
   và tạo phản xạ trên mặt nước.
3. **Mặc định UXGA 1600×1200** — hạt <2mm cần độ phân giải.
4. **Lưu cấu hình vào flash** — `?var=save` / `?var=reset`.
5. **`/device`** — device_id sinh từ MAC + thiết lập camera đang áp dụng.
6. **Chạy dài không chết** — tự nối lại WiFi, watchdog, chụp lỗi trả 503 rõ
   ràng thay vì treo. `loop()` chỉ in trạng thái WiFi mỗi ~10s, chia thành 10
   lát nghỉ 1 giây (không phải một cục `delay(10000)`): core esp32 3.x đã tự
   bật sẵn Task Watchdog 5 giây lúc boot, nên một cục `delay(10000)` sẽ làm
   board panic-reset giữa chừng mỗi lần — trông như biên dịch sạch nhưng thực
   chạy là boot loop vô tận. Nghỉ theo lát 1 giây, reset watchdog mỗi lát, thì
   không bao giờ để quá 1 giây trôi qua giữa hai lần reset watchdog, bất kể
   timeout thực tế là 5s (nếu cấu hình lại watchdog ở `setup()` thất bại) hay
   30s (khi thành công).

## Checklist nghiệm thu trên board thật

Chưa chạy đủ 7 mục này thì **chưa được nói firmware "chạy được"**.

- [ ] 1. Nạp xong, Serial 115200 in ra IP và `device_id = aqua-cam-xxxxxx`
- [ ] 2. `curl http://<ip>/device` → JSON hợp lệ, `psram: true`
- [ ] 3. Mở `http://<ip>/` chỉnh slider → nền xám đều, hạt là bóng đen rõ
- [ ] 4. `?var=save` → rút điện → cắm lại → `/device` báo `prefs_saved: true`
      và đúng thông số vừa chỉnh
- [ ] 5. Tắt router 30 giây rồi bật lại → board tự nối lại, `/device` phản hồi,
      **không** cần bấm reset
- [ ] 6. `python -m ml.infer --from-board <ip> --count 3 --dry-run` → 3 khung,
      không có dòng nào ghi vào DB
- [ ] 7. Bỏ `--dry-run` → 3 mẫu hiện trên dashboard, cột device_id đúng tên board

## Chưa có (cố ý)

Điều khiển đèn nền (đèn cắm thẳng, luôn sáng), điều khiển bơm, suy luận
on-device. State machine bơm nằm riêng ở `firmware/pump_stopflow_test/`; khi
gộp vào đây thì chỗ đặt là `loop()`, và relay dùng **GPIO13** (active-LOW —
phải kéo HIGH ở dòng đầu `setup()` để bơm không tự chạy lúc boot).
