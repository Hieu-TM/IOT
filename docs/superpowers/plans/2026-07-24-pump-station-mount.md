# Trạm bơm gọn (đế liền + hộp L298N + kẹp bơm RS365) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay placeholder bbox rời rạc `pump_rs365()` hiện tại bằng một cụm mount in 3D thật — 1 đế liền mang hộp che board L298N (có nắp) + 2 yên kẹp ôm thân trụ bơm RS365 — để bê đi 1 lần, dây điện đi trong khe/rãnh gọn thay vì lòng thòng.

**Architecture:** File mới `openscad/components/pump_station_001.scad` chứa 1 module lắp ghép `pump_station()` (đế + thành hộp L298N hở nắp + 2 yên kẹp bơm, KHÔNG nắp) + module `pump_station_lid()` (nắp hộp, chi tiết in RIÊNG). Baseplate KHÔNG có sàn hộp riêng — sàn hộp L298N chính LÀ mặt trên của đế (giảm 1 lớp thành, in liền khối). Hằng số mới đặt trong `constants.scad` theo đúng khối "Ống dẫn & bơm" hiện có, kèm `assert` an toàn kích thước (đúng cơ chế "test" duy nhất khả thi cho OpenSCAD trong dự án này — xem ghi chú trong `docs/superpowers/plans/2026-07-23-khay-lang-song-v003.md`). `pump_rs365()` trong `accessories_001.scad` giữ nguyên (mô hình hiển thị bơm mua sẵn, KHÔNG in).

**Tech Stack:** OpenSCAD (CLI qua `.claude/skills/*/scripts/*.sh`, xem `CLAUDE.md`).

## Global Constraints

- Ngôn ngữ comment trong mọi file `.scad`/`.md` sửa/tạo: **tiếng Việt** (quy ước repo).
- Hằng số mới đặt trong `openscad/constants.scad`, KHÔNG hardcode số trong component — theo đúng quy ước hiện có của file này.
- Mọi file component tự khai báo `EPS = 0.05;` cục bộ (quy ước đã dùng trong `flow_tray_003.scad`, `tube_body_002.scad`, v.v. — không có `EPS` global).
- `l298n_l/w/h` và `pump_motor_od` là số **ĐIỂN HÌNH/ƯỚC TÍNH**, chưa đo board/bơm thật — phải giữ nguyên các comment cảnh báo này trong code, không xoá.
- KHÔNG sửa `pump_rs365()`, `prescreen()`, `silicone_tube()` trong `accessories_001.scad` — giữ nguyên placeholder hiển thị.
- KHÔNG đổi lựa chọn driver bơm (relay/MOSFET/L298N) hay sửa firmware — phạm vi plan này chỉ là cơ khí mount + đi dây.
- "Test" cho OpenSCAD trong dự án này = 3 lớp: (1) `assert()` chạy khi render — fail thì báo lỗi ngay; (2) render PNG rồi tự đọc ảnh kiểm mắt; (3) export STL + `export-stl.sh` tự kiểm non-manifold/self-intersection. Không có test framework tự động nào khác khả thi cho OpenSCAD.
- OpenSCAD binary trên máy: `C:\Program Files\OpenSCAD\openscad.exe` (đã patch fallback trong 2 script `.sh`, xem `CLAUDE.md`).

---

## Cấu trúc file

| File | Trạng thái | Trách nhiệm |
|---|---|---|
| `openscad/constants.scad` | Sửa | Thêm khối hằng số + `assert` an toàn cho trạm bơm mới |
| `openscad/components/pump_station_001.scad` | Tạo mới | `l298n_box_walls()`, `pump_station_lid()`, `pump_clamp_post()`, `wire_channel()`, `pump_station()` |
| `openscad/print/print_pump_station.scad` | Tạo mới | Xuất STL đế + hộp (không nắp) + 2 yên kẹp — 1 khối in |
| `openscad/print/print_pump_station_lid.scad` | Tạo mới | Xuất STL nắp hộp L298N — chi tiết in riêng |
| `openscad/aqua_scope_assembly_001.scad` | Sửa | Thêm `use` + đặt `pump_station()` cạnh `pump_rs365()` trong khối `show_pump` |
| `HUONG_DAN_LAP_RAP.md` | Sửa | Thêm 2 STL mới vào bảng BOM mục A + ghi chú lắp ở §7 |

**Không đụng tới:** `accessories_001.scad` (giữ nguyên `pump_rs365()` placeholder), mọi firmware trong `firmware/`.

---

### Task 1: Hằng số + assert an toàn cho trạm bơm

**Files:**
- Modify: `openscad/constants.scad` (chèn khối mới ngay sau dòng 165 `// Điện (không thuộc mô hình)...`, trước dòng 167 `// ---... BIẾN THỂ ESP32-CAM`; chèn assert mới ngay trước dòng `echo(str(...))` ở cuối file)

**Interfaces:**
- Produces: `l298n_l`, `l298n_w`, `l298n_h`, `l298n_box_wall`, `l298n_box_clr`, `l298n_foot_h`, `l298n_lid_t`, `l298n_lid_screw_d`, `l298n_lid_clr_d`, `l298n_vent_w`, `l298n_vent_n`, `wire_notch_w`, `wire_notch_h`, `l298n_box_id_l`, `l298n_box_id_w`, `l298n_box_h`, `l298n_box_od_l`, `l298n_box_od_w`, `pump_motor_od`, `pump_clamp_clr`, `pump_clamp_t`, `pump_clamp_w`, `pump_clamp_slot_w`, `pump_clamp_strap_w`, `pump_clamp_gap`, `pump_clamp_id`, `pump_clamp_od`, `pump_station_base_t`, `pump_station_foot_h`, `pump_station_gap`, `pump_station_margin`, `pump_station_len`, `pump_station_wid` — Task 2/3/4/5 dùng trực tiếp các tên này, không đổi tên.

- [ ] **Step 1: Chèn khối hằng số mới**

Chèn vào `openscad/constants.scad` ngay sau dòng 165 (`// Điện (không thuộc mô hình): relay module 1 kênh (demo), 12V/2A, tụ 0.1µF ngang bơm.`):

```openscad

// ---------------------------------------------------------------- Trạm bơm gọn: đế liền + hộp L298N + kẹp bơm (2026-07-24)
// Nguồn: docs/superpowers/specs/2026-07-24-pump-station-mount-design.md
// ⚠️ l298n_* và pump_motor_od là số ĐIỂN HÌNH/ƯỚC TÍNH — CHƯA ĐO board/bơm thật.
// Hộp L298N cố ý rộng rãi (l298n_box_clr) để chịu sai số; yên kẹp bơm có rãnh
// zip-tie bù sai số đường kính nếu bơm thật khác pump_motor_od.
l298n_l             = 43.0;  // dài board L298N (điển hình, chưa đo)
l298n_w             = 43.0;  // rộng board
l298n_h             = 27.0;  // cao kể cả tản nhiệt nhô lên
l298n_box_wall      = 2.0;   // thành hộp
l298n_box_clr       = 2.5;   // khe hở mỗi bên quanh board (khay dung sai, KHÔNG khớp lỗ vít)
l298n_foot_h        = 2.0;   // gờ đỡ góc board bên trong hộp
l298n_lid_t         = 2.0;   // dày nắp hộp
l298n_lid_screw_d   = 2.8;   // lỗ tự-ren M3 giữ nắp (2 góc chéo, trong gờ hộp)
l298n_lid_clr_d     = 3.2;   // lỗ thông M3 trên nắp
l298n_vent_w        = 3.0;   // bề rộng mỗi khe thoát khí
l298n_vent_n        = 5;     // số khe thoát khí (cạnh đối diện khe dây logic)

wire_notch_w        = 6.0;   // bề rộng khe dây (xuyên thành, hở miệng hộp — nắp ép giữ dây)
wire_notch_h        = 5.0;   // sâu khe dây tính từ miệng hộp xuống

pump_motor_od       = 31.5;  // Ø thân trụ động cơ RS365 — ƯỚC TÍNH pump_bbox[2]*0.9 = 35*0.9,
                              // CHƯA ĐO bơm thật
pump_clamp_clr      = 1.0;   // khe hở giữa lòng máng kẹp và thân bơm
pump_clamp_t        = 2.4;   // bề dày thành máng kẹp (dưới lỗ khoan)
pump_clamp_w        = 8.0;   // bề rộng (dọc trục bơm) mỗi yên kẹp
pump_clamp_slot_w   = 24.0;  // bề rộng khe lồng từ đỉnh khối xuống lỗ khoan — HẸP HƠN
                              // pump_clamp_id để PETG hơi dẻo ép giữ bơm khi lồng từ trên
pump_clamp_strap_w  = 3.0;   // rãnh trên đỉnh yên để luồn zip-tie xiết thêm (bù sai số Ø bơm thật)
pump_clamp_gap      = 40.0;  // khoảng cách tâm 2 yên kẹp dọc trục bơm

pump_station_base_t = 3.0;   // dày đế
pump_station_foot_h = 2.0;   // chân đế 4 góc
pump_station_gap     = 20.0; // rãnh dây giữa hộp L298N và cụm yên kẹp bơm
pump_station_margin  = 4.0;  // biên đế quanh hộp/yên kẹp (mép ngoài cùng)

// Dẫn xuất — hộp L298N (đáy hộp = mặt đế, KHÔNG có sàn riêng)
l298n_box_id_l = l298n_l + 2*l298n_box_clr;                  // = 48
l298n_box_id_w = l298n_w + 2*l298n_box_clr;                  // = 48
l298n_box_h    = l298n_h + l298n_foot_h + 3.0;               // = 32: cao thành từ mặt đế tới miệng hộp
l298n_box_od_l = l298n_box_id_l + 2*l298n_box_wall;          // = 52
l298n_box_od_w = l298n_box_id_w + 2*l298n_box_wall;          // = 52

// Dẫn xuất — yên kẹp bơm (khối vuông, tâm lỗ khoan = pump_clamp_od/2 → đối xứng
// trên/dưới → thành dưới lỗ khoan luôn dày đúng bằng pump_clamp_t, không phụ thuộc
// số đo pump_bbox — ưu tiên AN TOÀN KẾT CẤU hơn khớp pixel với model placeholder)
pump_clamp_id = pump_motor_od + 2*pump_clamp_clr;   // = 33.5: Ø lòng máng kẹp
pump_clamp_od = pump_clamp_id + 2*pump_clamp_t;     // = 38.3: Ø ngoài máng kẹp = tổng cao khối yên

// Dẫn xuất — bố cục đế (đơn vị mm)
pump_station_len = pump_station_margin + l298n_box_od_l + pump_station_gap
                   + pump_clamp_gap + pump_clamp_w + pump_station_margin;   // = 128
pump_station_wid = max(l298n_box_od_w, pump_clamp_od) + 2*pump_station_margin; // = 60
```

- [ ] **Step 2: Thêm assert an toàn**

Chèn vào `openscad/constants.scad` ngay TRƯỚC dòng `echo(str("== Aqua Scope constants OK ==...` (dòng cuối file):

```openscad
// --- Assert an toàn cho trạm bơm gọn (2026-07-24) ---
assert(l298n_box_id_l > l298n_l && l298n_box_id_w > l298n_w,
       "khoang hộp L298N phải rộng hơn board (có khe hở dung sai lắp)");
assert(pump_clamp_slot_w < pump_clamp_id,
       "khe lồng yên kẹp phải HẸP HƠN Ø lỗ khoan mới giữ được bơm bằng ép đàn hồi");
assert(pump_clamp_id > pump_motor_od,
       "lòng máng kẹp phải lớn hơn Ø thân bơm (có khe hở lắp pump_clamp_clr)");
assert(pump_clamp_od/2 - pump_clamp_id/2 >= 2.0,
       "thành dưới yên kẹp (dưới lỗ khoan) phải dày ≥2mm để không vỡ khi ép bơm vào");
assert(pump_clamp_gap > pump_clamp_w,
       "2 yên kẹp không được chồng lên nhau dọc trục bơm");
assert(pump_station_wid > pump_clamp_od && pump_station_wid > l298n_box_od_w,
       "đế phải rộng hơn cả hộp L298N lẫn yên kẹp bơm (không hụt biên)");
```

- [ ] **Step 3: Render echo-check để xác nhận assert pass**

```bash
"/c/Program Files/OpenSCAD/openscad.exe" -o /tmp/constants_check.echo openscad/constants.scad
```

Expected: kết thúc bằng dòng `ECHO: "== Aqua Scope constants OK == ..."`, KHÔNG có dòng `ERROR: Assertion ... failed`.

- [ ] **Step 4: Commit**

```bash
git add openscad/constants.scad
git commit -m "feat(openscad): thêm hằng số + assert cho trạm bơm gọn (đế liền + hộp L298N + kẹp bơm)"
```

---

### Task 2: Component `pump_station_001.scad` — hộp L298N + yên kẹp bơm + đế

**Files:**
- Create: `openscad/components/pump_station_001.scad`

**Interfaces:**
- Consumes: mọi hằng số Task 1 sản xuất trong `constants.scad`.
- Produces: module `pump_station()` (đế + thành hộp L298N hở nắp + 2 yên kẹp bơm — KHÔNG nắp), module `pump_station_lid()` (nắp hộp, dùng ở Task 3/4), module nội bộ `l298n_box_walls()`, `pump_clamp_post()`, `wire_channel(length)`. Task 4 dùng `pump_station()` và `pump_station_lid()`; Task 5 dùng `pump_station()`.

- [ ] **Step 1: Tạo file với toàn bộ module**

Tạo `openscad/components/pump_station_001.scad`:

```openscad
// ============================================================================
// pump_station_001.scad — Trạm bơm gọn: đế liền + hộp che L298N + yên kẹp RS365
// ----------------------------------------------------------------------------
// Nguồn: docs/superpowers/specs/2026-07-24-pump-station-mount-design.md
// Kiến trúc: 1 tấm đế (baseplate) mang liền 2 cụm — hộp L298N (hở nắp, nắp rời
// pump_station_lid()) và 2 yên kẹp ôm thân trụ bơm RS365 — nối bằng 1 rãnh dây
// nông trên mặt đế. pump_rs365() (accessories_001.scad) KHÔNG đổi, vẫn chỉ là
// mô hình hiển thị bơm mua sẵn (không in); phần in MỚI ở file này là đế + hộp +
// yên kẹp.
//
// Trục dài đế = X. Hộp L298N ở đầu −X (gần), 2 yên kẹp ở đầu +X (xa) — lỗ khoan
// yên kẹp nằm NGANG dọc trục X, khớp hướng trục bơm (giống cách pump_rs365()
// dựng cylinder dọc X qua rotate([0,90,0])).
//
// Yên kẹp: khối vuông + lỗ khoan ngang Ø pump_clamp_id + khe hẹp từ đỉnh khối
// xuống tâm lỗ (rộng pump_clamp_slot_w < Ø lỗ) để lồng bơm từ TRÊN xuống, PETG
// hơi dẻo ép giữ. Tâm lỗ đặt tại pump_clamp_od/2 (đối xứng trên/dưới khối) để
// thành dưới lỗ luôn dày đúng pump_clamp_t bất kể số đo pump_bbox — ưu tiên AN
// TOÀN KẾT CẤU hơn là khớp pixel với model placeholder pump_rs365() (lệch cao độ
// vài mm so placeholder chỉ là sai khác hiển thị, không ảnh hưởng mount thật).
// ============================================================================
include <../constants.scad>

EPS = 0.05;

// ---------------------------------------------------------------- Hộp L298N (hở nắp — đáy = mặt đế bên dưới)
module l298n_box_walls() {
    difference() {
        cube([l298n_box_od_l, l298n_box_od_w, l298n_box_h]);
        // Khoét lòng hộp (chừa 4 thành; không chừa sàn — sàn = mặt đế)
        translate([l298n_box_wall, l298n_box_wall, -EPS])
            cube([l298n_box_id_l, l298n_box_id_w, l298n_box_h + 2*EPS]);
        // Khe dây INPUT 12V — cạnh −X (hướng ra ngoài trạm, xa bơm)
        translate([-EPS, l298n_box_od_w/2 - wire_notch_w/2, l298n_box_h - wire_notch_h])
            cube([l298n_box_wall + 2*EPS, wire_notch_w, wire_notch_h + EPS]);
        // Khe dây OUTPUT động cơ — cạnh +X (hướng về phía yên kẹp bơm)
        translate([l298n_box_od_l - l298n_box_wall - EPS, l298n_box_od_w/2 - wire_notch_w/2,
                   l298n_box_h - wire_notch_h])
            cube([l298n_box_wall + 2*EPS, wire_notch_w, wire_notch_h + EPS]);
        // Khe dây LOGIC (IN1/IN2/EN + GND lên ESP32) — cạnh +Y (về khối quang chính)
        translate([l298n_box_od_l/2 - wire_notch_w/2, l298n_box_od_w - l298n_box_wall - EPS,
                   l298n_box_h - wire_notch_h])
            cube([wire_notch_w, l298n_box_wall + 2*EPS, wire_notch_h + EPS]);
        // Khe thoát khí — cạnh −Y (đối diện khe logic, phía tản nhiệt board)
        for (i = [0 : l298n_vent_n - 1])
            translate([l298n_box_wall + 4 + i * (l298n_box_id_l - 8) / (l298n_vent_n - 1) - l298n_vent_w/2,
                       -EPS, 6])
                cube([l298n_vent_w, l298n_box_wall + 2*EPS, l298n_box_h - 6 - wire_notch_h - 2]);
    }
    // 4 gờ đỡ góc board (board tựa lên — KHÔNG cần khớp lỗ vít board thật)
    foot_sz = 5.0;
    for (cx = [l298n_box_wall + 1, l298n_box_od_l - l298n_box_wall - 1 - foot_sz])
        for (cy = [l298n_box_wall + 1, l298n_box_od_w - l298n_box_wall - 1 - foot_sz])
            translate([cx, cy, 0])
                cube([foot_sz, foot_sz, l298n_foot_h]);
    // 2 gờ vít M3 tự-ren giữ nắp, 2 góc chéo
    boss_d = 6.0;
    for (p = [[l298n_box_wall + boss_d/2 + 1, l298n_box_wall + boss_d/2 + 1],
              [l298n_box_od_l - l298n_box_wall - boss_d/2 - 1,
               l298n_box_od_w - l298n_box_wall - boss_d/2 - 1]])
        translate([p[0], p[1], 0])
            difference() {
                cylinder(d = boss_d, h = l298n_box_h - 3, $fn = 32);
                translate([0, 0, -EPS])
                    cylinder(d = l298n_lid_screw_d, h = l298n_box_h - 3 - 5 + EPS, $fn = 24);
            }
}

// Nắp hộp L298N — chi tiết in RIÊNG (print_pump_station_lid.scad)
module pump_station_lid() {
    boss_d = 6.0;
    difference() {
        cube([l298n_box_od_l, l298n_box_od_w, l298n_lid_t]);
        for (p = [[l298n_box_wall + boss_d/2 + 1, l298n_box_wall + boss_d/2 + 1],
                  [l298n_box_od_l - l298n_box_wall - boss_d/2 - 1,
                   l298n_box_od_w - l298n_box_wall - boss_d/2 - 1]])
            translate([p[0], p[1], -EPS])
                cylinder(d = l298n_lid_clr_d, h = l298n_lid_t + 2*EPS, $fn = 24);
    }
}

// ---------------------------------------------------------------- Yên kẹp bơm: khối + lỗ khoan ngang + khe lồng từ trên
module pump_clamp_post() {
    block_h  = pump_clamp_od;
    center_z = pump_clamp_od / 2;
    difference() {
        translate([0, -pump_clamp_od/2, 0])
            cube([pump_clamp_w, pump_clamp_od, block_h]);
        // Lỗ khoan ngang (trục X = trục bơm) giữ thân trụ động cơ
        translate([-EPS, 0, center_z])
            rotate([0, 90, 0])
                cylinder(d = pump_clamp_id, h = pump_clamp_w + 2*EPS, $fn = 64);
        // Khe lồng từ ĐỈNH khối xuống tâm lỗ (hẹp hơn Ø lỗ — PETG dẻo ép giữ bơm)
        translate([-EPS, -pump_clamp_slot_w/2, center_z])
            cube([pump_clamp_w + 2*EPS, pump_clamp_slot_w, block_h - center_z + EPS]);
        // Rãnh zip-tie trên đỉnh khối, cắt ngang qua khe lồng (bù sai số Ø bơm thật)
        translate([pump_clamp_w/2 - pump_clamp_strap_w/2, -pump_clamp_od/2 - EPS, block_h - 1.5])
            cube([pump_clamp_strap_w, pump_clamp_od + 2*EPS, 1.5 + EPS]);
    }
}

// ---------------------------------------------------------------- Rãnh dây nối hộp L298N ↔ yên kẹp bơm (khoét vào mặt đế)
module wire_channel(length) {
    ch_w = 6.0; ch_d = 1.5;
    translate([0, -ch_w/2, -ch_d])
        cube([length, ch_w, ch_d + EPS]);
}

// ---------------------------------------------------------------- Trạm bơm hoàn chỉnh (đế + hộp L298N không nắp + 2 yên kẹp)
// Gốc cục bộ: góc −X/−Y của đế tại z=0 (mặt TRÊN đế); đế dày pump_station_base_t
// nằm ở z ÂM (−pump_station_base_t .. 0).
module pump_station() {
    box_x    = pump_station_margin;
    clamp_x0 = box_x + l298n_box_od_l + pump_station_gap;
    clamp_x1 = clamp_x0 + pump_clamp_gap;
    base_y   = pump_station_wid / 2;
    chan_len = clamp_x0 - (box_x + l298n_box_od_l);

    // Đế (khoét rãnh dây trên mặt)
    difference() {
        translate([0, -base_y, -pump_station_base_t])
            cube([pump_station_len, pump_station_wid, pump_station_base_t]);
        translate([box_x + l298n_box_od_l, 0, 0])
            wire_channel(chan_len);
    }
    // 4 chân đế góc
    foot_sz = 6.0;
    for (fx = [3, pump_station_len - 3 - foot_sz])
        for (fy = [-base_y + 3, base_y - 3 - foot_sz])
            translate([fx, fy, -pump_station_base_t - pump_station_foot_h])
                cube([foot_sz, foot_sz, pump_station_foot_h]);
    // Hộp L298N (căn giữa theo bề rộng đế)
    translate([box_x, -l298n_box_od_w/2, 0]) l298n_box_walls();
    // 2 yên kẹp bơm (căn giữa theo bề rộng đế; lỗ khoan nằm ngang trục X)
    translate([clamp_x0, 0, 0]) pump_clamp_post();
    translate([clamp_x1, 0, 0]) pump_clamp_post();
}

// Xem lẻ
pump_station();
translate([0, 80, 0]) pump_station_lid();
```

- [ ] **Step 2: Render preview toàn cụm**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/pump_station_001.scad --size 1200x800 --camera 60,0,10,55,0,25,220 --output openscad/components/pump_station_001.png
```

- [ ] **Step 3: Đọc PNG kiểm mắt**

Đọc `openscad/components/pump_station_001.png` bằng tool Read. Kiểm:
- Đế 1 khối liền, hộp L298N ở 1 đầu (4 thành + 3 khe dây thấy rõ ở miệng hộp), 2 yên kẹp ở đầu kia (mỗi yên có lỗ tròn xuyên ngang + khe hở phía trên).
- Rãnh dây nông nối giữa hộp và yên kẹp thứ nhất, không bị khối nào che khuất/xoá mất (dấu hiệu lệnh `difference()` bị áp sai thứ tự).
- Nắp `pump_station_lid()` (khối phẳng có 2 lỗ) nằm tách biệt ở `y=80`, kích thước khớp bằng mắt với miệng hộp.

Nếu chi tiết nào biến mất hoặc chồng lấn sai vị trí, sửa lại `translate`/thứ tự `difference()` tương ứng trong file rồi lặp lại Step 2.

- [ ] **Step 4: Commit**

```bash
git add openscad/components/pump_station_001.scad openscad/components/pump_station_001.png
git commit -m "feat(openscad): thêm component pump_station_001 - đế liền + hộp L298N + yên kẹp bơm"
```

---

### Task 3: Xuất STL — cụm đế + hộp + yên kẹp

**Files:**
- Create: `openscad/print/print_pump_station.scad`

**Interfaces:**
- Consumes: `pump_station()` từ Task 2.

- [ ] **Step 1: Tạo file in**

Tạo `openscad/print/print_pump_station.scad`:

```openscad
// print_pump_station.scad — Đế liền + hộp che L298N (không nắp) + 2 yên kẹp bơm (1 chi tiết in).
// In phẳng (mặt đế xuống bàn), không cần support. Vật liệu PETG (dẻo hơn PLA —
// khe lồng yên kẹp cần đàn hồi nhẹ để ép giữ thân bơm khi lắp).
// Sau in: thử board L298N vào hộp (4 gờ góc phải đỡ được board không cấn),
// thử lồng ống trụ Ø~31.5mm (hoặc bơm thật) vào 2 yên kẹp từ trên xuống.
include <../constants.scad>
use <../components/pump_station_001.scad>

pump_station();
```

- [ ] **Step 2: Export STL + kiểm manifold**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station.scad --output openscad/print/print_pump_station.stl
```

Expected: kết thúc bằng thông báo export thành công, KHÔNG có cảnh báo `non-manifold` / `self-intersecting` nghiêm trọng. Nếu có, đọc thông báo, xác định module gây lỗi (thường là 1 trong các `difference()` trong `l298n_box_walls()` hoặc `pump_clamp_post()`), sửa (thường là thiếu `EPS` ở mặt cắt sát biên) rồi export lại.

- [ ] **Step 3: Commit**

```bash
git add openscad/print/print_pump_station.scad openscad/print/print_pump_station.stl
git commit -m "feat(openscad): xuất STL print_pump_station (đế + hộp L298N + yên kẹp bơm)"
```

---

### Task 4: Xuất STL — nắp hộp L298N

**Files:**
- Create: `openscad/print/print_pump_station_lid.scad`

**Interfaces:**
- Consumes: `pump_station_lid()` từ Task 2.

- [ ] **Step 1: Tạo file in**

Tạo `openscad/print/print_pump_station_lid.scad`:

```openscad
// print_pump_station_lid.scad — Nắp hộp L298N (1 chi tiết in riêng).
// In phẳng. Bắt 2 vít M3 tự-ren vào 2 gờ chéo của print_pump_station.stl để
// tháo/lắp khi cần chỉnh jumper 5V hoặc kiểm tra board.
include <../constants.scad>
use <../components/pump_station_001.scad>

pump_station_lid();
```

- [ ] **Step 2: Export STL + kiểm manifold**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station_lid.scad --output openscad/print/print_pump_station_lid.stl
```

Expected: export thành công, không cảnh báo non-manifold (đây là khối phẳng đơn giản, rủi ro thấp).

- [ ] **Step 3: Commit**

```bash
git add openscad/print/print_pump_station_lid.scad openscad/print/print_pump_station_lid.stl
git commit -m "feat(openscad): xuất STL print_pump_station_lid (nắp hộp L298N)"
```

---

### Task 5: Tích hợp vào assembly tổng

**Files:**
- Modify: `openscad/aqua_scope_assembly_001.scad:30` (thêm `use` sau dòng `use <components/accessories_001.scad>`)
- Modify: `openscad/aqua_scope_assembly_001.scad:92-105` (khối `if (show_pump) { ... }`)

**Interfaces:**
- Consumes: `pump_station()` từ Task 2.

- [ ] **Step 1: Thêm use statement**

Trong `openscad/aqua_scope_assembly_001.scad`, ngay sau dòng 30 (`use <components/accessories_001.scad>`), thêm:

```openscad
use <components/pump_station_001.scad>
```

- [ ] **Step 2: Đặt pump_station() cạnh pump_rs365() trong khối show_pump**

Thay khối hiện tại (dòng 92-95):

```openscad
if (show_pump) {
    // Bơm đặt trên mặt bàn (z = vành đáy vỏ), lệch +X, cách xa chống rung
    translate([120 + 1.5*e, 0, z_housing_bot])
        rotate([0, 0, 180]) pump_rs365();
```

Thành:

```openscad
if (show_pump) {
    // Bơm đặt trên mặt bàn (z = vành đáy vỏ), lệch +X, cách xa chống rung
    translate([120 + 1.5*e, 0, z_housing_bot])
        rotate([0, 0, 180]) pump_rs365();
    // Trạm bơm gọn (đế + hộp L298N + yên kẹp) — đặt CẠNH pump_rs365() để so kích
    // thước khi render. Vị trí không khớp pixel-perfect với placeholder pump_rs365()
    // ở trên (placeholder giả định motor tựa thẳng mặt bàn; yên kẹp thật nâng bơm
    // cao hơn mặt bàn ~19mm để an toàn kết cấu — xem comment trong pump_station_001.scad).
    // Khi lắp bơm THẬT, đặt nó vào đúng lòng 2 yên kẹp, không cần khớp model này.
    translate([190 + 1.5*e, 0, z_housing_bot]) pump_station();
```

(giữ nguyên phần còn lại của khối `if (show_pump) { ... }` — 2 dòng `tube_body()`/ống mềm không đổi)

- [ ] **Step 3: Render toàn cảnh assembly**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/aqua_scope_assembly_001.scad --size 1400x1000 --output openscad/aqua_scope_assembly_004check.png
```

- [ ] **Step 4: Đọc PNG kiểm mắt**

Đọc `openscad/aqua_scope_assembly_004check.png`. Kiểm: trạm bơm mới (đế + hộp + 2 yên kẹp) xuất hiện cạnh placeholder `pump_rs365()`, không chồng lấn/xuyên vào ống chính hay khay. Nếu chồng lấn, tăng offset X (190) trong Step 2.

- [ ] **Step 5: Commit**

```bash
git add openscad/aqua_scope_assembly_001.scad openscad/aqua_scope_assembly_004check.png
git commit -m "feat(openscad): tích hợp pump_station() vào assembly tổng"
```

---

### Task 6: Cập nhật hướng dẫn lắp ráp

**Files:**
- Modify: `HUONG_DAN_LAP_RAP.md:18-30` (bảng BOM mục A)
- Modify: `HUONG_DAN_LAP_RAP.md:134-162` (§7 — thêm ghi chú lắp trạm bơm mới)

**Interfaces:** (không có — chỉ sửa tài liệu)

- [ ] **Step 1: Thêm 2 STL mới vào bảng BOM mục A**

Trong `HUONG_DAN_LAP_RAP.md`, sau dòng bảng `| print_prescreen.stl | ... |` (dòng 27), thêm 2 dòng:

```markdown
| `print_pump_station.stl` | Đế liền + hộp che board L298N (hở nắp) + 2 yên kẹp ôm bơm RS365 | PETG (cần dẻo cho khe lồng yên kẹp); in phẳng, không support |
| `print_pump_station_lid.stl` | Nắp hộp L298N (tháo được, 2 vít M3 tự-ren) | In phẳng |
```

- [ ] **Step 2: Thêm ghi chú lắp trạm bơm ở §7**

Trong `HUONG_DAN_LAP_RAP.md`, ngay sau dòng 151 (`4. Đặt bơm **tách rời** khối quang (cách ly rung). Nối ống theo chuỗi ở §8.`), thêm:

```markdown
5. **Gá bơm + board vào trạm gọn (`print_pump_station.stl`):** lồng board L298N vào
   hộp (tựa lên 4 gờ góc, không cần khớp lỗ vít), bắt nắp `print_pump_station_lid.stl`
   bằng 2 vít M3 tự-ren. Ép thân trụ động cơ RS365 từ TRÊN xuống vào 2 yên kẹp (khe
   hẹp hơn Ø lỗ — PETG hơi dẻo, ép nhẹ tay); nếu lỏng, luồn zip-tie qua rãnh trên
   đỉnh yên xiết thêm. Dây 12V vào / dây ra động cơ / dây logic đi qua 3 khe ở 3
   cạnh hộp, chạy trong rãnh nông trên mặt đế tới yên kẹp — không để dây lòng thòng.
   ⚠️ Kích thước board L298N (43×43×27mm) và Ø thân bơm (31.5mm) trong model là
   ƯỚC TÍNH — nếu hàng thật lệch nhiều, sửa `l298n_l/w/h` và `pump_motor_od` trong
   `openscad/constants.scad` rồi in lại (không cần sửa gì khác).
```

- [ ] **Step 3: Commit**

```bash
git add HUONG_DAN_LAP_RAP.md
git commit -m "docs: cập nhật hướng dẫn lắp ráp cho trạm bơm gọn mới"
```

---

## Sau khi hoàn thành plan này

- In thử `print_pump_station.stl` + `print_pump_station_lid.stl`, đo board L298N và bơm RS365 thật, sửa `l298n_l/w/h`/`pump_motor_od` trong `constants.scad` nếu lệch nhiều, in lại.
- Việc chọn driver bơm thật (L298N so với MOSFET/relay đã ghi trong tài liệu khác) và cập nhật firmware tương ứng KHÔNG thuộc phạm vi plan này.
