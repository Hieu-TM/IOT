// ============================================================================
// mocks_001.scad — Linh kiện MUA SẴN (không in), chỉ để canh trục trong assembly.
// ============================================================================
include <../constants_1d.scad>

// Ống trong dọc Z, tâm O. Kèm nước + 1 hạt mẫu (tuỳ chọn).
module clear_tube(show_water = true, show_part = true) {
    color(col_acrylic)
        difference() {
            cylinder(d = tube_od, h = tube_len, center = true);
            cylinder(d = tube_id, h = tube_len + 1, center = true);
        }
    if (show_water)
        color(col_water) cylinder(d = tube_id - 0.2, h = tube_len - 2, center = true);
    if (show_part)
        color(col_part) translate([0, 0, 6]) sphere(d = 3.5);   // 1 hạt đang rơi qua
}

// Laser barrel: dựng dọc +Z, đầu phát (đỏ) ở TOP. Assembly xoay để chĩa vào O.
module laser_module() {
    color(col_metal) cylinder(d = laser_dia, h = laser_len);
    color(col_laser) translate([0, 0, laser_len - 0.6]) cylinder(d = laser_dia - 1, h = 0.8);
}

// Photodiode gói Ø5: thân + cửa sổ (teal) ở TOP. Assembly xoay để cửa sổ nhìn O.
module photodiode() {
    color(col_pd) cylinder(d = pd_dia, h = pd_len);
    color(col_pd_win) translate([0, 0, pd_len - 0.5]) cylinder(d = pd_dia - 0.8, h = 0.6);
}
