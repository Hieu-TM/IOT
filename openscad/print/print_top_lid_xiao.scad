// print_top_lid_xiao.scad — Nắp đậy trên cùng baseline XIAO (1 chi tiết in).
// In: LẬT 180° cho MẶT TRÊN tấm nắp xuống bàn (gờ định vị chĩa LÊN) — mặt phẳng
// tiếp bàn, gờ + khe USB-C là vách đứng/bridge ngắn → KHÔNG cần support.
// Sau in: thử úp lên nắp trụ (khe gờ 0.6mm — dũa nếu chật); vặn 4 vít M3 tự-ren
// vào nửa TRÊN 4 lỗ base (vít ngắn ≤6mm để không chạm vít bích ở nửa dưới).
include <../constants.scad>
use <../components/top_lid_xiao_001.scad>

// Lật để mặt trên tấm (z=lid_x_t) chạm bàn (z=0)
rotate([180, 0, 0]) translate([0, 0, -lid_x_t]) top_lid_xiao();
