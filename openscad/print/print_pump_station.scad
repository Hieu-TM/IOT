// print_pump_station.scad — Đế liền + hộp che L298N (không nắp) + 2 yên kẹp bơm (1 chi tiết in).
// In phẳng (mặt đế xuống bàn), không cần support. Vật liệu PETG (dẻo hơn PLA —
// khe lồng yên kẹp cần đàn hồi nhẹ để ép giữ thân bơm khi lắp).
// Sau in: thử board L298N vào hộp (4 gờ góc phải đỡ được board không cấn),
// thử lồng ống trụ Ø~31.5mm (hoặc bơm thật) vào 2 yên kẹp từ trên xuống.
include <../constants.scad>
use <../components/pump_station_002.scad>

pump_station();
