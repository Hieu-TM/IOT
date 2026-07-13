// ============================================================================
// tube_body_001.scad — Thân ống quang học (đoạn TRÊN của vỏ liền — G2)
// ----------------------------------------------------------------------------
// Dựng TRỰC TIẾP trong hệ toạ độ chung (trục Z = trục quang, z=0 = sàn khay).
// Phạm vi đoạn này: z = −8 (đáy vòng đỡ khay) .. 46 (mặt bích đỉnh).
// light_box.scad nối tiếp xuống dưới từ z=−8 (cùng OD50 → 1 khối in liền).
//
// Thành phần:
//  - Ống thẳng OD50/ID46 (KHÔNG phình cốc), nội thất ĐEN NHÁM (sơn/filament đen).
//  - Bích đỉnh z=43..46: đĩa đặc lỗ giữa Ø24 + 4 lỗ M3 Ø3.2 clearance (bước 30×30,
//    tâm = trục quang) — vít bắt NGƯỢC LÊN lỗ Ø2.8 tự-ren của base Matchboxscope.
//    Lỗ Ø24 không vignette: nón FOV chỉ cần r≈1.5+đồng tử tại z=43.
//  - Vòng chặn khay z=12..14 (ID40.5): khay luồn từ DƯỚI tì lên đây;
//    kiêm CHẮN SÁNG khe hở khay↔lòng ống (buồng tối).
//  - Vòng đỡ khay z=−8..−6.5 (ID40.5): đáy cụm khay đặt lên; màng khuếch tán
//    áp mặt dưới vòng này.
//  - 2 KHE DỌC ±X (rộng 12, lên tới z=+7): đường thò ngạnh ống nước của khay
//    khi luồn từ đáy + đường dẫn ống ra ngoài. (Ốc vách LED nằm ±Y nên không đụng.)
// ============================================================================
include <../constants.scad>

EPS = 0.05;

module tube_body() {
    color(col_plastic) difference() {
        union() {
            // Ống chính (đoạn trên)
            translate([0, 0, z_seat_bot])
                cylinder(d = tube_od, h = z_tube_top - z_seat_bot, $fn = 120);
        }
        // Lòng ống (khoét tới dưới bích)
        translate([0, 0, z_seat_bot - EPS])
            cylinder(d = tube_id, h = (z_tube_top - flange_t) - z_seat_bot + EPS, $fn = 120);
        // Lỗ giữa bích (đường quang)
        translate([0, 0, z_tube_top - flange_t - EPS])
            cylinder(d = flange_hole_d, h = flange_t + 2*EPS, $fn = 96);
        // 4 lỗ M3 clearance xuyên bích
        translate([0, 0, z_tube_top - flange_t - EPS])
            m3_mount_pattern()
                cylinder(d = mount_hole_lid_d, h = flange_t + 2*EPS, $fn = 32);
        // 2 khe dọc (mở hết đáy đoạn này; light_box cắt tiếp phần dưới)
        // +X (RA) rộng 12; −X (VÀO) rộng 24 cho hộp loe khe khuếch tán
        for (p = [[1, slot_w_out], [-1, slot_w_in]])
            translate([p[0] * (tube_id/2 + tube_wall/2), 0, (slot_top + z_seat_bot - EPS)/2])
                cube([tube_wall + 2, p[1], slot_top - z_seat_bot + EPS], center = true);
    }
    // Vòng chặn khay (z=12..14) — chắn sáng + cữ trên của khay
    color(col_plastic)
        translate([0, 0, z_stop_lo])
            difference() {
                cylinder(d = tube_id + EPS, h = stop_ring_t, $fn = 120);
                translate([0, 0, -EPS]) cylinder(d = stop_ring_id, h = stop_ring_t + 2*EPS, $fn = 120);
            }
    // Vòng đỡ khay (z=−8..−6.5) — khay tì lên, màng khuếch tán áp dưới
    color(col_plastic)
        translate([0, 0, z_seat_bot])
            difference() {
                cylinder(d = tube_id + EPS, h = seat_ring_t, $fn = 120);
                translate([0, 0, -EPS]) cylinder(d = seat_ring_id, h = seat_ring_t + 2*EPS, $fn = 120);
            }
}

tube_body();

// --- Que kiểm trực quan (chỉ khi mở file lẻ): nón FOV không chạm thành ---
%fov_cone();
