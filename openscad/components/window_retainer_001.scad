// ============================================================================
// window_retainer_001.scad — Đĩa acrylic đáy + vòng ép SNAP-FIT
// ----------------------------------------------------------------------------
// - acrylic_window(): đĩa acrylic TRONG Ø42×3 (MUA/CẮT — không in; mock tham chiếu).
// - window_retainer(): vòng ép IN 3D, luồn từ dưới vào hốc Ø42.7 của khay,
//   3 TAI NGÀM (90/210/330° — tránh cổng ±X) cài vào 3 cửa sổ ở váy khay,
//   ép đĩa lên gờ kê 1mm + lớp silicon hồ cá (chống rò, KHÔNG keo 502 — fogging).
//   Vít M2.5 bất khả thi hình học với OD khay 44 → snap-fit (README cho phép).
// Gốc cục bộ: mặt TRÊN vòng ép = z=0 (mặt tiếp đĩa); assembly đặt theo z_tray_bot.
// ============================================================================
include <../constants.scad>

EPS = 0.05;

module acrylic_window() {
    color(col_acrylic) cylinder(d = tray_win_d, h = tray_win_t, $fn = 96);
}

module window_retainer() {
    ring_od = tray_win_d + 2*win_clr - 0.3;  // Ø42.4 trượt trong hốc Ø42.7
    ring_id = 36.0;                          // không che cửa sổ sáng quá sâu
    tab_w   = 5.0;
    color(col_plastic) {
        difference() {
            translate([0, 0, -retainer_t]) cylinder(d = ring_od, h = retainer_t, $fn = 96);
            translate([0, 0, -retainer_t - EPS]) cylinder(d = ring_id, h = retainer_t + 2*EPS, $fn = 96);
            // 3 khe đàn hồi cạnh tai (cho vòng bóp vào khi luồn)
            for (a = [90, 210, 330])
                rotate([0, 0, a + 12])
                    translate([ring_od/2 - 2.6, -0.8, -retainer_t - EPS])
                        cube([3, 1.6, retainer_t + 2*EPS]);
        }
        // 3 tai ngàm (bướu ngoài, khớp cửa sổ 6×1.8 ở váy khay)
        for (a = [90, 210, 330])
            rotate([0, 0, a])
                translate([ring_od/2 - 0.6, -tab_w/2, -retainer_t + 0.3])
                    cube([1.6, tab_w, 1.5]);
    }
}

// Xem lẻ: vòng ép + đĩa (ghost) đặt đúng tương quan
window_retainer();
%translate([0, 0, 0.3]) acrylic_window();  // 0.3 = lớp silicon
