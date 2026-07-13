// ============================================================================
// xiao_esp32s3_001.scad — Board XIAO ESP32-S3 Sense (MOCK THAM CHIẾU)
// ----------------------------------------------------------------------------
// Chỉ để bố trí lắp/hiển thị trong assembly — KHÔNG in, KHÔNG chi tiết linh kiện.
// Cảm biến OV3660 (KHÔNG phải OV2640 — memory camera-sensor).
//
// GỐC CỤC BỘ: tâm mặt dưới ỐNG KÍNH camera = [0,0,0], camera nhìn xuống −Z.
// PCB nằm phía trên (+Z).
// ============================================================================
include <../constants.scad>

module xiao_esp32s3() {
    lens_h    = 2.0;   // phần ống kính nhô
    cam_blk   = 8.5;   // khối module camera vuông
    cam_blk_h = 3.0;

    // Ống kính (nhìn xuống −Z, mặt dưới tại z=0)
    color(col_metal) cylinder(d = xiao_cam_d, h = lens_h, $fn = 48);
    // Khối module camera
    color([0.15, 0.15, 0.15])
        translate([-cam_blk/2, -cam_blk/2, lens_h])
            cube([cam_blk, cam_blk, cam_blk_h]);
    // PCB (camera ~giữa board; expansion board Sense — mock phẳng)
    color(col_pcb)
        translate([-xiao_l/2, -xiao_w/2, lens_h + cam_blk_h])
            cube([xiao_l, xiao_w, xiao_h]);
    // Khối USB-C gợi vị trí (đầu +X)
    color(col_metal)
        translate([xiao_l/2 - 7, -4.5, lens_h + cam_blk_h + xiao_h])
            cube([8, 9, 3]);
}

xiao_esp32s3();
