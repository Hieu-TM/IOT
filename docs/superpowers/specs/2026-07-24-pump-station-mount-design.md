# Thiết kế: Trạm bơm gọn (đế liền + hộp L298N + kẹp bơm RS365)

**Ngày:** 2026-07-24
**Trạng thái:** Đã duyệt bởi user, chờ viết plan triển khai.

## Bối cảnh

Hiện tại "trạm bơm" trong `openscad/aqua_scope_assembly_001.scad` chỉ có
`pump_rs365()` — một placeholder bounding-box (90×40×35mm, KHÔNG in) đặt tách
rời trên bàn, nối bằng `silicone_tube()`. Không có mount/enclosure thật nào để
giữ bơm cố định hay gá mạch điều khiển; dây điện và dây tín hiệu hiện chưa có
chỗ đi tuyến gọn gàng.

Người dùng đang dùng **module L298N** để điều khiển bơm (khác với tài liệu
hiện có trong repo: `plan.md`/`HUONG_DAN_LAP_RAP.md` ghi "module relay", còn
`firmware/pump_pwm_test/pump_pwm_test.ino` ghi "MOSFET IRLZ44N trực tiếp").
Thiết kế này **chỉ giải quyết phần cơ khí** (mount + đi dây gọn cho in 3D),
không sửa lại lựa chọn driver hay firmware — đó là việc khác, ngoài phạm vi.

## Mục tiêu

Một cụm in 3D duy nhất, gọn, giữ cố định:
1. Board L298N (đã che hộp, có strain-relief dây).
2. Thân bơm màng RS365 (kẹp ôm thân trụ, đầu bơm + ngạnh ống lộ ra ngoài).

Sao cho: bê đi 1 lần, không dây rời rạc lòng thòng giữa 2 vật thể, và hình
dáng in ra nhìn có chủ đích (không phải lắp ráp tạm bằng băng keo/zip-tie
trần).

## Kiến trúc

Một tấm đế (baseplate) in liền mang 2 cụm chức năng ở 2 đầu, nối bằng 1 rãnh
dây ngắn ở giữa:

```
[Yên kẹp bơm ×2]---(rãnh dây ~5cm, gờ giữ dây)---[Hộp L298N + nắp rời]
   ôm thân trụ RS365                          khe dây IN 12V | ra bơm | logic→ESP32
```

### 1. Đế (baseplate)
- Tấm phẳng dày 3mm, kích thước ước lượng ~155mm (dài) × ~50mm (rộng) — đủ
  chứa bbox bơm 90×40 + hộp L298N ~49×49 + rãnh dây giữa.
- 4 chân đế cao 2mm ở góc, in phẳng, không cần support.
- Đế + thành hộp L298N + 2 trụ yên kẹp bơm là **CÙNG MỘT FILE IN** (chỉ nắp
  hộp L298N là chi tiết rời thứ 2).

### 2. Hộp L298N
- Hộp hở nắp, thành dày 2mm.
- Khoang trong ước lượng ~48×48×32mm — rộng hơn kích thước "board L298N phổ
  biến" (~43×43×27mm, đây là số ĐIỂN HÌNH, CHƯA ĐO board thật của user) khoảng
  2.5mm mỗi bên, có chủ đích rộng rãi để dung sai.
- Board tựa trên 4 gờ đỡ góc cao 2mm (không cần khớp đúng lỗ vít của board
  thật — thiết kế "khay hở dung sai" thay vì "khớp lỗ chính xác").
- Nắp rời, bắt 2 vít M3 tự-ren ở 2 góc chéo, tháo được để chỉnh jumper 5V hay
  kiểm tra board.
- 3 khe dây, theo bố trí chân chuẩn của board L298N phổ biến (input 1 cạnh,
  output động cơ 1 cạnh, logic 1 cạnh):
  - Cạnh xa bơm (hướng ra ngoài trạm): khe dây 12V vào từ adapter.
  - Cạnh gần bơm: khe dây ra động cơ, chạy trong rãnh đế tới yên kẹp.
  - Cạnh hướng về khối quang chính: khe bó dây logic (IN1/IN2/EN + GND) lên
    ESP32.
  - Mỗi khe có rãnh bán nguyệt nhỏ ở thành hộp — dây bị ép giữa rãnh và
    nắp/thành đối diện = strain-relief đơn giản, không cần giắc DC rời (theo
    lựa chọn user: xuyên lỗ dây trần + khoét rãnh kẹp).
- Khe hở thoát khí nhỏ đối diện phía tản nhiệt của board.

### 3. Yên kẹp bơm (2 yên)
- 2 trụ đứng từ đế, mỗi trụ có lòng máng ôm ~210° quanh thân trụ RS365.
- Bán kính máng = `pump_motor_od/2 + khe hở`; `pump_motor_od` mặc định lấy
  theo ước tính hiện có trong `accessories_001.scad` (`pump_bbox[2] * 0.9` =
  31.5mm) — **CHƯA ĐO bơm thật, cần xác nhận khi có hàng**.
- Mỗi yên có thêm 1 rãnh vòng nhỏ trên đỉnh để luồn dây rút nhựa (zip-tie)
  xiết chặt thêm, phòng khi đường kính bơm thật lệch so với ước tính — không
  cần in lại đế, chỉ cần xiết zip-tie chặt hơn/lỏng hơn.
- Đầu bơm (khối màng bơm) + 2 ngạnh ống KHÔNG bị che, lộ hẳn ra ngoài để dễ
  tháo lắp ống silicone.

## File / constants cần thêm

- Mới: `openscad/components/pump_station_001.scad` — module `pump_station()`
  chứa đế + hộp L298N (không nắp) + 2 yên kẹp bơm.
  - Giữ nguyên `pump_rs365()` trong `accessories_001.scad` (mô hình hiển thị
    bơm mua sẵn, KHÔNG in) — không đổi.
- Mới: `openscad/print/print_pump_station.scad` (xuất phần đế+hộp+yên) và
  `openscad/print/print_pump_station_lid.scad` (xuất nắp hộp L298N riêng).
- Sửa `openscad/constants.scad`, thêm (đặt cạnh block `pump_bbox`/`pump_barb_od`
  hiện có ở dòng ~163-164):
  - `l298n_l = 43; l298n_w = 43; l298n_h = 27;` — kèm comment "kích thước ĐIỂN
    HÌNH, CHƯA ĐO board thật — sửa lại khi có hàng".
  - `l298n_box_wall = 2;`
  - `l298n_box_clearance = 2.5;` — khe hở mỗi bên quanh board trong hộp.
  - `pump_motor_od = 31.5;` — kèm comment "ước tính từ pump_bbox[2]*0.9, CHƯA
    ĐO bơm thật".
  - `pump_clamp_clearance = 1.0;`
  - `clamp_wrap_deg = 210;`
  - `pump_station_baseplate_t = 3;`
  - `pump_station_foot_h = 2;`
- Sửa `openscad/aqua_scope_assembly_001.scad`: trong khối
  `if (show_pump) { ... }` (dòng ~92-105), thêm `use <components/pump_station_001.scad>`
  và đặt `pump_station()` tại cùng vị trí hiện có của `pump_rs365()`
  (translate `[120 + 1.5*e, 0, z_housing_bot]`), bên dưới bơm — bơm ngồi lên
  yên kẹp thay vì lơ lửng riêng.

## Không làm trong thiết kế này

- Không đổi driver bơm (relay/MOSFET/L298N) hay sửa firmware — chỉ mount cơ
  khí cho L298N mà user đang có.
- Không thiết kế giắc DC barrel jack (user đã chọn xuyên dây trần + rãnh kẹp).
- Không làm kín nước hoàn toàn hộp L298N (chỉ che bụi/dây gọn, không phải hộp
  chống nước IP-rated).

## Giả định cần xác nhận sau (không chặn triển khai, gắn cờ trong code)

1. Kích thước board L298N thật (43×43×27mm chỉ là điển hình).
2. Đường kính thân trụ động cơ RS365 thật (31.5mm chỉ là ước tính).
3. Board L298N thật có đúng bố trí 3 cạnh (input/output/logic) như module phổ
   biến hay không.
