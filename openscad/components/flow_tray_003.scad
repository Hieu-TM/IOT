// ============================================================================
// flow_tray_003.scad — Khay Macro-Flow CHỐNG SÓNG (2026-07-23)
// ----------------------------------------------------------------------------
// KHÁC _002: thêm 3 chi tiết chống sóng, KHÔNG đổi kích thước gốc của khay.
//   (1) Cửa vào ĐỤC LỖ: khe liền 20×3 → 4 cửa sổ 3.5×3 ngăn bởi 3 gân 1.2
//       (chia tia lớn thành tia nhỏ, tiêu tán động năng nhanh hơn).
//   (2) VÁCH CONG r=16.4, cao 7 (>mực nước), quét 90° đối diện cổng vào
//       (chắn đường đi thẳng vào→ra, ép nước đi vòng qua hành lang 3.0mm).
//   (3) MIỆNG LOE (bellmouth) nhô vào lòng khay tại cổng ra, bo R=3
//       (chống dồn ứ + dội sóng ngược tại miệng lỗ xả).
// Nguồn số liệu + 4 chỗ lệch có chủ ý so với tài liệu: constants.scad §CHỐNG SÓNG
// và docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md
// Lệch thứ 5 (file-local): khoang loe sâu 1.0 (chứ không 1.4), bảo toàn 3 gân.
//
// ⚠️ KIẾN TRÚC 2 TẦNG UNION — bắt buộc, không gộp được:
//   flow_tray() = tray_shell()  ∪  tray_internals()
//   Vách cong và miệng loe nằm TRONG lòng Ø40. Nếu union chúng vào khối thân
//   TRƯỚC khi khoét lòng Ø40 thì chính lệnh khoét đó sẽ xóa sạch chúng.
//   Vì vậy tray_shell() tự khoét xong lòng, RỒI mới union phần internals.
//
// Hệ toạ độ: z=0 = SÀN khay (mặt trên đĩa acrylic), trục Z = trục quang.
// ============================================================================
include <../constants.scad>

EPS = 0.05;
pocket_d    = tray_win_d + 2*win_clr;   // Ø42.7 hốc đĩa
z_skirt_bot = z_tray_bot;               // −6.5
barb_len    = 8.0;                      // đoạn ngạnh thò ra để trùm ống
plenum_w    = 22.0;                     // hộp loe (lọt khe vỏ 24)
plenum_deep = 7.0;                      // sâu hộp loe theo X

// --- ngạnh ống (nằm ngang trục X), gốc tại mặt bích trong, hướng +X ---
module barb(len = barb_len) {
    rotate([0, 90, 0]) {
        cylinder(d = outlet_barb_od, h = len, $fn = 48);
        for (zz = [len - 2, len - 5])
            translate([0, 0, zz])
                cylinder(d1 = outlet_barb_od + 1.4, d2 = outlet_barb_od - 1, h = 2, $fn = 48);
    }
}

// --- (1) Cửa vào ĐỤC LỖ: N cửa sổ ngăn bởi gân, canh giữa theo Y ---
// Gân = phần THÀNH còn lại giữa 2 cửa sổ (không phải chi tiết nhô ra lòng khay)
// → không va chạm vách cong, không cần support khi in.
module inlet_windows() {
    for (i = [0 : inlet_n_gap - 1])
        translate([-tray_outer/2 - 2,
                   -inlet_span/2 + i * inlet_pitch,
                   -EPS])
            cube([tray_wall + 4, inlet_gap_w, inlet_slot_h + EPS]);
}

// --- Thân khay (kế thừa _002, chỉ đổi cụm cửa vào) ---
module tray_shell() {
    difference() {
        union() {
            // Thân khay LIỀN 1 trụ (thành + gờ kê + váy hốc đĩa, z=−6.5..12)
            translate([0, 0, z_skirt_bot])
                cylinder(d = tray_outer, h = tray_depth - z_skirt_bot, $fn = 120);
            // Hộp loe cổng VÀO (−X): xuyên hẳn qua thành cong (phần thừa bị lòng
            // khay cắt lại) — mọi mặt giao TRANSVERSAL, tránh non-manifold.
            translate([-tray_outer/2 - plenum_deep + 1, -plenum_w/2, -1])
                cube([plenum_deep + 1.5, plenum_w, 7.5]);
            // Ngạnh VÀO (−X) nối hộp loe
            translate([-tray_outer/2 - plenum_deep + 1 - barb_len, 0, port_z])
                barb(barb_len + 1);
            // Ngạnh RA (+X) trên thành
            translate([tray_outer/2 - 1, 0, port_z]) barb(barb_len + 3);
        }
        // Lòng khay Ø40 khoét XUYÊN SUỐT (đáy mở — sửa lỗi in của _001)
        translate([0, 0, z_skirt_bot - EPS])
            cylinder(d = tray_inner, h = tray_depth - z_skirt_bot + 2*EPS, $fn = 120);
        // Hốc đĩa acrylic (từ dưới lên, chừa gờ kê 1mm)
        translate([0, 0, z_skirt_bot - EPS])
            cylinder(d = pocket_d, h = -z_skirt_bot - ledge_plate_t + EPS, $fn = 120);
        // (1) Cửa vào đục lỗ — THAY khe liền 20×3 của _002
        inlet_windows();
        // Khoang loe trong hộp: quạt từ lòng ngạnh Ø6 → bề rộng cụm cửa sổ.
        // ⚠️ Mặt cuối khoang DỪNG tại x=−22.2 (0.2mm chưa tới mặt ngoài thành r=22):
        //   - không tràn tới x=−20 (mặt trong thành), nếu tràn sẽ ăn mất 3 gân;
        //   - không dừng đúng x=−22 (tiếp tuyến mặt trụ ngoài → non-manifold).
        //   Dòng chảy vẫn liên tục: khoang này giao nhau hoàn toàn với vùng X của
        //   inlet_windows() (x −24 tới −18), nên 2 khoang dùng chung thể tích.
        hull() {
            translate([-tray_outer/2 - plenum_deep + 2, 0, port_z])
                rotate([0, 90, 0]) cylinder(d = outlet_bore, h = 1, $fn = 36);
            translate([-tray_outer/2 - 1.2, -inlet_slot_w/2, 0])
                cube([1.0, inlet_slot_w, inlet_slot_h]);
        }
        // Lòng ngạnh VÀO thông vào khoang loe (dừng trong hộp loe)
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

// --- (2) VÁCH CONG tiêu năng ---
// Hàng rào cung tròn đặt đối diện cổng vào: chắn tia thẳng, ép nước đi VÒNG qua
// hành lang rộng baffle_corridor (=3.0mm) ở 2 đầu mút.
// Kín đáy (không hở chân) để hạt không chui vào kẹt phía sau; 2 đầu mút bo bán
// nguyệt r=baffle_t/2 để hạt trượt qua không vướng góc sắc.
module arc_baffle() {
    r_in  = baffle_r_mid - baffle_t/2;
    r_out = baffle_r_mid + baffle_t/2;
    union() {
        // Thân cung: vành khuyên ∩ nêm góc
        intersection() {
            difference() {
                cylinder(r = r_out, h = baffle_h, $fn = 160);
                translate([0, 0, -EPS])
                    cylinder(r = r_in, h = baffle_h + 2*EPS, $fn = 160);
            }
            // Nêm quét baffle_angle°, canh giữa tại 180° (hướng cổng vào −X)
            rotate([0, 0, 180 - baffle_angle/2])
                linear_extrude(height = baffle_h + 2*EPS)
                    polygon(points = concat(
                        [[0, 0]],
                        [for (i = [0 : 24])
                            let (a = i * baffle_angle / 24)
                            [tray_outer * cos(a), tray_outer * sin(a)]]
                    ));
        }
        // Bo 2 đầu mút (bán nguyệt r = baffle_t/2 — tối đa khả thi trên vách 1.2mm)
        // ⚠️ Đường kính nắp PHẢI = baffle_t (đúng bằng bề dày vách): tâm nắp đặt tại
        // baffle_r_mid nên mép ngoài nắp trùng đúng mặt ngoài cung (r_out) — đây là
        // điều giữ hành lang baffle_corridor đúng bằng giá trị đã assert ở constants.
        // Hardcode một số khác baffle_t ở đây sẽ ăn lấn hành lang MÀ KHÔNG CÓ assert
        // nào bắt được (baffle_corridor chỉ tính từ baffle_r_mid/baffle_t, không đọc
        // giá trị thực dùng ở dòng dưới).
        for (s = [-1, 1])
            rotate([0, 0, 180 + s * baffle_angle/2])
                translate([baffle_r_mid, 0, 0])
                    cylinder(d = baffle_t, h = baffle_h, $fn = 24);
    }
}

// --- (3) MIỆNG LOE (bellmouth) tại cổng RA ---
// Biên dạng: cung 1/4 đường tròn bán kính bell_fillet_r, tiếp tuyến RADIAL tại
// miệng loe và tiếp tuyến DỌC TRỤC tại cổ → dòng lướt mượt vào lòng ống, không
// bị bóp nghẹt ở mép sắc (hệ số tổn thất K: ~0.5 → <0.05).
// Trục cục bộ +Z: miệng loe (rộng Ø12) tại z=0, cổ (Ø6) tại z=bell_fillet_r.
function bell_r(a) = outlet_bore/2 + bell_fillet_r - bell_fillet_r * sin(a);
function bell_z(a) = bell_fillet_r - bell_fillet_r * cos(a);

// Vỏ ngoài loa kèn (đặc). Kéo dài thêm 1mm quá cổ để CHỌC vào thành khay
// (giao transversal, tránh mặt tiếp tuyến gây non-manifold khi union).
module bell_outer() {
    rotate_extrude($fn = 96)
        polygon(points = concat(
            [[0, 0]],
            [for (i = [0 : bell_steps]) let (a = i * 90 / bell_steps)
                [bell_r(a) + bell_wall, bell_z(a)]],
            [[bell_r(90) + bell_wall, bell_fillet_r + 1.0],
             [0, bell_fillet_r + 1.0]]
        ));
}

// Lòng loa kèn (phần bị khoét). Kéo dài quá cổ để nối liền lòng ngạnh Ø6.
module bell_void() {
    rotate_extrude($fn = 96)
        polygon(points = concat(
            [[0, 0]],
            [for (i = [0 : bell_steps]) let (a = i * 90 / bell_steps)
                [bell_r(a), bell_z(a)]],
            [[outlet_bore/2, bell_fillet_r + 2.0],
             [0, bell_fillet_r + 2.0]]
        ));
}

// Cụm loa kèn đã đặt đúng vị trí + CẮT PHẲNG tại sàn z=0.
// Cắt sàn là ĐÚNG về vật lý: loa kèn hút sát sàn thì chính mặt sàn đóng vai trò
// thành dưới (giống bellmouth đặt sát đáy bể hút của bơm công nghiệp), đồng thời
// tránh loe thò xuống dưới z=0 (vùng hốc đĩa acrylic).
module bellmouth_boss() {
    intersection() {
        difference() {
            translate([tray_inner/2 - bell_fillet_r, 0, port_z])
                rotate([0, 90, 0]) bell_outer();
            translate([tray_inner/2 - bell_fillet_r, 0, port_z])
                rotate([0, 90, 0]) bell_void();
        }
        translate([-tray_outer, -tray_outer, 0])
            cube([2*tray_outer, 2*tray_outer, tray_depth]);
    }
}

// --- Chi tiết NẰM TRONG lòng Ø40 — phải union SAU khi tray_shell() đã khoét lòng ---
module tray_internals() {
    arc_baffle();
    bellmouth_boss();
}

module flow_tray() {
    color(col_plastic) union() {
        tray_shell();
        tray_internals();
    }
}

flow_tray();

// --- Tham chiếu khi mở file lẻ: đĩa acrylic + mực nước (ghost) ---
%color(col_acrylic) translate([0, 0, -ledge_plate_t - 0.3 - tray_win_t])
    cylinder(d = tray_win_d, h = tray_win_t, $fn = 96);
%color(col_water) cylinder(d = tray_inner, h = water_depth, $fn = 96);
