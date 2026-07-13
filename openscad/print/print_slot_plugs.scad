// print_slot_plugs.scad — 2 nút bịt khe dọc KIÊM CỘT ĐỠ KHAY (light_box_002).
// Chữ L: thân bịt khe (chống lọt sáng khoang đèn) + gờ ngang đỡ đáy váy khay
// tại z=−6.5 (thay vòng đỡ liền vỏ đã bỏ). Chân nút đứng cùng mặt bàn với đế.
// In NẰM: mặt ngoài thân úp xuống bàn, gờ đỡ thành gân nổi phía trên — không support.
// Nút hẹp = khe RA (+X, 12); nút rộng = khe VÀO (−X, 24).
include <../constants.scad>
use <../components/light_box_002.scad>

translate([0, 0, tube_wall - 0.2]) rotate([0, 90, 0]) slot_plug(slot_w_out);
translate([0, slot_w_out + 6, tube_wall - 0.2]) rotate([0, 90, 0]) slot_plug(slot_w_in);
