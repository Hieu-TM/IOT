// ============================================================================
// flow_path_probe_001.scad — Dò đường nước/hạt bằng khối "probe" hình con nhộng
// ----------------------------------------------------------------------------
// MỤC ĐÍCH: 3 lớp kiểm hiện có (assert kích thước, render mắt, export STL kiểm
// manifold) đều KHÔNG bắt được lớp lỗi mà docs/research/2026-07-23-khay-lang-song-
// nghien-cuu-hop-nhat.md PHẦN D ghi lại (thành mỏng knife-edge 0.231mm, miệng loe
// bị bịt kín, vách baffle trôi nổi) — cả 3 lỗi đó xuất STL "sạch", KHÔNG hề bị CGAL
// báo non-manifold. Nguyên nhân: manifold hợp lệ chỉ nói lên khối kín mặt, không
// nói lên đường nước có THỰC SỰ thông hay không.
//
// KỸ THUẬT: dựng 1 chuỗi capsule (hull() 2 sphere nối tiếp) đường kính = particle_max
// (2mm — đúng bằng hạt lớn nhất cần đo, KHÔNG lớn hơn), đi theo tuyến hẹp nhất đã
// CHỐT trong thiết kế: cửa vào → hành lang ngoài vách cong (baffle_corridor, hẹp
// nhất = 3.0mm) → vùng mở giữa khay → miệng loe → lòng cổng ra → ngạnh ra.
// Sau đó intersection(flow_tray(), probe): nếu render/export ra RỖNG (không có
// hình học) → xác nhận probe không chạm bất kỳ thành nào trên suốt tuyến → đường
// nước THÔNG SUỐT cho hạt 2mm. Nếu export ra khối đặc → chính là điểm probe bị
// solid tray chặn lại — vị trí khối đó = vị trí tắc nghẽn cần sửa.
//
// ⚠️ Đây là kiểm tra CẦN (necessary), không phải ĐỦ (sufficient): chỉ xác nhận 1
// tuyến hình học cụ thể có thông hay không, không mô phỏng động lực học dòng chảy
// thật (xoáy, va đập, ma sát) — việc đó cần CFD, xem docs/research (mục còn tồn
// đọng #4/#7) và openscad/verify/README.md.
//
// CÁCH DÙNG:
//   Xem trực quan (probe overlay màu đỏ trong suốt trên khay):
//     bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/verify/flow_path_probe_001.scad --size 1400x1000 --camera 0,0,0,55,0,30,180 --output openscad/verify/flow_path_probe_001_overlay.png
//   Kiểm đường thông (đổi MODE bên dưới thành "check" rồi export):
//     bash .claude/skills/export-stl/scripts/export-stl.sh openscad/verify/flow_path_probe_001.scad --output openscad/verify/flow_path_check.stl
//     → đọc log export-stl.sh: "Current top level object is not a 3D object" hoặc
//       file STL 0 byte / rỗng = THÔNG. Có hình học thật = TẮC, mở STL xem vị trí.
// ============================================================================
include <../constants.scad>
use <../components/flow_tray_003.scad>

// "overlay": flow_tray() đặc + probe bán trong suốt màu đỏ, để xem bằng mắt tuyến đi
// "check"  : chỉ intersection(flow_tray(), probe) — dùng để export STL kiểm rỗng
MODE = "overlay";

probe_d = particle_max;  // 2.0mm — đúng bằng hạt lớn nhất cần đo, không nới thêm
EPS2 = 0.05;

module probe_node(p) {
    translate(p) sphere(d = probe_d, $fn = 16);
}

module probe_capsule(p1, p2) {
    hull() {
        probe_node(p1);
        probe_node(p2);
    }
}

// Tuyến hẹp nhất đã chốt trong thiết kế (xem constants.scad §CHỐNG SÓNG):
//   P0        : ngay trong thành, phía cổng vào (r=19, trong dải hành lang ngoài)
//   P1..P7    : quét cung hành lang NGOÀI vách cong tại bán kính 18.3mm (giữa
//               17.0=baffle_r_mid+baffle_t/2 và 19.8~tray_inner/2) — CHÍNH LÀ
//               baffle_corridor=3.0mm, hành lang hẹp nhất trong toàn bộ thiết kế.
//               Bước góc 9° giữ sagitta dây cung < 0.07mm, không cắt lẹm vào vách.
//   P8        : vừa qua mép vách (góc 126° < baffle bắt đầu tại 135°) — hết bị chặn
//               bởi vách ở MỌI bán kính từ đây trở đi.
//   P9..P10   : cắt qua vùng mở giữa khay (bán kính < baffle_r_mid−baffle_t/2, không
//               có vách chắn ở dải bán kính này) hướng về cổng ra.
//   P11       : miệng loe (bellmouth) — Ø12 hiệu dụng, không hẹp hơn tuyến trên.
//   P12       : lòng cổng ra Ø6 (outlet_bore) tại cao độ port_z.
//   P13       : ra khỏi ngạnh, xác nhận thông hẳn ra ngoài khay.
corridor_r = (baffle_r_mid + baffle_t/2 + tray_inner/2) / 2;  // = 18.3, giữa hành lang
corridor_pts = [for (a = [180 : -9 : 126])
    [corridor_r * cos(a), corridor_r * sin(a), water_depth/2]];

waypoints = concat(
    [[-19, 0, water_depth/2]],                      // P0 cổng vào, trong thành
    corridor_pts,                                    // P1..Pn quét hành lang ngoài vách
    [[-11.8, 14.2, water_depth/2]],                  // qua khỏi mép vách (a≈126°, r=18.3)
    [[0, 8, water_depth/2]],                          // cắt ngang vùng mở giữa khay
    [[12, 3, water_depth/2]],                         // hướng về phía cổng ra
    [[tray_inner/2 - bell_fillet_r + 0.5, 0, port_z]], // miệng loe (bellmouth mouth)
    [[tray_outer/2 - tray_wall - 0.5, 0, port_z]],     // lòng cổng ra Ø6
    [[tray_outer/2 + 6, 0, port_z]]                    // ra khỏi ngạnh, hẳn ngoài khay
);

module flow_path_probe() {
    for (i = [0 : len(waypoints) - 2])
        probe_capsule(waypoints[i], waypoints[i + 1]);
}

if (MODE == "overlay") {
    color(col_plastic, 0.25) flow_tray();
    color("red", 0.9) flow_path_probe();
} else {
    intersection() {
        flow_tray();
        flow_path_probe();
    }
}
