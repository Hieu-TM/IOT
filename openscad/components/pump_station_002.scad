// ============================================================================
// pump_station_002.scad — Trạm bơm gọn: đế liền + hộp che L298N + yên kẹp RS365
//                          (v2: kênh giấu dây liền mạch + hộp nới khoang bất đối xứng)
// ----------------------------------------------------------------------------
// Nguồn: docs/superpowers/specs/2026-07-25-pump-station-wire-shroud-design.md
// (sửa trên nền pump_station_001.scad / spec 2026-07-24 — kiến trúc tổng KHÔNG đổi,
// chỉ đổi phần đi dây theo phản hồi lắp thật: xem spec 07-25 mục "Bối cảnh").
//
// Thay đổi so v1:
//   1. l298n_box_walls(): khoang hộp bất đối xứng (l298n_box_clr_x/y) để chừa chỗ
//      bẻ dây quanh domino IN/OUT; khe LOGIC đổi sang wire_notch_logic_w/h (rộng
//      hơn, chứa nhiều đầu jumper); khe OUT (động cơ) HẠ XUỐNG MỨC SÀN thay vì hở
//      miệng hộp — nối THẲNG vào kênh dây bên ngoài, khỏi zíc-zắc lên tận miệng hộp
//      rồi vòng xuống lại (đây là nguyên nhân "không tính đủ độ dài dây" ở v1); khe
//      IN(12V) GIỮ NGUYÊN cơ chế hở miệng hộp (nắp ép giữ dây) vì không cần khớp
//      kênh dây nội bộ. Thêm trụ neo dây l298n_wire_anchor() ngay ngoài khe LOGIC.
//   2. pump_clamp_post(): thêm khe nhỏ xuyên đáy máng kẹp (pump_clamp_wire_notch_*)
//      nối lòng máng ↔ kênh dây bên dưới — lòng máng hình trụ nên bơm xoay tự do,
//      không phụ thuộc hướng lắp (ngạnh ống hướng nào cũng được).
//   3. wire_channel()/wire_channel_rails()/pump_station_wire_cover(): rãnh dây cũ
//      (chỉ dài đoạn hộp↔yên gần) đổi thành kênh liền mạch chạy suốt qua CẢ 2 yên
//      kẹp, có nắp đậy rời (ép giữ bằng PETG đàn hồi, không vít) che 2 đoạn hở
//      (hộp↔yên gần, yên gần↔yên xa) — đoạn kênh NẰM DƯỚI khối yên kẹp không cần
//      nắp riêng vì khối yên kẹp tự che (khác dải z: yên kẹp z≥0, kênh z<0).
//
// Trục dài đế = X. Hộp L298N ở đầu −X (gần), 2 yên kẹp ở đầu +X (xa) — không đổi
// so v1.
// ============================================================================
include <../constants.scad>

EPS = 0.05;

// ---------------------------------------------------------------- Hộp L298N (hở nắp — đáy = mặt đế bên dưới)
module l298n_box_walls() {
    difference() {
        cube([l298n_box_od_l, l298n_box_od_w, l298n_box_h]);
        // Khoét lòng hộp (chừa 4 thành; không chừa sàn — sàn = mặt đế)
        translate([l298n_box_wall, l298n_box_wall, -EPS])
            cube([l298n_box_id_l, l298n_box_id_w, l298n_box_h + 2*EPS]);
        // Khe dây INPUT 12V — cạnh −X (hướng ra ngoài trạm, xa bơm) — dây trần/cosse,
        // hở miệng hộp (rim) để NẮP ép giữ dây = strain-relief (không đổi so v1)
        translate([-EPS, l298n_box_od_w/2 - wire_notch_w/2, l298n_box_h - wire_notch_h])
            cube([l298n_box_wall + 2*EPS, wire_notch_w, wire_notch_h + EPS]);
        // Khe dây OUTPUT động cơ — cạnh +X — HẠ XUỐNG MỨC SÀN (ĐỔI SO V1) để nối
        // THẲNG vào kênh dây liền mạch bên ngoài
        translate([l298n_box_od_l - l298n_box_wall - EPS, l298n_box_od_w/2 - wire_notch_w/2, 0])
            cube([l298n_box_wall + 2*EPS, wire_notch_w, wire_notch_h + EPS]);
        // Khe dây LOGIC (ENA/IN1/IN2/GND lên ESP32) — cạnh +Y — RỘNG HƠN v1, chứa
        // nhiều đầu jumper cạnh nhau, vẫn hở miệng hộp (nắp ép giữ)
        translate([l298n_box_od_l/2 - wire_notch_logic_w/2, l298n_box_od_w - l298n_box_wall - EPS,
                   l298n_box_h - wire_notch_logic_h])
            cube([wire_notch_logic_w, l298n_box_wall + 2*EPS, wire_notch_logic_h + EPS]);
        // Khe thoát khí — cạnh −Y (đối diện khe logic, phía tản nhiệt board)
        for (i = [0 : l298n_vent_n - 1])
            translate([l298n_box_wall + 4 + i * (l298n_box_id_l - 8) / (l298n_vent_n - 1) - l298n_vent_w/2,
                       -EPS, 6])
                cube([l298n_vent_w, l298n_box_wall + 2*EPS, l298n_box_h - 6 - wire_notch_logic_h - 2]);
    }
    // 4 gờ đỡ góc board (board tựa lên — KHÔNG cần khớp lỗ vít board thật)
    foot_sz = 5.0;
    for (cx = [l298n_box_wall + 1, l298n_box_od_l - l298n_box_wall - 1 - foot_sz])
        for (cy = [l298n_box_wall + 1, l298n_box_od_w - l298n_box_wall - 1 - foot_sz])
            translate([cx, cy, 0])
                cube([foot_sz, foot_sz, l298n_foot_h]);
    // 2 gờ vít M3 tự-ren giữ nắp, 2 góc chéo
    boss_d = 6.0;
    for (p = [[l298n_box_wall + boss_d/2 + 1, l298n_box_wall + boss_d/2 + 1],
              [l298n_box_od_l - l298n_box_wall - boss_d/2 - 1,
               l298n_box_od_w - l298n_box_wall - boss_d/2 - 1]])
        translate([p[0], p[1], 0])
            difference() {
                cylinder(d = boss_d, h = l298n_box_h - 3, $fn = 32);
                translate([0, 0, 5])
                    cylinder(d = l298n_lid_screw_d, h = l298n_box_h - 3 - 5 + EPS, $fn = 24);
            }
}

// Trụ neo bó dây logic — đặt ngay ngoài khe LOGIC, dây vòng qua 1 lần trước khi đi
// tự do ra ESP32, tránh lực kéo trực tiếp vào chân cắm trên board.
module l298n_wire_anchor() {
    cylinder(d = l298n_wire_anchor_d, h = wire_notch_logic_h, $fn = 24);
}

// Nắp hộp L298N — chi tiết in RIÊNG (print_pump_station_lid.scad) — KHÔNG đổi so
// v1, tự khớp theo l298n_box_od_l/w mới vì dùng chung hằng số.
module pump_station_lid() {
    boss_d = 6.0;
    difference() {
        cube([l298n_box_od_l, l298n_box_od_w, l298n_lid_t]);
        for (p = [[l298n_box_wall + boss_d/2 + 1, l298n_box_wall + boss_d/2 + 1],
                  [l298n_box_od_l - l298n_box_wall - boss_d/2 - 1,
                   l298n_box_od_w - l298n_box_wall - boss_d/2 - 1]])
            translate([p[0], p[1], -EPS])
                cylinder(d = l298n_lid_clr_d, h = l298n_lid_t + 2*EPS, $fn = 24);
    }
}

// ---------------------------------------------------------------- Yên kẹp bơm: khối + lỗ khoan ngang + khe lồng từ trên + khe dây đáy (MỚI)
module pump_clamp_post() {
    block_h  = pump_clamp_od;
    center_z = pump_clamp_od / 2;
    difference() {
        translate([0, -pump_clamp_od/2, 0])
            cube([pump_clamp_w, pump_clamp_od, block_h]);
        // Lỗ khoan ngang (trục X = trục bơm) giữ thân trụ động cơ
        translate([-EPS, 0, center_z])
            rotate([0, 90, 0])
                cylinder(d = pump_clamp_id, h = pump_clamp_w + 2*EPS, $fn = 64);
        // Khe lồng từ ĐỈNH khối xuống tâm lỗ (hẹp hơn Ø lỗ — PETG dẻo ép giữ bơm) —
        // khe này giờ KIÊM LUÔN lối thoát dây khi chân điện bơm quay lên trên
        translate([-EPS, -pump_clamp_slot_w/2, center_z])
            cube([pump_clamp_w + 2*EPS, pump_clamp_slot_w, block_h - center_z + EPS]);
        // Rãnh zip-tie trên đỉnh khối, cắt ngang qua khe lồng (bù sai số Ø bơm thật)
        translate([pump_clamp_w/2 - pump_clamp_strap_w/2, -pump_clamp_od/2 - EPS, block_h - 1.5])
            cube([pump_clamp_strap_w, pump_clamp_od + 2*EPS, 1.5 + EPS]);
        // MỚI: khe xuyên đáy máng kẹp, nối lòng máng ↔ kênh dây bên dưới — cho phép
        // dây thoát ra ĐÁY yên kẹp khi chân điện bơm quay xuống dưới (bù hướng lắp
        // ngược so v1). Cắt tại điểm thấp nhất của lòng máng (y=0, thành mỏng nhất
        // = pump_clamp_t theo thiết kế đối xứng trên/dưới).
        translate([pump_clamp_w/2 - pump_clamp_wire_notch_w/2, -pump_clamp_wire_notch_w/2, -EPS])
            cube([pump_clamp_wire_notch_w, pump_clamp_wire_notch_w, pump_clamp_wire_notch_h + EPS]);
    }
}

// ---------------------------------------------------------------- Kênh dây liền mạch (đế) + nắp đậy rời
// Kênh cắt vào ĐẾ (z âm), chạy SUỐT từ hộp L298N tới hết cụm yên kẹp — kể cả đoạn
// NẰM DƯỚI 2 khối yên kẹp (2 vật thể khác dải z, không xung đột hình học). Gờ ray +
// nắp đậy CHỈ cần ở 2 đoạn HỞ (hộp↔yên gần, yên gần↔yên xa) — đoạn dưới yên kẹp đã
// được chính khối yên kẹp che kín, không cần nắp riêng.
module wire_channel(length) {
    translate([0, -wire_channel_w/2, -wire_channel_d])
        cube([length, wire_channel_w, wire_channel_d + EPS]);
}

module wire_channel_rails(length) {
    for (ry = [wire_channel_w/2, -wire_channel_w/2 - wire_channel_rail_w])
        translate([0, ry, 0])
            cube([length, wire_channel_rail_w, wire_channel_rail_h]);
}

// Nắp đậy kênh dây — chi tiết in RIÊNG, rộng hơn khe giữa 2 ray đúng
// wire_cover_fit_interference để PETG đàn hồi ép giữ (không vít, không khớp cài).
module pump_station_wire_cover(length) {
    cube([length, wire_channel_w + wire_cover_fit_interference, wire_channel_rail_h]);
}

// Cả 2 nắp kênh dây, xếp cạnh nhau theo Y để in chung 1 lần (dùng trong
// print_pump_station_channel_cover.scad) — độ dài từng nắp tính lại từ layout
// pump_station() để luôn khớp, không hardcode.
module pump_station_wire_covers() {
    box_x      = pump_station_margin;
    clamp_x0   = box_x + l298n_box_od_l + pump_station_gap;
    clamp_x1   = clamp_x0 + pump_clamp_gap;
    chan_a_len = clamp_x0 - (box_x + l298n_box_od_l);
    chan_b_len = clamp_x1 - (clamp_x0 + pump_clamp_w);

    pump_station_wire_cover(chan_a_len);
    translate([0, wire_channel_w + wire_cover_fit_interference + 4, 0])
        pump_station_wire_cover(chan_b_len);
}

// ---------------------------------------------------------------- Trạm bơm hoàn chỉnh (đế + hộp L298N không nắp + 2 yên kẹp)
// Gốc cục bộ: góc −X/−Y của đế tại z=0 (mặt TRÊN đế); đế dày pump_station_base_t
// nằm ở z ÂM (−pump_station_base_t .. 0).
module pump_station() {
    box_x    = pump_station_margin;
    clamp_x0 = box_x + l298n_box_od_l + pump_station_gap;
    clamp_x1 = clamp_x0 + pump_clamp_gap;
    base_y   = pump_station_wid / 2;

    chan_a_x0     = box_x + l298n_box_od_l;      // đầu kênh (mép ngoài hộp, cạnh OUT)
    chan_a_len    = clamp_x0 - chan_a_x0;        // đoạn hở 1: hộp ↔ yên gần
    chan_b_x0     = clamp_x0 + pump_clamp_w;
    chan_b_len    = clamp_x1 - chan_b_x0;        // đoạn hở 2: yên gần ↔ yên xa
    chan_full_len = (clamp_x1 + pump_clamp_w) - chan_a_x0; // toàn bộ kênh cắt (kể cả dưới 2 yên)

    // Đế (khoét kênh dây liền mạch trên mặt)
    difference() {
        translate([0, -base_y, -pump_station_base_t])
            cube([pump_station_len, pump_station_wid, pump_station_base_t]);
        translate([chan_a_x0, 0, 0]) wire_channel(chan_full_len);
    }
    // Gờ ray nắp đậy — chỉ 2 đoạn hở (dưới yên kẹp đã được chính yên kẹp che)
    translate([chan_a_x0, 0, 0]) wire_channel_rails(chan_a_len);
    translate([chan_b_x0, 0, 0]) wire_channel_rails(chan_b_len);
    // 4 chân đế góc
    foot_sz = 6.0;
    for (fx = [3, pump_station_len - 3 - foot_sz])
        for (fy = [-base_y + 3, base_y - 3 - foot_sz])
            translate([fx, fy, -pump_station_base_t - pump_station_foot_h])
                cube([foot_sz, foot_sz, pump_station_foot_h]);
    // Hộp L298N (căn giữa theo bề rộng đế)
    translate([box_x, -l298n_box_od_w/2, 0]) l298n_box_walls();
    // Trụ neo dây logic — ngay ngoài khe LOGIC (cạnh +Y của hộp)
    translate([box_x + l298n_box_od_l/2, l298n_box_od_w/2 + l298n_wire_anchor_d/2 + 2, 0])
        l298n_wire_anchor();
    // 2 yên kẹp bơm (căn giữa theo bề rộng đế; lỗ khoan nằm ngang trục X)
    translate([clamp_x0, 0, 0]) pump_clamp_post();
    translate([clamp_x1, 0, 0]) pump_clamp_post();
}

// Xem lẻ
pump_station();
translate([0, 80, 0]) pump_station_lid();
translate([0, -80, 0]) pump_station_wire_covers();
