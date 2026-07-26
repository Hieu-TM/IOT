# Thiết kế: Trả mặc định camera trạm (aqua_scope_station) về auto exposure

**Ngày:** 2026-07-25
**Trạng thái:** Đã duyệt bởi user, chờ viết plan triển khai.
**Liên quan:** [[image-processing-hybrid]] (memory), `firmware/aqua_scope_station/README.md`, `docs/superpowers/specs/2026-07-19-aqua-scope-station-firmware-design.md` (spec gốc dựng file này — doc này chỉ SỬA hành vi mặc định camera, không đổi kiến trúc).

## Bối cảnh

`aquaPrefsApplyDefaults()` (`firmware/aqua_scope_station/aqua_prefs.cpp`) ép
cứng AEC / AEC-DSP / AGC **tắt** và một mức phơi sáng thủ công tối
(`aec_value=100`, `agc_gain=0`) mỗi lần board boot **và** mỗi lần gọi
`/control?var=reset`. Hàm này chạy TRƯỚC khi `aquaPrefsLoad()` nạp cấu hình đã
lưu (nếu có), nên đây luôn là trạng thái camera đầu tiên người dùng nhìn thấy.

Hệ quả: ảnh mặc định tối, khó ngắm/chỉnh, và mỗi phiên làm việc phải tự bật lại
AEC/AGC qua web UI rồi mới chỉnh tiếp — kể cả khi chỉ đang thử nghiệm, không
chụp đo thật.

`firmware/aqua_scope_cam/aqua_scope_cam.ino` (firmware camera-only tiền đề của
trạm) đã được sửa trước đó để KHÔNG ép AEC/AGC tắt — `applyConfig()` của file
đó chỉ set brightness/contrast/special_effect/mirror/flip/quality, để sensor tự
chạy auto exposure/gain mặc định của nó. Đây chính là hành vi "các firmware
khác" mà user muốn `aqua_scope_station` khớp theo.

**Xác nhận với user trước khi viết doc này:**
- Chỉ đổi **mặc định lúc boot/reset**. Khả năng chỉnh tay sang chế độ
  backlit/manual (tắt AEC/AGC, đặt exposure/gain) qua `/control?var=aec` v.v.
  (đã có sẵn trong `app_httpd.cpp`) giữ nguyên — vẫn cần dùng nó trước khi chụp
  đo hạt thật.
- Cập nhật luôn comment/README trong thư mục firmware cho khớp hành vi mới.
- Cập nhật luôn đoạn liên quan trong CLAUDE.md gốc (mục "Lighting").

## Mục tiêu

Sau khi sửa: cấp điện lần đầu (chưa từng `save`) hoặc gọi `?var=reset` →
camera ở trạng thái auto exposure/gain bình thường như CameraWebServer gốc,
ảnh sáng và ngắm được ngay. Muốn chụp đo backlit thật thì người vận hành tự
tắt AEC/AGC + chỉnh tay qua web UI/serial rồi `?var=save` như quy trình hiện
có — không đổi phần này.

## Thay đổi mã nguồn

### `aqua_prefs.cpp` — `aquaPrefsApplyDefaults()`

Xoá 5 dòng ép tắt auto và đẩy giá trị thủ công tối:

```cpp
s->set_exposure_ctrl(s, 0);  // AEC off
s->set_aec2(s, 0);           // AEC-DSP off
s->set_gain_ctrl(s, 0);      // AGC off
s->set_aec_value(s, DEF_AEC_VALUE);
s->set_agc_gain(s, DEF_AGC_GAIN);
```

Giữ nguyên các dòng còn lại của hàm (`set_contrast`, `set_brightness`,
`set_quality`, `set_framesize` qua `clampFramesize`, `set_hmirror`,
`set_vflip`) — các thông số này không liên quan tới vấn đề "tối/khó chỉnh".

Không gọi `set_exposure_ctrl`/`set_aec2`/`set_gain_ctrl` với giá trị `1` để ép
bật — để trống, y hệt cách `aqua_scope_cam.ino` làm: sensor tự giữ trạng thái
auto mà driver `esp_camera_init()` đã thiết lập sẵn (đúng behavior của bản
CameraWebServer gốc).

Hằng số `DEF_AEC_VALUE`, `DEF_AGC_GAIN` **giữ lại** — vẫn dùng làm giá trị dự
phòng trong `aquaPrefsLoad()` khi đọc NVS thiếu key `aec_value`/`agc_gain`
(trường hợp phòng thủ, không phải đường chạy chính).

### Không đổi

- `aquaPrefsLoad()` — khi flash đã có cấu hình lưu (`saved=true`), tức người
  dùng đã chủ động chỉnh + bấm `?var=save` trước đó, hàm này vẫn nạp và áp
  đúng y những gì đã lưu (kể cả nếu đó là cấu hình backlit/manual). Đây là
  đường "chỉnh 1 lần dùng mãi" đúng như thiết kế ban đầu, không phải thứ đang
  gây khó chịu.
- `app_httpd.cpp` — các endpoint `/control?var=aec|aec2|agc|aec_value|agc_gain`
  giữ nguyên toàn bộ.
- Bơm, WiFi, watchdog, `/device`, `/status` — ngoài phạm vi.

## Tài liệu cần cập nhật theo

1. `firmware/aqua_scope_station/README.md`
   - Mục "Khác gì bản CameraWebServer gốc", điểm 1: đổi từ "Mặc định backlit —
     tắt AEC/AEC-DSP/AGC..." sang mô tả mặc định là auto exposure như bản gốc;
     backlit/manual là bước người vận hành tự bật trước khi đo.
   - Dòng bảng endpoint `?var=reset`: bỏ chữ "về mặc định backlit", thay bằng
     "xoá cấu hình đã lưu, về mặc định auto exposure (như bản gốc)".
2. `aqua_scope_station.ino` — comment đầu file, mục "Khác bản CameraWebServer
   gốc đúng 3 điểm", điểm 1: cập nhật tương tự.
3. `aqua_prefs.h` — comment đầu file và comment trên khai báo
   `aquaPrefsApplyDefaults()`: bỏ mô tả "áp bộ mặc định backlit silhouette",
   thay bằng mô tả mặc định auto + ghi rõ manual backlit là cấu hình người
   dùng tự chỉnh/lưu.
4. `aqua_prefs.cpp` — comment khối "Mặc định backlit silhouette" phía trên
   các hằng `DEF_*`: cập nhật cho khớp (không còn ép AEC/AGC tắt mặc định).
5. `CLAUDE.md`, mục "Lighting is backlit silhouette...": giữ nguyên yêu cầu
   vật lý (phải tắt AEC/AGC + đặt exposure thấp **trước khi chụp khung phân
   tích**), nhưng làm rõ đây không còn là trạng thái mặc định lúc cấp điện —
   là bước người vận hành (hoặc script tự động sau này) phải chủ động bật qua
   web UI/serial rồi lưu, giống các firmware camera khác trong repo.

## Kiểm thử / nghiệm thu

Không có test tự động cho firmware (nạp qua Arduino IDE, kiểm bằng board
thật). Bổ sung 1 mục vào checklist "Nghiệm thu trên board thật" của README:

- [ ] Cấp điện lần đầu (chưa từng `?var=save`) → mở `http://<ip>/` → ảnh sáng
      bình thường (không phải mảng xám tối cháy contrast), slider AEC/AGC ở
      trạng thái ON.
- [ ] `?var=reset` khi đang ở cấu hình đã lưu → về lại đúng trạng thái auto ở
      trên (không quay lại dark cũ).
- [ ] Tắt AEC/AGC + chỉnh tay qua web UI như quy trình canh sáng backlit hiện
      có → `?var=save` → rút điện → cắm lại → đúng cấu hình backlit đã lưu
      (không bị ghi đè bởi default auto).

Không cần thêm test nào khác — đây là thay đổi phạm vi hẹp, không đụng tới
logic bơm/WiFi/lưu trữ.
