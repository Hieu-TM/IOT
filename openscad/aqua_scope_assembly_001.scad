// ============================================================================
// aqua_scope_assembly_001.scad — LẮP GHÉP TỔNG Aqua Scope
// ----------------------------------------------------------------------------
// Hệ toạ độ chung: z=0 = sàn khay, trục Z = trục quang, ống kính tại z=46.
// Chồng từ trên xuống: base Matchboxscope (nắp, IN SẴN) → thân ống quang học
// → khay Macro-Flow (+ đĩa acrylic + vòng ép snap-fit) → hộp đèn LED xuôi
// (vách rời + module + màng khuếch tán) → vành đáy = chân đế.
// Trạm bơm RS365 TÁCH RỜI (cách rung), nối bằng ống silicone ID8.
//
// CỜ ĐIỀU KHIỂN:
//   explode          : 0 = lắp kín; >0 = tách rời theo Z (thử 18)
//   show_pump        : hiện trạm bơm + ống + lưới lọc thô
//   show_electronics : hiện board XIAO trong nắp
//   show_window      : hiện cửa sổ ép phẳng mặt nước (tùy chọn)
//   show_water       : hiện khối nước 6mm (ghost)
//   show_fov         : hiện nón FOV kiểm vignette (ghost)
// ============================================================================
include <constants.scad>
use <components/xiao_esp32s3_001.scad>
use <components/top_cap_004.scad>  // _004: khoan thông cả 4 lỗ M3 (+trám Ø8 di sản +3 lỗ Ø4 ngoài)
use <components/top_lid_xiao_001.scad>  // nắp đậy trên cùng baseline XIAO
use <components/top_cap_esp32cam_001.scad>  // biến thể ESP32-CAM (cam_variant=1)
use <components/esp32cam_001.scad>
use <components/tube_body_002.scad>   // _002: bỏ vòng đỡ khay (chặn đường luồn từ đáy)
use <components/flow_tray_002.scad>   // _002: đáy khay mở (hết đĩa đặc 1mm bít đáy)
use <components/window_retainer_001.scad>
use <components/glass_window_top_001.scad>
use <components/light_box_002.scad>   // _002: nút bịt khe kiêm cột đỡ khay chữ L
use <components/led_module_001.scad>
use <components/accessories_001.scad>

explode          = 0;      // 0 = lắp kín
cam_variant      = 0;      // 0 = XIAO ESP32-S3 + base Matchboxscope (baseline)
                           // 1 = ESP32-CAM + nắp adapter in + lid Matchboxscope kẹp trên
show_pump        = true;
show_electronics = true;
show_window      = false;  // cửa sổ trên: tùy chọn
show_water       = true;
show_fov         = false;
show_top_lid     = true;   // nắp đậy trên cùng (baseline XIAO)

e = explode;

// ---------------- Khối quang học ----------------
if (cam_variant == 0) {
    // Baseline: nắp = base in sẵn + XIAO (tách LÊN khi explode)
    translate([0, 0, z_tube_top + 2.4*e]) top_cap();
    if (show_electronics)
        translate([0, 0, z_lens + 1 + 3.2*e]) xiao_esp32s3();
    // Nắp đậy trên cùng (ngồi trên mặt trên base = z_tube_top + cap_h)
    if (show_top_lid)
        translate([0, 0, z_tube_top + cap_h + 5.0*e]) top_lid_xiao();
} else {
    // Biến thể: nắp adapter in + ESP32-CAM úp xuống + lid Matchboxscope kẹp trên
    translate([0, 0, z_tube_top + 2.4*e]) top_cap_esp32cam();
    translate([0, 0, z_tube_top + 3.4*e]) lid_ref();
    if (show_electronics)
        translate([0, 0, 42 + 3.0*e]) esp32cam();  // lens z=42..45 xuyên sàn + lỗ bích Ø24
}

// Vỏ liền (tube_body + light_box_body = 1 KHỐI IN)
tube_body();
light_box_body();

// Khay + cửa sổ đáy + vòng ép (tách XUỐNG khi explode — lắp từ đáy;
// offset lớn để vượt ra khỏi lòng vỏ cao ~108mm)
translate([0, 0, -4.2*e]) flow_tray();
translate([0, 0, -(ledge_plate_t + 0.3 + tray_win_t) - 5.0*e]) acrylic_window();
translate([0, 0, -(ledge_plate_t + 0.3 + tray_win_t) - 5.6*e]) window_retainer();
if (show_window) translate([0, 0, 1.2*e]) glass_window_top();
if (show_water && e == 0)
    %color(col_water) cylinder(d = tray_inner, h = water_depth, $fn = 96);

// Hộp đèn: vách rời + module LED + màng khuếch tán (tách XUỐNG)
translate([0, 0, -7.6*e]) led_shelf();
translate([0, 0, z_led_tip - 8.4*e]) led_module();
translate([0, 0, -6.6*e]) diffuser_stack();

// 2 nút bịt khe dọc KIÊM CỘT ĐỠ KHAY (luồn từ đáy SAU khay; gờ đỡ đáy váy khay
// tại z=−6.5, chân đứng cùng mặt bàn với đế; tách NGANG ±X khi explode)
translate([1.2*e, 0, 0])
    translate([tube_id/2 + 0.1, -(slot_w_out - 2*tol)/2, z_housing_bot])
        slot_plug(slot_w_out);
mirror([1, 0, 0]) translate([1.2*e, 0, 0])
    translate([tube_id/2 + 0.1, -(slot_w_in - 2*tol)/2, z_housing_bot])
        slot_plug(slot_w_in);

// Nón FOV kiểm vignette
if (show_fov) %fov_cone();

// ---------------- Trạm bơm tách rời + đường ống ----------------
if (show_pump) {
    // Bơm đặt trên mặt bàn (z = vành đáy vỏ), lệch +X, cách xa chống rung
    translate([120 + 1.5*e, 0, z_housing_bot])
        rotate([0, 0, 180]) pump_rs365();
    // Ống mềm chỉ vẽ khi LẮP KÍN (explode thì ẩn — chi tiết mềm không "tách")
    if (e == 0) {
        // Ống RA: từ ngạnh khay (+X, z=3) tới bơm (2 đoạn gấp khúc đơn giản)
        translate([33, 0, port_z]) rotate([0, 90, 0]) silicone_tube(30);
        translate([63, 0, port_z]) rotate([0, 130, 0]) silicone_tube(48);
        // Ống VÀO từ nguồn: lưới lọc thô + đoạn ống tới ngạnh khay (−X)
        translate([-62, 0, port_z]) rotate([0, 90, 0]) silicone_tube(26);
        translate([-62, 0, port_z]) rotate([0, -90, 0]) prescreen();
    }
}
