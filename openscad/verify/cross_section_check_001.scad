// cross_section_check_001.scad — mặt cắt ngang z=CUT_Z để soi vùng nghi ngờ mà
// verify_flow_tray.py (raycast) báo mỏng gần bellmouth (x≈17-20, y≈0-2, z≈0-0.2).
// Kỹ thuật giống PHAN D (docs/research) đã dùng để xác nhận lỗi miệng loe bị bịt.
include <../constants.scad>
use <../components/flow_tray_003.scad>

CUT_Z = 0.15;  // ngay trên sàn z=0, trong dải verify_flow_tray.py báo mỏng

linear_extrude(height = 0.5)
    translate([0, 0, -CUT_Z])
        projection(cut = true)
            flow_tray();
