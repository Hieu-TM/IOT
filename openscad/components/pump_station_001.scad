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
                // Lỗ tự-ren hở TỪ ĐỈNH gờ (vít xuyên nắp từ trên xuống bắt vào đây);
                // chừa 5mm đặc ở ĐÁY gờ (giáp mặt đế) để không thông xuống đế.
                // (SỬA so bản gốc trong brief: bản gốc đặt lỗ hở ở ĐÁY [z=-EPS] và
                // đặc ở ĐỈNH [z=24..29] — ngược hướng, vít từ trên không vào được lỗ.)
                translate([0, 0, 5])
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
