// ============================================================================
// top_cap_002.scad — Nắp trụ = base Matchboxscope ĐÃ IN (tái dùng nguyên bản)
// ----------------------------------------------------------------------------
// Thay đổi so với _001: TRÁM KÍN HOÀN TOÀN 3 lỗ Ø8 DI SẢN Matchboxscope
// (không dùng cho Aqua Scope). STL import không sửa mesh được → loại bỏ lỗ bằng
// 3 TRỤ NÚT union đè lên (Ø8.6 nuốt trọn lỗ Ø8, cao 5.5 > sâu lỗ ~4.5mm đo từ
// lát cắt z trong technical_specs.md). Trên phần cứng thật: lỗ mù, không xuyên
// sáng — nếu muốn đồng bộ vật lý thì trám putty/che băng dính đen là đủ.
//
// KHÔNG dựng nắp mới — import STL gốc và CĂN VỀ HỆ CHUNG:
//   - Trục quang (mount_center trong toạ độ STL = (−6.2, 81.5)) → trục Z.
//   - Mặt ĐÁY base (chứa lỗ camera Ø7.5, STL z=−46.03373) → z=0 cục bộ
//     (assembly sẽ nâng lên z_tube_top).
// Đo trimesh: bounds X[−30.617,19.835] Y[55.527,107.527] Z[−46.034,−34.034].
// 4 lỗ M3 Ø2.8 tự-ren bước vuông 30×30 quanh trục quang — bích ống bắt vào đây.
// ============================================================================
include <../constants.scad>

BASE_STL   = "../../base/Assembly_Matchboxscope_injectionmolded_xiao_IM_Matchboxscope_base_xiao_9.stl";
BASE_ZMIN  = -46.03373;   // đo trimesh 2026-07-07

// 3 lỗ Ø8 DI SẢN (toạ độ STL, technical_specs.md) — bị trám ở module này
LEGACY_HOLES   = [[7.2, 95.1], [-15.7, 92.5], [-19.6, 68.1]];
LEGACY_HOLE_D  = 8.0;
PLUG_D         = LEGACY_HOLE_D + 0.6;  // nuốt trọn thành lỗ (tránh mặt trùng)
PLUG_H         = 5.5;                  // > sâu lỗ ~4.5mm (lỗ MÙ từ mặt đáy)

// Nắp trụ đã căn: trục quang = Z, mặt đáy (phía ống) = z=0, camera nhìn −Z.
// 3 lỗ di sản đã được trám kín — coi như không tồn tại.
// ⚠️ Lỗ A & C chỉ cách 2 lỗ M3 lắp ghép ~2.1–2.3mm (Ø8 nuốt trọn miệng M3 trên
// mặt đáy) → nút trám phải KHOÉT LẠI đường M3 Ø2.8 xuyên qua, kẻo bịt mất
// giao diện bắt vít với bích ống.
module top_cap() {
    color(col_plastic) {
        translate([-mount_center[0], -mount_center[1], -BASE_ZMIN])
            import(BASE_STL, convexity = 6);
        // Nút trám 3 lỗ di sản (đè từ mặt đáy z=0 lên), chừa lỗ M3
        difference() {
            for (p = LEGACY_HOLES)
                translate([p[0] - mount_center[0], p[1] - mount_center[1], 0])
                    cylinder(d = PLUG_D, h = PLUG_H, $fn = 48);
            m3_mount_pattern()
                translate([0, 0, -1])
                    cylinder(d = mount_hole_base_d, h = PLUG_H + 2, $fn = 32);
        }
    }
}

// --- Que kiểm datum (chỉ để soi căn trục — assembly không gọi) ---
module datum_check() {
    // 4 que M3 phải xuyên ĐÚNG TÂM 4 lỗ Ø2.8 của base
    color([1, 0, 0])
        m3_mount_pattern()
            translate([0, 0, -4]) cylinder(d = 2.0, h = 22, $fn = 24);
    // Que trục quang phải xuyên đúng tâm lỗ camera Ø7.5
    color([0, 0.4, 1])
        translate([0, 0, -6]) cylinder(d = 3.0, h = 26, $fn = 24);
}

top_cap();
datum_check();
