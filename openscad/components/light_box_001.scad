// ============================================================================
// light_box_001.scad — Hộp đèn nền "LED XUÔI" (G1) — đoạn DƯỚI của vỏ liền (G2)
// ----------------------------------------------------------------------------
// Hệ toạ độ chung. Phạm vi: z = −61.5 (vành đáy = CHÂN ĐẾ) .. −8 (nối tube_body).
// Xếp lớp từ trên xuống (đúng thiet_ke_hop_den_nen.md):
//   z −8..−6.5  : vòng đỡ khay (thuộc tube_body)
//   z −12..−8   : MÀNG KHUẾCH TÁN xếp lớp 0–4mm (giấy can/mica mờ, Ø42) áp dưới vòng đỡ,
//                 đỡ bằng 3 CỘT từ vách — thêm/bớt lớp để chỉnh độ tán
//   z −20..−12  : BUỒNG TRỘN 8mm (khử hotspot nguồn điểm)
//   z = −20     : ĐẦU LED của module (hướng THẲNG LÊN — "LED xuôi", KHÔNG bounce)
//   z −38.75    : mặt VÁCH ĐỠ RỜI (G5): đĩa Ø45.4 thả vào lòng ống, 2 ỐC M3 XUYÊN
//                 NGANG thành ống tại ±Y (tránh 2 khe dọc ±X) vào mép vách;
//                 module xỏ qua LỖ GIỮA vách (tiết diện +0.4 — cắm ma sát)
//   z −57.5     : đáy module (nửa pin nằm dưới vách)
//   z −61.5     : vành đáy ống = chân đế; HỞ GIỮA để thao tác/thay pin từ dưới
// Mặt trong khoang đèn: TRẮNG mờ (sơn/dán trắng — thân in đen); 2 NÚT BỊT KHE in kèm
// bịt 2 khe dọc đoạn dưới (chống lọt sáng buồng trộn), chừa đoạn trên cho ngạnh+ống.
// ============================================================================
include <../constants.scad>

EPS = 0.05;
shelf_d = tube_id - 2*shelf_clr;   // Ø45.4

// ---------------- Thân đoạn dưới (in liền với tube_body thành 1 khối) ----------------
module light_box_body() {
    color(col_plastic_w) difference() {
        translate([0, 0, z_housing_bot])
            cylinder(d = tube_od, h = z_seat_bot - z_housing_bot, $fn = 120);
        // Lòng ống
        translate([0, 0, z_housing_bot - EPS])
            cylinder(d = tube_id, h = z_seat_bot - z_housing_bot + 2*EPS, $fn = 120);
        // 2 khe dọc tiếp nối (mở từ vành đáy lên hết đoạn này)
        for (p = [[1, slot_w_out], [-1, slot_w_in]])
            translate([p[0] * (tube_id/2 + tube_wall/2), 0, (z_seat_bot + z_housing_bot)/2])
                cube([tube_wall + 2, p[1], z_seat_bot - z_housing_bot + 2*EPS], center = true);
        // 2 lỗ M3 ngang ±Y bắt vách đỡ (tự-ren vào mép vách)
        for (sy = [1, -1])
            translate([0, sy * (tube_id/2 + tube_wall/2), shelf_screw_z])
                rotate([90, 0, 0])
                    cylinder(d = mount_hole_lid_d, h = tube_wall + 2, center = true, $fn = 24);
    }
}

// ---------------- Vách đỡ RỜI (G5) — chi tiết in riêng ----------------
module led_shelf() {
    color(col_plastic_w) {
        difference() {
            translate([0, 0, z_shelf_top - shelf_t])
                cylinder(d = shelf_d, h = shelf_t, $fn = 96);
            // Lỗ giữa xỏ module (fit ma sát +0.4)
            translate([-(led_mod_w + 2*shelf_hole_clr)/2, -(led_mod_d + 2*shelf_hole_clr)/2,
                       z_shelf_top - shelf_t - EPS])
                cube([led_mod_w + 2*shelf_hole_clr, led_mod_d + 2*shelf_hole_clr, shelf_t + 2*EPS]);
            // 2 lỗ mồi M3 ở mép (±Y) — ốc xuyên thành ống tự-ren vào đây
            for (sy = [1, -1])
                translate([0, sy * shelf_d/2, shelf_screw_z])
                    rotate([90, 0, 0])
                        cylinder(d = 2.5, h = 12, center = true, $fn = 24);
        }
        // 3 cột đỡ màng khuếch tán (lên tới z_diff_bot)
        for (a = [30, 150, 270])
            rotate([0, 0, a])
                translate([16, 0, z_shelf_top])
                    cylinder(d = 4, h = z_diff_bot - z_shelf_top, $fn = 24);
    }
}

// ---------------- Màng khuếch tán (mock — giấy can/mica mờ, MUA/CẮT) ----------------
module diffuser_stack(layers = 2, layer_t = 1.0) {
    color(col_diffuser)
        for (i = [0:layers-1])
            translate([0, 0, z_diff_top - (i + 1) * layer_t - i * 0.2])
                cylinder(d = bl_diff_d, h = layer_t, $fn = 96);
}

// ---------------- Nút bịt khe dọc (in riêng, cắm ma sát sau khi lắp) ----------------
// Bịt từ vành đáy tới z=−2 (chừa z −2..+7 cho ngạnh + ống); chặn lọt sáng buồng trộn.
module slot_plug(w = slot_w_out) {
    color(col_plastic)
        cube([tube_wall - 0.2, w - 2*tol, (z_housing_bot * -1) - 2 - 0.5]);
}

// ---------------- Xem lẻ ----------------
light_box_body();
led_shelf();
diffuser_stack();
// Module LED đặt đúng vị trí (ghost)
%translate([0, 0, z_led_tip]) rotate([0, 0, 90])
    translate([0, 0, 0]) {
        translate([-led_mod_w/2, -led_mod_d/2, -led_mod_h]) cube([led_mod_w, led_mod_d, led_mod_h]);
    }
