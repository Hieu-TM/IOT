// ============================================================================
// top_cap_004.scad — Nắp trụ = base Matchboxscope ĐÃ IN (tái dùng nguyên bản)
// ----------------------------------------------------------------------------
// KHÁC _003: KHOAN THÔNG CẢ 4 LỖ M3 TỪ ĐÁY (sửa lỗi lắp 2026-07-08).
// ⚠️ Lỗi phát hiện: 4 lỗ M3 gốc của base là lỗ TỰ-REN MỞ TỪ TRÊN (Matchboxscope
// base+lid bắt vít từ trên), BỊT ĐÁY ~4–5mm. Aqua Scope bắt bích ống TỪ DƯỚI LÊN
// → 2 lỗ UL(−21.2,96.5) & LR(8.8,66.5) BỊT đáy, vít không vào được (2/4 lỗ lỗi).
// (2 lỗ LL & UR tình cờ thông vì trùng nút trám di sản được khoan lại ở _002/_003.)
// SỬA: difference() ở cấp cao khoan Ø2.8 XUYÊN SUỐT (z=−1..cap_h+1) cả 4 lỗ M3
// → cả 4 mở đều 2 mặt, vít bích (dưới) + vít nắp đậy (trên) đều tự-ren được.
//
// Kế thừa _003: trám 3 lỗ Ø8 di sản (mù từ đáy) + 3 lỗ Ø4 xuyên vành ngoài cùng.
//
// KHÔNG dựng nắp mới — import STL gốc và CĂN VỀ HỆ CHUNG:
//   - Trục quang (mount_center STL = (−6.2,81.5)) → trục Z; mặt ĐÁY base (STL
//     z=−46.03373, chứa lỗ camera Ø7.5) → z=0 cục bộ. base cao 12 (z=0..12).
// ============================================================================
include <../constants.scad>

BASE_STL   = "../../base/Assembly_Matchboxscope_injectionmolded_xiao_IM_Matchboxscope_base_xiao_9.stl";
BASE_ZMIN  = -46.03373;   // đo trimesh 2026-07-07
EPS = 0.05;

// 3 lỗ Ø8 DI SẢN (toạ độ STL) — trám mù từ đáy
LEGACY_HOLES   = [[7.2, 95.1], [-15.7, 92.5], [-19.6, 68.1]];
PLUG_D         = 8.0 + 0.6;  // Ø8.6 nuốt trọn thành lỗ
PLUG_H         = 5.5;        // > sâu lỗ mù ~5mm

// 3 lỗ Ø4 XUYÊN ở vành ngoài (toạ độ STL) — trám đặc suốt
OUTER_HOLES    = [[16.6, 74.4], [0.0, 58.5], [-22.5, 98.6]];
OUTER_PLUG_D   = 4.0 + 0.6;  // Ø4.6
OUTER_PLUG_H   = cap_h;      // 12: đặc suốt

module top_cap() {
    color(col_plastic)
    difference() {
        union() {
            // Base gốc (import), căn trục quang về Z, mặt đáy về z=0
            translate([-mount_center[0], -mount_center[1], -BASE_ZMIN])
                import(BASE_STL, convexity = 6);
            // Trám 3 lỗ Ø8 di sản (mù, từ đáy lên)
            for (p = LEGACY_HOLES)
                translate([p[0] - mount_center[0], p[1] - mount_center[1], 0])
                    cylinder(d = PLUG_D, h = PLUG_H, $fn = 48);
            // Trám 3 lỗ Ø4 xuyên vành ngoài (đặc suốt)
            for (p = OUTER_HOLES)
                translate([p[0] - mount_center[0], p[1] - mount_center[1], 0])
                    cylinder(d = OUTER_PLUG_D, h = OUTER_PLUG_H, $fn = 40);
        }
        // KHOAN THÔNG cả 4 lỗ M3 Ø2.8 xuyên suốt (sửa 2/4 lỗ bịt đáy)
        m3_mount_pattern()
            translate([0, 0, -1])
                cylinder(d = mount_hole_base_d, h = cap_h + 2, $fn = 32);
    }
}

// --- Que kiểm datum (chỉ để soi căn trục — assembly/print không gọi) ---
module datum_check() {
    color([1, 0, 0])
        m3_mount_pattern()
            translate([0, 0, -4]) cylinder(d = 2.0, h = 22, $fn = 24);
    color([0, 0.4, 1])
        translate([0, 0, -6]) cylinder(d = 3.0, h = 26, $fn = 24);
}

top_cap();
datum_check();
