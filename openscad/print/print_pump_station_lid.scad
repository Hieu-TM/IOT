// print_pump_station_lid.scad — Nắp hộp L298N (1 chi tiết in riêng).
// In phẳng. Bắt 2 vít M3 tự-ren vào 2 gờ chéo của print_pump_station.stl để
// tháo/lắp khi cần chỉnh jumper 5V hoặc kiểm tra board.
include <../constants.scad>
use <../components/pump_station_001.scad>

pump_station_lid();
