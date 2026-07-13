// ============================================================================
// esp32cam_001.scad — Board ESP32-CAM AI-Thinker (MOCK THAM CHIẾU — không in)
// ----------------------------------------------------------------------------
// Biến thể thay cho XIAO ESP32-S3: dùng với nắp adapter top_cap_esp32cam.
// Tư thế LẮP: camera úp XUỐNG (−Z) → 2 hàng pin header chĩa LÊN (+Z).
// GỐC CỤC BỘ: tâm mặt dưới barrel LENS = [0,0,0] (giống convention xiao mock).
// Lens OV2640 lệch tâm PCB e32_lens_off dọc trục dài — ⚠️ đo lại board thật.
// Lens barrel VẶN CHỈNH NÉT được (khác lens XIAO cố định — chỉnh về ~36mm).
// ============================================================================
include <../constants.scad>

module esp32cam() {
    // Barrel lens (nhìn xuống −Z, mặt dưới tại z=0)
    color(col_metal) cylinder(d = e32_lens_d, h = 3, $fn = 48);
    // Khối module camera
    color([0.15, 0.15, 0.15])
        translate([-e32_cam_blk/2, -e32_cam_blk/2, 3]) cube([e32_cam_blk, e32_cam_blk, 3]);
    // PCB (tâm PCB lệch −e32_lens_off theo Y so với lens)
    color(col_pcb)
        translate([-e32_pcb_w/2, -e32_pcb_l/2 - e32_lens_off, 6])
            cube([e32_pcb_w, e32_pcb_l, e32_pcb_t]);
    // 2 hàng pin header 8 chân chĩa LÊN dọc 2 cạnh dài
    color(col_metal)
        for (sx = [1, -1])
            translate([sx * (e32_pcb_w/2 - 1.27) - 1.27, -17.15, 6 + e32_pcb_t])
                cube([2.54, 20.3, e32_hdr_h]);
    // Gợi khe microSD ở đầu +Y
    color(col_metal)
        translate([-7, e32_pcb_l/2 - e32_lens_off - 6, 6 + e32_pcb_t])
            cube([14, 5, 2]);
}

esp32cam();
