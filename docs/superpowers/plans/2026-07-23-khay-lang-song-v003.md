# Khay lặng sóng `flow_tray_003` + firmware bơm PWM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Trạng thái — ✅ 7/7 TASK HOÀN TẤT (2026-07-24).** Toàn bộ nội dung đã có mặt trong repo và đã commit
> (`e771ba7`…`f7f895c`, xem `git log --oneline` các task); checkbox trong file này trước đó chưa được tick dù
> việc đã xong — nay đã đồng bộ lại. Task 7 thực tế ghi **6 lỗi** (không phải 4 như bản kế hoạch gốc): phát
> hiện thêm 2 lỗi Critical (#5 vách trôi nổi không dính khối, #6 thành bellmouth mỏng 0.231mm) trong lúc dựng
> `flow_tray_003.scad` thành khối 3D thật và soi CGAL — đã bổ sung vào cùng bảng PHẦN D của tài liệu nghiên
> cứu thay vì mở task mới. Việc còn lại (in thử, dò cruise duty, đo lắng thực tế…) nằm ngoài phạm vi code,
> xem §"Sau khi hoàn thành plan này" cuối file.

**Goal:** Giảm sóng mặt nước trong khay Stop-Flow đủ để chụp ảnh nét trong pha SETTLING 2s, bằng 3 thay đổi hình học khay (cửa vào đục lỗ, vách cong tiêu năng, miệng loe cổng ra) + firmware điều khiển bơm bằng MOSFET/PWM có tăng-giảm tốc mềm.

**Architecture:** Tạo `flow_tray_003.scad` mới (giữ `_002` để đối chiếu in thử). Khay dựng theo 2 tầng union: `tray_shell()` (thân + ngạnh + cửa vào đục lỗ — kế thừa _002) và `tray_internals()` (vách cong + miệng loe — nằm TRONG lòng Ø40 nên phải union SAU khi đã khoét lòng, nếu không sẽ bị chính lệnh khoét lòng xóa mất). Toàn bộ tham số mới + ràng buộc an toàn hạt đặt trong `constants.scad` dưới dạng `assert` — đây là cơ chế "test" khả thi duy nhất cho OpenSCAD. Firmware tách file mới, không sửa bản relay đang chạy được.

**Tech Stack:** OpenSCAD (CLI qua `.claude/skills/*/scripts/*.sh`), Arduino-ESP32 core 3.x (API `ledcAttach`/`ledcWrite`).

## Global Constraints

- **Ràng buộc cứng #1 (ưu tiên cao nhất, trên cả chống sóng):** mọi hạt phải RA HẾT, không đọng. Không được tạo chi tiết giữ hạt, khe hẹp hơn hạt, hay túi cụt.
- Hạt lớn nhất trong phạm vi test hiện tại: **2.0mm** (CLAUDE.md — "current test scope is <2mm").
- Mọi khe/hành lang hạt phải đi qua: **≥ 1.5 × 2.0 = 3.0mm**. Lòng cổng ra giữ nguyên quy tắc cũ ≥ 3× hạt = 6mm (`constants.scad:247`).
- Khay: lòng nước Ø40 (`tray_inner`), ngoài Ø44 (`tray_outer`), thành 2mm, cao 12mm, mực nước 6mm (`water_depth`). **Không đổi các số này.**
- In FDM đầu đùn 0.4mm → bề dày vách mỏng nhất = 1.2mm (3 perimeter).
- MOSFET là **IRLZ44N logic-level, ACTIVE-HIGH** (GPIO HIGH = bơm CHẠY) — **ngược hoàn toàn** với module relay active-LOW đang dùng trong `firmware/pump_stopflow_test/pump_stopflow_test.ino`. Sai chiều này = bơm tự chạy full tốc lúc boot.
- Nguồn số liệu: `docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md`.
- Ngôn ngữ comment trong file: tiếng Việt (theo quy ước repo).

---

## 4 LỖI MỚI phát hiện khi dựng hình học — số liệu ĐÃ SỬA so với tài liệu nghiên cứu

Bốn lỗi này chỉ lộ ra khi tính va chạm hình học thật, không lộ khi đọc/kiểm chứng công thức:

| # | Tài liệu nghiên cứu | Vấn đề | Số dùng trong plan này |
|---|---|---|---|
| 1 | `baffle_r_mid = 17.6` | Hành lang nước đi vòng sau vách = 20 − (17.6+0.6) = **1.8mm < hạt 2mm**. Hạt KHÔNG lọt qua → kẹt vĩnh viễn trong túi cổng vào. Đây là lối thoát DUY NHẤT của túi đó → **vi phạm ràng buộc cứng #1** | **`baffle_r_mid = 16.4`** → hành lang 3.0mm = 1.5× hạt |
| 2 | `baffle_h = 5.0` (thấp hơn mực nước 1mm "để thoát bọt") | Diện tích tràn qua NÓC vách (1mm × cung 27.6mm ≈ 27.6mm²) còn LỚN HƠN diện tích đi vòng 2 đầu → ~50% lưu lượng xả động năng thẳng vào MẶT NƯỚC, đúng chỗ cần phẳng nhất. Lý do "thoát bọt" không áp dụng: vách là hàng rào HỞ 2 ĐẦU, bọt thoát tự do | **`baffle_h = 7.0`** (> mực nước 6mm) → chặn hết, nước chỉ đi vòng |
| 3 | `post_gap = 2.5` tại cửa vào | Chỉ dư 0.5mm so hạt 2mm, ngay tại CỬA VÀO. Hạt nghẽn ở đây = không vào được khay = không đếm được (sai số đo, tệ hơn kẹt ở cửa ra vì hỏng chính phép đo) | **`inlet_gap_w = 3.5`** = 1.75× hạt |
| 4 | `fillet_r = 2.0` bo 2 đầu mút vách | Bất khả thi: vách dày 1.2mm thì bán kính bo tối đa = 1.2/2 = 0.6mm | Bo bán nguyệt r = `baffle_t/2` = **0.6mm** (tối đa khả thi) |

**Hệ quả đã biết và chấp nhận:** vách cong tại r=16.4 (mặt trong 15.8) làm vùng ảnh hóa giảm từ Ø40 → **Ø31.6mm** (~62% diện tích cũ). Không ảnh hưởng độ phân giải hạt (vẫn ~14px/mm ở VGA → hạt 1mm = 14px), chỉ giảm lượng nước soi được mỗi lần chụp. `baffle_r_mid` để dạng tham số để tinh chỉnh sau khi in thử.

---

## Cấu trúc file

| File | Trạng thái | Trách nhiệm |
|---|---|---|
| `openscad/constants.scad` | Sửa | Thêm khối hằng số chống sóng + 6 assert an toàn hạt. Nguồn sự thật duy nhất cho mọi số liệu mới |
| `openscad/components/flow_tray_003.scad` | Tạo mới | Khay: `tray_shell()` + `tray_internals()` + `flow_tray()` |
| `openscad/print/print_flow_tray.scad` | Sửa | Trỏ `use` sang `_003` |
| `openscad/aqua_scope_assembly_001.scad` | Sửa | Trỏ `use` sang `_003` (dòng 25) |
| `firmware/pump_pwm_test/pump_pwm_test.ino` | Tạo mới | Chu trình Stop-Flow điều khiển bằng MOSFET/PWM: soft-start, cruise duty, soft-stop |
| `docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md` | Sửa | Ghi 4 lỗi mới vào §PHẦN C |

**Không đụng tới:** `flow_tray_002.scad` (giữ nguyên để đối chiếu bản đã in), `firmware/pump_stopflow_test/` (bản relay vẫn chạy được, giữ làm fallback).

---

## Ghi chú về "test" trong dự án OpenSCAD này

OpenSCAD không có test framework, và **không mô phỏng được dòng chảy**. Ba lớp kiểm chứng khả thi, dùng thay cho test tự động:

1. **`assert` trong `constants.scad`** — chạy mỗi lần render, fail thì OpenSCAD báo lỗi và không dựng. Đây là lớp gần "unit test" nhất: kiểm các ràng buộc số (khe ≥ hạt, vách cao hơn mực nước, chi tiết nằm gọn trong lòng...).
2. **Render PNG + đọc ảnh** — kiểm mắt: chi tiết có xuất hiện đúng chỗ không, có bị lệnh khoét nào xóa mất không.
3. **Export STL + validate manifold** (`export-stl.sh` tự kiểm non-manifold/self-intersection).

Mọi khẳng định về hiệu quả giảm sóng chỉ được xác nhận bằng **in thật + chạy nước thật**, nằm ngoài phạm vi plan này (xem §Sau khi hoàn thành).

---

### Task 1: Hằng số + assert an toàn hạt

**Files:**
- Modify: `openscad/constants.scad` (chèn khối mới ngay sau dòng 63, cuối khối "Khay dòng chảy"; các assert chèn vào cụm assert cuối file sau dòng 249)

**Interfaces:**
- Produces: `particle_max`, `inlet_rib_t`, `inlet_gap_w`, `inlet_n_gap`, `inlet_pitch`, `inlet_span`, `baffle_t`, `baffle_r_mid`, `baffle_h`, `baffle_angle`, `baffle_corridor`, `bell_fillet_r`, `bell_wall` — Task 2/3/4 dùng trực tiếp.

- [x] **Step 1: Viết assert TRƯỚC khi có hằng số (để thấy nó fail)**

Chèn vào `openscad/constants.scad` ngay sau dòng `assert(bl_diff_d >= tray_inner, ...)` (dòng 248):

```openscad
// --- Assert an toàn hạt cho cụm chống sóng (2026-07-23) ---
assert(inlet_gap_w >= 1.5 * particle_max,
       "cửa sổ vào phải ≥1.5× hạt — nghẽn ở CỬA VÀO nghĩa là hạt không vào được khay, hỏng phép đếm");
assert(inlet_span <= inlet_slot_w,
       "cụm cửa sổ + gân phải nằm gọn trong bề rộng khe vào 20mm");
assert(baffle_corridor >= 1.5 * particle_max,
       "hành lang sau vách cong phải ≥1.5× hạt — đây là lối thoát DUY NHẤT của túi cổng vào");
assert(baffle_h > water_depth,
       "vách phải CAO HƠN mực nước, nếu không dòng tràn qua nóc đập thẳng vào mặt nước");
assert(baffle_r_mid + baffle_t/2 < tray_inner/2 - 0.01,
       "vách cong phải nằm trong lòng khay");
assert(bell_fillet_r >= 0.15 * outlet_bore,
       "bo loe phải đủ tròn (r/d ≥ 0.15) mới hạ được hệ số tổn thất K");
```

- [x] **Step 2: Chạy để xác nhận FAIL**

OpenSCAD không có chế độ "chỉ kiểm cú pháp", nên dùng export định dạng `.echo` — nó chạy
hết file (kể cả `assert`) mà không phải dựng khối 3D:

```bash
"/c/Program Files/OpenSCAD/openscad.exe" -o /tmp/constants_check.echo "openscad/constants.scad"
```

Expected: FAIL — `WARNING: Ignoring unknown variable 'inlet_gap_w'` rồi `ERROR: Assertion ... failed`. Chưa khai báo hằng số nên assert không thể đúng.

*(Nếu bản OpenSCAD cài trên máy không nhận đuôi `.echo`, thay bằng `-o /tmp/constants_check.stl` — assert vẫn chạy y hệt, chỉ khác là nó dựng thêm khối rỗng.)*

- [x] **Step 3: Khai báo hằng số**

Chèn vào `openscad/constants.scad` ngay sau dòng `drain_port_d = 8.0;` (dòng 63):

```openscad

// ---------------------------------------------------------------- CHỐNG SÓNG (2026-07-23)
// Nguồn: docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md
// ⚠️ 4 số dưới đây LỆCH CÓ CHỦ Ý so với tài liệu nghiên cứu — lý do ghi tại chỗ.
particle_max = 2.0;    // hạt lớn nhất trong phạm vi test (CLAUDE.md: <2mm)

// (e) Cửa vào ĐỤC LỖ — thay khe hở liền 20×3 bằng N cửa sổ ngăn bởi gân.
// Chia tia nước lớn thành nhiều tia nhỏ → tiêu tán động năng nhanh hơn nhiều.
inlet_rib_t  = 1.2;    // bề dày gân giữa 2 cửa sổ (3 perimeter × nozzle 0.4)
inlet_gap_w  = 3.5;    // ⚠️ LỆCH tài liệu (2.5): 2.5 chỉ dư 0.5mm so hạt 2mm, NGAY
                       // CỬA VÀO. Hạt nghẽn ở đây = không vào khay = không đếm được
                       // (hỏng chính phép đo, tệ hơn kẹt ở cửa ra). 3.5 = 1.75× hạt.
inlet_n_gap  = 4;      // số cửa sổ
inlet_pitch  = inlet_gap_w + inlet_rib_t;                              // = 4.7
inlet_span   = inlet_n_gap * inlet_gap_w + (inlet_n_gap - 1) * inlet_rib_t;  // = 17.6

// (c) VÁCH CONG tiêu năng — chắn đường đi thẳng cổng vào → cổng ra (short-circuiting)
baffle_t     = 1.2;    // bề dày vách (3 perimeter FDM)
baffle_r_mid = 16.4;   // ⚠️ LỆCH tài liệu (17.6): 17.6 → hành lang chỉ 1.8mm < hạt
                       // 2mm ⇒ hạt KHÔNG lọt, kẹt trong túi cổng vào (lối thoát duy
                       // nhất) ⇒ vi phạm ràng buộc cứng "mọi hạt ra hết".
                       // GIÁ PHẢI TRẢ: vùng ảnh hóa Ø40 → Ø31.6. Chỉnh tham số này
                       // sau khi in thử nếu muốn đổi cân bằng.
baffle_h     = 7.0;    // ⚠️ LỆCH tài liệu (5.0): 5.0 < mực nước 6 ⇒ ~50% lưu lượng
                       // tràn qua NÓC vách, xả động năng thẳng vào MẶT NƯỚC (chỗ cần
                       // phẳng nhất). Lý do "thoát bọt" của tài liệu không áp dụng vì
                       // vách là HÀNG RÀO HỞ 2 ĐẦU, bọt thoát tự do quanh 2 đầu mút.
baffle_angle = 90;     // góc quét cung (độ), tâm tại −X (đối diện cổng vào)
                       // Bo 2 đầu mút: bán nguyệt r = baffle_t/2 = 0.6 — ⚠️ tài liệu
                       // ghi fillet_r=2.0 là BẤT KHẢ THI trên vách dày 1.2mm.
baffle_corridor = tray_inner/2 - (baffle_r_mid + baffle_t/2);  // DẪN XUẤT = 3.0

// (Bellmouth) MIỆNG LOE cổng RA — chống dồn ứ + dội sóng ngược tại miệng lỗ xả
// Nhô VÀO lòng khay (KHÔNG khoét lõm vào thành): thành chỉ dày 2mm, khoét lõm bo
// R=3 sẽ ăn hết thịt quanh ngạnh OD8 (còn ~0.25mm) → vỡ khi in/dùng.
bell_fillet_r = 3.0;   // bán kính bo loe (r/d = 0.5 ≫ ngưỡng 0.15 ⇒ K: 0.5 → <0.05)
bell_wall     = 1.2;   // bề dày vỏ loa kèn (3 perimeter)
bell_steps    = 24;    // số đoạn xấp xỉ cung 90° khi revolve
```

- [x] **Step 4: Chạy để xác nhận PASS**

```bash
"/c/Program Files/OpenSCAD/openscad.exe" -o /tmp/constants_check.echo "openscad/constants.scad" && cat /tmp/constants_check.echo
```

Expected: exit 0, không có `ERROR` trên stderr, và file `.echo` chứa dòng:
```
ECHO: "== Aqua Scope constants OK == tube OD/ID/H = 50/46/45 | z_lens = 46 | tray outer/inner = 44/40"
```
⚠️ Lưu ý: OpenSCAD ghi ECHO vào **file `.echo`**, không ra stdout — phải `cat` mới thấy.
Lỗi `assert` thì ngược lại: hiện trên **stderr** và tiến trình trả exit khác 0.

- [x] **Step 5: Xác nhận assert THỰC SỰ bắt lỗi (không phải assert giả)**

Tạm đổi `baffle_r_mid = 16.4;` thành `baffle_r_mid = 17.6;` (đúng số của tài liệu nghiên cứu), chạy lại lệnh Step 4.

Expected: FAIL với `"hành lang sau vách cong phải ≥1.5× hạt..."` — chứng minh assert bắt đúng lỗi #1. **Đổi lại về 16.4 sau khi xác nhận.**

- [x] **Step 6: Commit**

```bash
git add openscad/constants.scad
git commit -m "feat(openscad): hằng số + assert an toàn hạt cho cụm chống sóng khay"
```

---

### Task 2: `flow_tray_003.scad` — thân khay + cửa vào đục lỗ

**Files:**
- Create: `openscad/components/flow_tray_003.scad`
- Reference (đọc, không sửa): `openscad/components/flow_tray_002.scad`

**Interfaces:**
- Consumes: toàn bộ hằng số Task 1.
- Produces: `module flow_tray()` (điểm vào chung, giữ đúng tên như `_001`/`_002` để `print_flow_tray.scad` và assembly gọi được không cần sửa lệnh gọi); `module tray_shell()`; `module barb(len)`.

- [x] **Step 1: Tạo file với thân khay + cửa vào đục lỗ**

Tạo `openscad/components/flow_tray_003.scad`:

```openscad
// ============================================================================
// flow_tray_003.scad — Khay Macro-Flow CHỐNG SÓNG (2026-07-23)
// ----------------------------------------------------------------------------
// KHÁC _002: thêm 3 chi tiết chống sóng, KHÔNG đổi kích thước gốc của khay.
//   (1) Cửa vào ĐỤC LỖ: khe liền 20×3 → 4 cửa sổ 3.5×3 ngăn bởi 3 gân 1.2
//       (chia tia lớn thành tia nhỏ, tiêu tán động năng nhanh hơn).
//   (2) VÁCH CONG r=16.4, cao 7 (>mực nước), quét 90° đối diện cổng vào
//       (chắn đường đi thẳng vào→ra, ép nước đi vòng qua hành lang 3.0mm).
//   (3) MIỆNG LOE (bellmouth) nhô vào lòng khay tại cổng ra, bo R=3
//       (chống dồn ứ + dội sóng ngược tại miệng lỗ xả).
// Nguồn số liệu + 4 chỗ lệch có chủ ý so với tài liệu: constants.scad §CHỐNG SÓNG
// và docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md
//
// ⚠️ KIẾN TRÚC 2 TẦNG UNION — bắt buộc, không gộp được:
//   flow_tray() = tray_shell()  ∪  tray_internals()
//   Vách cong và miệng loe nằm TRONG lòng Ø40. Nếu union chúng vào khối thân
//   TRƯỚC khi khoét lòng Ø40 thì chính lệnh khoét đó sẽ xóa sạch chúng.
//   Vì vậy tray_shell() tự khoét xong lòng, RỒI mới union phần internals.
//
// Hệ toạ độ: z=0 = SÀN khay (mặt trên đĩa acrylic), trục Z = trục quang.
// ============================================================================
include <../constants.scad>

EPS = 0.05;
pocket_d    = tray_win_d + 2*win_clr;   // Ø42.7 hốc đĩa
z_skirt_bot = z_tray_bot;               // −6.5
barb_len    = 8.0;                      // đoạn ngạnh thò ra để trùm ống
plenum_w    = 22.0;                     // hộp loe (lọt khe vỏ 24)
plenum_deep = 7.0;                      // sâu hộp loe theo X

// --- ngạnh ống (nằm ngang trục X), gốc tại mặt bích trong, hướng +X ---
module barb(len = barb_len) {
    rotate([0, 90, 0]) {
        cylinder(d = outlet_barb_od, h = len, $fn = 48);
        for (zz = [len - 2, len - 5])
            translate([0, 0, zz])
                cylinder(d1 = outlet_barb_od + 1.4, d2 = outlet_barb_od - 1, h = 2, $fn = 48);
    }
}

// --- (1) Cửa vào ĐỤC LỖ: N cửa sổ ngăn bởi gân, canh giữa theo Y ---
// Gân = phần THÀNH còn lại giữa 2 cửa sổ (không phải chi tiết nhô ra lòng khay)
// → không va chạm vách cong, không cần support khi in.
module inlet_windows() {
    for (i = [0 : inlet_n_gap - 1])
        translate([-tray_outer/2 - 2,
                   -inlet_span/2 + i * inlet_pitch,
                   -EPS])
            cube([tray_wall + 4, inlet_gap_w, inlet_slot_h + EPS]);
}

// --- Thân khay (kế thừa _002, chỉ đổi cụm cửa vào) ---
module tray_shell() {
    difference() {
        union() {
            // Thân khay LIỀN 1 trụ (thành + gờ kê + váy hốc đĩa, z=−6.5..12)
            translate([0, 0, z_skirt_bot])
                cylinder(d = tray_outer, h = tray_depth - z_skirt_bot, $fn = 120);
            // Hộp loe cổng VÀO (−X): xuyên hẳn qua thành cong (phần thừa bị lòng
            // khay cắt lại) — mọi mặt giao TRANSVERSAL, tránh non-manifold.
            translate([-tray_outer/2 - plenum_deep + 1, -plenum_w/2, -1])
                cube([plenum_deep + 1.5, plenum_w, 7.5]);
            // Ngạnh VÀO (−X) nối hộp loe
            translate([-tray_outer/2 - plenum_deep + 1 - barb_len, 0, port_z])
                barb(barb_len + 1);
            // Ngạnh RA (+X) trên thành
            translate([tray_outer/2 - 1, 0, port_z]) barb(barb_len + 3);
        }
        // Lòng khay Ø40 khoét XUYÊN SUỐT (đáy mở — sửa lỗi in của _001)
        translate([0, 0, z_skirt_bot - EPS])
            cylinder(d = tray_inner, h = tray_depth - z_skirt_bot + 2*EPS, $fn = 120);
        // Hốc đĩa acrylic (từ dưới lên, chừa gờ kê 1mm)
        translate([0, 0, z_skirt_bot - EPS])
            cylinder(d = pocket_d, h = -z_skirt_bot - ledge_plate_t + EPS, $fn = 120);
        // (1) Cửa vào đục lỗ — THAY khe liền 20×3 của _002
        inlet_windows();
        // Khoang loe trong hộp: quạt từ lòng ngạnh Ø6 → bề rộng cụm cửa sổ.
        // ⚠️ Mặt cuối khoang DỪNG tại x=−21.8 (0.2mm bên trong mặt ngoài thành r=22):
        //   - không tràn tới x=−20 (mặt trong thành), nếu tràn sẽ ăn mất 3 gân;
        //   - không dừng đúng x=−22 (tiếp tuyến mặt trụ ngoài → non-manifold).
        hull() {
            translate([-tray_outer/2 - plenum_deep + 2, 0, port_z])
                rotate([0, 90, 0]) cylinder(d = outlet_bore, h = 1, $fn = 36);
            translate([-tray_outer/2 - 1.2, -inlet_slot_w/2, 0])
                cube([1.4, inlet_slot_w, inlet_slot_h]);
        }
        // Lòng ngạnh VÀO thông vào khoang loe (dừng trong hộp loe)
        translate([-tray_outer/2 - plenum_deep - barb_len, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = barb_len + 4, $fn = 36);
        // Lòng cổng RA Ø6 sát đáy (z=0..6) xuyên thành + ngạnh
        translate([tray_outer/2 - tray_wall - 1, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = tray_wall + barb_len + 6, $fn = 36);
        // 3 cửa sổ ngàm snap-fit ở váy (tránh ±X: đặt 90/210/330°)
        for (a = [90, 210, 330])
            rotate([0, 0, a])
                translate([tray_outer/2 - 1.5, -3, z_skirt_bot + 0.4])
                    cube([3, 6, 1.8]);
    }
}

module flow_tray() {
    color(col_plastic) tray_shell();
}

flow_tray();

// --- Tham chiếu khi mở file lẻ: đĩa acrylic + mực nước (ghost) ---
%color(col_acrylic) translate([0, 0, -ledge_plate_t - 0.3 - tray_win_t])
    cylinder(d = tray_win_d, h = tray_win_t, $fn = 96);
%color(col_water) cylinder(d = tray_inner, h = water_depth, $fn = 96);
```

- [x] **Step 2: Render và kiểm bằng mắt**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/flow_tray_003.scad --size 1200x900 --camera 0,0,0,55,0,25,150
```

Đọc file PNG `openscad/components/flow_tray_003_preview.png`. Expected: thấy rõ **4 cửa sổ chữ nhật** ở thành −X (thay vì 1 khe dài liền), 3 gân ngăn giữa chúng còn nguyên thịt.

- [x] **Step 3: Xác nhận gân KHÔNG bị khoang loe ăn mất**

Render nhìn thẳng từ trong khay ra cổng vào:

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/flow_tray_003.scad --size 1200x900 --camera 40,0,3,90,0,90,120 --output openscad/components/flow_tray_003_inlet.png
```

Đọc PNG. Expected: nhìn từ trong lòng khay thấy 4 lỗ riêng biệt. **Nếu thấy 1 khe dài liền** → khoang loe (hull) đã ăn mất gân → giảm `1.4` trong `cube([1.4, ...])` xuống `1.0` và render lại.

- [x] **Step 4: Export STL và kiểm manifold**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/components/flow_tray_003.scad --output /tmp/tray003_t2.stl
```

Expected: `--- Geometry Validation ---` báo manifold OK, không có non-manifold edge / self-intersection.

- [x] **Step 5: Commit**

```bash
git add openscad/components/flow_tray_003.scad
git commit -m "feat(openscad): flow_tray_003 - cửa vào đục lỗ 4 cửa sổ thay khe liền 20x3"
```

---

### Task 3: Vách cong tiêu năng

**Files:**
- Modify: `openscad/components/flow_tray_003.scad`

**Interfaces:**
- Consumes: `baffle_t`, `baffle_r_mid`, `baffle_h`, `baffle_angle` (Task 1); `tray_shell()` (Task 2).
- Produces: `module arc_baffle()`; `module tray_internals()` (Task 4 sẽ thêm miệng loe vào chính module này).

- [x] **Step 1: Thêm module vách cong + tầng union thứ 2**

Trong `openscad/components/flow_tray_003.scad`, chèn TRƯỚC `module flow_tray()`:

```openscad
// --- (2) VÁCH CONG tiêu năng ---
// Hàng rào cung tròn đặt đối diện cổng vào: chắn tia thẳng, ép nước đi VÒNG qua
// hành lang rộng baffle_corridor (=3.0mm) ở 2 đầu mút.
// Kín đáy (không hở chân) để hạt không chui vào kẹt phía sau; 2 đầu mút bo bán
// nguyệt r=baffle_t/2 để hạt trượt qua không vướng góc sắc.
module arc_baffle() {
    r_in  = baffle_r_mid - baffle_t/2;
    r_out = baffle_r_mid + baffle_t/2;
    union() {
        // Thân cung: vành khuyên ∩ nêm góc
        intersection() {
            difference() {
                cylinder(r = r_out, h = baffle_h, $fn = 160);
                translate([0, 0, -EPS])
                    cylinder(r = r_in, h = baffle_h + 2*EPS, $fn = 160);
            }
            // Nêm quét baffle_angle°, canh giữa tại 180° (hướng cổng vào −X)
            rotate([0, 0, 180 - baffle_angle/2])
                linear_extrude(height = baffle_h + 2*EPS)
                    polygon(points = concat(
                        [[0, 0]],
                        [for (i = [0 : 24])
                            let (a = i * baffle_angle / 24)
                            [tray_outer * cos(a), tray_outer * sin(a)]]
                    ));
        }
        // Bo 2 đầu mút (bán nguyệt r = baffle_t/2 — tối đa khả thi trên vách 1.2mm)
        for (s = [-1, 1])
            rotate([0, 0, 180 + s * baffle_angle/2])
                translate([baffle_r_mid, 0, 0])
                    cylinder(d = baffle_t, h = baffle_h, $fn = 24);
    }
}

// --- Chi tiết NẰM TRONG lòng Ø40 — phải union SAU khi tray_shell() đã khoét lòng ---
module tray_internals() {
    arc_baffle();
}
```

Rồi sửa `module flow_tray()` thành:

```openscad
module flow_tray() {
    color(col_plastic) union() {
        tray_shell();
        tray_internals();
    }
}
```

- [x] **Step 2: Render kiểm vách có tồn tại (không bị lệnh khoét lòng xóa)**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/flow_tray_003.scad --size 1200x900 --camera 0,0,0,55,0,25,150 --output openscad/components/flow_tray_003_baffle.png
```

Đọc PNG. Expected: thấy **vách cong nằm trong lòng khay**, phía −X, cao hơn mực nước (mực nước là khối trong suốt cao 6mm). **Nếu không thấy vách** → nó đã bị khoét mất; kiểm lại `flow_tray()` có union 2 tầng đúng chưa.

- [x] **Step 3: Xác nhận hành lang 3.0mm bằng số (không ước lượng bằng mắt)**

Tạo file kiểm tạm `openscad/_check_baffle.scad`:

```openscad
// File kiểm tạm — in ra số liệu hành lang hạt & vùng ảnh còn lại. Xoá sau khi dùng.
include <constants.scad>
echo(str("hanh lang = ", baffle_corridor, " mm | hat = ", particle_max,
         " mm | ty le = ", baffle_corridor / particle_max));
echo(str("vung anh con lai = D", (baffle_r_mid - baffle_t/2) * 2, " mm"));
echo(str("vach cao ", baffle_h, " mm vs muc nuoc ", water_depth, " mm"));
```

Chạy:

```bash
"/c/Program Files/OpenSCAD/openscad.exe" -o /tmp/baffle_check.echo openscad/_check_baffle.scad && cat /tmp/baffle_check.echo
```

Expected (3 dòng ECHO trong file — không ra stdout, phải `cat`):
```
ECHO: "hanh lang = 3 mm | hat = 2 mm | ty le = 1.5"
ECHO: "vung anh con lai = D31.6 mm"
ECHO: "vach cao 7 mm vs muc nuoc 6 mm"
```

Xoá file kiểm sau khi xác nhận:

```bash
rm openscad/_check_baffle.scad
```

- [x] **Step 4: Export STL và kiểm manifold**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/components/flow_tray_003.scad --output /tmp/tray003_t3.stl
```

Expected: manifold OK. (Điểm rủi ro: chỗ vách cong tì lên mặt sàn z=0 và 2 nắp bo đầu mút chồng lấn thân cung — nếu báo self-intersection, đổi `cylinder(d = baffle_t, h = baffle_h, ...)` thành `h = baffle_h - EPS` và render lại.)

- [x] **Step 5: Commit**

```bash
git add openscad/components/flow_tray_003.scad
git commit -m "feat(openscad): vách cong tiêu năng r16.4 cao 7mm, hành lang hạt 3.0mm"
```

---

### Task 4: Miệng loe (bellmouth) cổng ra

**Files:**
- Modify: `openscad/components/flow_tray_003.scad`

**Interfaces:**
- Consumes: `bell_fillet_r`, `bell_wall`, `bell_steps`, `outlet_bore`, `port_z`, `tray_inner` (Task 1); `tray_internals()` (Task 3).
- Produces: `function bell_r(a)`, `function bell_z(a)`, `module bell_outer()`, `module bell_void()`.

- [x] **Step 1: Thêm miệng loe**

Trong `openscad/components/flow_tray_003.scad`, chèn TRƯỚC `module tray_internals()`:

```openscad
// --- (3) MIỆNG LOE (bellmouth) tại cổng RA ---
// Biên dạng: cung 1/4 đường tròn bán kính bell_fillet_r, tiếp tuyến RADIAL tại
// miệng loe và tiếp tuyến DỌC TRỤC tại cổ → dòng lướt mượt vào lòng ống, không
// bị bóp nghẹt ở mép sắc (hệ số tổn thất K: ~0.5 → <0.05).
// Trục cục bộ +Z: miệng loe (rộng Ø12) tại z=0, cổ (Ø6) tại z=bell_fillet_r.
function bell_r(a) = outlet_bore/2 + bell_fillet_r - bell_fillet_r * sin(a);
function bell_z(a) = bell_fillet_r - bell_fillet_r * cos(a);

// Vỏ ngoài loa kèn (đặc). Kéo dài thêm 1mm quá cổ để CHỌC vào thành khay
// (giao transversal, tránh mặt tiếp tuyến gây non-manifold khi union).
module bell_outer() {
    rotate_extrude($fn = 96)
        polygon(points = concat(
            [[0, 0]],
            [for (i = [0 : bell_steps]) let (a = i * 90 / bell_steps)
                [bell_r(a) + bell_wall, bell_z(a)]],
            [[bell_r(90) + bell_wall, bell_fillet_r + 1.0],
             [0, bell_fillet_r + 1.0]]
        ));
}

// Lòng loa kèn (phần bị khoét). Kéo dài quá cổ để nối liền lòng ngạnh Ø6.
module bell_void() {
    rotate_extrude($fn = 96)
        polygon(points = concat(
            [[0, 0]],
            [for (i = [0 : bell_steps]) let (a = i * 90 / bell_steps)
                [bell_r(a), bell_z(a)]],
            [[outlet_bore/2, bell_fillet_r + 2.0],
             [0, bell_fillet_r + 2.0]]
        ));
}

// Cụm loa kèn đã đặt đúng vị trí + CẮT PHẲNG tại sàn z=0.
// Cắt sàn là ĐÚNG về vật lý: loa kèn hút sát sàn thì chính mặt sàn đóng vai trò
// thành dưới (giống bellmouth đặt sát đáy bể hút của bơm công nghiệp), đồng thời
// tránh loe thò xuống dưới z=0 (vùng hốc đĩa acrylic).
module bellmouth_boss() {
    intersection() {
        difference() {
            translate([tray_inner/2 - bell_fillet_r, 0, port_z])
                rotate([0, 90, 0]) bell_outer();
            translate([tray_inner/2 - bell_fillet_r, 0, port_z])
                rotate([0, 90, 0]) bell_void();
        }
        translate([-tray_outer, -tray_outer, 0])
            cube([2*tray_outer, 2*tray_outer, tray_depth]);
    }
}
```

Rồi sửa `module tray_internals()` thành:

```openscad
module tray_internals() {
    arc_baffle();
    bellmouth_boss();
}
```

- [x] **Step 2: Render kiểm miệng loe**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/flow_tray_003.scad --size 1200x900 --camera -60,0,6,70,0,20,140 --output openscad/components/flow_tray_003_bell.png
```

Đọc PNG. Expected: thấy **loa kèn nhô vào lòng khay ở phía +X**, miệng rộng hướng vào tâm khay, chân tì phẳng trên sàn z=0.

- [x] **Step 3: Kiểm lòng loe thông suốt ra ngạnh (không bị bít)**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/flow_tray_003.scad --size 1200x900 --camera 0,0,3,90,0,0,120 --output openscad/components/flow_tray_003_bore.png
```

Đọc PNG (nhìn dọc trục Y, thấy mặt cắt ngang tại cao độ cổng). Expected: nhìn xuyên được từ miệng loe ra tới đầu ngạnh — **không có vách nào chắn ngang**. Nếu bị bít → `bell_void()` chưa kéo dài đủ; tăng `bell_fillet_r + 2.0` thành `+ 3.0`.

- [x] **Step 4: Export STL và kiểm manifold**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/components/flow_tray_003.scad --output /tmp/tray003_t4.stl
```

Expected: manifold OK.

- [x] **Step 5: Commit**

```bash
git add openscad/components/flow_tray_003.scad openscad/components/flow_tray_003_*.png
git commit -m "feat(openscad): miệng loe bellmouth R3 cổng ra chống dồn ứ dội sóng"
```

---

### Task 5: Nối `_003` vào file in + assembly

**Files:**
- Modify: `openscad/print/print_flow_tray.scad:6`
- Modify: `openscad/aqua_scope_assembly_001.scad:25`
- Create: `openscad/print/print_flow_tray.stl` (ghi đè bản cũ)

**Interfaces:**
- Consumes: `flow_tray()` từ `flow_tray_003.scad`.

- [x] **Step 1: Trỏ file in sang `_003`**

Sửa `openscad/print/print_flow_tray.scad`, thay toàn bộ nội dung:

```openscad
// print_flow_tray.scad — Khay Macro-Flow (1 chi tiết in).
// _003: thêm cụm CHỐNG SÓNG — cửa vào đục lỗ 4 cửa sổ, vách cong tiêu năng
// r16.4 cao 7mm, miệng loe bellmouth R3 tại cổng ra. Kích thước gốc khay không đổi.
// In: úp miệng khay xuống bàn (đáy hốc đĩa lên trên) hoặc đứng như dùng + support
// cho 2 ngạnh ngang & hộp loe. Sau in: doa lòng ngạnh Ø6, thử đĩa acrylic vào hốc,
// KIỂM 4 cửa sổ vào không bị dính nhựa thừa (thông được que Ø3).
include <../constants.scad>
use <../components/flow_tray_003.scad>

flow_tray();
```

- [x] **Step 2: Trỏ assembly sang `_003`**

Sửa `openscad/aqua_scope_assembly_001.scad` dòng 25, từ:

```openscad
use <components/flow_tray_002.scad>   // _002: đáy khay mở (hết đĩa đặc 1mm bít đáy)
```

thành:

```openscad
use <components/flow_tray_003.scad>   // _003: cụm chống sóng (vách cong + loe + cửa đục lỗ)
```

- [x] **Step 3: Render assembly kiểm không va chạm chi tiết khác**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/aqua_scope_assembly_001.scad --size 1400x1000 --output openscad/aqua_scope_assembly_003check.png
```

Đọc PNG. Expected: cụm lắp dựng được, không có `ERROR`; vách cong + loa kèn nằm gọn trong lòng ống, không đâm ra ngoài vỏ, không chạm vòng chặn khay (`stop_ring`, z=12..14) — vách cao 7mm < 12mm nên phải còn hở.

- [x] **Step 4: Export STL bản in chính thức + kiểm manifold**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_flow_tray.scad --output openscad/print/print_flow_tray.stl
```

Expected: manifold OK, báo số facet > 0.

- [x] **Step 5: Commit**

```bash
git add openscad/print/print_flow_tray.scad openscad/print/print_flow_tray.stl openscad/aqua_scope_assembly_001.scad openscad/aqua_scope_assembly_003check.png
git commit -m "feat(openscad): chuyển file in + assembly sang flow_tray_003"
```

---

### Task 6: Firmware bơm MOSFET/PWM — soft-start, cruise, soft-stop

**Files:**
- Create: `firmware/pump_pwm_test/pump_pwm_test.ino`
- Reference (đọc, không sửa): `firmware/pump_stopflow_test/pump_stopflow_test.ino`

**Interfaces:**
- Produces: firmware độc lập, điều khiển qua Serial 115200. Lệnh: `p` trạng thái, `0`/`1` tắt/bật tay, `a` chạy lại auto, `f/s/x/c<ms>` đặt thời lượng 4 pha, `d<0-100>` đặt cruise duty pha FILL, `X<0-100>` đặt duty pha FLUSH, `u<ms>` ramp-up, `w<ms>` ramp-down, `r` khôi phục mặc định, `?` menu.

- [x] **Step 1: Viết firmware**

Tạo `firmware/pump_pwm_test/pump_pwm_test.ino`:

```cpp
// pump_pwm_test.ino
// Firmware TEST bơm RS365 12V qua MOSFET + PWM (thay module relay ON/OFF).
// Mục tiêu chống sóng (docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md):
//   1. SOFT-STOP: vuốt duty 100%→0 trong ~350ms trước khi tắt hẳn, thay vì cắt đột
//      ngột. Cắt đột ngột gây BÚA NƯỚC (xung áp suất do khối nước trong ống có quán
//      tính, không dừng kịp theo motor) — tự nó kích một đợt sóng mới đúng lúc bắt
//      đầu pha SETTLING.
//   2. SOFT-START: vuốt 0→duty khi khởi động, tránh cú giật hút lúc bơm vào tải.
//   3. CRUISE DUTY < 100% suốt pha FILL: giảm vận tốc hút trung bình xuống dưới
//      ngưỡng gây "ực nước" (xoáy hút khí) tại miệng cổng xả. Giá trị đúng KHÔNG
//      tính được bằng lý thuyết — phải dò thực nghiệm bằng lệnh 'd'.
//      Pha FLUSH vẫn chạy duty cao để quét sạch hạt.
//
// ⚠️⚠️ KHÁC BIỆT SỐNG CÒN SO VỚI BẢN RELAY (pump_stopflow_test.ino):
//   Module relay opto trong bản cũ là ACTIVE-LOW  (GPIO LOW  = bơm CHẠY).
//   MOSFET N-channel IRLZ44N ở đây là  ACTIVE-HIGH (GPIO HIGH = bơm CHẠY).
//   Nạp nhầm bản này với đấu nối relay (hoặc ngược lại) = bơm chạy full tốc ngay
//   lúc boot. Kiểm kỹ phần cứng trước khi nạp.
//
// Đấu nối (MOSFET N-channel low-side):
//   ESP32 GPIO13 --[220Ω]--> Gate IRLZ44N
//   Gate --[10kΩ]--> GND        (kéo xuống: MOSFET TẮT khi ESP32 reset/boot,
//                                lúc đó GPIO ở trạng thái trôi nổi)
//   Source IRLZ44N -> GND chung (ESP32 GND + GND nguồn 12V)
//   Drain  IRLZ44N -> Bơm (−)
//   Bơm (+)        -> 12V+ (adapter 12V/2A)
//   Diode 1N4007/UF4007 song song 2 cực bơm, CATỐT (vạch) về phía 12V+
//     → dập xung cảm ứng ngược khi ngắt dòng cuộn dây motor
//   Tụ gốm 0.1µF hàn ngang 2 cực bơm, càng sát motor càng tốt (chống nhiễu chổi than)
//   Tụ hóa 470–1000µF trên rail 12V (gánh dòng khởi động đỉnh ~2A)
//
// ⚠️ IRLZ44N (logic-level) — KHÔNG dùng IRF540N: IRF540N là standard-level, cần
//    ~10V ở cổng mới mở bão hòa; với 3.3V của ESP32 nó chỉ mở dở, điện trở dẫn cao
//    hơn nhiều so datasheet → nóng bất thường, có thể hỏng.
//
// Board: ESP32 bất kỳ, Arduino-ESP32 core 3.x (API ledcAttach/ledcWrite).
//        Core 2.x dùng ledcSetup/ledcAttachPin — KHÔNG biên dịch được file này.

#include <Arduino.h>

// ---------- Cấu hình chân & PWM ----------
const int PUMP_PIN  = 13;
const int PWM_FREQ  = 20000;  // 20kHz: ngoài ngưỡng nghe + dòng cuộn cảm liên tục
const int PWM_BITS  = 10;     // độ phân giải 10 bit → duty 0..1023
const int PWM_MAX   = (1 << PWM_BITS) - 1;

// ---------- Tham số chu trình ----------
struct Timing {
  uint32_t fillMs     = 5000;
  uint32_t settleMs   = 2000;
  uint32_t flushMs    = 5000;
  uint32_t cooldownMs = 3000;
  uint32_t rampUpMs   = 250;   // vuốt lên khi khởi động
  uint32_t rampDownMs = 350;   // vuốt xuống trước khi tắt (chống búa nước)
  uint8_t  fillDuty   = 55;    // % — GIÁ TRỊ KHỞI ĐIỂM, phải dò thực nghiệm bằng 'd'
  uint8_t  flushDuty  = 100;   // % — flush cần mạnh để quét sạch hạt
} timing;

enum Phase { FILLING, SETTLING, FLUSHING, COOLDOWN };

const char* phaseName(Phase p) {
  switch (p) {
    case FILLING:  return "FILLING (bom chay cruise - fill)";
    case SETTLING: return "SETTLING (bom tat - lang nuoc - CHUP ANH)";
    case FLUSHING: return "FLUSHING (bom chay manh - xa hat)";
    case COOLDOWN: return "COOLDOWN (bom tat - nghi)";
  }
  return "?";
}

Phase    phase        = FILLING;
uint32_t phaseStartMs = 0;
bool     autoRunning  = true;
uint32_t cycleCount   = 0;
uint8_t  curDuty      = 0;     // % duty hiện tại

void pumpDuty(uint8_t pct) {
  if (pct > 100) pct = 100;
  curDuty = pct;
  ledcWrite(PUMP_PIN, (uint32_t)pct * PWM_MAX / 100);
}

// Vuốt duty tuyến tính từ mức hiện tại tới đích trong ms mili-giây.
// CHẶN (blocking) — chấp nhận được vì đây là firmware test 1 việc, và mọi pha
// đều phải đợi ramp xong mới có ý nghĩa. Bước 10ms đủ mượt so quán tính motor.
void rampDuty(uint8_t target, uint32_t ms) {
  const uint32_t stepMs = 10;
  if (ms < stepMs) { pumpDuty(target); return; }
  uint32_t steps = ms / stepMs;
  int      from  = curDuty;
  for (uint32_t i = 1; i <= steps; i++) {
    pumpDuty((uint8_t)(from + (int)(target - from) * (int)i / (int)steps));
    delay(stepMs);
  }
  pumpDuty(target);
}

void enterPhase(Phase p) {
  // Ra khỏi pha đang chạy: nếu sắp dừng bơm thì vuốt xuống TRƯỚC (chống búa nước)
  bool willRun = (p == FILLING || p == FLUSHING);
  if (!willRun && curDuty > 0) rampDuty(0, timing.rampDownMs);

  phase = p;
  phaseStartMs = millis();

  if (willRun) {
    uint8_t target = (p == FILLING) ? timing.fillDuty : timing.flushDuty;
    rampDuty(target, timing.rampUpMs);
  }

  Serial.printf("[%lu ms] -> %s | duty=%u%%\n", phaseStartMs, phaseName(p), curDuty);
  if (p == SETTLING) {
    Serial.println("          (day la luc thuc te se: bat den nen + chup 1 anh)");
  }
}

void printStatus() {
  Serial.println(F("--- Trang thai ---"));
  Serial.printf("Auto:      %s\n", autoRunning ? "dang chay" : "TAM DUNG (dieu khien tay)");
  Serial.printf("Pha:       %s (da %lu ms)\n", phaseName(phase), millis() - phaseStartMs);
  Serial.printf("Duty:      %u%%\n", curDuty);
  Serial.printf("Chu ky:    %lu\n", cycleCount);
  Serial.printf("Timing(ms): fill=%lu settle=%lu flush=%lu cooldown=%lu\n",
                timing.fillMs, timing.settleMs, timing.flushMs, timing.cooldownMs);
  Serial.printf("Ramp(ms):   up=%lu down=%lu\n", timing.rampUpMs, timing.rampDownMs);
  Serial.printf("Duty(%%):    fill=%u flush=%u\n", timing.fillDuty, timing.flushDuty);
  Serial.println(F("------------------"));
}

void printHelp() {
  Serial.println(F("Lenh Serial:"));
  Serial.println(F("  p         - in trang thai"));
  Serial.println(F("  0         - TAM DUNG auto, vuot bom ve 0"));
  Serial.println(F("  1         - TAM DUNG auto, vuot bom len fillDuty"));
  Serial.println(F("  a         - chay lai auto tu dau pha FILLING"));
  Serial.println(F("  f<ms>     - thoi gian fill,     vd f3000"));
  Serial.println(F("  s<ms>     - thoi gian settle,   vd s1500"));
  Serial.println(F("  x<ms>     - thoi gian flush,    vd x8000"));
  Serial.println(F("  c<ms>     - thoi gian cooldown, vd c5000"));
  Serial.println(F("  u<ms>     - ramp UP,            vd u250"));
  Serial.println(F("  w<ms>     - ramp DOWN,          vd w350"));
  Serial.println(F("  d<0-100>  - CRUISE duty pha FILL  (do thuc nghiem!), vd d45"));
  Serial.println(F("  X<0-100>  - duty pha FLUSH,        vd X100"));
  Serial.println(F("  r         - khoi phuc mac dinh"));
  Serial.println(F("  ?         - in lai menu"));
  Serial.println(F(""));
  Serial.println(F("CACH DO CRUISE DUTY: chay 'a', nhin mat nuoc luc FILLING."));
  Serial.println(F("Con nghe 'uc uc'/xoay phieu o mieng xa -> ha 'd' 5%% roi thu lai."));
  Serial.println(F("Lay muc THAP NHAT ma van day nuoc len du muc trong fillMs."));
}

void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  char cmd = line[0];
  long val = line.length() > 1 ? line.substring(1).toInt() : -1;

  switch (cmd) {
    case 'p': printStatus(); break;
    case '?': printHelp();   break;
    case '0':
      autoRunning = false;
      rampDuty(0, timing.rampDownMs);
      Serial.println("Manual: bom TAT (da vuot xuong), auto tam dung.");
      break;
    case '1':
      autoRunning = false;
      rampDuty(timing.fillDuty, timing.rampUpMs);
      Serial.printf("Manual: bom BAT duty=%u%%, auto tam dung.\n", curDuty);
      break;
    case 'a':
      autoRunning = true;
      enterPhase(FILLING);
      Serial.println("Da chay lai auto Stop-Flow.");
      break;
    case 'f': if (val > 0) { timing.fillMs     = val; Serial.printf("fillMs=%ld\n", val); }     break;
    case 's': if (val > 0) { timing.settleMs   = val; Serial.printf("settleMs=%ld\n", val); }   break;
    case 'x': if (val > 0) { timing.flushMs    = val; Serial.printf("flushMs=%ld\n", val); }    break;
    case 'c': if (val > 0) { timing.cooldownMs = val; Serial.printf("cooldownMs=%ld\n", val); } break;
    case 'u': if (val >= 0) { timing.rampUpMs   = val; Serial.printf("rampUpMs=%ld\n", val); }   break;
    case 'w': if (val >= 0) { timing.rampDownMs = val; Serial.printf("rampDownMs=%ld\n", val); } break;
    case 'd':
      if (val >= 0 && val <= 100) {
        timing.fillDuty = (uint8_t)val;
        Serial.printf("fillDuty=%ld%%\n", val);
        if (phase == FILLING && curDuty > 0) rampDuty(timing.fillDuty, 200);
      } else Serial.println("Duty phai trong 0..100");
      break;
    case 'X':
      if (val >= 0 && val <= 100) {
        timing.flushDuty = (uint8_t)val;
        Serial.printf("flushDuty=%ld%%\n", val);
      } else Serial.println("Duty phai trong 0..100");
      break;
    case 'r':
      timing = Timing();
      Serial.println("Da khoi phuc mac dinh.");
      break;
    default:
      Serial.println("Lenh khong hop le. Go '?' de xem menu.");
  }
}

void setup() {
  // AN TOÀN TRƯỚC TIÊN: ghim chân xuống LOW (= MOSFET TẮT) trước mọi việc khác,
  // rồi mới gắn PWM. Ngược chiều với bản relay active-low — xem cảnh báo đầu file.
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);

  ledcAttach(PUMP_PIN, PWM_FREQ, PWM_BITS);
  pumpDuty(0);

  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println(F("=== Aqua Scope - Pump PWM (MOSFET IRLZ44N) test firmware ==="));
  Serial.printf("PUMP_PIN=GPIO%d | PWM %dHz %d-bit | ACTIVE-HIGH (HIGH = bom CHAY)\n",
                PUMP_PIN, PWM_FREQ, PWM_BITS);
  Serial.println(F("!! Firmware nay dung cho MOSFET. KHONG nap khi dang dau RELAY active-low !!"));
  printHelp();

  enterPhase(FILLING);
}

void loop() {
  handleSerial();
  if (!autoRunning) return;

  uint32_t elapsed = millis() - phaseStartMs;
  switch (phase) {
    case FILLING:  if (elapsed >= timing.fillMs)     enterPhase(SETTLING); break;
    case SETTLING: if (elapsed >= timing.settleMs)   enterPhase(FLUSHING); break;
    case FLUSHING: if (elapsed >= timing.flushMs)    enterPhase(COOLDOWN); break;
    case COOLDOWN:
      if (elapsed >= timing.cooldownMs) { cycleCount++; enterPhase(FILLING); }
      break;
  }
}
```

- [x] **Step 2: Biên dịch kiểm cú pháp (KHÔNG nạp)**

Tìm `arduino-cli` đi kèm Arduino IDE (theo ghi chú dự án: build firmware cam bằng arduino-cli đi kèm IDE):

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/pump_pwm_test
```

Expected: `Sketch uses ... bytes`, không có lỗi. **Nếu báo `'ledcAttach' was not declared`** → máy đang dùng Arduino-ESP32 core 2.x; đổi 3 dòng trong `setup()` thành:
```cpp
  ledcSetup(0, PWM_FREQ, PWM_BITS);
  ledcAttachPin(PUMP_PIN, 0);
```
và trong `pumpDuty()` đổi `ledcWrite(PUMP_PIN, ...)` thành `ledcWrite(0, ...)`.

- [x] **Step 3: Kiểm bằng mắt logic an toàn boot**

Đọc lại `setup()` trong file vừa tạo và xác nhận đúng thứ tự: `pinMode` → `digitalWrite(LOW)` → `ledcAttach` → `pumpDuty(0)` → mới tới `Serial.begin`. Xác nhận không có lệnh nào đặt duty > 0 trước `enterPhase(FILLING)`.

- [x] **Step 4: Commit**

```bash
git add firmware/pump_pwm_test/pump_pwm_test.ino
git commit -m "feat(firmware): điều khiển bơm MOSFET/PWM - soft-start, cruise duty, soft-stop"
```

---

### Task 7: Ghi 4 lỗi mới vào tài liệu nghiên cứu

**Files:**
- Modify: `docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md` (chèn vào cuối PHẦN C)

- [x] **Step 1: Thêm mục ghi lỗi**

Chèn vào cuối `docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md`:

```markdown

---

## PHẦN D — 4 lỗi phát hiện thêm khi DỰNG HÌNH HỌC (2026-07-23)

Bốn lỗi dưới đây chỉ lộ ra khi tính va chạm hình học thật, không lộ khi kiểm chứng
công thức. Số đã sửa nằm trong `openscad/constants.scad` §CHỐNG SÓNG; chi tiết lý do
trong `docs/superpowers/plans/2026-07-23-khay-lang-song-v003.md`.

| # | Số của tài liệu | Vấn đề | Số đã sửa |
|---|---|---|---|
| 1 | `baffle_r_mid = 17.6` | Hành lang sau vách chỉ 1.8mm < hạt 2mm. Đây là lối thoát DUY NHẤT của túi cổng vào ⇒ hạt kẹt vĩnh viễn ⇒ **vi phạm ràng buộc cứng** | `16.4` (hành lang 3.0mm) |
| 2 | `baffle_h = 5.0` | Thấp hơn mực nước 6mm ⇒ diện tích tràn qua nóc (~27.6mm²) còn lớn hơn diện tích đi vòng 2 đầu (~21.6mm²) ⇒ ~50% lưu lượng xả động năng thẳng vào MẶT NƯỚC. Lý do "thoát bọt" không áp dụng vì vách hở 2 đầu | `7.0` (> mực nước) |
| 3 | `post_gap = 2.5` | Chỉ dư 0.5mm so hạt 2mm, ngay CỬA VÀO. Nghẽn ở đây = hạt không vào khay = không đếm được (hỏng chính phép đo) | `inlet_gap_w = 3.5` |
| 4 | `fillet_r = 2.0` bo đầu mút vách | Bất khả thi trên vách dày 1.2mm (tối đa = 0.6mm) | bo bán nguyệt `0.6` |

**Giá phải trả đã chấp nhận:** vách tại r=16.4 làm vùng ảnh hóa giảm Ø40 → **Ø31.6mm**
(~62% diện tích cũ). Không giảm độ phân giải hạt (vẫn ~14px/mm ở VGA), chỉ giảm lượng
nước soi được mỗi lần chụp. `baffle_r_mid` để dạng tham số, chỉnh lại được sau in thử.
```

- [x] **Step 2: Commit**

```bash
git add docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md
git commit -m "docs(research): ghi 4 lỗi hình học phát hiện khi dựng SCAD"
```

---

## Sau khi hoàn thành plan này — việc phải làm ngoài phạm vi code

Các mục dưới đây **không thể xác nhận bằng render/STL**, phải in thật + chạy nước thật:

1. **In thử `print_flow_tray.stl`**, kiểm 4 cửa sổ vào thông (que Ø3 lọt), hành lang sau vách cong lọt hạt 2mm thật.
2. **Dò cruise duty**: nạp `pump_pwm_test.ino`, chạy `a`, hạ dần `d` tới khi hết "ực nước" ở miệng xả. Ghi lại giá trị → cập nhật `fillDuty` mặc định.
3. **Đo tần số nhịp màng bơm RS365 thật** — quyết định cả nghi vấn cộng hưởng khay (§2 tài liệu) lẫn có cần T-Dome không (§6).
4. **Quyết T-Dome** (đã hoãn khỏi đợt này): chỉ làm nếu sau (2) và (3) vẫn còn rung nhịp bơm rõ trên mặt nước.
5. **Đo lại thời gian lắng thực tế** so mốc 2s của pha SETTLING — đây mới là thước đo cuối cùng xem cả cụm có đạt hay không.
