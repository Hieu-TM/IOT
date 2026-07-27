// print_pump_station_channel_cover.scad — Nắp đậy kênh dây trạm bơm (2 thanh, in chung).
// In phẳng, PETG (đàn hồi nhẹ để ép giữ vào gờ ray — không vít, không khớp cài).
// Sau in: ép thử vào gờ ray của print_pump_station.stl, đầu nắp phải hơi chặt
// (wire_cover_fit_interference) — nếu lỏng quá thì tăng interference trong
// constants.scad và in lại; nếu chặt quá không lắp được thì giảm xuống.
include <../constants.scad>
use <../components/pump_station_002.scad>

pump_station_wire_covers();
