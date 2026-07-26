# Pump Station Wire-Shroud (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `pump_station` (OpenSCAD) so jumper-wire routing between the L298N driver, the RS365 pump, and the ESP32 logic cable is fully hidden under a removable low-profile cover, regardless of which way the pump is clamped.

**Architecture:** New versioned component `pump_station_002.scad` supersedes `pump_station_001.scad` (old file kept for history, no longer referenced). A continuous wire trough is cut into the baseplate spanning from the L298N box to the far edge of the pump-clamp cluster; a snap-fit (interference-fit) cover strip hides the two open segments (box↔near-clamp, near-clamp↔far-clamp) — the segment under each clamp needs no cover because the solid clamp block already sits on top of it. Each clamp gets a small notch through its thin floor wall connecting the bore to the trough, so wire can exit downward regardless of which way the pump is inserted. The L298N box gains asymmetric wall clearance (wide on the two terminal edges, tight on the other two) and a repositioned floor-level motor-output notch that feeds directly into the trough instead of exiting at the box rim and zig-zagging down outside.

**Tech Stack:** OpenSCAD (`.scad`), project skills `/openscad` (version-scad.sh), `/preview-scad` (render-scad.sh), `/export-stl` (export-stl.sh). No unit-test framework exists for this project — "tests" here are: OpenSCAD `assert()` sanity checks in `constants.scad` (fail = compile error), rendered PNG preview inspected visually, and STL manifold-geometry validation via the export-stl script.

## Global Constraints

- Source spec: `docs/superpowers/specs/2026-07-25-pump-station-wire-shroud-design.md` — every task below implements a section of it; do not add geometry not described there.
- No soldering, no screws for the new wire cover — PETG interference-fit only (same pattern already used for `pump_clamp_slot_w` in v1).
- Do not change the pump-clamp insertion mechanism, the L298N lid screw-boss mechanism, or the overall two-cluster baseplate layout (box at −X, clamps at +X) — only the wire-routing geometry changes.
- OpenSCAD binary resolution is already handled by the skill scripts (macOS path → PATH → `C:\Program Files\OpenSCAD\openscad.exe` fallback) — do not hardcode a different path.
- All new/edited Vietnamese comments must match the existing file's terse, technical voice (see `pump_station_001.scad` for tone reference).
- Every `.scad` edit must be followed by a render/export check before moving to the next task — do not batch multiple untested geometry changes.

---

### Task 1: `constants.scad` — asymmetric box clearance, logic-notch, channel, and clamp-notch constants

**Files:**
- Modify: `openscad/constants.scad:169-218` (trạm bơm gọn block)
- Modify: `openscad/constants.scad:378-390` (assert block cho trạm bơm)

**Interfaces:**
- Consumes: nothing new (pure constants file).
- Produces (used by Task 2): `l298n_box_clr_x`, `l298n_box_clr_y`, `wire_notch_logic_w`, `wire_notch_logic_h`, `l298n_wire_anchor_d`, `pump_clamp_wire_notch_w`, `pump_clamp_wire_notch_h`, `wire_channel_w`, `wire_channel_d`, `wire_channel_rail_w`, `wire_channel_rail_h`, `wire_cover_fit_interference`, and updated derived values `l298n_box_id_l/w`, `l298n_box_od_l/w`, `pump_station_len`, `pump_station_wid`. (`wire_notch_w`/`wire_notch_h` keep their old meaning, now scoped to the IN/OUT notches only.)

- [ ] **Step 1: Replace the `l298n_box_clr` single constant with per-axis constants**

Replace (lines 169-177):
```openscad
// ⚠️ l298n_* và pump_motor_od là số ĐIỂN HÌNH/ƯỚC TÍNH — CHƯA ĐO board/bơm thật.
// Hộp L298N cố ý rộng rãi (l298n_box_clr) để chịu sai số; yên kẹp bơm có rãnh
// zip-tie bù sai số đường kính nếu bơm thật khác pump_motor_od.
l298n_l             = 43.0;  // dài board L298N (điển hình, chưa đo)
l298n_w             = 43.0;  // rộng board
l298n_h             = 27.0;  // cao kể cả tản nhiệt nhô lên
l298n_box_wall      = 2.0;   // thành hộp
l298n_box_clr       = 2.5;   // khe hở mỗi bên quanh board (khay dung sai, KHÔNG khớp lỗ vít)
l298n_foot_h        = 2.0;   // gờ đỡ góc board bên trong hộp
```

With:
```openscad
// ⚠️ l298n_* và pump_motor_od là số ĐIỂN HÌNH/ƯỚC TÍNH — CHƯA ĐO board/bơm thật.
// Hộp L298N cố ý rộng rãi (l298n_box_clr_x/y) để chịu sai số; yên kẹp bơm có rãnh
// zip-tie bù sai số đường kính nếu bơm thật khác pump_motor_od.
// (2026-07-25: l298n_box_clr tách thành 2 trục — xem docs/superpowers/specs/
// 2026-07-25-pump-station-wire-shroud-design.md mục Kiến trúc §3.)
l298n_l             = 43.0;  // dài board L298N (điển hình, chưa đo)
l298n_w             = 43.0;  // rộng board
l298n_h             = 27.0;  // cao kể cả tản nhiệt nhô lên
l298n_box_wall      = 2.0;   // thành hộp
l298n_box_clr_x     = 8.0;   // khe hở cạnh X (IN 12V / OUT động cơ — có domino nhô ra, cần chỗ bẻ dây)
l298n_box_clr_y     = 4.0;   // khe hở cạnh Y (LOGIC + thoát khí — không có domino nhô ra)
l298n_foot_h        = 2.0;   // gờ đỡ góc board bên trong hộp
```

- [ ] **Step 2: Add logic-notch and wire-anchor constants**

Replace (lines 184-185):
```openscad
wire_notch_w        = 6.0;   // bề rộng khe dây (xuyên thành, hở miệng hộp — nắp ép giữ dây)
wire_notch_h        = 5.0;   // sâu khe dây tính từ miệng hộp xuống
```

With:
```openscad
wire_notch_w        = 6.0;   // bề rộng khe dây IN(12V)/OUT(động cơ) — dây trần/cosse
wire_notch_h        = 5.0;   // sâu khe dây IN/OUT
wire_notch_logic_w  = 14.0;  // bề rộng khe dây LOGIC — đủ ôm 3-4 đầu jumper (ENA/IN1/IN2/GND)
wire_notch_logic_h  = 6.0;   // sâu khe dây LOGIC
l298n_wire_anchor_d = 6.0;   // Ø trụ neo bó dây logic ngay ngoài khe LOGIC
```

- [ ] **Step 3: Add clamp wire-notch constants after `pump_clamp_gap`**

Find this line (line 195):
```openscad
pump_clamp_gap      = 40.0;  // khoảng cách tâm 2 yên kẹp dọc trục bơm
```

Add immediately after it (before the blank line that precedes `pump_station_base_t`):
```openscad
pump_clamp_wire_notch_w = 4.0;                // bề rộng khe xuyên đáy máng kẹp nối lòng máng ↔ kênh dây
pump_clamp_wire_notch_h = pump_clamp_t + 2.0; // sâu khe — GIÁ TRỊ KHỞI ĐIỂM, chỉnh theo preview-scad
```

- [ ] **Step 4: Add wire-channel constants after `pump_station_margin`**

Find this line (line 200):
```openscad
pump_station_margin  = 4.0;  // biên đế quanh hộp/yên kẹp (mép ngoài cùng)
```

Add immediately after it (before the `// Dẫn xuất` comment):
```openscad

wire_channel_w              = 10.0;  // bề rộng lòng kênh dây liền mạch (đủ 2-3 đầu jumper cạnh nhau)
wire_channel_d              = 2.0;   // sâu kênh dây (khoét vào mặt đế)
wire_channel_rail_w         = 2.0;   // bề rộng gờ ray 2 bên miệng kênh (đỡ nắp đậy)
wire_channel_rail_h         = 1.5;   // cao gờ ray nhô lên khỏi mặt đế = dày nắp đậy
wire_cover_fit_interference = 0.3;   // nắp kênh dây rộng hơn khe giữa 2 ray — PETG đàn hồi ép giữ
```

- [ ] **Step 5: Update the derived-values block to use the new per-axis clearance and wire-anchor width**

Replace (lines 202-218):
```openscad
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

With:
```openscad
// Dẫn xuất — hộp L298N (đáy hộp = mặt đế, KHÔNG có sàn riêng)
l298n_box_id_l = l298n_l + 2*l298n_box_clr_x;                 // = 59
l298n_box_id_w = l298n_w + 2*l298n_box_clr_y;                 // = 51
l298n_box_h    = l298n_h + l298n_foot_h + 3.0;                // = 32: cao thành từ mặt đế tới miệng hộp
l298n_box_od_l = l298n_box_id_l + 2*l298n_box_wall;           // = 63
l298n_box_od_w = l298n_box_id_w + 2*l298n_box_wall;           // = 55

// Dẫn xuất — yên kẹp bơm (khối vuông, tâm lỗ khoan = pump_clamp_od/2 → đối xứng
// trên/dưới → thành dưới lỗ khoan luôn dày đúng bằng pump_clamp_t, không phụ thuộc
// số đo pump_bbox — ưu tiên AN TOÀN KẾT CẤU hơn khớp pixel với model placeholder)
pump_clamp_id = pump_motor_od + 2*pump_clamp_clr;   // = 33.5: Ø lòng máng kẹp
pump_clamp_od = pump_clamp_id + 2*pump_clamp_t;     // = 38.3: Ø ngoài máng kẹp = tổng cao khối yên

// Dẫn xuất — bố cục đế (đơn vị mm)
pump_station_len = pump_station_margin + l298n_box_od_l + pump_station_gap
                   + pump_clamp_gap + pump_clamp_w + pump_station_margin;   // = 139
// Bề rộng đế: nửa-rộng lớn nhất giữa (a) hộp L298N + trụ neo dây logic nhô ra cạnh
// +Y, (b) bán kính yên kẹp bơm — nhân đôi để đối xứng qua tâm.
pump_station_wid = 2*max(l298n_box_od_w/2 + l298n_wire_anchor_d + 2, pump_clamp_od/2)
                   + 2*pump_station_margin;   // = 79
```

- [ ] **Step 6: Add two safety asserts**

Find the existing pump-station assert block (lines 378-390), specifically this last assert:
```openscad
assert(pump_station_wid > pump_clamp_od && pump_station_wid > l298n_box_od_w,
       "đế phải rộng hơn cả hộp L298N lẫn yên kẹp bơm (không hụt biên)");
```

Add immediately after it (before the blank line / `echo(...)`):
```openscad
assert(pump_clamp_wire_notch_w < pump_clamp_w,
       "khe dây xuyên đáy yên kẹp phải hẹp hơn bề rộng yên kẹp (không cắt lủng 2 đầu)");
assert(pump_station_wid/2 >= l298n_box_od_w/2 + l298n_wire_anchor_d + 2,
       "đế phải đủ rộng để chứa trụ neo dây logic ngoài hộp L298N");
```

- [ ] **Step 7: Smoke-test — confirm constants.scad still compiles and all asserts pass**

Run (from project root):
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/print/print_pump_station.scad --output "C:/Users/hieut/AppData/Local/Temp/claude/C--University-Semester-4-IOT102-project/018107a9-43ac-4f7a-ba0a-bcc676c9a5e2/scratchpad/constants_smoke.png"
```
Expected: `Success: Preview saved to ...`, no `ERROR`/`assert` failure text in the output. (This still renders the OLD `pump_station_001.scad` geometry — that's fine, the goal here is only to confirm `constants.scad` itself has no syntax errors and every `assert()` in it evaluates true. The `echo(...)` line at the end of `constants.scad` should appear in the console text captured by the script if you inspect stderr; a failing `assert()` aborts with `ERROR: Assertion failed` instead of producing the PNG.)

- [ ] **Step 8: Commit**

```bash
git add openscad/constants.scad
git commit -m "$(cat <<'EOF'
feat(openscad): tách l298n_box_clr theo trục X/Y + thêm hằng số kênh dây liền mạch

Chuẩn bị cho pump_station_002 (giấu dây jumper) — spec 2026-07-25.
EOF
)"
```

---

### Task 2: `pump_station_002.scad` — new component with wire trough, clamp notch, box repositioning

**Files:**
- Create: `openscad/components/pump_station_002.scad` (via `version-scad.sh`)

**Interfaces:**
- Consumes: all constants from Task 1.
- Produces (used by Tasks 3-6): modules `l298n_box_walls()`, `l298n_wire_anchor()`, `pump_station_lid()`, `pump_clamp_post()`, `wire_channel(length)`, `wire_channel_rails(length)`, `pump_station_wire_cover(length)`, `pump_station_wire_covers()`, `pump_station()` — same public names as v1 (`pump_station()`, `pump_station_lid()`) plus new ones, so print files only need their `use` path changed.

- [ ] **Step 1: Generate the next version number**

```bash
cd "openscad/components" && bash ../../.claude/skills/openscad/scripts/version-scad.sh pump_station
```
Expected output includes `Next version: pump_station_002` (since `pump_station_001.scad` already exists in that directory).

- [ ] **Step 2: Write the full file**

Create `openscad/components/pump_station_002.scad`:
```openscad
// ============================================================================
// pump_station_002.scad — Trạm bơm gọn: đế liền + hộp che L298N + yên kẹp RS365
//                          (v2: kênh giấu dây liền mạch + hộp nới khoang bất đối xứng)
// ----------------------------------------------------------------------------
// Nguồn: docs/superpowers/specs/2026-07-25-pump-station-wire-shroud-design.md
// (sửa trên nền pump_station_001.scad / spec 2026-07-24 — kiến trúc tổng KHÔNG đổi,
// chỉ đổi phần đi dây theo phản hồi lắp thật: xem spec 07-25 mục "Bối cảnh").
//
// Thay đổi so v1:
//   1. l298n_box_walls(): khoang hộp bất đối xứng (l298n_box_clr_x/y) để chừa chỗ
//      bẻ dây quanh domino IN/OUT; khe LOGIC đổi sang wire_notch_logic_w/h (rộng
//      hơn, chứa nhiều đầu jumper); khe OUT (động cơ) HẠ XUỐNG MỨC SÀN thay vì hở
//      miệng hộp — nối THẲNG vào kênh dây bên ngoài, khỏi zíc-zắc lên tận miệng hộp
//      rồi vòng xuống lại (đây là nguyên nhân "không tính đủ độ dài dây" ở v1); khe
//      IN(12V) GIỮ NGUYÊN cơ chế hở miệng hộp (nắp ép giữ dây) vì không cần khớp
//      kênh dây nội bộ. Thêm trụ neo dây l298n_wire_anchor() ngay ngoài khe LOGIC.
//   2. pump_clamp_post(): thêm khe nhỏ xuyên đáy máng kẹp (pump_clamp_wire_notch_*)
//      nối lòng máng ↔ kênh dây bên dưới — lòng máng hình trụ nên bơm xoay tự do,
//      không phụ thuộc hướng lắp (ngạnh ống hướng nào cũng được).
//   3. wire_channel()/wire_channel_rails()/pump_station_wire_cover(): rãnh dây cũ
//      (chỉ dài đoạn hộp↔yên gần) đổi thành kênh liền mạch chạy suốt qua CẢ 2 yên
//      kẹp, có nắp đậy rời (ép giữ bằng PETG đàn hồi, không vít) che 2 đoạn hở
//      (hộp↔yên gần, yên gần↔yên xa) — đoạn kênh NẰM DƯỚI khối yên kẹp không cần
//      nắp riêng vì khối yên kẹp tự che (khác dải z: yên kẹp z≥0, kênh z<0).
//
// Trục dài đế = X. Hộp L298N ở đầu −X (gần), 2 yên kẹp ở đầu +X (xa) — không đổi
// so v1.
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
        // Khe dây INPUT 12V — cạnh −X (hướng ra ngoài trạm, xa bơm) — dây trần/cosse,
        // hở miệng hộp (rim) để NẮP ép giữ dây = strain-relief (không đổi so v1)
        translate([-EPS, l298n_box_od_w/2 - wire_notch_w/2, l298n_box_h - wire_notch_h])
            cube([l298n_box_wall + 2*EPS, wire_notch_w, wire_notch_h + EPS]);
        // Khe dây OUTPUT động cơ — cạnh +X — HẠ XUỐNG MỨC SÀN (ĐỔI SO V1) để nối
        // THẲNG vào kênh dây liền mạch bên ngoài
        translate([l298n_box_od_l - l298n_box_wall - EPS, l298n_box_od_w/2 - wire_notch_w/2, 0])
            cube([l298n_box_wall + 2*EPS, wire_notch_w, wire_notch_h + EPS]);
        // Khe dây LOGIC (ENA/IN1/IN2/GND lên ESP32) — cạnh +Y — RỘNG HƠN v1, chứa
        // nhiều đầu jumper cạnh nhau, vẫn hở miệng hộp (nắp ép giữ)
        translate([l298n_box_od_l/2 - wire_notch_logic_w/2, l298n_box_od_w - l298n_box_wall - EPS,
                   l298n_box_h - wire_notch_logic_h])
            cube([wire_notch_logic_w, l298n_box_wall + 2*EPS, wire_notch_logic_h + EPS]);
        // Khe thoát khí — cạnh −Y (đối diện khe logic, phía tản nhiệt board)
        for (i = [0 : l298n_vent_n - 1])
            translate([l298n_box_wall + 4 + i * (l298n_box_id_l - 8) / (l298n_vent_n - 1) - l298n_vent_w/2,
                       -EPS, 6])
                cube([l298n_vent_w, l298n_box_wall + 2*EPS, l298n_box_h - 6 - wire_notch_logic_h - 2]);
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
                translate([0, 0, 5])
                    cylinder(d = l298n_lid_screw_d, h = l298n_box_h - 3 - 5 + EPS, $fn = 24);
            }
}

// Trụ neo bó dây logic — đặt ngay ngoài khe LOGIC, dây vòng qua 1 lần trước khi đi
// tự do ra ESP32, tránh lực kéo trực tiếp vào chân cắm trên board.
module l298n_wire_anchor() {
    cylinder(d = l298n_wire_anchor_d, h = wire_notch_logic_h, $fn = 24);
}

// Nắp hộp L298N — chi tiết in RIÊNG (print_pump_station_lid.scad) — KHÔNG đổi so
// v1, tự khớp theo l298n_box_od_l/w mới vì dùng chung hằng số.
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

// ---------------------------------------------------------------- Yên kẹp bơm: khối + lỗ khoan ngang + khe lồng từ trên + khe dây đáy (MỚI)
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
        // Khe lồng từ ĐỈNH khối xuống tâm lỗ (hẹp hơn Ø lỗ — PETG dẻo ép giữ bơm) —
        // khe này giờ KIÊM LUÔN lối thoát dây khi chân điện bơm quay lên trên
        translate([-EPS, -pump_clamp_slot_w/2, center_z])
            cube([pump_clamp_w + 2*EPS, pump_clamp_slot_w, block_h - center_z + EPS]);
        // Rãnh zip-tie trên đỉnh khối, cắt ngang qua khe lồng (bù sai số Ø bơm thật)
        translate([pump_clamp_w/2 - pump_clamp_strap_w/2, -pump_clamp_od/2 - EPS, block_h - 1.5])
            cube([pump_clamp_strap_w, pump_clamp_od + 2*EPS, 1.5 + EPS]);
        // MỚI: khe xuyên đáy máng kẹp, nối lòng máng ↔ kênh dây bên dưới — cho phép
        // dây thoát ra ĐÁY yên kẹp khi chân điện bơm quay xuống dưới (bù hướng lắp
        // ngược so v1). Cắt tại điểm thấp nhất của lòng máng (y=0, thành mỏng nhất
        // = pump_clamp_t theo thiết kế đối xứng trên/dưới).
        translate([pump_clamp_w/2 - pump_clamp_wire_notch_w/2, -pump_clamp_wire_notch_w/2, -EPS])
            cube([pump_clamp_wire_notch_w, pump_clamp_wire_notch_w, pump_clamp_wire_notch_h + EPS]);
    }
}

// ---------------------------------------------------------------- Kênh dây liền mạch (đế) + nắp đậy rời
// Kênh cắt vào ĐẾ (z âm), chạy SUỐT từ hộp L298N tới hết cụm yên kẹp — kể cả đoạn
// NẰM DƯỚI 2 khối yên kẹp (2 vật thể khác dải z, không xung đột hình học). Gờ ray +
// nắp đậy CHỈ cần ở 2 đoạn HỞ (hộp↔yên gần, yên gần↔yên xa) — đoạn dưới yên kẹp đã
// được chính khối yên kẹp che kín, không cần nắp riêng.
module wire_channel(length) {
    translate([0, -wire_channel_w/2, -wire_channel_d])
        cube([length, wire_channel_w, wire_channel_d + EPS]);
}

module wire_channel_rails(length) {
    for (ry = [wire_channel_w/2, -wire_channel_w/2 - wire_channel_rail_w])
        translate([0, ry, 0])
            cube([length, wire_channel_rail_w, wire_channel_rail_h]);
}

// Nắp đậy kênh dây — chi tiết in RIÊNG, rộng hơn khe giữa 2 ray đúng
// wire_cover_fit_interference để PETG đàn hồi ép giữ (không vít, không khớp cài).
module pump_station_wire_cover(length) {
    cube([length, wire_channel_w + wire_cover_fit_interference, wire_channel_rail_h]);
}

// Cả 2 nắp kênh dây, xếp cạnh nhau theo Y để in chung 1 lần (dùng trong
// print_pump_station_channel_cover.scad) — độ dài từng nắp tính lại từ layout
// pump_station() để luôn khớp, không hardcode.
module pump_station_wire_covers() {
    box_x      = pump_station_margin;
    clamp_x0   = box_x + l298n_box_od_l + pump_station_gap;
    clamp_x1   = clamp_x0 + pump_clamp_gap;
    chan_a_len = clamp_x0 - (box_x + l298n_box_od_l);
    chan_b_len = clamp_x1 - (clamp_x0 + pump_clamp_w);

    pump_station_wire_cover(chan_a_len);
    translate([0, wire_channel_w + wire_cover_fit_interference + 4, 0])
        pump_station_wire_cover(chan_b_len);
}

// ---------------------------------------------------------------- Trạm bơm hoàn chỉnh (đế + hộp L298N không nắp + 2 yên kẹp)
// Gốc cục bộ: góc −X/−Y của đế tại z=0 (mặt TRÊN đế); đế dày pump_station_base_t
// nằm ở z ÂM (−pump_station_base_t .. 0).
module pump_station() {
    box_x    = pump_station_margin;
    clamp_x0 = box_x + l298n_box_od_l + pump_station_gap;
    clamp_x1 = clamp_x0 + pump_clamp_gap;
    base_y   = pump_station_wid / 2;

    chan_a_x0     = box_x + l298n_box_od_l;      // đầu kênh (mép ngoài hộp, cạnh OUT)
    chan_a_len    = clamp_x0 - chan_a_x0;        // đoạn hở 1: hộp ↔ yên gần
    chan_b_x0     = clamp_x0 + pump_clamp_w;
    chan_b_len    = clamp_x1 - chan_b_x0;        // đoạn hở 2: yên gần ↔ yên xa
    chan_full_len = (clamp_x1 + pump_clamp_w) - chan_a_x0; // toàn bộ kênh cắt (kể cả dưới 2 yên)

    // Đế (khoét kênh dây liền mạch trên mặt)
    difference() {
        translate([0, -base_y, -pump_station_base_t])
            cube([pump_station_len, pump_station_wid, pump_station_base_t]);
        translate([chan_a_x0, 0, 0]) wire_channel(chan_full_len);
    }
    // Gờ ray nắp đậy — chỉ 2 đoạn hở (dưới yên kẹp đã được chính yên kẹp che)
    translate([chan_a_x0, 0, 0]) wire_channel_rails(chan_a_len);
    translate([chan_b_x0, 0, 0]) wire_channel_rails(chan_b_len);
    // 4 chân đế góc
    foot_sz = 6.0;
    for (fx = [3, pump_station_len - 3 - foot_sz])
        for (fy = [-base_y + 3, base_y - 3 - foot_sz])
            translate([fx, fy, -pump_station_base_t - pump_station_foot_h])
                cube([foot_sz, foot_sz, pump_station_foot_h]);
    // Hộp L298N (căn giữa theo bề rộng đế)
    translate([box_x, -l298n_box_od_w/2, 0]) l298n_box_walls();
    // Trụ neo dây logic — ngay ngoài khe LOGIC (cạnh +Y của hộp)
    translate([box_x + l298n_box_od_l/2, l298n_box_od_w/2 + l298n_wire_anchor_d/2 + 2, 0])
        l298n_wire_anchor();
    // 2 yên kẹp bơm (căn giữa theo bề rộng đế; lỗ khoan nằm ngang trục X)
    translate([clamp_x0, 0, 0]) pump_clamp_post();
    translate([clamp_x1, 0, 0]) pump_clamp_post();
}

// Xem lẻ
pump_station();
translate([0, 80, 0]) pump_station_lid();
translate([0, -80, 0]) pump_station_wire_covers();
```

- [ ] **Step 3: Render a full-CSG preview (catches boolean/geometry errors preview mode misses)**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/pump_station_002.scad --output openscad/components/pump_station_002.png --render --size 1200x900
```
Expected: `Success: Preview saved to openscad/components/pump_station_002.png`, no `ERROR`/`WARNING: ... non-manifold` in the captured output.

- [ ] **Step 4: Visually inspect the render**

Read `openscad/components/pump_station_002.png`. Confirm:
- The L298N box is now a visibly non-square rectangle (longer along X than Y).
- A continuous shallow trough with raised side rails runs from the box to the far clamp, broken only where the two clamp blocks sit on top of it.
- A small cylindrical post (wire anchor) stands just outside the box's +Y wall.
- The two pump clamps look unchanged in silhouette (the new floor notch is too small to read at this zoom — that's expected, verified structurally via the Step 3 render succeeding without geometry errors).
- The separate lid (translated +Y 80mm) and the two wire-cover bars (translated −Y 80mm) both appear as flat rectangular slabs, roughly matching the box/trough footprint.

If anything looks wrong (e.g. a cover bar the wrong size, box notch missing), fix the code and re-render before continuing.

- [ ] **Step 5: Commit**

```bash
git add openscad/components/pump_station_002.scad openscad/components/pump_station_002.png
git commit -m "$(cat <<'EOF'
feat(openscad): pump_station_002 — kênh giấu dây liền mạch + hộp L298N nới bất đối xứng

Thay rãnh dây ngắn (chỉ hộp↔yên gần) bằng kênh liền mạch có nắp đậy rời chạy
suốt qua cả 2 yên kẹp; mỗi yên kẹp thêm khe đáy nối lòng máng↔kênh (lắp bơm
chiều nào cũng có lối thoát dây); khe OUT động cơ hạ xuống mức sàn nối thẳng
vào kênh thay vì hở miệng hộp rồi vòng xuống ngoài.
EOF
)"
```

---

### Task 3: Regenerate `print_pump_station.scad` (đế + hộp + yên kẹp) against v2

**Files:**
- Modify: `openscad/print/print_pump_station.scad`

**Interfaces:**
- Consumes: `pump_station()` from Task 2.
- Produces: `openscad/print/print_pump_station.stl` (overwritten).

- [ ] **Step 1: Point the print file at the new component**

In `openscad/print/print_pump_station.scad`, replace:
```openscad
use <../components/pump_station_001.scad>
```
With:
```openscad
use <../components/pump_station_002.scad>
```

- [ ] **Step 2: Export STL and check manifold status**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station.scad
```
Expected: `STATUS: PASSED - No geometry issues detected` and `RESULT: Export successful`. If it reports `STATUS: WARNING` with non-manifold/self-intersect issues, identify which new feature caused it (most likely candidates: the clamp floor notch at Task 2's `pump_clamp_post()`, or the trough/rail boolean near the clamp footprints) and fix `pump_station_002.scad` before proceeding — do not ship a warned STL.

- [ ] **Step 3: Commit**

```bash
git add openscad/print/print_pump_station.scad openscad/print/print_pump_station.stl
git commit -m "chore(openscad): trỏ print_pump_station sang pump_station_002"
```

---

### Task 4: Regenerate `print_pump_station_lid.scad` against v2

**Files:**
- Modify: `openscad/print/print_pump_station_lid.scad`

**Interfaces:**
- Consumes: `pump_station_lid()` from Task 2.
- Produces: `openscad/print/print_pump_station_lid.stl` (overwritten, now larger/asymmetric to match the new box footprint).

- [ ] **Step 1: Point the print file at the new component**

In `openscad/print/print_pump_station_lid.scad`, replace:
```openscad
use <../components/pump_station_001.scad>
```
With:
```openscad
use <../components/pump_station_002.scad>
```

- [ ] **Step 2: Export STL and check manifold status**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station_lid.scad
```
Expected: `STATUS: PASSED - No geometry issues detected`.

- [ ] **Step 3: Commit**

```bash
git add openscad/print/print_pump_station_lid.scad openscad/print/print_pump_station_lid.stl
git commit -m "chore(openscad): trỏ print_pump_station_lid sang pump_station_002 (khớp hộp mới)"
```

---

### Task 5: New print file for the wire-channel cover

**Files:**
- Create: `openscad/print/print_pump_station_channel_cover.scad`

**Interfaces:**
- Consumes: `pump_station_wire_covers()` from Task 2.
- Produces: `openscad/print/print_pump_station_channel_cover.stl`.

- [ ] **Step 1: Write the file**

Create `openscad/print/print_pump_station_channel_cover.scad`:
```openscad
// print_pump_station_channel_cover.scad — Nắp đậy kênh dây trạm bơm (2 thanh, in chung).
// In phẳng, PETG (đàn hồi nhẹ để ép giữ vào gờ ray — không vít, không khớp cài).
// Sau in: ép thử vào gờ ray của print_pump_station.stl, đầu nắp phải hơi chặt
// (wire_cover_fit_interference) — nếu lỏng quá thì tăng interference trong
// constants.scad và in lại; nếu chặt quá không lắp được thì giảm xuống.
include <../constants.scad>
use <../components/pump_station_002.scad>

pump_station_wire_covers();
```

- [ ] **Step 2: Export STL and check manifold status**

```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station_channel_cover.scad
```
Expected: `STATUS: PASSED - No geometry issues detected`.

- [ ] **Step 3: Commit**

```bash
git add openscad/print/print_pump_station_channel_cover.scad openscad/print/print_pump_station_channel_cover.stl
git commit -m "feat(openscad): xuất STL print_pump_station_channel_cover (nắp giấu dây trạm bơm)"
```

---

### Task 6: Wire the new component into the main assembly and sanity-check the render

**Files:**
- Modify: `openscad/aqua_scope_assembly_001.scad:31`

**Interfaces:**
- Consumes: `pump_station()` from Task 2 (same call signature as v1 — no changes needed at the call site itself).
- Produces: updated `openscad/aqua_scope_assembly_001.scad` (no new public interface).

- [ ] **Step 1: Swap the `use` line**

In `openscad/aqua_scope_assembly_001.scad`, replace:
```openscad
use <components/pump_station_001.scad>
```
With:
```openscad
use <components/pump_station_002.scad>
```

- [ ] **Step 2: Render the full assembly and inspect**

```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/aqua_scope_assembly_001.scad --output openscad/aqua_scope_assembly_001_preview.png --size 1400x1000
```
Read the resulting PNG. The pump station's baseplate grew from 128×60mm to 139×79mm — confirm it doesn't visually overlap/collide with the `pump_rs365()` placeholder or other geometry placed nearby (around the `translate([190 + 1.5*e, 0, z_housing_bot])` call at `openscad/aqua_scope_assembly_001.scad:102`). If it now overlaps, increase that translate's X offset by the same amount `pump_station_len` grew (11mm) — this is a cosmetic dev-preview fix only, it does not affect any print file (the assembly is a viewing aid, individual parts are what get printed).

- [ ] **Step 3: Commit**

```bash
git add openscad/aqua_scope_assembly_001.scad openscad/aqua_scope_assembly_001_preview.png
git commit -m "chore(openscad): assembly dùng pump_station_002"
```

---

### Task 7: Close out the spec — update status and cross-link

**Files:**
- Modify: `docs/superpowers/specs/2026-07-25-pump-station-wire-shroud-design.md`
- Modify: `docs/superpowers/specs/2026-07-24-pump-station-mount-design.md:4`

**Interfaces:**
- Consumes: nothing (docs only).
- Produces: nothing (docs only).

- [ ] **Step 1: Mark the v2 spec as implemented, and correct the file-list section to match the actual print/ folder convention**

In `docs/superpowers/specs/2026-07-25-pump-station-wire-shroud-design.md`, replace:
```markdown
**Trạng thái:** Đã duyệt bởi user (phương án A), chờ viết plan triển khai.
```
With:
```markdown
**Trạng thái:** Đã triển khai (`pump_station_002.scad`, 2026-07-25). Ghi chú: các
file `print/` trong repo này KHÔNG đánh version (khác `components/`) — triển khai
thực tế SỬA TRỰC TIẾP `print_pump_station.scad`/`print_pump_station_lid.scad` (đổi
dòng `use` sang `pump_station_002.scad`) thay vì tạo bản `_002` mới, và file nắp
kênh dây mới được đặt tên `print_pump_station_channel_cover.scad` (không hậu tố
`_001`) để khớp quy ước đó — khác nhẹ so với tên file dự kiến ở mục "File/constants"
bên dưới.
```

- [ ] **Step 2: Cross-link from the v1 spec**

In `docs/superpowers/specs/2026-07-24-pump-station-mount-design.md`, replace:
```markdown
**Trạng thái:** Đã duyệt bởi user, chờ viết plan triển khai.
```
With:
```markdown
**Trạng thái:** Đã triển khai (`pump_station_001.scad`). Phần đi dây được sửa
tiếp ở [2026-07-25-pump-station-wire-shroud-design.md](2026-07-25-pump-station-wire-shroud-design.md)
(`pump_station_002.scad`) sau phản hồi lắp thật.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-25-pump-station-wire-shroud-design.md docs/superpowers/specs/2026-07-24-pump-station-mount-design.md
git commit -m "docs: đánh dấu spec trạm bơm v1/v2 đã triển khai, liên kết chéo"
```

---

### Task 8: Update `HUONG_DAN_LAP_RAP.md` §7 step 5 and the STL table (spec §4 requirement)

**Files:**
- Modify: `HUONG_DAN_LAP_RAP.md:28-29` (bảng STL)
- Modify: `HUONG_DAN_LAP_RAP.md:162-170` (§7 bước 5)

**Interfaces:**
- Consumes: nothing (docs only, describes the physical result of Tasks 2-5).
- Produces: nothing (docs only).

- [ ] **Step 1: Add the new STL to the parts table**

Find (lines 28-29):
```markdown
| `print_pump_station.stl` | Đế liền + hộp che board L298N (hở nắp) + 2 yên kẹp ôm bơm RS365 | PETG (cần dẻo cho khe lồng yên kẹp); in phẳng, không support |
| `print_pump_station_lid.stl` | Nắp hộp L298N (tháo được, 2 vít M3 tự-ren) | In phẳng |
```

Add immediately after it:
```markdown
| `print_pump_station_channel_cover.stl` | Nắp đậy kênh giấu dây (2 thanh, ép giữ đàn hồi, không vít) | PETG; in phẳng, không support |
```

- [ ] **Step 2: Rewrite §7 step 5 to describe the v2 wiring**

Find (lines 162-170):
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

Replace with:
```markdown
5. **Gá bơm + board vào trạm gọn (`print_pump_station.stl`):** lồng board L298N vào
   hộp (tựa lên 4 gờ góc, không cần khớp lỗ vít), bắt nắp `print_pump_station_lid.stl`
   bằng 2 vít M3 tự-ren. Ép thân trụ động cơ RS365 từ TRÊN xuống vào 2 yên kẹp (khe
   hẹp hơn Ø lỗ — PETG hơi dẻo, ép nhẹ tay); xoay bơm sao cho 2 chân điện của motor
   hướng xuống khe nhỏ ở đáy yên kẹp (ngạnh ống quay hướng nào cũng được — khe đáy
   có ở cả 2 yên); nếu lỏng, luồn zip-tie qua rãnh trên đỉnh yên xiết thêm.
   Dây 12V vào và dây logic (ENA/IN1/IN2/GND) đi qua 2 khe hở miệng hộp (nắp hộp ép
   giữ dây khi đậy) — dây logic vòng qua trụ neo nhỏ ngay ngoài khe rồi mới ra
   ESP32; bó đoạn từ trụ neo tới ESP32 bằng ống gen xoắn cho gọn (không có chi tiết
   in nào che đoạn này — 2 cụm tách rời chống rung, xem đầu mục 7). Dây ra động cơ
   đi qua khe SÁT ĐÁY hộp, chạy thẳng vào kênh dây liền mạch trên mặt đế tới yên
   kẹp — ép `print_pump_station_channel_cover.stl` (2 thanh) vào gờ ray 2 bên kênh
   để giấu kín (đàn hồi PETG giữ, không vít — bẩy nhẹ để tháo khi cần bảo trì).
   ⚠️ Kích thước board L298N (43×43×27mm) và Ø thân bơm (31.5mm) trong model là
   ƯỚC TÍNH — nếu hàng thật lệch nhiều, sửa `l298n_l/w/h` và `pump_motor_od` trong
   `openscad/constants.scad` rồi in lại (không cần sửa gì khác).
```

- [ ] **Step 3: Commit**

```bash
git add HUONG_DAN_LAP_RAP.md
git commit -m "docs: cập nhật §7 bước 5 + bảng STL cho trạm bơm v2 (kênh giấu dây)"
```

---

## Post-plan note (not a task — do after Task 8)

Update project memory (`pump-drive-decision.md` in the auto-memory store) to record that the wire-routing problem from the first real assembly was fixed in `pump_station_002.scad`, and that `pump_clamp_wire_notch_w/h` values may still need physical-print tuning (per the spec's flagged assumption #3). This is a memory-system update, not a code task, so it is intentionally left out of the checkbox list above.
