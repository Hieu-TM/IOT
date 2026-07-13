// print_flow_tray.scad — Khay Macro-Flow (1 chi tiết in).
// _002: đáy khay đã MỞ (lòng Ø40 xuyên suốt — _001 bị đĩa đặc 1mm bít đáy khi in).
// In: úp miệng khay xuống bàn (đáy hốc đĩa lên trên) hoặc đứng như dùng + support
// cho 2 ngạnh ngang & hộp loe. Sau in: doa lòng ngạnh Ø6, thử đĩa acrylic vào hốc.
include <../constants.scad>
use <../components/flow_tray_002.scad>

flow_tray();
