# /stream trang: thay demo mô phỏng bằng live-view MJPEG thật — thiết kế

**Ngày:** 2026-07-27
**Bối cảnh:** người dùng báo "lỗi ở chế độ stream" — điều tra cho thấy `/stream` chưa từng
là lỗi: nó luôn là canvas mô phỏng thuần frontend (hạt rơi ngẫu nhiên), không gọi backend,
đúng như `stream.html`/`stream_sim.js` đã tự ghi chú. Người dùng xác nhận muốn thứ họ
mong đợi từ đầu: xem hình ảnh/video **thật** từ board. Quyết định: xây live-view thật,
trên nhánh git mới.

## Phần cứng đã có sẵn (không cần đổi firmware)

`firmware/aqua_scope_station/app_httpd.cpp` đã chạy MỘT server MJPEG riêng ở
`server_port + 1` (mặc định `HTTPD_DEFAULT_CONFIG()` → port 80 cho API chính, nên
**stream luôn ở cổng 81**), route `GET /stream`, `Content-Type: multipart/x-mixed-replace`.
Đây chính là format mà thẻ `<img>` render được thẳng, không cần JS giải mã multipart thủ công
(giống cách `esp32-cam-webserver`'s stock UI làm: `view.src = streamURL`).

## Phạm vi

Chỉ sửa trang `/stream` (frontend). Không đổi firmware, không thêm route backend mới —
`station_host` đã có sẵn qua `GET /api/settings` (dùng lại, không proxy qua backend: trình
duyệt tự lấy `<img>` thẳng từ board qua LAN, giống triết lý "no framework, no CDN, chạy được
offline trên LAN" đã áp dụng toàn dự án).

## Hành vi

1. `stream.html` tải xong → JS gọi `GET /api/settings`, đọc `station_host`.
2. **Không có `station_host`:** hiện thông báo "Chưa cấu hình địa chỉ board — vào trang chủ
   để nhập/dò IP trước." + link về `/`. Không hiện demo giả nữa (thay hẳn theo lựa chọn của
   người dùng).
3. **Có `station_host`:** dựng URL `http://<host không kèm port>:81/stream`, gán vào
   `<img id="live-view">`. Trình duyệt tự render MJPEG liên tục — không cần vòng lặp JS.
4. **Lỗi tải ảnh** (`<img>` bắn sự kiện `error` — board tắt máy, sai IP, mất mạng): hiện banner
   lỗi "Không kết nối được tới board tại `<host>:81` — kiểm tra board còn bật và cùng mạng."
   kèm nút "Thử lại" gắn lại `img.src` (thêm cache-bust query để chắc chắn trình duyệt request
   lại thay vì dùng ảnh lỗi cache).
5. **Không có HUD giả.** Bỏ hẳn số hạt/FPS/bbox tự sinh (đó là dữ liệu bịa cho demo, sẽ đánh
   lừa người xem tưởng là suy luận thật). Giữ lại duy nhất một chip nhỏ ghi rõ đang xem live
   từ host nào, để không ai nhầm đây là kết quả model.
6. Banner "Chế độ demo" đổi thành ghi chú trung thực: đây là stream thô từ camera, KHÔNG có
   overlay/suy luận — số liệu đếm/phân loại vẫn chỉ có ở luồng chụp-suy luận (control panel /
   sample detail), vì hybrid pipeline chạy theo chu kỳ bơm, không chạy real-time trên video.

## Xoá bỏ

- `stream_sim.js` (toàn bộ file — không còn nơi nào dùng).
- Các phần tử/markup demo trong `stream.html`: nút tốc độ, toggle "Hiện detection", canvas,
  pause-overlay, HUD giả.

## Việc KHÔNG làm (out of scope)

- Không chạy detection real-time trên luồng video (hybrid pipeline vẫn theo chu kỳ bơm, đúng
  kiến trúc đã chốt trong CLAUDE.md — không đổi).
- Không proxy MJPEG qua backend FastAPI (giữ đơn giản: trình duyệt lấy thẳng từ board).
- Không thêm cấu hình port tuỳ chỉnh cho server MJPEG (giả định cố định `+1` như firmware viết
  chết); nếu sau này firmware đổi cổng thì phải sửa lại điểm này.

## Kiểm thử

- `web/backend/tests/test_module5_pages.py` hiện có test cho `/stream` (nếu có) — cập nhật để
  khớp nội dung mới (không còn assert nội dung demo cũ), vẫn giữ test "trang trả 200, không
  đụng DB".
- Không thể test tự động việc `<img>` thật sự nhận được MJPEG (cần board thật) — việc này ghi
  rõ là giới hạn, xác minh thủ công bằng board thật hoặc mô tả trong PR.
