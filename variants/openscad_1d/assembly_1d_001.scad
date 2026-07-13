// ============================================================================
// assembly_1d_001.scad — Ráp Đầu dò quang 1D.
// Flags: explode, show_tube, show_optics, show_block, half.
// ============================================================================
include <constants_1d.scad>
use <components/mocks_001.scad>
use <components/sensor_block_002.scad>

explode      = 0;   // 0..1 tách rời
show_tube    = true;
show_optics  = true;
show_block   = true;
block_mode   = "both";  // "both" | "upper" | "lower"

ex = explode;

// ---- Khối gá ----
if (show_block) {
    if (block_mode == "both") {
        sensor_block_half("lower");
        translate([0, 0, ex * 26]) sensor_block_half("upper");
    } else {
        sensor_block_half(block_mode);
    }
}

// ---- Ống kênh (dọc Z) ----
if (show_tube)
    clear_tube();

// ---- Quang học (seat đúng vào rãnh; đầu phát/cửa sổ nằm ở vai khẩu độ ~±8.15) ----
if (show_optics) {
    // Laser −X: local+Z→+X, đầu phát (top) tới vai −laser_shoulder_x.
    translate([-(laser_shoulder_x + laser_len) - ex*20, 0, 0])
        rotate([0, 90, 0]) laser_module();
    // PD hấp thụ +X: local+Z→−X, cửa sổ (top) tới vai +pd_shoulder, nhìn về O.
    translate([pd_shoulder + pd_len + ex*20, 0, 0])
        rotate([0, -90, 0]) photodiode();
    // PD tán xạ: đặt như PD +X rồi xoay quanh Z một góc scatter_ang (cửa sổ luôn nhìn O).
    rotate([0, 0, scatter_ang])
        translate([pd_shoulder + pd_len + ex*20, 0, 0])
            rotate([0, -90, 0]) photodiode();
}
