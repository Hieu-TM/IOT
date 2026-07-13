// ============================================================================
// accessories_001.scad — Phụ kiện: lưới lọc thô + ống silicone + bơm RS365
// ----------------------------------------------------------------------------
// - prescreen(): lưới lọc thô khe >5mm cắm ĐẦU NGUỒN (chỉ chặn rác to lá/cành,
//   KHÔNG lọc mất hạt 1–5mm cần đo). Chi tiết in nhỏ, nối tiếp ống vào.
// - silicone_tube(): mô phỏng ống ID8/OD11 (G4: trùm ngạnh OD8) — đi dây assembly.
// - pump_rs365(): PLACEHOLDER bơm màng RS365 12V MUA SẴN (bbox ~90×40×35 + 2 ngạnh
//   OD8). Chỉ để bố trí trạm bơm TÁCH RỜI (cách rung) — KHÔNG in, KHÔNG chi tiết.
// ============================================================================
include <../constants.scad>

// Lưới lọc thô: ống lồng Ø14 dài 20, đầu vào chia khe 6mm bởi 2 gân chữ thập
module prescreen() {
    color(col_plastic) {
        difference() {
            cylinder(d = 14, h = 20, $fn = 48);
            translate([0, 0, -0.5]) cylinder(d = 11, h = 21, $fn = 48);
        }
        // Chữ thập chắn ở miệng (tạo khe ~6mm > 5mm — hạt đo lọt, rác to bị chặn)
        for (a = [0, 90])
            rotate([0, 0, a]) translate([-7, -1, 0]) cube([14, 2, 3]);
        // Cổ nối trùm ngạnh/ống
        translate([0, 0, 20]) difference() {
            cylinder(d = sil_tube_od + 2, h = 8, $fn = 48);
            translate([0, 0, -0.5]) cylinder(d = sil_tube_od + 2*tol, h = 9, $fn = 48);
        }
    }
}

// Ống silicone (mô phỏng đoạn thẳng; assembly có thể xếp nhiều đoạn gấp khúc)
module silicone_tube(len = 60) {
    color([0.95, 0.95, 0.95, 0.55]) difference() {
        cylinder(d = sil_tube_od, h = len, $fn = 48);
        translate([0, 0, -0.5]) cylinder(d = sil_tube_id, h = len + 1, $fn = 48);
    }
}

// Bơm màng RS365 (placeholder): thân hộp + motor trụ + 2 ngạnh OD8 một đầu
module pump_rs365() {
    L = pump_bbox[0]; W = pump_bbox[1]; H = pump_bbox[2];
    // Đầu bơm màng (hộp)
    color(col_plastic) translate([-L/2, -W/2, 0]) cube([L*0.45, W, H]);
    // Thân motor RS365 (trụ)
    color(col_metal) translate([-L/2 + L*0.45, 0, H/2])
        rotate([0, 90, 0]) cylinder(d = H*0.9, h = L*0.55, $fn = 64);
    // 2 ngạnh vào/ra (OD8) trên đầu bơm
    color(col_plastic) for (sy = [1, -1])
        translate([-L/2 - 8, sy * W/4, H*0.6])
            rotate([0, 90, 0]) cylinder(d = pump_barb_od, h = 10, $fn = 32);
}

// Xem lẻ
prescreen();
translate([40, 0, 0]) silicone_tube();
translate([130, 0, 0]) pump_rs365();
