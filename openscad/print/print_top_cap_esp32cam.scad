// print_top_cap_esp32cam.scad — Nắp adapter biến thể ESP32-CAM (1 chi tiết in).
// CHỈ in khi dùng ESP32-CAM thay XIAO (baseline dùng base Matchboxscope in sẵn).
// In: mặt ĐÁY xuống bàn (hốc ngửa lên — không cần support; lỗ vuông sàn bridge ngắn).
// Sau in: thử board vào hốc (khe +0.4), dũa nhẹ nếu 4 điểm ren M3 sượt thành hốc.
include <../constants.scad>
use <../components/top_cap_esp32cam_001.scad>

top_cap_esp32cam();
