// ============================================================================
// top_lid_xiao_001.scad — NẮP ĐẬY TRÊN CÙNG baseline XIAO ESP32-S3 Sense (IN MỚI)
// ----------------------------------------------------------------------------
// Đậy board XIAO ngồi trong top_cap (base Matchboxscope): chắn bụi/sáng từ trên,
// giữ board, luồn cáp USB-C ra. CÙNG giao diện 4×M3 30×30 như lid Matchboxscope
// in sẵn, nhưng IN DÀY hơn cho cứng + có KHE CÁP USB-C + GỜ ĐỊNH VỊ ôm ngoài miệng.
//
// Kết cấu (gốc: TRỤC QUANG = Z tại gốc; MẶT DƯỚI tấm nắp = z=0, +Z lên):
//  - Tấm nắp rounded-rect (footprint = outline base + gờ), dày lid_x_t, z=0..lid_x_t.
//  - GỜ ĐỊNH VỊ thò xuống z=−lid_x_lip_h..0: hốc trong ôm ngoài miệng base
//    (khe lid_x_lip_clr rộng rãi — 4 vít định vị chính, gờ chỉ chắn sáng/bụi).
//    Base chui LÊN vào hốc, mặt trên base chạm mặt dưới tấm nắp.
//  - 4 lỗ THÔNG M3 Ø3.2 (bước 30×30, tâm=trục quang) + khoét đầu vít: vít M3
//    tự-ren vào NỬA TRÊN 4 lỗ base (nửa dưới dành cho vít bích ống — lỗ base sâu
//    12mm nên 2 vít ngắn không chạm nhau; đây đúng ý đồ base+lid gốc Matchboxscope).
//  - KHE CÁP USB-C ở cạnh +X (cắt hết gờ + mép tấm): cáp thoát ra từ dưới tấm.
// Assembly đặt nắp tại mặt trên base (global z = z_tube_top + cap_h).
// ============================================================================
include <../constants.scad>

EPS = 0.05;

// footprint hốc (ôm base) và tấm nắp (= hốc + vách gờ)
recess_dims = [cap_outline[0] + 2*lid_x_lip_clr, cap_outline[1] + 2*lid_x_lip_clr];
recess_r    = cap_corner_r + lid_x_lip_clr;
outer_dims  = [recess_dims[0] + 2*lid_x_lip_wall, recess_dims[1] + 2*lid_x_lip_wall];
outer_r     = recess_r + lid_x_lip_wall;

module rrect(dims, r) {
    hull() for (sx = [1, -1], sy = [1, -1])
        translate([sx*(dims[0]/2 - r), sy*(dims[1]/2 - r)]) circle(r = r, $fn = 48);
}

module top_lid_xiao() {
    color(col_plastic) difference() {
        union() {
            // Tấm nắp (z=0..lid_x_t)
            translate([cap_outline_off[0], cap_outline_off[1], 0])
                linear_extrude(lid_x_t) rrect(outer_dims, outer_r);
            // Gờ định vị (vành thò xuống z=−lip_h..0)
            translate([cap_outline_off[0], cap_outline_off[1], -lid_x_lip_h])
                linear_extrude(lid_x_lip_h)
                    difference() {
                        rrect(outer_dims, outer_r);
                        rrect(recess_dims, recess_r);
                    }
        }
        // 4 lỗ thông M3 (xuyên cả gờ+tấm) + khoét đầu vít từ mặt trên
        m3_mount_pattern() {
            translate([0, 0, -lid_x_lip_h - EPS])
                cylinder(d = lid_x_screw_d, h = lid_x_lip_h + lid_x_t + 2*EPS, $fn = 32);
            translate([0, 0, lid_x_t - lid_x_cbore_h])
                cylinder(d = lid_x_cbore_d, h = lid_x_cbore_h + EPS, $fn = 32);
        }
        // Khe cáp USB-C cạnh +X (cắt hết gờ + mép tấm, suốt chiều cao)
        translate([cap_outline_off[0] + outer_dims[0]/2 - lid_x_lip_wall - 4,
                   -lid_x_usb_w/2, -lid_x_lip_h - EPS])
            cube([lid_x_lip_wall + 6, lid_x_usb_w, lid_x_lip_h + lid_x_t + 2*EPS]);
    }
}

top_lid_xiao();
