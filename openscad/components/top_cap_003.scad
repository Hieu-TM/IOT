// ============================================================================
// top_cap_003.scad — Nắp trụ = base Matchboxscope ĐÃ IN (tái dùng nguyên bản)
// ----------------------------------------------------------------------------
// KHÁC _002: TRÁM THÊM 3 LỖ Ø4 XUYÊN ở VÀNH NGOÀI CÙNG (di sản Matchboxscope,
// Aqua Scope KHÔNG dùng — user yêu cầu 2026-07-08). 3 lỗ này ở r≈23.6–23.9mm
// (đo trimesh): STL (16.6,74.4),(0,58.5),(−22.5,98.6) — LỖ XUYÊN cả 2 mặt nên
// trám bằng trụ ĐẶC SUỐT CHIỀU CAO base (z=0..12), Ø4.6 nuốt trọn thành lỗ.
// An toàn: r>23mm nằm NGOÀI footprint board XIAO (bán kính ~13.7mm) → không đụng board,
// và không trùng 4 lỗ M3 (r=21.2, khác vị trí góc) nên KHÔNG cần khoét lại.
//
// Kế thừa _002: vẫn trám 3 lỗ Ø8 di sản (mù 5mm từ đáy) + chừa 4 lỗ M3 30×30.
//
// KHÔNG dựng nắp mới — import STL gốc và CĂN VỀ HỆ CHUNG:
//   - Trục quang (mount_center trong toạ độ STL = (−6.2, 81.5)) → trục Z.
//   - Mặt ĐÁY base (chứa lỗ camera Ø7.5, STL z=−46.03373) → z=0 cục bộ.
// Đo trimesh: bounds X[−30.617,19.835] Y[55.527,107.527] Z[−46.034,−34.034].
// ============================================================================
include <../constants.scad>

BASE_STL   = "../../base/Assembly_Matchboxscope_injectionmolded_xiao_IM_Matchboxscope_base_xiao_9.stl";
BASE_ZMIN  = -46.03373;   // đo trimesh 2026-07-07

// 3 lỗ Ø8 DI SẢN (toạ độ STL) — trám mù từ đáy (kế thừa _002)
LEGACY_HOLES   = [[7.2, 95.1], [-15.7, 92.5], [-19.6, 68.1]];
LEGACY_HOLE_D  = 8.0;
PLUG_D         = LEGACY_HOLE_D + 0.6;  // Ø8.6 nuốt trọn thành lỗ
PLUG_H         = 5.5;                  // > sâu lỗ mù ~5mm (đo lại trimesh 2026-07-08)

// 3 lỗ Ø4 XUYÊN ở vành ngoài (toạ độ STL) — trám ĐẶC SUỐT (mới ở _003)
OUTER_HOLES    = [[16.6, 74.4], [0.0, 58.5], [-22.5, 98.6]];
OUTER_HOLE_D   = 4.0;
OUTER_PLUG_D   = OUTER_HOLE_D + 0.6;   // Ø4.6
OUTER_PLUG_H   = cap_h;                // 12: đặc suốt (lỗ xuyên → phải kín cả 2 mặt)

module top_cap() {
    color(col_plastic) {
        translate([-mount_center[0], -mount_center[1], -BASE_ZMIN])
            import(BASE_STL, convexity = 6);
        // Nút trám 3 lỗ Ø8 di sản (đè từ mặt đáy z=0 lên), chừa lỗ M3
        difference() {
            for (p = LEGACY_HOLES)
                translate([p[0] - mount_center[0], p[1] - mount_center[1], 0])
                    cylinder(d = PLUG_D, h = PLUG_H, $fn = 48);
            m3_mount_pattern()
                translate([0, 0, -1])
                    cylinder(d = mount_hole_base_d, h = PLUG_H + 2, $fn = 32);
        }
        // Nút trám 3 lỗ Ø4 xuyên ngoài cùng (đặc suốt z=0..cap_h) — MỚI _003
        for (p = OUTER_HOLES)
            translate([p[0] - mount_center[0], p[1] - mount_center[1], 0])
                cylinder(d = OUTER_PLUG_D, h = OUTER_PLUG_H, $fn = 40);
    }
}

// --- Que kiểm datum (chỉ để soi căn trục — assembly không gọi) ---
module datum_check() {
    color([1, 0, 0])
        m3_mount_pattern()
            translate([0, 0, -4]) cylinder(d = 2.0, h = 22, $fn = 24);
    color([0, 0.4, 1])
        translate([0, 0, -6]) cylinder(d = 3.0, h = 26, $fn = 24);
}

top_cap();
datum_check();
