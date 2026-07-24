// print_flow_tray.scad — Khay Macro-Flow (1 chi tiết in).
// _003: thêm cụm CHỐNG SÓNG — cửa vào đục lỗ 4 cửa sổ, vách cong tiêu năng
// r16.4 cao 7mm, miệng loe bellmouth R3 tại cổng ra. Kích thước gốc khay không đổi.
// In: úp miệng khay xuống bàn (đáy hốc đĩa lên trên) hoặc đứng như dùng + support
// cho 2 ngạnh ngang & hộp loe. Sau in: doa lòng ngạnh Ø6, thử đĩa acrylic vào hốc,
// KIỂM 4 cửa sổ vào không bị dính nhựa thừa (thông được que Ø3).
include <../constants.scad>
use <../components/flow_tray_003.scad>

flow_tray();
