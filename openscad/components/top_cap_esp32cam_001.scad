// ============================================================================
// top_cap_esp32cam_001.scad — NẮP ADAPTER cho biến thể ESP32-CAM (CHI TIẾT IN)
// ----------------------------------------------------------------------------
// Thay cho base Matchboxscope khi dùng ESP32-CAM thay XIAO ESP32-S3.
// KHÔNG ảnh hưởng bản gốc — CÙNG giao diện bích: 4 lỗ M3 bước vuông 30×30,
// tâm = trục quang → tháo base XIAO ra, bắt nắp này vào là chạy.
//
// Kết cấu (dày 15, footprint = outline lid Matchboxscope 50.4×52):
//  - HỐC board 27.4×40.9 sâu 13 từ mặt trên: board camera úp xuống, LENS TRÙNG
//    TRỤC QUANG (hốc dịch −e32_lens_off theo Y để bù lens lệch tâm), pin header
//    chĩa lên CHÌM HẲN trong hốc (13 > 1.6 + 11).
//  - Sàn 2mm: lỗ vuông 10.4 xuyên sàn cho khối camera + lens thò xuống lỗ Ø24
//    của bích (lens tự vặn chỉnh nét — cự ly tới nước ~36mm thay vì 40).
//  - 4 lỗ tự-ren M3 Ø2.8 MÙ hai đầu, cùng trục (dưới sâu 6: vít bích từ dưới;
//    trên sâu 6: vít kẹp LID MATCHBOXSCOPE IN SẴN — lid 50.42×52×2, 4 lỗ Ø3.2
//    đúng pattern, đo trimesh — đậy hốc làm nắp kẹp/chắn bụi). Vách ngăn giữa 3mm.
//  - Khe luồn dây jumper ở thành +Y (rộng 16, từ z=8 lên mặt trên) — dán băng
//    đen khi chụp để kín sáng.
//  ⚠️ Lỗ M3 tại ±15 chỉ cách mép hốc 13.7 đúng 0.1mm → ren vít có thể sượt nhẹ
//    vào thành hốc tại 4 điểm — chấp nhận (board 27.0 vẫn lọt, dũa nhẹ nếu kẹt).
// Gốc cục bộ: trục quang = Z, mặt ĐÁY (áp bích ống) = z=0. Assembly nâng lên z=46.
// ============================================================================
include <../constants.scad>

EPS = 0.05;
LID_STL  = "../../base/Assembly_Matchboxscope_injectionmolded_xiao_IM_Matchboxscope_base_xiao_lid_10.stl";
LID_ZMIN = -34.03373;                 // đo trimesh 2026-07-08
outline_off = [0.82, 0.03];           // tâm outline lid lệch trục quang (như base)

module top_cap_esp32cam() {
    pocket_w = e32_pcb_w + 2*e32_clr; // 27.8
    pocket_l = e32_pcb_l + 2*e32_clr; // 41.3
    color(col_plastic) difference() {
        // Thân: rounded-rect footprint lid 50.4×52, r góc 8
        translate([outline_off[0], outline_off[1], 0])
            linear_extrude(cap_e32_t)
                hull() for (sx = [1,-1], sy = [1,-1])
                    translate([sx*(50.4/2 - 8), sy*(52/2 - 8)]) circle(r = 8, $fn = 48);
        // Hốc board (tâm dịch −lens_off theo Y để lens về trục quang)
        translate([-pocket_w/2, -pocket_l/2 - e32_lens_off, cap_e32_t - cap_e32_pocket])
            cube([pocket_w, pocket_l, cap_e32_pocket + EPS]);
        // Lỗ vuông xuyên sàn cho khối camera (tâm = trục quang)
        translate([-(e32_cam_blk + 2*e32_clr)/2, -(e32_cam_blk + 2*e32_clr)/2, -EPS])
            cube([e32_cam_blk + 2*e32_clr, e32_cam_blk + 2*e32_clr, 2 + 2*EPS]);
        // 4 lỗ tự-ren M3 mù ĐÁY (vít bích từ dưới lên)
        m3_mount_pattern()
            translate([0, 0, -EPS]) cylinder(d = mount_hole_base_d, h = cap_e32_screw + EPS, $fn = 32);
        // 4 lỗ tự-ren M3 mù ĐỈNH (vít kẹp lid từ trên xuống)
        m3_mount_pattern()
            translate([0, 0, cap_e32_t - cap_e32_screw]) cylinder(d = mount_hole_base_d, h = cap_e32_screw + EPS, $fn = 32);
        // Khe luồn dây +Y
        translate([-8, 12, 8]) cube([16, 20, cap_e32_t - 8 + EPS]);
    }
}

// Lid Matchboxscope IN SẴN làm nắp kẹp (mock import — không in lại)
module lid_ref() {
    color(col_plastic)
        translate([-mount_center[0], -mount_center[1], cap_e32_t - LID_ZMIN])
            import(LID_STL, convexity = 4);
}

// Xem lẻ: nắp + lid kẹp (ghost); board mock xem trong assembly (cam_variant=1)
top_cap_esp32cam();
%lid_ref();
