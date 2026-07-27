// ============================================================================
// fluid_domain_001.scad — Xuất KHỐI NƯỚC (âm bản của flow_tray_003) cho CFD
// ----------------------------------------------------------------------------
// CFD (SimScale/OpenFOAM) cần mesh của KHÔNG GIAN CHẤT LỎNG (thể tích nước có
// thể chiếm), KHÔNG PHẢI khối nhựa print_flow_tray.stl. Đây là 2 khối bù nhau:
// fluid_domain = (bao lồi rộng rãi quanh vùng nước) − flow_tray().
//
// Bao lồi gồm 3 phần, đủ rộng để chắc chắn phủ hết vùng nước thật, rồi bị
// flow_tray() cắt gọt lại đúng hình khoang thật (vách cong, hành lang, bellmouth
// đều tự động hiện ra đúng hình sau phép trừ — không cần dựng tay từng chi tiết):
//   1. main_lumen   : trụ Ø40 (tray_inner) cao water_depth=6 — đúng khối nước
//                      tĩnh khi settle, GIỐNG hệt ghost "%water" cuối
//                      flow_tray_003.scad.
//   2. inlet_channel: hộp bao phủ hộp loe cổng vào (rộng plenum_w, cao tới ~7.5)
//                      + 1 đoạn ống thẳng nối dài INLET_STUB_LEN=20mm ra ngoài
//                      khay — CFD cần 1 đoạn ống thẳng trước khi vào hình học
//                      phức tạp để đặt biên inlet ổn định (thông lệ CFD chuẩn,
//                      không đặt biên sát ngay 1 khúc cua/co hẹp).
//   3. outlet_channel: trụ đủ rộng phủ hết miệng loe (Ø > 2×bell_r max) + ống
//                      thẳng nối dài OUTLET_STUB_LEN=20mm ra ngoài khay, cùng lý
//                      do như trên cho biên outlet.
//
// KHÔNG dùng để in — chỉ để export STL nạp vào SimScale/OpenFOAM. Xem hướng dẫn
// setup CFD đầy đủ trong docs/research (mục còn tồn đọng #4/#7) và
// openscad/verify/README.md.
// ============================================================================
include <../constants.scad>
use <../components/flow_tray_003.scad>

INLET_STUB_LEN  = 20;   // mm — đoạn ống thẳng nối dài để CFD có biên inlet ổn định
OUTLET_STUB_LEN = 20;   // mm — tương tự cho biên outlet
EPS3 = 0.05;

// --- 1. Khối nước tĩnh trong lòng khay (giống ghost %water gốc) ---
module main_lumen() {
    cylinder(d = tray_inner, h = water_depth, $fn = 120);
}

// --- 2. Kênh vào: TÁI DÙNG đúng khối hull() mà tray_shell() dùng để khoét
// "khoang loe" (flow_tray_003.scad, trong tray_shell(), gần dòng 84-89) + ống
// thẳng nối dài ra ngoài khay. Tái dùng NGUYÊN XI toạ độ đó (không tự ước lượng
// hộp bao riêng) để đảm bảo khớp tuyệt đối với vùng flow_tray() ĐÃ khoét sẵn —
// nếu tự vẽ hộp bao khác đi (như bản đầu của file này), sau khi trừ flow_tray()
// phần nối vào lòng khay có thể bị đứt rời (đã gặp: body_count=2, xác nhận bằng
// verify_flow_tray.py kiểu check trên STL kênh vào).
module inlet_channel() {
    x_bore_start = -tray_outer/2 - plenum_deep_local() + 2;
    x_stub_far   = -tray_outer/2 - plenum_deep_local() - barb_len_local() - INLET_STUB_LEN;
    hull() {
        translate([x_bore_start, 0, port_z])
            rotate([0, 90, 0]) cylinder(d = outlet_bore, h = 1, $fn = 36);
        // ⚠️ KHÁC tray_shell(): box này kéo dài X tới −18 (qua khỏi tray_inner/2=
        // −20 hẳn 2mm), không dừng ở −22.2 như khối tray_shell() dùng để khoét —
        // để CHỒNG THỂ TÍCH thật với main_lumen() (Ø40, tới x=−20), tránh đứt
        // rời thành 2 khối sau khi trừ flow_tray() (đã gặp: body_count=2).
        // flow_tray() vẫn tự cắt lại đúng hình thật, phần kéo dài thừa này chỉ
        // là biên candidate rộng rãi, không ảnh hưởng hình học cuối.
        translate([-tray_outer/2 - 1.2, -inlet_slot_w/2, 0])
            cube([5.2, inlet_slot_w, inlet_slot_h]);
    }
    // nối tiếp ra ống thẳng dài INLET_STUB_LEN, chờm EPS3 vào khối hull ở trên
    // (chồng thể tích THẬT, tránh mặt tiếp tuyến gây non-manifold khi union).
    translate([x_stub_far - EPS3, 0, port_z])
        rotate([0, 90, 0])
            cylinder(d = outlet_bore, h = x_bore_start - x_stub_far + EPS3, $fn = 32);
}
function plenum_deep_local() = 7.0;   // = plenum_deep trong flow_tray_003.scad
function barb_len_local()    = 8.0;   // = barb_len trong flow_tray_003.scad

// --- 3. Kênh ra: trụ phủ miệng loe + ống thẳng nối dài ra ngoài khay ---
module outlet_channel() {
    bell_cover_d = 2 * (outlet_bore/2 + 2*bell_fillet_r) + 4;  // phủ rộng hơn miệng loe max
    x_wall = tray_outer/2;
    x_stub_far = x_wall + barb_len_local() + OUTLET_STUB_LEN;
    hull() {
        translate([x_wall - 5, 0, port_z])
            rotate([0, 90, 0])
                cylinder(d = bell_cover_d, h = 5 + EPS3, $fn = 48);
        translate([x_stub_far, 0, port_z])
            rotate([0, 90, 0])
                cylinder(d = outlet_bore, h = EPS3, $fn = 32);
    }
}

module fluid_candidate_region() {
    union() {
        main_lumen();
        inlet_channel();
        outlet_channel();
    }
}

module fluid_domain() {
    difference() {
        fluid_candidate_region();
        flow_tray();
    }
}

fluid_domain();

// --- Tham chiếu khi mở file lẻ: khối nhựa thật, bán trong suốt để đối chiếu ---
%color(col_plastic, 0.25) flow_tray();
