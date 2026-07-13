// print_housing.scad — VỎ LIỀN 1 KHỐI IN (G2): thân ống quang học + hộp đèn.
// _002: BỎ vòng đỡ khay z=−8..−6.5 (chặn đường luồn khay OD44 từ đáy);
// khay nay đỡ bằng 2 nút bịt khe kiêm cột đỡ (print_slot_plugs). Nóc khe dọc +0.5.
// In: đặt BÍCH ĐỈNH xuống bàn in (lật 180°) — mặt bích phẳng, không cần support
// cho vòng chặn (lỗ ngang cần bridge ngắn). Nội thất đoạn trên sơn/để ĐEN
// NHÁM; khoang đèn đoạn dưới sơn/dán TRẮNG mờ.
include <../constants.scad>
use <../components/tube_body_002.scad>
use <../components/light_box_002.scad>

tube_body();
light_box_body();
