# Trạm bơm v2 — giấu dây & gọn hóa đấu nối Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa cụm in 3D "trạm bơm gọn" (`pump_station_001` → `pump_station_002`) để khắc phục 3 vấn đề dây điện phát hiện khi lắp thật: (1) jack DC 12V lộ ngoài không chỗ giấu, (2) dây động cơ phải vòng qua thân bơm do 2 chân dẹt lệch ~180°, (3) dây logic ra ESP32 không có strain-relief.

**Architecture:** Giữ nguyên kiến trúc v1 đã duyệt (đế liền + hộp hở nắp L298N + 2 yên kẹp bơm kiểu lồng-từ-trên). Tạo file component mới `pump_station_002.scad` (kế thừa toàn bộ code từ `_001`, KHÔNG sửa `_001` tại chỗ — theo quy ước versioning của repo), áp 3 thay đổi hình học cục bộ, rồi trỏ lại các file `print_*.scad` và `aqua_scope_assembly_001.scad` sang bản `_002`.

**Tech Stack:** OpenSCAD (`.scad`), scripts versioning/preview/export tại `.claude/skills/{openscad,preview-scad,export-stl}/scripts/`.

## Global Constraints

- Vật liệu in: PETG (khe lồng yên kẹp cần đàn hồi nhẹ) — không đổi.
- KHÔNG sửa `pump_station_001.scad` tại chỗ — mọi thay đổi vào file mới `pump_station_002.scad` (quy ước "phiên bản mới nhất thắng" của repo, giống `top_cap_002` supersede `_001`).
- KHÔNG đổi driver bơm (giữ L298N) hay firmware (`firmware/pump_l298n_xiao/pump_l298n_xiao.ino` không đổi).
- KHÔNG thiết kế đế/khung chung nối trạm bơm với khối quang chính — 2 cụm vẫn đặt rời trên bàn.
- KHÔNG thiết kế ngàm giữ đầu jumper phía dây động cơ (OUT1/OUT2) — user sẽ HÀN trực tiếp, phía dây logic (IN1/IN2/EN/GND) vẫn giữ jumper đực-cái.
- Mọi hằng số kích thước chưa đo từ phần cứng thật phải có comment "CHƯA ĐO ... — xác nhận khi lắp" (quy ước xuyên suốt `constants.scad`).
- Không có framework test tự động cho OpenSCAD trong repo này — chu trình kiểm chứng là: render PNG bằng `render-scad.sh` rồi **đọc ảnh bằng Read tool** để xác nhận hình học đúng như mô tả (thay cho unit test).
- Nguồn duy nhất cho phạm vi thay đổi: [docs/superpowers/specs/2026-07-25-pump-station-wiring-v2-design.md](../specs/2026-07-25-pump-station-wiring-v2-design.md) — không thêm tính năng ngoài spec này.

---

## File Structure

| File | Vai trò |
|---|---|
| `openscad/constants.scad` | Thêm 1 block hằng số mới (v2) cạnh block `pump_station_*` hiện có (dòng ~163-218) — KHÔNG sửa hằng số cũ. |
| `openscad/components/pump_station_002.scad` | **File mới.** Copy nguyên `pump_station_001.scad`, áp 3 thay đổi: lỗ panel-mount jack DC (thay khe input), rãnh dẫn dây trên yên kẹp gần hộp + nới khe output, gờ bo tròn khe logic. |
| `openscad/print/print_pump_station.scad` | Sửa 1 dòng `use` trỏ sang `_002`. |
| `openscad/print/print_pump_station_lid.scad` | Sửa 1 dòng `use` trỏ sang `_002` (module `pump_station_lid()` không đổi nội dung). |
| `openscad/aqua_scope_assembly_001.scad` | Sửa 1 dòng `use` (dòng 31) trỏ sang `_002`. |
| `openscad/print/print_pump_station.stl`, `print_pump_station_lid.stl` | Xuất lại sau khi đổi component. |
| `openscad/components/pump_station_002.png` | Ảnh preview mới (theo đúng quy ước đã có với `pump_station_001.png`). |

---

### Task 1: Thêm hằng số v2 vào `constants.scad`

**Files:**
- Modify: `openscad/constants.scad:218` (chèn block mới ngay sau dòng `pump_station_wid = ...`, trước block "BIẾN THỂ ESP32-CAM" ở dòng 220)

**Interfaces:**
- Produces: các hằng số sau, dùng bởi Task 2–4 trong `pump_station_002.scad`:
  `dc_jack_hole_d`, `dc_jack_hole_z`, `dc_jack_shelf_h`, `dc_jack_shelf_w`, `dc_jack_shelf_depth`, `wire_notch_w_out`, `pump_wire_groove_w`, `pump_wire_groove_d`, `logic_notch_fillet_r`.

- [ ] **Step 1: Chèn block hằng số mới**

Mở `openscad/constants.scad`, tìm dòng:
```
pump_station_wid = max(l298n_box_od_w, pump_clamp_od) + 2*pump_station_margin; // = 60
```
(dòng 218), chèn NGAY SAU dòng này (trước dòng trống + comment "BIẾN THỂ ESP32-CAM"):

```openscad

// ---------------------------------------------------------------- Trạm bơm v2: giấu dây & gọn hóa đấu nối (2026-07-25)
// Nguồn: docs/superpowers/specs/2026-07-25-pump-station-wiring-v2-design.md
// Rút kinh nghiệm lắp thật bản in v1: (1) jack DC 12V rời lộ ngoài không chỗ giấu,
// (2) dây động cơ phải vòng qua thân bơm do 2 chân dẹt lệch ~180° quanh chu vi,
// (3) dây logic ra ESP32 không có strain-relief. CHƯA ĐO các kích thước dưới đây.
dc_jack_hole_d       = 9.5;   // Ø lỗ panel-mount jack DC 5.5×2.1mm — CHƯA ĐO module thật
dc_jack_hole_z       = l298n_foot_h + 10.0; // tâm lỗ tính từ mặt đế — ước lượng ngang tầm cầu đấu vít
dc_jack_shelf_h      = 3.0;   // cao gờ đỡ board jack+cầu đấu, tính từ mặt đế
dc_jack_shelf_w      = 24.0;  // rộng gờ đỡ (dọc Y) — CHƯA ĐO board thật (~20×15mm điển hình)
dc_jack_shelf_depth  = 15.0;  // sâu gờ đỡ (dọc X, từ mặt trong thành −X vào) — CHƯA ĐO

wire_notch_w_out     = 7.0;   // bề rộng khe dây OUTPUT (+X, ra yên kẹp) — rộng hơn wire_notch_w
                              // vì chứa 2 dây hàn trực tiếp + co nhiệt song song

pump_wire_groove_w   = 3.0;   // rộng rãnh dẫn dây trên mặt −X yên kẹp gần hộp L298N
pump_wire_groove_d   = 1.5;   // sâu rãnh dẫn dây (khoét vào mặt ngoài khối, KHÔNG xuyên lòng máng)

logic_notch_fillet_r = 2.0;   // bán kính gờ bo tròn thoát dây logic (strain relief), cạnh +Y
```

- [ ] **Step 2: Kiểm tra cú pháp — render lại 1 file hiện có (chưa dùng hằng số mới) để xác nhận `constants.scad` không lỗi cú pháp**

Run:
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/print/print_pump_station.scad --output "$SCRATCHPAD/task1_syntax_check.png"
```
(thay `$SCRATCHPAD` bằng đường dẫn scratchpad thật của phiên làm việc)

Expected: `Success: Preview saved to ...` — không có dòng `ERROR`/`Parser error` nào từ OpenSCAD. File này vẫn dùng `pump_station_001.scad` (chưa đổi), nên đây chỉ là phép thử "constants.scad thêm block mới không phá vỡ include hiện có".

- [ ] **Step 3: Commit**

```bash
git add openscad/constants.scad
git commit -m "feat(openscad): thêm hằng số v2 cho trạm bơm - giấu jack DC, dẫn dây, strain relief"
```

---

### Task 2: Tạo `pump_station_002.scad` + thay đổi 1 (lỗ panel-mount jack DC 12V)

**Files:**
- Create: `openscad/components/pump_station_002.scad`

**Interfaces:**
- Consumes: hằng số từ Task 1 (`dc_jack_hole_d`, `dc_jack_hole_z`, `dc_jack_shelf_h`, `dc_jack_shelf_w`, `dc_jack_shelf_depth`) + toàn bộ hằng số `pump_station_001.scad` đã dùng (`l298n_*`, `pump_clamp_*`, `pump_station_*`) — không đổi.
- Produces: module `pump_station()`, `pump_station_lid()` — **cùng tên và cùng chữ ký (không tham số) như `_001`**, để Task 5 chỉ cần đổi dòng `use`, không đổi lời gọi.

- [ ] **Step 1: Xác nhận số phiên bản kế tiếp**

Run:
```bash
cd openscad/components && bash ../../.claude/skills/openscad/scripts/version-scad.sh pump_station && cd ../..
```
Expected output chứa dòng: `Next version: pump_station_002`

- [ ] **Step 2: Tạo file `pump_station_002.scad` — copy `_001` nguyên vẹn + đổi khe input thành lỗ jack DC**

Tạo `openscad/components/pump_station_002.scad` với nội dung sau (toàn bộ file, đã copy từ `_001` và áp thay đổi 1; thay đổi 2 và 3 sẽ chèn ở Task 3, 4):

```openscad
// ============================================================================
// pump_station_002.scad — Trạm bơm gọn v2: giấu dây & gọn hóa đấu nối
// ----------------------------------------------------------------------------
// Kế thừa pump_station_001.scad (đế liền + hộp che L298N hở nắp + 2 yên kẹp RS365).
// Nguồn thay đổi: docs/superpowers/specs/2026-07-25-pump-station-wiring-v2-design.md
// (rút kinh nghiệm lắp thật bản in v1, xem ảnh user cung cấp trong buổi brainstorm).
//
// 3 thay đổi so _001 (KHÔNG đổi kiến trúc tổng thể — đế/hộp hở nắp/yên kẹp lồng
// từ trên giữ nguyên như đã duyệt ở spec v1):
//   1. Khe dây INPUT 12V (cạnh −X hộp L298N) → LỖ TRÒN panel-mount cho jack DC
//      5.5×2.1mm + gờ đỡ board nhỏ (jack + cầu đấu vít) bên trong.
//   2. Khe dây OUTPUT động cơ (cạnh +X) nới rộng (dây hàn trực tiếp, bỏ đầu jumper)
//      + thêm rãnh dẫn dây trên mặt ngoài yên kẹp GẦN hộp (bù 2 chân dẹt mô-tơ
//      lệch ~180° quanh chu vi, không cùng hướng khe lồng đỉnh khối).
//   3. Khe dây LOGIC (cạnh +Y, ra ESP32) thêm gờ bo tròn (strain relief) ở mép khe.
//
// Trục dài đế = X. Hộp L298N ở đầu −X (gần), 2 yên kẹp ở đầu +X (xa) — không đổi
// so _001. Tâm lỗ khoan yên kẹp nằm ngang dọc trục X, khớp hướng trục bơm.
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
        // v2: LỖ PANEL-MOUNT jack DC 12V — cạnh −X (thay khe dây input trần cũ của
        // _001). Xuyên thẳng qua thành, tâm cao dc_jack_hole_z tính từ mặt đế —
        // CHƯA ĐO module jack thật, xác nhận khi lắp (xem constants.scad).
        translate([-EPS, l298n_box_od_w/2, dc_jack_hole_z])
            rotate([0, 90, 0])
                cylinder(d = dc_jack_hole_d, h = l298n_box_wall + 2*EPS, $fn = 32);
        // Khe dây OUTPUT động cơ — cạnh +X (hướng về phía yên kẹp bơm). v2: nới rộng
        // (wire_notch_w_out thay wire_notch_w) vì 2 dây HÀN trực tiếp + co nhiệt cần
        // chỗ hơn dây trần đơn — đầu jumper phía này đã bỏ (user sẽ hàn).
        translate([l298n_box_od_l - l298n_box_wall - EPS, l298n_box_od_w/2 - wire_notch_w_out/2,
                   l298n_box_h - wire_notch_h])
            cube([l298n_box_wall + 2*EPS, wire_notch_w_out, wire_notch_h + EPS]);
        // Khe dây LOGIC (IN1/IN2/EN + GND lên ESP32) — cạnh +Y (về khối quang chính).
        // Vị trí/bề rộng giữ nguyên như _001 (vẫn dùng jumper đực-cái, không đổi).
        translate([l298n_box_od_l/2 - wire_notch_w/2, l298n_box_od_w - l298n_box_wall - EPS,
                   l298n_box_h - wire_notch_h])
            cube([wire_notch_w, l298n_box_wall + 2*EPS, wire_notch_h + EPS]);
        // Khe thoát khí — cạnh −Y (đối diện khe dây logic, phía tản nhiệt board)
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
                translate([0, 0, 5])
                    cylinder(d = l298n_lid_screw_d, h = l298n_box_h - 3 - 5 + EPS, $fn = 24);
            }
    // v2: gờ đỡ (shelf) cho board nhỏ jack DC + cầu đấu vít — tựa ngang tầm lỗ jack,
    // sát mặt trong thành −X. Kích thước board thật CHƯA ĐO (ước lượng ~20×15mm) —
    // xác nhận footprint không đội board L298N chính khi lắp thật (2 board cùng
    // đáy hộp, chỉ khác chiều cao gờ đỡ).
    translate([l298n_box_wall, l298n_box_od_w/2 - dc_jack_shelf_w/2, 0])
        cube([dc_jack_shelf_depth, dc_jack_shelf_w, dc_jack_shelf_h]);
    // v2: gờ bo tròn thoát dây logic (strain relief) — cạnh +Y, ngoài khe dây logic.
    // Tâm đặt đúng mặt ngoài thành (y = l298n_box_od_w) để nửa trong chồng khít vào
    // thành (union liền khối), nửa ngoài nhô ra làm mặt cong cho dây tựa khi bẻ góc.
    translate([l298n_box_od_l/2, l298n_box_od_w, l298n_box_h - wire_notch_h])
        rotate([0, 90, 0])
            cylinder(d = 2*logic_notch_fillet_r, h = wire_notch_w, center = true, $fn = 32);
}

// Nắp hộp L298N — chi tiết in RIÊNG (print_pump_station_lid.scad) — KHÔNG đổi so _001
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
// v2: tham số wire_groove — khi true, khoét thêm rãnh dẫn dây trên mặt −X (hướng
// hộp L298N) để bù trường hợp 2 chân dẹt mô-tơ không cùng hướng khe lồng đỉnh khối.
// Chỉ bật true ở yên kẹp GẦN hộp L298N (xem pump_station()).
module pump_clamp_post(wire_groove = false) {
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
        // v2: rãnh dẫn dây động cơ trên mặt NGOÀI khối (mặt −X, hướng hộp L298N),
        // chạy dọc trục Z từ đáy khối tới tầm lỗ khoan — dẫn dây từ rãnh đế lên tới
        // chỗ chân dẹt mô-tơ, PHÒNG trường hợp chân dẹt không lộ ra đúng khe lồng
        // đỉnh khối. CHƯA ĐO góc lệch thật giữa 2 chân dẹt — xem giả định #3 trong
        // spec v2. Không xuyên vào lòng máng (chỉ khoét mặt ngoài).
        if (wire_groove)
            translate([-EPS, -pump_wire_groove_w/2, -EPS])
                cube([pump_wire_groove_d + EPS, pump_wire_groove_w, center_z + EPS]);
    }
}

// ---------------------------------------------------------------- Rãnh dây nối hộp L298N ↔ yên kẹp bơm (khoét vào mặt đế) — KHÔNG đổi so _001
module wire_channel(length) {
    ch_w = 6.0; ch_d = 1.5;
    translate([0, -ch_w/2, -ch_d])
        cube([length, ch_w, ch_d + EPS]);
}

// ---------------------------------------------------------------- Trạm bơm hoàn chỉnh (đế + hộp L298N không nắp + 2 yên kẹp)
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
    // 2 yên kẹp bơm — yên GẦN hộp (clamp_x0) bật wire_groove=true để dẫn dây từ
    // rãnh đế lên tới chân dẹt mô-tơ (v2); yên xa (clamp_x1) giữ nguyên.
    translate([clamp_x0, 0, 0]) pump_clamp_post(wire_groove = true);
    translate([clamp_x1, 0, 0]) pump_clamp_post();
}

// Xem lẻ
pump_station();
translate([0, 80, 0]) pump_station_lid();
```

- [ ] **Step 3: Render preview**

Run:
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/pump_station_002.scad --output "$SCRATCHPAD/task2_check.png" --size 1200x900
```
Expected: `Success: Preview saved to ...`, không có lỗi OpenSCAD.

- [ ] **Step 4: Đọc ảnh để xác nhận hình học**

Dùng Read tool mở `$SCRATCHPAD/task2_check.png`. Kỳ vọng thấy:
- Hộp L298N vẫn có 4 gờ góc + 2 trụ vít chéo bên trong (không đổi so _001).
- Cạnh hộp GẦN yên kẹp (phía −X, xa yên kẹp — hướng "ra ngoài trạm") có **1 lỗ tròn xuyên thành** thay vì khe chữ nhật trần như bản _001 cũ.
- Không còn khe chữ nhật ở vị trí input cũ.

Nếu lỗ tròn không xuất hiện hoặc vị trí sai (ví dụ xuyên nhầm cạnh), sửa lại `translate`/`rotate` ở Step 2 rồi lặp lại Step 3–4.

- [ ] **Step 5: Commit**

```bash
git add openscad/components/pump_station_002.scad
git commit -m "feat(openscad): pump_station_002 - lỗ panel-mount jack DC 12V thay khe dây input"
```

---

### Task 3: Thay đổi 2 — nới khe output + rãnh dẫn dây yên kẹp gần hộp

**Files:**
- Modify: `openscad/components/pump_station_002.scad` (đã tạo ở Task 2)

**Interfaces:**
- Consumes: `wire_notch_w_out`, `pump_wire_groove_w`, `pump_wire_groove_d` (Task 1).
- Note: thay đổi này **đã được viết sẵn trong nội dung Task 2 Step 2** ở trên (khe output dùng `wire_notch_w_out`, module `pump_clamp_post(wire_groove=false)` có nhánh `if (wire_groove)`, và lời gọi `pump_clamp_post(wire_groove = true)` cho yên gần hộp). Task này chỉ là bước **kiểm chứng độc lập** hình học của riêng 2 thay đổi đó bằng cách render cận cảnh — không cần sửa code thêm trừ khi Step 1 phát hiện sai lệch.

- [ ] **Step 1: Render cận cảnh cụm yên kẹp + cạnh output hộp**

Run (dùng `--camera` để phóng vào vùng yên kẹp gần hộp; toạ độ ước lượng theo layout `pump_station_len=128`, hộp ở x≈0-52, yên gần ở x≈72-80):
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/pump_station_002.scad --output "$SCRATCHPAD/task3_check.png" --size 1200x900 --camera 40,0,20,60,0,0,150
```

- [ ] **Step 2: Đọc ảnh để xác nhận**

Dùng Read tool mở `$SCRATCHPAD/task3_check.png`. Kỳ vọng thấy:
- Khe dây ở cạnh hộp hướng về yên kẹp (+X) **rộng hơn rõ rệt** so với khe logic đối diện (bên kia hộp) — vì `wire_notch_w_out=7.0` > `wire_notch_w=6.0`.
- Yên kẹp GẦN hộp (yên đầu tiên theo hướng +X) có **1 rãnh dọc trên mặt hướng về hộp** (mặt −X của khối yên), chạy từ đáy khối lên khoảng nửa chiều cao khối (tới tâm lỗ khoan).
- Yên kẹp XA hộp (yên thứ hai) **KHÔNG** có rãnh này — chỉ có khối kẹp + khe lồng + rãnh zip-tie như bản gốc.

Nếu rãnh không xuất hiện đúng vị trí (ví dụ lộn qua yên xa, hoặc xuyên vào lòng máng thay vì chỉ ở mặt ngoài), sửa lại `translate` trong nhánh `if (wire_groove)` của `pump_clamp_post()` (Task 2 Step 2) rồi lặp lại Step 1–2.

- [ ] **Step 3: Commit (chỉ commit nếu Step 2 phát hiện cần sửa code; nếu hình học đã đúng từ Task 2, bỏ qua bước này)**

```bash
git add openscad/components/pump_station_002.scad
git commit -m "fix(openscad): điều chỉnh rãnh dẫn dây yên kẹp / khe output sau kiểm tra render"
```

---

### Task 4: Thay đổi 3 — xác nhận gờ bo tròn thoát dây logic

**Files:**
- Modify: `openscad/components/pump_station_002.scad` (đã tạo ở Task 2; gờ bo tròn đã viết sẵn ở Task 2 Step 2 trong `l298n_box_walls()`)

**Interfaces:**
- Consumes: `logic_notch_fillet_r` (Task 1).
- Note: cũng giống Task 3 — code đã có sẵn từ Task 2, task này là bước kiểm chứng render độc lập cho riêng chi tiết này.

- [ ] **Step 1: Render cận cảnh cạnh logic (+Y) của hộp**

Run:
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/pump_station_002.scad --output "$SCRATCHPAD/task4_check.png" --size 1200x900 --camera 26,52,27,26,26,10,120
```

- [ ] **Step 2: Đọc ảnh để xác nhận**

Dùng Read tool mở `$SCRATCHPAD/task4_check.png`. Kỳ vọng thấy: ở mép ngoài khe dây logic (cạnh +Y, gần đỉnh hộp), có **1 gờ cong lồi ra** (nửa trụ tròn nhô khỏi mặt thành phẳng) thay vì mép vuông 90° sắc cạnh như bản _001. Gờ này nằm đúng bề rộng khe (không tràn ra ngoài khe logic).

Nếu gờ bị chìm vào trong thành (không nhô ra ngoài) hoặc lệch vị trí khỏi khe, sửa lại toạ độ `translate` của khối `cylinder` bo tròn trong `l298n_box_walls()` (Task 2 Step 2) rồi lặp lại Step 1–2.

- [ ] **Step 3: Commit (chỉ nếu có sửa)**

```bash
git add openscad/components/pump_station_002.scad
git commit -m "fix(openscad): điều chỉnh gờ bo tròn thoát dây logic sau kiểm tra render"
```

---

### Task 5: Trỏ các file in + assembly tổng sang `pump_station_002`

**Files:**
- Modify: `openscad/print/print_pump_station.scad:7`
- Modify: `openscad/print/print_pump_station_lid.scad:5`
- Modify: `openscad/aqua_scope_assembly_001.scad:31`

**Interfaces:**
- Consumes: `pump_station()`, `pump_station_lid()` từ `pump_station_002.scad` (Task 2–4) — chữ ký không đổi so `_001` nên không cần sửa lời gọi, chỉ đổi dòng `use`.

- [ ] **Step 1: Sửa `print_pump_station.scad`**

Trong `openscad/print/print_pump_station.scad`, đổi dòng 7:
```openscad
use <../components/pump_station_001.scad>
```
thành:
```openscad
use <../components/pump_station_002.scad>
```

- [ ] **Step 2: Sửa `print_pump_station_lid.scad`**

Trong `openscad/print/print_pump_station_lid.scad`, đổi dòng 5:
```openscad
use <../components/pump_station_001.scad>
```
thành:
```openscad
use <../components/pump_station_002.scad>
```

- [ ] **Step 3: Sửa `aqua_scope_assembly_001.scad`**

Trong `openscad/aqua_scope_assembly_001.scad`, đổi dòng 31:
```openscad
use <components/pump_station_001.scad>
```
thành:
```openscad
use <components/pump_station_002.scad>
```

- [ ] **Step 4: Render lại 2 file in + assembly tổng để xác nhận không lỗi**

Run:
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/print/print_pump_station.scad --output "$SCRATCHPAD/task5_print.png"
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/print/print_pump_station_lid.scad --output "$SCRATCHPAD/task5_lid.png"
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/aqua_scope_assembly_001.scad --output "$SCRATCHPAD/task5_assembly.png" --size 1400x1000
```

Expected: cả 3 lệnh in ra `Success: Preview saved to ...`, không có `ERROR`/assert fail nào từ `aqua_scope_assembly_001.scad` (file này có các `assert()` kiểm tra kích thước tổng thể — nếu `pump_station_002` phá vỡ giả định về `pump_station_len`/`pump_station_wid`, assembly sẽ báo lỗi ở bước này).

- [ ] **Step 5: Đọc ảnh `task5_assembly.png` để xác nhận trạm bơm vẫn xuất hiện đúng vị trí**

Dùng Read tool mở `$SCRATCHPAD/task5_assembly.png`. Kỳ vọng: cụm trạm bơm (đế + hộp + yên kẹp) vẫn nằm cạnh mô hình `pump_rs365()` placeholder ở vùng +X như trước (không dịch chuyển vị trí, không biến mất, không lỗi hình học vỡ vụn).

- [ ] **Step 6: Commit**

```bash
git add openscad/print/print_pump_station.scad openscad/print/print_pump_station_lid.scad openscad/aqua_scope_assembly_001.scad
git commit -m "feat(openscad): trỏ print_pump_station + assembly sang pump_station_002"
```

---

### Task 6: Xuất STL, kiểm tra manifold, cập nhật ảnh preview component

**Files:**
- Modify (regenerate): `openscad/print/print_pump_station.stl`
- Modify (regenerate): `openscad/print/print_pump_station_lid.stl`
- Create: `openscad/components/pump_station_002.png`

**Interfaces:**
- Consumes: `print_pump_station.scad`, `print_pump_station_lid.scad` (đã trỏ sang `_002` ở Task 5).

- [ ] **Step 1: Xuất STL cho đế + hộp + yên kẹp**

Run:
```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station.scad --output openscad/print/print_pump_station.stl
```
Expected: không có cảnh báo `non-manifold`, `self-intersect`, hay `degenerate` trong output. Nếu có, quay lại Task 2–4 sửa hình học (thường do 2 solid chạm nhau đúng 1 mặt phẳng với `EPS` không đủ) rồi lặp lại.

- [ ] **Step 2: Xuất STL cho nắp hộp L298N**

Run:
```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/print/print_pump_station_lid.scad --output openscad/print/print_pump_station_lid.stl
```
Expected: không có cảnh báo manifold/self-intersect/degenerate (nắp không đổi so `_001` nên đây chủ yếu là phép thử "vẫn xuất được sau khi đổi include").

- [ ] **Step 3: Tạo ảnh preview component mới (theo đúng quy ước đã có `pump_station_001.png`)**

Run:
```bash
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/components/pump_station_002.scad --output openscad/components/pump_station_002.png --size 1200x900
```

- [ ] **Step 4: Đọc ảnh `pump_station_002.png` lần cuối — xác nhận cả 3 thay đổi cùng hiện diện**

Dùng Read tool mở `openscad/components/pump_station_002.png`. Kỳ vọng thấy đồng thời:
1. Lỗ tròn panel-mount ở cạnh hộp xa yên kẹp (thay khe input cũ).
2. Khe output (cạnh hộp gần yên kẹp) rộng hơn khe logic đối diện + rãnh dọc trên mặt yên kẹp gần hộp.
3. Gờ bo tròn ở khe logic (cạnh hộp còn lại, hướng ra ngoài — phía ESP32).

- [ ] **Step 5: Commit**

```bash
git add openscad/print/print_pump_station.stl openscad/print/print_pump_station_lid.stl openscad/components/pump_station_002.png
git commit -m "build(openscad): xuất STL + preview pump_station_002 (giấu jack DC, dẫn dây, strain relief)"
```

---

## Giả định chưa xác nhận (kế thừa từ spec, không chặn triển khai)

1. Đường kính lỗ panel-mount jack DC thật (9.5mm chỉ là điển hình cho jack 5.5×2.1mm) — đo lại khi lắp, sửa `dc_jack_hole_d` trong `constants.scad` nếu lệch.
2. Kích thước + vị trí board nhỏ (jack + cầu đấu) thật — hiện ước lượng ~20×15mm, `dc_jack_shelf_h`/`dc_jack_shelf_w`/`dc_jack_shelf_depth`/`dc_jack_hole_z` có thể cần chỉnh lại để board thật vừa khít và không đội board L298N chính (2 board cùng đáy hộp).
3. Góc lệch thật giữa 2 chân dẹt trên thân mô-tơ RS365 (giả định ~180° dựa theo ảnh) — nếu góc lệch thật khác, có thể cần xoay vị trí rãnh dẫn dây (`pump_wire_groove_*`) trong `pump_clamp_post()`.
4. Các giả định cũ từ spec v1 (kích thước board L298N 43×43×27mm, Ø thân bơm 31.5mm) vẫn CHƯA ĐO, không đổi trong plan này.
