// print_led_shelf.scad — Vách đỡ RỜI module LED (G5) + 3 cột đỡ màng (1 chi tiết in).
// In: mặt vách xuống bàn, cột hướng lên (không support). Lỗ giữa +0.4 cắm ma sát.
include <../constants.scad>
use <../components/light_box_002.scad>

// Hạ về z=0 để in (mặt dưới vách chạm bàn)
translate([0, 0, -(z_shelf_top - shelf_t)]) led_shelf();
