// ============================================================================
// fluid_domain_full_001.scad — Khối KHÔNG GIAN TÍNH TOÁN đầy đủ cho CFD đa pha
// (nước + khí), KHÁC fluid_domain_001.scad (chỉ khối nước tĩnh khi settle).
// ----------------------------------------------------------------------------
// Mô phỏng sóng (VOF/multiphase) cần cả 2 pha CÙNG TỒN TẠI trong 1 miền tính:
// nước bên dưới + khoảng khí bên trên để mặt nước có chỗ dao động/nhấp nhô khi
// bơm bơm xung — KHÔNG chỉ khối nước hình dạng tĩnh lúc settle
// (fluid_domain_001.stl chỉ dùng để đối chiếu hình dạng lúc nghỉ, KHÔNG nạp
// thẳng vào SimScale cho mô phỏng sóng).
//
// Khác fluid_domain_001.scad duy nhất 1 điểm: main_lumen() cao tới tray_depth
// (12mm, hết thành khay) thay vì chỉ water_depth (6mm). Mặt trên (z=12) sẽ được
// khai báo là biên "opening" (áp suất khí quyển) trong SimScale — nước chỉ được
// gán làm điều kiện ban đầu (initial phase fraction) TRONG PHẦN MỀM, ở z<6,
// KHÔNG cần dựng 2 khối rời trong CAD.
// ============================================================================
include <../constants.scad>
use <../components/flow_tray_003.scad>

INLET_STUB_LEN  = 20;
OUTLET_STUB_LEN = 20;
EPS3 = 0.05;

function plenum_deep_local() = 7.0;
function barb_len_local()    = 8.0;

module main_lumen_full() {
    cylinder(d = tray_inner, h = tray_depth, $fn = 120);  // KHÁC bản water-only: h=tray_depth
}

module inlet_channel() {
    x_bore_start = -tray_outer/2 - plenum_deep_local() + 2;
    x_stub_far   = -tray_outer/2 - plenum_deep_local() - barb_len_local() - INLET_STUB_LEN;
    hull() {
        translate([x_bore_start, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = 1, $fn = 36);
        translate([-tray_outer/2 - 1.2, -inlet_slot_w/2, 0])
            cube([5.2, inlet_slot_w, inlet_slot_h]);
    }
    translate([x_stub_far - EPS3, 0, port_z])
        rotate([0, 90, 0])
            cylinder(d = outlet_bore, h = x_bore_start - x_stub_far + EPS3, $fn = 32);
}

module outlet_channel() {
    bell_cover_d = 2 * (outlet_bore/2 + 2*bell_fillet_r) + 4;
    x_wall = tray_outer/2;
    x_stub_far = x_wall + barb_len_local() + OUTLET_STUB_LEN;
    hull() {
        translate([x_wall - 5, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = bell_cover_d, h = 5 + EPS3, $fn = 48);
        translate([x_stub_far, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = EPS3, $fn = 32);
    }
}

module fluid_domain_full() {
    difference() {
        union() {
            main_lumen_full();
            inlet_channel();
            outlet_channel();
        }
        flow_tray();
    }
}

fluid_domain_full();
%color(col_plastic, 0.2) flow_tray();
