# Aqua Scope — Firmware chính thức (ESP32-CAM AI-Thinker)

**Đây là bản duy nhất cần nạp.** Các thư mục firmware khác trong repo là thử
nghiệm hoặc tiền đề, giữ lại để tham khảo:

| Thư mục | Là gì |
|---|---|
| `firmware/Esp32 cam/` | thử nghiệm ban đầu — không nạp |
| `firmware/aqua_scope_cam/` | tiền đề — không nạp |
| `firmware/esp32-cam-webserver/` | **repo git lồng** (bản port easytarget, đang sửa dở). Không phải firmware của trạm. Vì là repo riêng nên không đặt ghi chú vào README của nó — ghi ở đây thay thế |
| `firmware/pump_stopflow_test/` | công cụ test bơm độc lập, vẫn dùng được — không phải firmware của trạm |
| `dataset_collector/firmware/` | bản tiền thân trực tiếp của thư mục này. `collect_dataset.py` chạy được với cả hai vì cùng `/capture` |

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
| mDNS `aqua-scope.local` | Board tự xưng tên trong LAN — khỏi mở Serial Monitor lấy IP |
| `GET /status` | JSON cấu hình cho slider (bản gốc Espressif) |
| `GET /control?var=darkmode&val=1` | **Bật preset buồng tối backlit** (tắt AEC/AEC-DSP/AGC, gain 0, exposure 200, contrast +2, …) — chạy trước khi chụp khung phân tích |
| `GET /control?var=save&val=1` | Ghi cứng cấu hình camera + bơm vào flash |
| `GET /control?var=reset&val=1` | Xóa cấu hình đã lưu, về mặc định auto exposure (như bản gốc) + reset pump |
| `GET /control?var=device_id&val=<tên>` | Đổi device_id (khớp `[A-Za-z0-9._-]`, 1–64 ký tự) |
| `GET /control?var=pump_auto&val=1` | Bật chu trình Stop-Flow tự động |
| `GET /control?var=pump_auto&val=0` | Tắt chu trình (ramp bơm xuống 0) |
| `GET /control?var=pump_fill_ms&val=5000` | Thời gian pha FILLING (ms) |
| `GET /control?var=pump_settle_ms&val=2000` | Thời gian pha SETTLING (ms) |
| `GET /control?var=pump_flush_ms&val=5000` | Thời gian pha FLUSHING (ms) |
| `GET /control?var=pump_cooldown_ms&val=3000` | Thời gian pha COOLDOWN (ms) |
| `GET /control?var=pump_fill_duty&val=55` | Duty % pha FILL (0–100) |
| `GET /control?var=pump_flush_duty&val=100` | Duty % pha FLUSH (0–100) |
| `GET /control?var=pump_ramp_up_ms&val=250` | Thời gian ramp lên (ms) |
| `GET /control?var=pump_ramp_down_ms&val=350` | Thời gian ramp xuống (ms) |

## Đấu nối bơm L298N

```
ESP32-CAM GPIO13 ──→ L298N ENA (PWM 20kHz/10-bit)
L298N IN1         ──→ 3.3V (cố định)
L298N IN2         ──→ GND  (cố định, một chiều)
L298N +12V        ──→ Adapter 12V/2A riêng
L298N GND         ──→ GND chung với ESP32-CAM
L298N OUT1/OUT2   ──→ Bơm RS365 12V
Tụ gốm 0.1µF hàn ngang 2 cực bơm (chống nhiễu chổi than)
```

> **An toàn:** `autoRunning` mặc định **TẮT** lúc cấp điện — phải bật tay qua
> `?var=pump_auto&val=1` (HTTP) hoặc `a` (Serial).
>
> GPIO13 được ép LOW ở **dòng đầu tiên của `setup()`**, trước cả `Serial.begin()`.
> Ép muộn hơn là để hở một cửa sổ dài: giữa lúc cấp điện và lúc gắn PWM còn có
> camera init + WiFi connect (timeout tới 20s) và cả nhánh restart khi camera
> lỗi — thừa thời gian để một chân ENA thả nổi (L298N đọc là HIGH) làm tràn khay.
>
> Nếu `ledcAttach` thất bại, firmware **báo lỗi ra Serial và `/device` trả
> `pump.pwm_ready: false`** thay vì im lặng nhận lệnh mà bơm không nhúc nhích.

## Serial commands (bơm)

Gõ trong Serial Monitor 115200, mỗi lệnh 1 ký tự:

| Lệnh | Ý nghĩa |
|---|---|
| `p` | In trạng thái bơm |
| `0` | Manual OFF (ramp xuống 0, tắt auto) |
| `1` | Manual ON (ramp lên fillDuty, tắt auto) |
| `a` | Bật auto Stop-Flow từ FILLING |
| `f<ms>` | Đặt fill time, vd `f3000` |
| `s<ms>` | Đặt settle time, vd `s1500` |
| `x<ms>` | Đặt flush time, vd `x8000` |
| `c<ms>` | Đặt cooldown time, vd `c5000` |
| `u<ms>` | Ramp UP time, vd `u250` |
| `w<ms>` | Ramp DOWN time, vd `w350` |
| `d<0-100>` | CRUISE duty pha FILL, vd `d45` |
| `X<0-100>` | Duty pha FLUSH, vd `X100` |
| `r` | Reset timing về mặc định |
| `?` | In menu lệnh |

## Nạp firmware

Arduino IDE, cần gói board **esp32 by Espressif ≥ 3.0**:

| Mục | Chọn |
|---|---|
| Board | **AI Thinker ESP32-CAM** |
| Partition Scheme | **Huge APP (3MB No OTA/1MB SPIFFS)** |

Sửa WiFi ở đầu `aqua_scope_station.ino`, nối **IO0 → GND**, cấp nguồn, Upload,
rút IO0, reset. Mở Serial Monitor 115200 để lấy IP và `device_id`.

## Khác gì bản CameraWebServer gốc

> **Phơi sáng mặc định: GIỐNG bản gốc (auto).** Bản trước ép tắt
> AEC/AEC-DSP/AGC + exposure 100 ngay lúc boot và mỗi lần `?var=reset`, nên ảnh
> mặc định tối và khó ngắm/chỉnh — đã bỏ. Cấp điện lần đầu là ảnh sáng bình
> thường.
>
> Nhưng **canh sáng backlit vẫn bắt buộc trước khi chụp khung phân tích** —
> chụp đo ở chế độ auto thì nền cháy trắng và nuốt mất hạt. Không phải kéo tay
> từng slider: gọi **một lệnh**
>
> ```
> curl "http://<ip>/control?var=darkmode&val=1"
> ```
>
> (port từ `?var=darkmode` của `dataset_collector` — bộ thông số đã canh trên
> chính rig này), tinh chỉnh thêm bằng slider Exposure nếu cần, rồi `?var=save`.
> Đã `save` một lần thì các lần boot sau nạp lại đúng cấu hình đó, mặc định auto
> không ghi đè. Muốn về lại auto: `?var=reset` (lưu ý reset xoá cả cấu hình bơm).

1. **Không bật đèn flash khi chụp.** Bản gốc bật GPIO4 150ms trước mỗi lần
   chụp. Rig này chiếu sáng **từ dưới** — thêm đèn từ trên làm nhạt bóng hạt
   và tạo phản xạ trên mặt nước.
2. **Mặc định UXGA 1600×1200** — hạt <2mm cần độ phân giải.
3. **Lưu cấu hình vào flash** — `?var=save` / `?var=reset` (lưu cả camera lẫn bơm).
4. **`/device`** — device_id sinh từ MAC + thiết lập camera + trạng thái bơm.
5. **Chạy dài không chết** — tự nối lại WiFi, watchdog, chụp lỗi trả 503.
   `loop()` nghỉ 50ms mỗi vòng (thay vì 10×1s) để pump tick phản hồi kịp thời.
6. **Điều khiển bơm L298N** — state machine Stop-Flow (FILLING/SETTLING/FLUSHING/
   COOLDOWN) với PWM ramp chống búa nước, điều khiển qua HTTP và Serial.

## mDNS — khỏi đi tìm IP

Board tự xưng `aqua-scope.local` sau khi nối WiFi (và tự xưng lại sau mỗi lần
nối lại). Dashboard web thử tên này trước khi bắt bạn gõ IP.

```
curl http://aqua-scope.local/device
```

**Không phải mạng nào cũng cho.** Một số router chặn multicast, mạng khách bật
AP isolation, vài máy Windows cũ thiếu bộ phân giải .local. Ô nhập IP tay trên
dashboard là đường dự phòng chính thức — không phải tính năng thừa. Chế độ
`USE_AP` không bật mDNS (nối thẳng vào board thì IP đã cố định và in ra Serial).

## Checklist nghiệm thu trên board thật

Chưa chạy đủ các mục này thì **chưa được nói firmware "chạy được"**.

- [ ] 1. Nạp xong, Serial 115200 in ra IP và `device_id = aqua-cam-xxxxxx`
- [ ] 2. `curl http://<ip>/device` → JSON hợp lệ, `psram: true`, có object `pump`
- [ ] 3. Mở `http://<ip>/` chỉnh slider → nền xám đều, hạt là bóng đen rõ
- [ ] 3a. Cấp điện lần đầu (chưa từng `?var=save`) → mở `http://<ip>/` → ảnh
      **sáng bình thường**, không phải mảng xám tối; slider AEC/AGC ở trạng thái ON
- [ ] 3b. `?var=reset` khi đang ở cấu hình đã lưu → về đúng trạng thái auto ở
      mục 3a (không quay lại mặc định dark cũ)
- [ ] 3c. `?var=darkmode&val=1` → Serial in `[cam] Da ap preset buong toi`, ảnh
      chuyển sang nền sáng đều + hạt là bóng đen; `?var=reset` → về lại auto
- [ ] 4. Tắt AEC/AGC + chỉnh tay theo quy trình canh sáng backlit → `?var=save`
      → rút điện → cắm lại → `/device` báo `prefs_saved: true` và đúng thông số
      camera + bơm vừa chỉnh (mặc định auto **không** ghi đè)
- [ ] 5. Tắt router 30 giây rồi bật lại → board tự nối lại, `/device` phản hồi,
      **không** cần bấm reset
- [ ] 6. `python -m ml.infer --from-board <ip> --count 3 --dry-run` → 3 khung,
      không có dòng nào ghi vào DB
- [ ] 7. Bỏ `--dry-run` → 3 mẫu hiện trên dashboard, cột device_id đúng tên board
- [ ] 8. Serial in `[pump] init OK`, `/device` báo `pump.pwm_ready: true`
- [ ] 9. Cấp điện, **chưa gõ lệnh nào** → bơm đứng im hoàn toàn (kể cả trong
      lúc board đang dò WiFi). Đây là mục kiểm tra chân ENA không thả nổi.
- [ ] 10. Serial gõ `a` → bơm chạy chu trình, `p` → in đúng trạng thái pha
- [ ] 11. `?var=pump_auto&val=1` → bơm bắt đầu, `/device` báo `pump.auto: true`
- [ ] 12. `?var=pump_fill_duty&val=150` → trả **HTTP 500** (không phải 200)
- [ ] 13. `?var=save` → rút điện → cắm lại → `/device` báo đúng timing bơm đã lưu
- [ ] 14. Serial in `[mdns] http://aqua-scope.local` sau dòng `WiFi OK`
- [ ] 15. Tắt router 30 giây rồi bật lại → sau khi board tự nối lại,
      `curl http://aqua-scope.local/device` **vẫn** trả JSON (mDNS được bật lại,
      không chết theo lần rớt mạng)

## Chưa có (cố ý)

Điều khiển đèn nền (đèn cắm thẳng, luôn sáng), suy luận on-device, tự động
chụp ảnh theo pha SETTLING (script PC chủ động pull `/capture`, trường
`pump.phase` trong `/device` là thông tin để script tự biết lúc nào là SETTLING
nếu sau này muốn tự động hoá — nằm ngoài phạm vi firmware).
