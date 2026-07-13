// ============================================================================
// flow_tray_001.scad — Khay Macro-Flow (thiết kế MỚI 2026-07-07)
// ----------------------------------------------------------------------------
// MỤC TIÊU DUY NHẤT: mọi hạt RA HẾT, không đọng. KHÔNG chi tiết giữ hạt
// (khác khay cũ khay_dong_chay_001 còn lưới 0.8mm — đã bỏ).
//
// Hệ toạ độ chung: z=0 = SÀN khay (mặt trên đĩa acrylic + silicon), trục Z = trục quang.
//  - Thành ID40/OD44, z=0..12 (lọt lòng ống ID46 có khe; luồn từ ĐÁY vỏ lên).
//  - Cổng VÀO (−X): NGẠNH OD8 → HỘP LOE (plenum 22 rộng) → KHE KHUẾCH TÁN 20×3
//    SÁT ĐÁY (z=0..3): biến tia thành màng rộng quét mặt đáy, xóa 2 thùy tĩnh.
//  - Cổng RA (+X): ngạnh OD8/lòng Ø6 SÁT ĐÁY (lòng z=0..6) — flush được hạt CHÌM.
//    VÀO ↔ RA đối tâm 180°.
//  - Sàn = ĐĨA ACRYLIC Ø42×3 lắp TỪ DƯỚI vào hốc (bore Ø42.7), ép lên gờ 1mm
//    + silicon; giữ bằng VÒNG ÉP SNAP-FIT 3 tai (window_retainer.scad) cài vào
//    3 cửa sổ ở váy khay (tránh ±X). Mối nối Ø40 vê tròn silicon (fillet chống đọng).
//  - Mép tràn (weir) + van xả đáy: TÙY CHỌN — KHÔNG dựng ở bản này (mực nước giữ
//    bằng van bơm tự chặn khi tắt).
// ============================================================================
include <../constants.scad>

EPS = 0.05;
pocket_d   = tray_win_d + 2*win_clr;          // Ø42.7 hốc đĩa
z_skirt_bot = z_tray_bot;                      // −6.5
barb_len   = 8.0;                              // đoạn ngạnh thò ra để trùm ống
plenum_w   = 22.0;                             // hộp loe (lọt khe vỏ 24)
plenum_deep = 7.0;                             // sâu hộp loe theo X

// --- ngạnh ống (nằm ngang trục X), gốc tại mặt bích trong, hướng +X ---
module barb(len = barb_len) {
    rotate([0, 90, 0]) {
        cylinder(d = outlet_barb_od, h = len, $fn = 48);
        for (zz = [len - 2, len - 5])
            translate([0, 0, zz]) cylinder(d1 = outlet_barb_od + 1.4, d2 = outlet_barb_od - 1, h = 2, $fn = 48);
    }
}

module flow_tray() {
    color(col_plastic) difference() {
        union() {
            // Thân khay LIỀN 1 trụ (thành + gờ kê + váy hốc đĩa, z=−6.5..12)
            // — không xếp 2 trụ trùng mặt tại z=0 (gây non-manifold)
            translate([0, 0, z_skirt_bot])
                cylinder(d = tray_outer, h = tray_depth - z_skirt_bot, $fn = 120);
            // Hộp loe cổng VÀO (−X): XUYÊN HẲN qua thành cong (phần thừa bị lòng
            // khay cắt lại) — mọi mặt giao TRANSVERSAL, không tiếp tuyến/trùng phẳng
            // (nguồn non-manifold). Đáy −1 / nóc 6.5: có sàn & trần quanh khoang loe.
            translate([-tray_outer/2 - plenum_deep + 1, -plenum_w/2, -1])
                cube([plenum_deep + 1.5, plenum_w, 7.5]);
            // Ngạnh VÀO (−X) nối hộp loe (dài +1 chồng lấn vào hộp — tránh mặt trùng)
            translate([-tray_outer/2 - plenum_deep + 1 - barb_len, 0, port_z])
                barb(barb_len + 1);
            // Ngạnh RA (+X) trên thành
            translate([tray_outer/2 - 1, 0, port_z]) barb(barb_len + 3);
        }
        // Lòng khay (vùng nước Ø40)
        translate([0, 0, -EPS]) cylinder(d = tray_inner, h = tray_depth + 2*EPS, $fn = 120);
        // Hốc đĩa acrylic (từ dưới lên, chừa gờ kê 1mm)
        translate([0, 0, z_skirt_bot - EPS])
            cylinder(d = pocket_d, h = -z_skirt_bot - ledge_plate_t + EPS, $fn = 120);
        // Khoang chứa vòng ép dưới đĩa (cùng bore) — đã nằm trong hốc trên
        // Khe khuếch tán VÀO 20×3 sát đáy xuyên thành (−X)
        translate([-tray_outer/2 - 2, -inlet_slot_w/2, 0 - EPS])
            cube([tray_wall + 4, inlet_slot_w, inlet_slot_h + EPS]);
        // Khoang loe trong hộp: quạt từ lòng ngạnh Ø6 → khe 20×3.
        // Mặt cuối khoang (−20.6) nằm SÂU TRONG khối hộp+thành → giao transversal.
        hull() {
            translate([-tray_outer/2 - plenum_deep + 2, 0, port_z])
                rotate([0, 90, 0]) cylinder(d = outlet_bore, h = 1, $fn = 36);
            translate([-tray_outer/2 + 0.4, -inlet_slot_w/2, 0])
                cube([1, inlet_slot_w, inlet_slot_h]);
        }
        // Lòng ngạnh VÀO thông vào khoang loe (DỪNG trong hộp loe — không chạm
        // tiếp tuyến mặt trong thành cong, tránh non-manifold; nước đi tiếp qua quạt loe)
        translate([-tray_outer/2 - plenum_deep - barb_len, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = barb_len + 4, $fn = 36);
        // Lòng cổng RA Ø6 sát đáy (z=0..6) xuyên thành + ngạnh
        translate([tray_outer/2 - tray_wall - 1, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = tray_wall + barb_len + 6, $fn = 36);
        // 3 cửa sổ ngàm snap-fit ở váy (tránh ±X: đặt 90/210/330°)
        for (a = [90, 210, 330])
            rotate([0, 0, a])
                translate([tray_outer/2 - 1.5, -3, z_skirt_bot + 0.4])
                    cube([3, 6, 1.8]);
    }
}

flow_tray();

// --- Tham chiếu khi mở file lẻ: đĩa acrylic + mực nước (ghost) ---
%color(col_acrylic) translate([0, 0, -ledge_plate_t - 0.3 - tray_win_t])
    cylinder(d = tray_win_d, h = tray_win_t, $fn = 96);
%color(col_water) cylinder(d = tray_inner, h = water_depth, $fn = 96);
