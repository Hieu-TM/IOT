// ============================================================================
// sensor_block_001.scad — Khối gá quang clamshell (2 nửa tách ở z=0).
// Rãnh quang nằm ở mặt tách → in úp mặt tách xuống, KHÔNG cần support.
// ============================================================================
include <../constants_1d.scad>

// Các hốc quang (trừ khỏi khối đặc) — KHÔNG gồm lỗ vít (xử lý theo nửa).
module _optical_cavities() {
    // Bore ống dọc Z
    cylinder(d = tube_bore_d, h = block_h + 2, center = true);
    // Laser (−X): rãnh barrel + khẩu độ tới ống
    x_cyl(laser_dia, -(block_w/2 + 1), -laser_shoulder_x);
    x_cyl(laser_ap,  -laser_shoulder_x, -tube_bore_r + 0.1);
    // PD hấp thụ (+X): khẩu độ + rãnh
    x_cyl(pd_ap,  tube_bore_r - 0.1, pd_shoulder);
    x_cyl(pd_dia, pd_shoulder, block_w/2 + 1);
    // PD tán xạ (+Y): khẩu độ + rãnh
    y_cyl(pd_ap,  tube_bore_r - 0.1, pd_shoulder);
    y_cyl(pd_dia, pd_shoulder, block_d/2 + 1);
}

// Khối đặc trước khi khoét.
module _block_solid() {
    cube([block_w, block_d, block_h], center = true);
}

// which = "upper" (z>0) hoặc "lower" (z<0).
module sensor_block_half(which = "lower") {
    zmin = (which == "upper") ? 0 : -block_h;
    screw_d = (which == "upper") ? m3_clear : m3_tap;
    color(col_block)
    difference() {
        intersection() {
            _block_solid();
            translate([-block_w, -block_d, zmin]) cube([2*block_w, 2*block_d, block_h]);
        }
        _optical_cavities();
        m3_corners() cylinder(d = screw_d, h = block_h + 2, center = true);
    }
}

// Cả 2 nửa tại chỗ (xem lắp ghép).
module sensor_block_assembled() {
    sensor_block_half("upper");
    sensor_block_half("lower");
}

// Preview mặc định: 2 nửa tách nhau kiểm mặt cắt rãnh.
sensor_block_half("lower");
translate([0, 0, 24]) sensor_block_half("upper");
