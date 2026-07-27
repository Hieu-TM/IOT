# Thiết kế: Kênh giấu dây cho trạm bơm (pump_station v2)

**Ngày:** 2026-07-25
**Trạng thái:** Đã duyệt bởi user (phương án A), chờ viết plan triển khai.
**Liên quan:** [[pump-drive-decision]] (memory), `docs/superpowers/specs/2026-07-24-pump-station-mount-design.md` (spec v1 — vẫn là kiến trúc nền, doc này chỉ SỬA phần đi dây).

## Bối cảnh

`pump_station_001.scad` (spec 2026-07-24) đã in và lắp thử thật. Từ lần lắp đó,
user phản hồi 4 vấn đề cụ thể (không phải giả thuyết — quan sát trên phần cứng
thật, có ảnh):

1. **Khoang hộp L298N không tính thêm độ dài của driver**: khay dung sai hiện
   tại (`l298n_box_clr = 2.5mm` quanh 4 cạnh) không chừa đủ chỗ cho domino/
   terminal vít nhô ra mép board + bán kính bẻ dây xuống khe thoát — dây bị ép
   sát thành hộp.
2. **Yên kẹp bơm không có lối thoát dây theo thiết kế**: bơm RS365 thật có 2
   chân điện (tab đồng) nhô ra **ngang thân trụ động cơ, gần nắp đen** (không
   phải từ đầu trục như giả định ngầm) — ảnh thực tế cho thấy rõ. Khi lắp bơm
   theo chiều cần thiết để ngạnh ống hướng đúng ra khay, chân điện lại quay xa
   hộp L298N, dây phải vòng hở qua đỉnh cả 2 yên kẹp — xấu và không được thiết
   kế che.
3. **Không có gì che bó dây logic** (ENA/IN1/IN2/GND) chạy từ hộp L298N lên
   ESP32 gắn trên nắp ống quang học — lộ thiên hoàn toàn giữa 2 cụm tách rời
   (tách rời là chủ đích, để cách ly rung — xem `plan.md` §8).
4. **Toàn bộ khe/rãnh dây hiện có được tính theo dây trần** (mesh hở
   `wire_notch_w=6mm`, rãnh `wire_channel` rộng 6mm sâu 1.5mm). User dùng dây
   jumper đực-cái (không hàn) — mỗi đầu jumper là 1 khối nhựa nhỏ (~3×6mm),
   không lọt qua khe hẹp hoặc bị kẹt ở mép.

Người dùng đã xác nhận (qua hỏi-đáp trước khi viết spec này):
- **Giữ kiến trúc tách rời** ESP32 (trên nắp quang học) ↔ trạm bơm — không gộp
  điện tử vào 1 hộp. Chỉ cải thiện cách đi dây giữa 2 cụm.
- **Không hàn** — vẫn dùng jumper đực-cái, thiết kế phải chừa chỗ cho đầu nhựa.
- **Hướng lắp bơm linh hoạt cả 2 chiều** — không chốt cứng "chân điện luôn quay
  về phía hộp", vì thực tế đã cho thấy hướng đó xung đột với hướng ngạnh ống.

## Mục tiêu

Sửa `pump_station_001.scad` → `pump_station_002.scad` (bump version qua
`version-scad.sh pump_station`), chỉ đổi phần đi dây — **không đổi** cơ chế
kẹp bơm, cơ chế nắp hộp L298N, hay bố cục tổng (hộp ở đầu này, yên kẹp ở đầu
kia, nối bằng đế liền).

Sau khi sửa: dây (jumper hay trần) đi từ domino L298N tới bơm, và đầu dây logic
ra ESP32, đều nằm dưới 1 nắp che phẳng liền — nhìn từ trên xuống không thấy dây
nào, bất kể lắp bơm chiều nào.

## Kiến trúc

### 1. Kênh dây liền mạch mức thấp (thay rãnh ngắn hiện tại)

- `wire_channel()` hiện chỉ chạy đoạn hộp↔yên kẹp GẦN (`chan_len`). Kéo dài
  chạy SUỐT từ thành hộp L298N (cạnh OUT) tới hết mép ngoài yên kẹp XA —
  nghĩa là kênh chạy XUYÊN QUA bên dưới footprint của cả 2 khối yên kẹp (kênh
  cắt vào **đế**, ở z âm; khối yên kẹp là vật thể riêng đặt ĐÈ LÊN mặt đế từ
  z=0 trở lên — 2 vật thể không xung đột hình học vì khác dải z).
- Rộng ra từ 6mm → `wire_channel_w = 10.0mm`, đủ xếp 2-3 đầu jumper cạnh nhau.
  Sâu giữ `wire_channel_d = 2.0mm` (tăng nhẹ từ 1.5mm).
- 2 gờ ray dọc 2 bên miệng kênh (`wire_channel_rail`) để nắp đậy gài khớp nhựa
  dẻo (cùng cơ chế "PETG hơi dẻo ép giữ" đã dùng ở khe lồng bơm — không cần
  vít).
- **Nắp đậy kênh dây**: 1 thanh dài duy nhất, phẳng, dày ~2mm, dài suốt chiều
  dài kênh — chi tiết in RIÊNG (`print_pump_station_channel_cover_001.scad`).
  Tháo ra được để bảo trì/tháo bơm.

### 2. Khe nối lòng máng kẹp ↔ kênh dây (mới, ở yên kẹp)

- Mỗi yên kẹp (`pump_clamp_post()`) thêm 1 khe nhỏ xuyên qua bề dày đáy máng
  kẹp (`pump_clamp_t = 2.4mm`, đúng tại điểm thấp nhất của lòng máng — đã là
  điểm mỏng nhất theo thiết kế đối xứng trên/dưới của v1), nối lòng máng với
  mặt đế ngay phía trên kênh dây bên dưới. Kỹ thuật giống hệt `wire_notch` đã
  dùng trong `l298n_box_walls()` (khe xuyên thành tại mức sàn) — tái dùng
  pattern có sẵn, không phát minh cơ chế mới.
- Vì lòng máng là hình trụ, bơm xoay tự do trước khi ép xuống từ khe lồng
  trên đỉnh (khe lồng hiện có, không đổi) — user chỉnh chân điện của bơm
  hướng xuống khe mới này lúc lắp, bất kể ngạnh ống hướng ra +X hay −X.
- **Chưa chốt kích thước chính xác khe này** (`pump_clamp_wire_notch_w/h`) —
  sẽ tinh chỉnh bằng render preview lúc triển khai (`/preview-scad`), vì phụ
  thuộc khớp nối hình học 3D giữa mặt cong lòng máng và mặt phẳng đế mà mô tả
  bằng lời không đủ chính xác.

### 3. Hộp L298N — nới khoang 2 cạnh có domino

- Đổi `l298n_box_clr` (1 hằng số dùng chung 4 cạnh) thành 2 hằng số riêng:
  - `l298n_box_clr_x = 8.0mm` — cạnh dọc trục X (cạnh IN 12V ở −X, cạnh OUT
    động cơ ở +X) — đây là 2 cạnh có domino vít nhô ra, cần chỗ bẻ dây.
  - `l298n_box_clr_y = 4.0mm` — cạnh dọc trục Y (cạnh LOGIC + cạnh thoát khí)
    — tăng nhẹ so 2.5mm cũ, đủ cho đầu jumper logic nhưng không lãng phí
    nhựa như cạnh X.
  - Hộp từ hình vuông 52×52mm → hình chữ nhật `l298n_box_od_l ≈ 63mm ×
    l298n_box_od_w ≈ 55mm`. Nắp hộp (`pump_station_lid()`) tự động khớp theo
    vì dùng chung các hằng số `l298n_box_od_*` — không cần đổi thiết kế nắp,
    chỉ regenerate theo kích thước mới.
- Khe dây LOGIC (cạnh +Y) nới từ `wire_notch_w=6mm` → hằng số riêng
  `wire_notch_logic_w = 14.0mm`, `wire_notch_logic_h = 6.0mm` — đủ ôm 3-4 đầu
  jumper (ENA, IN1, IN2, GND) xếp cạnh nhau. Khe IN(12V)/OUT(động cơ) giữ
  `wire_notch_w/h` cũ (6/5mm) — 2 khe này chủ yếu là dây trần/đầu cosse vào
  domino vít, không phải đầu jumper nhựa, không cần nới rộng miệng khe (vấn đề
  của chúng là THIẾU CHỖ BẺ DÂY bên trong hộp, đã giải quyết bằng
  `l298n_box_clr_x`, không phải miệng khe hẹp).
- Thêm 1 gờ neo bó dây nhỏ (trụ tròn `l298n_wire_anchor_d = 6mm`, cao bằng
  `wire_notch_logic_h`) ngay bên ngoài khe LOGIC, cách thành hộp ~8mm — dây ra
  ESP32 vòng qua gờ này 1 lần trước khi đi tự do, tránh lực kéo trực tiếp vào
  chân cắm trên board.

### 4. Ghi chú lắp ráp (không phải hình học in — ghi vào tài liệu lắp ráp)

- Bó 3-4 dây logic ra ESP32 bằng ống gen xoắn (spiral wrap) hoặc ống gen mềm,
  đoạn từ gờ neo tới ESP32 — biến dây rời thành 1 bó gọn. Việc này nằm ngoài
  phạm vi in 3D.

## File / constants cần thêm hoặc sửa

- Mới: `openscad/components/pump_station_002.scad` — dựng bằng
  `.claude/skills/openscad/scripts/version-scad.sh pump_station` (kế thừa
  toàn bộ `pump_station_001.scad`, sửa `l298n_box_walls()`, `wire_channel()`,
  `pump_clamp_post()`; thêm module `pump_station_wire_cover()`).
- Mới: `openscad/print/print_pump_station_002.scad` (đế+hộp+yên, kế thừa
  `print_pump_station.scad` trỏ sang file component mới).
- Mới: `openscad/print/print_pump_station_channel_cover_001.scad` (chi tiết
  nắp che kênh dây, in riêng — thứ 3 cùng bộ với đế+hộp và nắp hộp L298N).
- `print_pump_station_lid.scad` (nắp hộp L298N) — regenerate theo kích thước
  hộp mới (`l298n_box_od_l/w` đổi), KHÔNG đổi thiết kế cơ chế nắp.
- Sửa `openscad/constants.scad` (cạnh block `l298n_*`/`pump_clamp_*`/
  `pump_station_*` hiện có, dòng ~169-218):
  - Đổi `l298n_box_clr` → 2 hằng số `l298n_box_clr_x = 8.0`,
    `l298n_box_clr_y = 4.0`.
  - Thêm `wire_notch_logic_w = 14.0`, `wire_notch_logic_h = 6.0`.
  - Thêm `l298n_wire_anchor_d = 6.0`.
  - Đổi `wire_channel` liên quan: `wire_channel_w = 10.0` (thay tên khỏi biến
    cục bộ `ch_w=6.0` trong module cũ, đưa lên constants.scad),
    `wire_channel_d = 2.0`, `wire_channel_rail_w = 2.0`,
    `wire_channel_rail_h = 1.5`.
  - Thêm `pump_clamp_wire_notch_w`, `pump_clamp_wire_notch_h` — giá trị khởi
    điểm đề xuất `4.0` / `pump_clamp_t + 2.0`, **sẽ chỉnh lại theo preview**
    (xem ghi chú ở mục 2 Kiến trúc).
  - Dẫn xuất `l298n_box_id_l/w`, `l298n_box_od_l/w`,
    `pump_station_len/wid` — sửa công thức dùng `l298n_box_clr_x/y` thay
    `l298n_box_clr` (các assert hiện có ở dòng ~379-389 giữ nguyên logic,
    chỉ đổi biến tham chiếu).

## Không làm trong thiết kế này

- Không đổi cơ chế kẹp bơm (khe lồng từ trên, ép PETG dẻo) hay cơ chế nắp hộp
  L298N (vít M3 tự-ren 2 góc chéo) — 2 đã hoạt động tốt theo phản hồi lắp thật,
  chỉ vấn đề nằm ở phần đi dây.
- Không thiết kế giắc DC barrel jack tích hợp — ảnh thực tế cho thấy user đã
  tự dùng 1 domino xanh (pluggable terminal) làm adapter DC-jack→dây trần rồi
  cắm vào domino 12V của L298N; domino xanh đó nằm NGOÀI hộp in, không thuộc
  phạm vi thiết kế này.
- Không gộp ESP32/adapter 12V vào chung hộp với L298N (đã hỏi và user chọn giữ
  tách rời).
- Không thiết kế conduit/ống gen cứng nối 2 cụm (ống gen mềm là giải pháp lắp
  ráp, không phải chi tiết in).

## Giả định cần xác nhận sau (không chặn triển khai, gắn cờ trong code)

1. Kích thước chính xác board L298N thật vẫn CHƯA ĐO (kế thừa từ spec v1) —
   `l298n_box_clr_x/y` mới là ước tính dựa trên quan sát ảnh domino nhô ra, có
   thể cần chỉnh lại khi đo board thật.
2. Vị trí chính xác 2 chân điện trên thân bơm (khoảng cách từ nắp đen, góc
   quay) chưa đo bằng số — thiết kế khe nối lòng máng↔kênh dây ở mục Kiến
   trúc §2 chấp nhận sai số bằng cách để lòng máng xoay tự do, không cần biết
   góc chính xác.
3. `pump_clamp_wire_notch_w/h` là giá trị khởi điểm, sẽ chỉnh qua preview-scad
   lúc triển khai thực tế.
