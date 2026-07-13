// ============================================================================
// led_module_001.scad — Mock module LED móc khoá (MUA SẴN — không in)
// ----------------------------------------------------------------------------
// Cả module = "1 bóng" (1 đơn vị sáng): 37.5 × 10 × 16 mm, LED ở ĐẦU MŨI,
// 3 pin cúc trong thân. Dựng ĐỨNG, đầu LED hướng LÊN (G1 "LED xuôi").
// Cắm-tháo bằng ma sát qua lỗ vách đỡ (không keo).
// Gốc cục bộ: TÂM ĐẦU LED (đỉnh module) = [0,0,0], thân xuống −Z.
// ============================================================================
include <../constants.scad>

module led_module() {
    // Thân module (hộp), đỉnh tại z=0
    color(col_led) translate([-led_mod_w/2, -led_mod_d/2, -led_mod_h])
        cube([led_mod_w, led_mod_d, led_mod_h - led_head_h]);
    // Đầu mũi chứa LED (thu nhỏ nhẹ)
    color([1, 1, 0.85]) translate([-led_mod_w/2 + 1, -led_mod_d/2 + 1, -led_head_h])
        cube([led_mod_w - 2, led_mod_d - 2, led_head_h]);
    // Chấm LED phát sáng trên đỉnh
    color([1, 1, 0.6]) translate([0, 0, -0.5]) cylinder(d = 5, h = 0.6, $fn = 32);
    // Gợi khối 3 pin cúc ở nửa dưới
    color(col_metal) translate([0, 0, -led_mod_h + 4])
        for (i = [0:2]) translate([0, 0, i * 3.4]) cylinder(d = led_mod_d - 4, h = 3, $fn = 32);
}

led_module();
