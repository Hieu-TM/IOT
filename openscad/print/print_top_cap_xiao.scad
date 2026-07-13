// print_top_cap_xiao.scad — Nắp trụ baseline XIAO ESP32-S3 Sense (1 chi tiết in).
// = base Matchboxscope (import STL) đã TRÁM 3 lỗ Ø8 di sản + 3 lỗ Ø4 xuyên ngoài
//   cùng (di sản, Aqua Scope không dùng — _003), chừa 4 lỗ M3 30×30 + lỗ camera.
// In bản này khi KHÔNG có base đúc sẵn (thay vì tái dùng base injection-molded).
// In: mặt ĐÁY (lỗ camera Ø7.5) xuống bàn — mặt phẳng, hốc board ngửa lên.
// Sau in: taro/doa nhẹ 4 lỗ M3 nếu cần; đặt XIAO vào hốc, camera chui lỗ Ø7.5.
// Chỉ gọi top_cap() — KHÔNG gọi datum_check() (que căn trục, không phải geometry).
include <../constants.scad>
use <../components/top_cap_004.scad>

top_cap();
