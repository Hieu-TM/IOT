// ============================================================================
// top_cap_001.scad — Nắp trụ = base Matchboxscope ĐÃ IN (tái dùng nguyên bản)
// ----------------------------------------------------------------------------
// KHÔNG dựng nắp mới — import STL gốc và CĂN VỀ HỆ CHUNG:
//   - Trục quang (mount_center trong toạ độ STL = (−6.2, 81.5)) → trục Z.
//   - Mặt ĐÁY base (chứa lỗ camera Ø7.5, STL z=−46.03373) → z=0 cục bộ
//     (assembly sẽ nâng lên z_tube_top).
// Đo trimesh: bounds X[−30.617,19.835] Y[55.527,107.527] Z[−46.034,−34.034].
// 4 lỗ M3 Ø2.8 tự-ren bước vuông 30×30 quanh trục quang — bích ống bắt vào đây.
// ⚠️ 3 lỗ Ø8 quanh lỗ camera là DI SẢN — bỏ qua, không dùng.
// ============================================================================
include <../constants.scad>

BASE_STL   = "../../base/Assembly_Matchboxscope_injectionmolded_xiao_IM_Matchboxscope_base_xiao_9.stl";
BASE_ZMIN  = -46.03373;   // đo trimesh 2026-07-07

// Nắp trụ đã căn: trục quang = Z, mặt đáy (phía ống) = z=0, camera nhìn −Z...
// (giữ nguyên chiều STL: lỗ camera ở mặt đáy → úp lên miệng ống là đúng chiều)
module top_cap() {
    color(col_plastic)
        translate([-mount_center[0], -mount_center[1], -BASE_ZMIN])
            import(BASE_STL, convexity = 6);
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
