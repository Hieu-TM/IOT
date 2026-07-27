// ============================================================================
// pump_station_wire_path_001.scad — KIỂM CHỨNG (không in) đường dây trạm bơm v2
// ----------------------------------------------------------------------------
// Mục đích: cắt dọc mặt phẳng y=0 (mặt phẳng chứa trục kênh dây + trục lỗ khoan
// yên kẹp) để mắt thường xác nhận đường dây LIỀN MẠCH từ trong hộp L298N ra tới
// lòng máng kẹp bơm, không đoạn nào bị bịt:
//
//   [trong hộp L298N] → khe OUT mức sàn → kênh dây trong đế (z<0)
//     → khe xuyên đáy máng kẹp (pump_clamp_wire_notch_*) → [lòng máng, chân bơm]
//
// Đây là file VERIFY (giống các file khác trong openscad/verify/) — KHÔNG xuất
// STL, không thuộc bộ chi tiết in.
// ============================================================================
include <../constants.scad>
use <../components/pump_station_002.scad>

// Nửa không gian y<0 bị cắt bỏ → nhìn thẳng vào mặt cắt y=0
difference() {
    pump_station();
    translate([-10, -pump_station_wid, -20])
        cube([pump_station_len + 20, pump_station_wid, 80]);
}
