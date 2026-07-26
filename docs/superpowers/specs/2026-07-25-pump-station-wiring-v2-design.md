# Thiết kế: Trạm bơm v2 — giấu dây & gọn hóa đấu nối (sau khi lắp thật)

**Ngày:** 2026-07-25
**Trạng thái:** Đã duyệt bởi user, chờ viết plan triển khai.
**Kế thừa:** [2026-07-24-pump-station-mount-design.md](2026-07-24-pump-station-mount-design.md)
(đã in `openscad/print/print_pump_station.stl` + `print_pump_station_lid.stl`, đã lắp thử
thật với module L298N + dây jumper đực-cái).

## Bối cảnh

Sau khi lắp thật bản in `pump_station_001` (xem ảnh user cung cấp), phát sinh 3 vấn đề
mà thiết kế v1 chưa lường tới:

1. **Ngõ vào 12V lộ ra ngoài, không chỗ giấu.** User dùng 1 module nhỏ rời gồm jack DC
   barrel + cầu đấu vít 2 chân (nối vào chân input 12V của L298N), hiện nằm lỏng lẻo bên
   ngoài hộp — thiết kế v1 chỉ có khe dây trần xuyên thành, không tính tới module này.
2. **Dây ra động cơ bơm phải vòng qua thân bơm.** 2 chân dẹt (spade) trên thân trụ mô-tơ
   RS365 nằm cách nhau ~180° quanh chu vi (không cùng hướng về phía hộp L298N) — 1 dây
   (vàng/lam trong ảnh) nối thẳng vào hộp, còn dây kia (cam) phải vòng lỏng lẻo qua dưới
   thân bơm mới tới được chân còn lại. Thiết kế v1 chỉ có 1 rãnh dây thẳng nối hộp↔yên kẹp,
   không tính đường vòng này.
3. **Dây tín hiệu ESP32→L298N (IN1/IN2/EN/GND) chạy lộ thiên, mất thẩm mỹ.** Trạm bơm và
   khối quang chính (ống + XIAO ESP32-S3) hiện là **2 cụm rời, đặt tự do trên bàn, không
   chung đế/khung** — dây tín hiệu nối 2 cụm hiện không có strain-relief hay đường dẫn nào.

User xác nhận (qua hỏi-đáp trước khi viết spec này):
- **Vẫn dùng jumper đực-cái cho phần logic** (IN1/IN2/EN/GND lên ESP32) — không hàn.
- **Dây ra động cơ bơm (OUT1/OUT2) sẽ HÀN trực tiếp** vào chân spade, bỏ đầu jumper —
  nên không cần thiết kế ngàm giữ đầu jumper ở phía này, chỉ cần khe hở đủ cho dây trần +
  co nhiệt.
- **Jack 12V: khoét lỗ xuyên vỏ hộp, gắn cố định kiểu panel-mount** — không chỉ là 1 khoang
  chứa module rời.
- **2 cụm (trạm bơm / khối quang) không có đế chung** — vẫn đặt rời trên bàn, nên KHÔNG
  thiết kế rãnh dây cứng nối liền 2 cụm (không khả thi vì chúng di chuyển độc lập).

## Mục tiêu

Sửa `pump_station_001` (đế + hộp L298N + yên kẹp bơm) → `pump_station_002`, chỉ thay đổi
3 điểm dây điện nêu trên, **giữ nguyên kiến trúc tổng thể** (đế liền, hộp hở nắp, yên kẹp
kiểu lồng-từ-trên) đã duyệt ở bản v1.

## Kiến trúc — 3 thay đổi

### 1. Lỗ panel-mount cho jack DC 12V (thay khe dây input cũ)

- Thay khe dây bán-nguyệt input 12V (cạnh −X hộp L298N) bằng **1 lỗ tròn xuyên thành**,
  đường kính `dc_jack_hole_d` (mặc định 9.5mm — cỡ phổ biến cho jack DC 5.5×2.1mm dạng
  module nhỏ có ren, **CHƯA ĐO module thật của user — xác nhận khi lắp**).
- Tâm lỗ đặt ở giữa bề rộng thành, cao ngang tầm cầu đấu vít trên board L298N (để dây
  input ra khỏi jack đi thẳng vào board, không phải vòng).
- Bên trong, thêm 1 **gờ đỡ (shelf)** cao `dc_jack_shelf_h` sát mặt trong thành, để board
  nhỏ (jack + cầu đấu) tựa lên và ép sát ra lỗ — cố định bằng ma sát + keo nến (module này
  không có lỗ bắt vít chuẩn). Không thiết kế ngàm khớp chính xác kích thước board (vì chưa
  đo) — chỉ cần gờ đỡ phẳng đủ rộng.
- Nắp hộp (`pump_station_lid`) không đổi, vẫn đậy phía trên; module jack nằm thấp hơn mép
  hộp nên không đội nắp.

### 2. Rãnh dẫn dây vòng quanh yên kẹp bơm (thay vì dây vòng tự do)

- Khe dây output (cạnh +X hộp, hướng về yên kẹp) **nới rộng nhẹ** từ `wire_notch_w=6.0` lên
  đủ chứa 2 dây trần + co nhiệt song song (ước lượng `wire_notch_w=7.0`, không cần rộng bằng
  đầu jumper cũ vì đã bỏ đầu nối nhựa ở phía này).
- Thêm **rãnh dẫn dây (wire guide groove)** khoét nông trên mặt ngoài khối yên kẹp
  (`pump_clamp_post`), chạy dọc theo 1 phần chu vi lòng máng (song song với lỗ khoan ngang,
  ở mặt ngoài khối chứ không xuyên vào lòng máng) — đủ sâu (~1.5mm) và rộng (~3mm) để ép
  1 dây trần + co nhiệt vào, giữ nó áp sát thân bơm thay vì lơ lửng. Rãnh này chạy từ vị trí
  gần hộp L298N vòng ra phía sau khối yên kẹp gần nhất với hộp — đủ dùng cho trường hợp
  người dùng xoay bơm sao cho 2 chân dẹt nằm gần mặt phẳng chứa rãnh nhất có thể (khuyến
  nghị lắp: xoay bơm khi lồng vào yên sao cho 2 chân dẹt cùng nằm về phía mặt có rãnh,
  giảm tối đa đoạn dây phải treo tự do ở đoạn cuối).
- Không đảm bảo rãnh khớp chính xác 100% mọi góc xoay chân dẹt thật (vì chưa đo vị trí góc
  thật trên bơm) — đây là cải thiện thẩm mỹ + strain relief một phần, không phải khớp kỹ
  thuật tuyệt đối. Ghi chú "CHƯA ĐO góc lệch thật giữa 2 chân dẹt" trong code.

### 3. Gờ thoát dây bo cong (strain relief) cho dây logic ra ESP32

- Khe dây logic hiện tại (cạnh +Y hộp, hướng khối quang chính) giữ nguyên vị trí, nhưng
  thêm 1 **gờ lồi bo tròn (radius) ở mép ngoài khe**, để dây bẻ cong mượt khi ra khỏi hộp
  thay vì gập khúc 90° sát cạnh vỏ (giảm mỏi dây + gọn mắt hơn).
- **Không** thiết kế rãnh/kênh cứng nối 2 cụm (trạm bơm ↔ khối quang) — vì 2 cụm đặt rời,
  di chuyển độc lập, rãnh cứng sẽ vô nghĩa. Khuyến nghị dùng ống lò xo quấn dây (spiral
  wrap) mua ngoài cho đoạn dây tự do này — nằm ngoài phạm vi bản in.

## File / constants cần thêm

- Sửa `openscad/components/pump_station_001.scad` → tạo mới
  `openscad/components/pump_station_002.scad` (dùng script version-scad.sh, supersede
  `_001` giống cách `top_cap_002` supersede `_001` trước đây). Thay đổi trong
  `l298n_box_walls()` (lỗ jack thay khe input), `pump_clamp_post()` (thêm rãnh dẫn dây),
  và khe dây logic (thêm gờ bo tròn).
- Sửa `openscad/print/print_pump_station.scad` trỏ sang `pump_station_002.scad`.
- `openscad/print/print_pump_station_lid.scad` — không đổi logic, chỉ cần trỏ include nếu
  module `pump_station_lid()` được giữ trong file `_002` mới (copy nguyên, không sửa).
- Sửa `openscad/constants.scad`, thêm cạnh block `l298n_*`/`pump_clamp_*` hiện có (~dòng
  163-218):
  - `dc_jack_hole_d = 9.5;` — kèm comment "CHƯA ĐO module jack thật — xác nhận khi lắp".
  - `dc_jack_shelf_h = 3.0;` — cao gờ đỡ board jack tính từ đáy hộp.
  - `dc_jack_shelf_depth = 15.0;` — sâu gờ đỡ (đủ tựa board nhỏ ~20×15mm điển hình, CHƯA ĐO).
  - Thêm hằng riêng `wire_notch_w_out = 7.0` chỉ dùng cho khe dây output (cạnh +X, ra yên
    kẹp bơm). Giữ nguyên `wire_notch_w = 6.0` cho khe logic (+Y) — khe input cũ (−X) bị
    THAY THẾ hoàn toàn bởi lỗ jack (`dc_jack_hole_d`) nên không còn dùng `wire_notch_w` ở
    cạnh đó nữa.
  - `pump_wire_groove_w = 3.0;` `pump_wire_groove_d = 1.5;` — rãnh dẫn dây trên yên kẹp.
  - `logic_notch_fillet_r = 2.0;` — bo tròn gờ thoát dây logic.
- Sửa `openscad/aqua_scope_assembly_001.scad`: đổi `use <components/pump_station_001.scad>`
  → `use <components/pump_station_002.scad>` tại khối `if (show_pump)`.

## Không làm trong thiết kế này

- Không đổi driver bơm hay firmware (giữ nguyên L298N + `pump_l298n_xiao.ino`).
- Không thiết kế ngàm giữ đầu jumper phía dây động cơ (user sẽ hàn trực tiếp).
- Không thiết kế đế/khung chung nối trạm bơm với khối quang chính (2 cụm vẫn rời).
- Không làm kín nước hoàn toàn (giữ nguyên định hướng "che bụi/dây gọn", không phải hộp
  IP-rated) — vẫn đúng như spec v1.
- Không đảm bảo khớp chính xác 100% vị trí góc thật của 2 chân dẹt trên mô-tơ (chưa đo).

## Giả định cần xác nhận sau (không chặn triển khai, gắn cờ trong code)

1. Đường kính lỗ panel-mount jack DC thật (9.5mm chỉ là điển hình cho jack 5.5×2.1mm).
2. Kích thước board nhỏ (jack + cầu đấu) thật để gờ đỡ vừa khít hơn (hiện ước lượng
   ~20×15mm, CHƯA ĐO).
3. Góc lệch thật giữa 2 chân dẹt trên thân mô-tơ RS365 (giả định ~180°, dựa theo ảnh —
   CHƯA ĐO chính xác bằng thước đo góc).
4. Các giả định cũ từ spec v1 (kích thước board L298N 43×43×27mm, Ø thân bơm 31.5mm) vẫn
   CHƯA ĐO, không đổi trong bản v2 này.
