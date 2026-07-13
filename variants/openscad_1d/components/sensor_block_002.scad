// ============================================================================
// sensor_block_002.scad — Khối gá quang clamshell (SUPERSEDE _001).
// Thêm so với _001 (sửa lỗi khớp module + vá theo README variants):
//   • Góc PD tán xạ THAM SỐ HOÁ (scatter_ang) — README ưu tiên FSC/BSC hơn 90° SSC.
//   • CHỐT ĐỊNH VỊ Ø3 rời ở cả 2 nửa → khử lệch nửa-rãnh quang do khe vít (lỗi _001).
//   • Khoét đầu vít M3 chìm mặt trên; vít giữ ống chống tuột (mặt −Y, nửa trên).
// Rãnh quang vẫn nằm ở mặt tách z=0 → in phẳng KHÔNG support.
// ============================================================================
include <../constants_1d.scad>

r_exit = sqrt(block_w*block_w + block_d*block_d)/2 + 2;  // đủ dài để rãnh thoát ra mặt khối

// Hốc quang (trừ khỏi khối) — chung cho cả 2 nửa.
module _optical_cavities() {
    // Bore ống dọc Z
    cylinder(d = tube_bore_d, h = block_h + 2, center = true);
    // Laser (−X): rãnh barrel + khẩu độ
    x_cyl(laser_dia, -(block_w/2 + 1), -laser_shoulder_x);
    x_cyl(laser_ap,  -laser_shoulder_x, -tube_bore_r + 0.1);
    // PD hấp thụ (+X): khẩu độ + rãnh (trục che-khuất, đối diện laser)
    x_cyl(pd_ap,  tube_bore_r - 0.1, pd_shoulder);
    x_cyl(pd_dia, pd_shoulder, block_w/2 + 1);
    // PD tán xạ (góc scatter_ang quanh O, vẫn nằm mặt phẳng z=0)
    rotate([0, 0, scatter_ang]) {
        x_cyl(pd_ap,  tube_bore_r - 0.1, pd_shoulder);
        x_cyl(pd_dia, pd_shoulder, r_exit);
    }
    // Chốt định vị (lỗ xuyên qua mặt tách — mỗi nửa nhận phần của mình)
    dowel_positions()
        cylinder(d = dowel_hole_d, h = 2*dowel_depth, center = true);
}

module _block_solid() {
    cube([block_w, block_d, block_h], center = true);
}

// which = "upper" (z>0) | "lower" (z<0).
module sensor_block_half(which = "lower") {
    zmin    = (which == "upper") ? 0 : -block_h;
    screw_d = (which == "upper") ? m3_clear : m3_tap;
    color(col_block)
    difference() {
        intersection() {
            _block_solid();
            translate([-block_w, -block_d, zmin]) cube([2*block_w, 2*block_d, block_h]);
        }
        _optical_cavities();
        m3_corners() cylinder(d = screw_d, h = block_h + 2, center = true);
        if (which == "upper") {
            // Khoét đầu vít chìm mặt trên
            m3_corners()
                translate([0, 0, block_h/2 - cbore_h]) cylinder(d = cbore_d, h = cbore_h + 1);
            // Vít giữ ống (tự-ren) từ mặt −Y vào bore, cao độ tube_set_z
            translate([0, -(block_d/2 + 1), tube_set_z]) rotate([-90, 0, 0])
                cylinder(d = tube_set_d, h = (block_d/2 + 1) - tube_bore_r + 0.6);
        }
    }
}

module sensor_block_assembled() {
    sensor_block_half("upper");
    sensor_block_half("lower");
}

// Preview: 2 nửa tách theo Z.
sensor_block_half("lower");
translate([0, 0, 24]) sensor_block_half("upper");
