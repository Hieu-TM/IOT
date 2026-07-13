// ============================================================================
// constants_1d.scad — Biến thể Đầu dò quang 1D (Optofluidic Sensor Head)
// ----------------------------------------------------------------------------
// TOÀN BỘ hằng số + assert. Nguồn: variants/02_openscad_plan_1d.md.
// KHÔNG liên quan baseline openscad/constants.scad (hệ tách rời).
//
// HỆ TRỤC:
//   O = ĐIỂM CẢM BIẾN (chùm laser ∩ trục ống). Z = trục dòng chảy (nước chảy −Z).
//   X = trục chùm: laser ở −X, PD hấp thụ ở +X. Y = tán xạ: PD tán xạ ở +Y (90°).
//   Cả 3 phần tử quang nằm ở mặt phẳng z=0 = MẶT TÁCH clamshell.
// ============================================================================

$fn = 48;

// ---------------------------------------------------------------- In / dung sai
tol   = 0.2;   // khe trượt FDM
wall  = 3.0;   // thành tối thiểu quanh lỗ (kín sáng + cứng)

// ---------------------------------------------------------------- Ống kênh (MUA SẴN — không in)
tube_od   = 10.0;   // ống trong bán sẵn
tube_id   = 8.0;    // hạt 5mm lọt (biên 3mm)
tube_clr  = 0.3;    // khe bore ôm ống
tube_len  = 60.0;   // thò 2 đầu nối ống bơm
part_max  = 5.0;    // hạt lớn nhất (kiểm nghẽn)
tube_bore_d = tube_od + tube_clr;         // = 10.3
tube_bore_r = tube_bore_d / 2;            // = 5.15

// ---------------------------------------------------------------- Khối gá (clamshell tách z=0)
block_w  = 50.0;    // X — chứa barrel laser + PD 2 bên
block_d  = 44.0;    // Y — chứa PD tán xạ +Y
block_h  = 36.0;    // Z — 2 nửa mỗi 18
split_z  = 0.0;     // mặt tách = mặt phẳng quang

// ---------------------------------------------------------------- Laser (MUA SẴN)
laser_dia = 6.0;    // barrel
laser_len = 20.0;   // đoạn thân trong rãnh
laser_ap  = 2.5;    // khẩu độ ra sát ống (giới hạn sáng)
ap_len    = 3.0;    // chiều dài kênh khẩu độ (vai chặn barrel/PD)
laser_shoulder_x = tube_bore_r + ap_len;  // = 8.15: vai chặn barrel

// ---------------------------------------------------------------- Photodiode ×2 (MUA SẴN — BPW34/Ø5)
pd_dia = 5.0;       // gói Ø5
pd_len = 8.0;       // thân PD trong rãnh
pd_ap  = 3.0;       // khẩu độ PD nhìn O
scatter_ang = 90;   // góc PD tán xạ (chỉ ghi chú; hình học đặt ở +Y)
pd_shoulder = tube_bore_r + ap_len;       // = 8.15

// ---------------------------------------------------------------- Vít M3 (kẹp 2 nửa)
m3_clear   = 3.4;   // lỗ thông nửa TRÊN
m3_tap     = 2.8;   // lỗ tự-ren nửa DƯỚI
screw_inset = 5.0;  // vít cách mép
cbore_d    = 6.0;   // khoét đầu vít M3 chìm (mặt trên nửa TRÊN)
cbore_h    = 3.0;   // sâu khoét đầu vít

// ---------------------------------------------------------------- Đăng ký 2 nửa (chốt định vị) + giữ ống
// Chốt Ø3 RỜI (que thép 3mm / in rời) cắm vào lỗ ở CẢ 2 nửa → canh khít mặt tách,
// khử xê dịch 0.4mm do khe vít, tránh lệch nửa-rãnh quang. (Bản _001 thiếu — lỗi khớp.)
dowel_d      = 3.0;
dowel_hole_d = 3.3;                 // lỗ chốt (khe cắm)
dowel_depth  = 4.0;                 // sâu lỗ mỗi nửa
dowel_pos    = [[16, -11], [-16, -11]]; // 2 chốt ở nửa −Y (tránh rãnh tán xạ +Y & rãnh X)
tube_set_d   = 2.5;   // lỗ tự-ren vít GIỮ ỐNG (chống tuột), từ mặt −Y, nửa TRÊN
tube_set_z   = 8.0;   // cao độ vít giữ ống (trên mặt quang z=0, nằm trong nửa trên)

// ---------------------------------------------------------------- Màu (mượn palette baseline)
col_block    = [0.20, 0.20, 0.22];       // nhựa in ĐEN NHÁM (thân quang)
col_acrylic  = [0.65, 0.88, 0.95, 0.30]; // ống trong
col_water    = [0.35, 0.65, 0.90, 0.30]; // nước
col_metal    = [0.78, 0.78, 0.80];       // barrel laser
col_laser    = [0.95, 0.15, 0.15];       // tia/đầu laser đỏ
col_pd       = [0.10, 0.20, 0.35];       // gói PD
col_pd_win   = [0.30, 0.75, 0.65];       // cửa sổ PD (teal)
col_part     = [0.15, 0.15, 0.14];       // hạt mẫu

// ============================================================================
// HELPER
// ============================================================================

// 4 lỗ vít M3 ở 4 góc (thẳng đứng). Dùng: m3_corners() cylinder(...);
module m3_corners() {
    for (sx = [-1, 1]) for (sy = [-1, 1])
        translate([sx*(block_w/2 - screw_inset), sy*(block_d/2 - screw_inset), 0])
            children();
}

// 2 vị trí chốt định vị. Dùng: dowel_positions() cylinder(...);
module dowel_positions() {
    for (p = dowel_pos) translate([p[0], p[1], 0]) children();
}

// Trụ nằm theo trục X từ x0 → x1 (x1 > x0)
module x_cyl(d, x0, x1) {
    translate([x0, 0, 0]) rotate([0, 90, 0]) cylinder(d = d, h = x1 - x0);
}
// Trụ nằm theo trục Y từ y0 → y1 (y1 > y0)
module y_cyl(d, y0, y1) {
    translate([0, y0, 0]) rotate([-90, 0, 0]) cylinder(d = d, h = y1 - y0);
}

// ============================================================================
// ASSERT lắp ghép
// ============================================================================
assert(tube_id - part_max >= 2, "hạt lớn nhất phải còn biên ≥2mm trong ống (chống nghẽn)");
assert(laser_ap < laser_dia, "khẩu độ laser phải nhỏ hơn barrel (có vai chặn)");
assert(pd_ap  < pd_dia,      "khẩu độ PD phải nhỏ hơn gói PD (có vai chặn)");
assert(laser_shoulder_x < block_w/2, "rãnh laser phải nằm trong nửa khối");
assert(pd_shoulder < block_w/2, "rãnh PD hấp thụ (+X) phải nằm trong nửa khối");
assert(pd_shoulder < block_d/2, "rãnh PD tán xạ (+Y) phải nằm trong nửa khối");
assert(sqrt(pow(block_w/2 - screw_inset, 2) + pow(block_d/2 - screw_inset, 2))
       - m3_clear/2 > tube_bore_r + wall, "lỗ vít 4 góc phải cách bore ống ≥ wall");
assert(block_h/2 - laser_dia/2 >= wall, "thành trên/dưới rãnh quang ≥ wall");
assert(scatter_ang >= 30 && scatter_ang <= 150,
       "góc tán xạ giữ trong [30,150]° để rãnh không đè trục chùm X & mặt −Y (chốt/vít giữ ống)");
assert(tube_set_z + tube_set_d/2 < block_h/2, "vít giữ ống phải nằm gọn trong nửa TRÊN");
assert(cbore_h < block_h/2 - wall, "khoét đầu vít không được mỏng nóc nửa trên");

echo(str("== 1D sensor constants OK == tube OD/ID = ", tube_od, "/", tube_id,
         " | block WxDxH = ", block_w, "x", block_d, "x", block_h,
         " | shoulder x = ", laser_shoulder_x));
