// ============================================================================
// glass_window_top_001.scad — Cửa sổ ép phẳng mặt nước (TÙY CHỌN)
// ----------------------------------------------------------------------------
// Tấm acrylic/lam kính Ø41.5×2 GÁC LÊN MÉP KHAY (z=12), bị vòng chặn của ống
// (z=12..14, ID40.5) đè giữ — GÁC GỜ, KHÔNG thả nổi (kính nặng hơn nước, chìm).
// Bật/tắt trong assembly bằng cờ show_window. MUA/CẮT — không in.
// ============================================================================
include <../constants.scad>

module glass_window_top() {
    color(col_acrylic)
        translate([0, 0, tray_depth])
            cylinder(d = tray_outer - 2.5, h = win_top_t, $fn = 96);
}

glass_window_top();
