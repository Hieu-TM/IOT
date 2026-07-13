// ============================================================================
// light_box_002.scad — Hộp đèn nền "LED XUÔI" (G1) — đoạn DƯỚI của vỏ liền (G2)
// ----------------------------------------------------------------------------
// KHÁC _001: NÚT BỊT KHE nâng cấp thành CỘT ĐỠ KHAY chữ L (thay vòng đỡ liền vỏ
// của tube_body_001 — vòng đó chặn đường luồn khay OD44 từ đáy, đã bỏ ở _002):
//  - Thân nút trượt trong khe dọc ±X như cũ (bịt sáng), kéo dài từ vành đáy
//    (z=−61.5, chân đứng CÙNG MẶT BÀN với đế) lên z=−1.2 (chừa 0.2 dưới ngạnh/hộp loe).
//  - GỜ NGANG thò vào lòng ống (sâu 1.7 → r21.4): mặt trên tại z=−6.5 ĐỠ ĐÁY VÁY
//    KHAY (vành r21.35..22). Không lấn cột sáng Ø40 (r20); màng Ø42 (r21) lọt qua.
//  - Tải: khay + nước (~40g) → 2 gờ ±X → thân nút → mặt bàn. Cắm ma sát; có thể
//    chấm keo cố định vĩnh viễn (nút rẻ, in lại dễ).
// THỨ TỰ LẮP TỪ ĐÁY (bắt buộc): (1) khay luồn lên (ngạnh theo khe dọc, giữ tay);
// (2) 2 nút bịt trượt vào khe từ dưới → gờ đỡ khay, thả tay; (3) vách LED + module
// + màng khuếch tán (đặt sẵn trên 3 cột) đưa lên, bắt 2 ốc M3 ±Y; xong.
//
// Hệ toạ độ chung. Phạm vi: z = −61.5 (vành đáy = CHÂN ĐẾ) .. −8 (nối tube_body).
// Xếp lớp từ trên xuống:
//   z −6.5      : đáy khay tì lên GỜ 2 nút bịt (vòng đỡ liền vỏ ĐÃ BỎ)
//   z −12..−8   : MÀNG KHUẾCH TÁN xếp lớp 0–4mm (giấy can/mica mờ, Ø42) ĐẶT TRÊN
//                 3 CỘT từ vách — thêm/bớt lớp để chỉnh độ tán
//   z −20..−12  : BUỒNG TRỘN 8mm (khử hotspot nguồn điểm)
//   z = −20     : ĐẦU LED của module (hướng THẲNG LÊN — "LED xuôi", KHÔNG bounce)
//   z −38.75    : mặt VÁCH ĐỠ RỜI (G5): đĩa Ø45.4 thả vào lòng ống, 2 ỐC M3 XUYÊN
//                 NGANG thành ống tại ±Y (tránh 2 khe dọc ±X) vào mép vách;
//                 module xỏ qua LỖ GIỮA vách (tiết diện +0.4 — cắm ma sát)
//   z −57.5     : đáy module (nửa pin nằm dưới vách)
//   z −61.5     : vành đáy ống = chân đế; HỞ GIỮA để thao tác/thay pin từ dưới
// Mặt trong khoang đèn: TRẮNG mờ (sơn/dán trắng — thân in đen).
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

// ---------------- Nút bịt khe KIÊM CỘT ĐỠ KHAY (in riêng, luồn từ đáy SAU khay) ---
// Gốc cục bộ: x=0 = mặt TRONG thân nút (phía lòng ống, +x hướng ra ngoài),
// z=0 = chân nút (= vành đáy vỏ z_housing_bot khi lắp). Chữ L: thân trong khe
// + gờ đỡ thò vào lòng ống, mặt trên gờ = z_tray_bot (đáy váy khay tì lên).
// Bịt sáng: thân che khe từ vành đáy tới z=−1.2 — kín toàn bộ khoang đèn (<−8).
module slot_plug(w = slot_w_out) {
    plug_h  = plug_top_z - z_housing_bot;        // 60.3: chân → sát dưới ngạnh
    tab_top = z_tray_bot - z_housing_bot;        // 55.0: mặt trên gờ đỡ (cục bộ)
    color(col_plastic) union() {
        // Thân trượt trong khe (dày = thành − 0.2)
        cube([tube_wall - 0.2, w - 2*tol, plug_h]);
        // Gờ đỡ khay: thò vào lòng ống plug_tab_d, chồng lấn 1mm vào thân
        // (giao dương — tránh mặt trùng gây non-manifold)
        translate([-plug_tab_d, 0, tab_top - plug_tab_h])
            cube([plug_tab_d + 1, w - 2*tol, plug_tab_h]);
    }
}

// ---------------- Xem lẻ ----------------
light_box_body();
led_shelf();
diffuser_stack();
// 2 nút bịt kiêm cột đỡ đặt đúng vị trí (+X thật, −X mirror)
translate([tube_id/2 + 0.1, -(slot_w_out - 2*tol)/2, z_housing_bot]) slot_plug(slot_w_out);
mirror([1, 0, 0])
    translate([tube_id/2 + 0.1, -(slot_w_in - 2*tol)/2, z_housing_bot]) slot_plug(slot_w_in);
// Module LED đặt đúng vị trí (ghost)
%translate([0, 0, z_led_tip]) rotate([0, 0, 90])
    translate([0, 0, 0]) {
        translate([-led_mod_w/2, -led_mod_d/2, -led_mod_h]) cube([led_mod_w, led_mod_d, led_mod_h]);
    }
