# Prompt: thiết kế UI trên Claude Design — Aqua Scope QC Dashboard

> **Cách dùng:** copy nguyên khối trong dấu `---` bên dưới, dán vào Claude Design (hoặc bất kỳ công cụ thiết kế UI nào không có quyền đọc repo).
> Prompt **tự chứa** toàn bộ ngữ cảnh — không tham chiếu file trong repo, vì Claude Design không đọc được repo.
> Đầu ra mong muốn: **mockup UI** (không phải code sản phẩm). Việc code thật do prompt `2026-07-14-frontend-ui-build-prompt.md` đảm nhiệm; mockup này là đầu vào thị giác cho nó.
> Nguồn sự thật của mọi con số/màu/màn hình dưới đây: `docs/superpowers/specs/2026-07-14-web-system-design.md` §5, §7.

---

## PROMPT (copy từ đây)

Thiết kế giao diện web cho **Aqua Scope** — dashboard truy xuất nguồn gốc (traceability) của một trạm quan trắc hạt/rác thải vi mô trong nước.

### 1. Bối cảnh sản phẩm
Một trạm phần cứng (ESP32-Cam + camera) soi **dòng nước đầu vào của nhà máy chế biến thực phẩm** để kiểm soát chất lượng (QC). Mỗi chu kỳ đo, trạm bơm nước vào khay, để lắng, bật đèn nền phía dưới rồi chụp một ảnh: hạt/rác hiện ra thành **bóng đen trên nền sáng đều** (backlit silhouette). Thiết bị tự đếm hạt, đo kích thước (mm) và phân loại từng hạt, rồi gửi kết quả + ảnh lên server. Dashboard này là nơi nhân viên QC **xem và audit** các mẫu đó.

Yêu cầu nghiệp vụ cốt lõi: **truy xuất nguồn gốc** — mỗi mẫu phải xem lại được đầy đủ (mã mẫu, mã lô sản xuất, thời gian, ảnh gốc, từng hạt) và **không bao giờ được sửa/xoá** (append-only, dữ liệu audit).

### 2. Người dùng & ngữ cảnh sử dụng
- **Nhân viên QC nhà máy**: dùng trên desktop, trong mạng LAN, xem theo lô/theo ca.
- **Hội đồng chấm đồ án**: xem khi trình chiếu → giao diện phải **ấn tượng, dễ đọc từ xa**.
- **Ngôn ngữ UI: 100% tiếng Việt.** Sentence case, không ALL CAPS.
- Phong cách: **hiện đại, thoáng, nhiều khoảng trắng, sạch sẽ** — kiểu dashboard công nghiệp cao cấp, không rườm rà.

### 3. Design tokens (dùng đúng, không tự đổi)
**Màu thương hiệu**
- Teal `#1D9E75` (đậm `#0F6E56`, nền nhạt `#E1F5EE`) — màu chủ đạo (nước/quang học), đồng thời là trạng thái QC **"Đạt"**.
- Amber `#EF9F27` (đậm `#854F0B`, nền nhạt `#FAEEDA`) — gợi đèn nền backlit, đồng thời là trạng thái **"Cảnh báo"**.
- Blue `#378ADD` (nền nhạt `#E8F1FC`) — dòng chảy / thông tin / link.
- Xám `#888780` — trung tính, chữ phụ, cấu trúc.

**Bảng màu nhãn hạt — DUY NHẤT, dùng nhất quán ở MỌI nơi** (bbox trên ảnh, chart, chip trong bảng — người xem học một lần đọc được mọi chỗ):
- `plastic` (nhựa) = teal `#1D9E75`
- `bubble` (bọt khí) = blue `#378ADD`
- `organic` (hữu cơ) = amber `#EF9F27`
- `fiber` (sợi) = xám `#888780`
- `unknown` (không xác định) = xám nhạt `#B4B2A9`

**Nền / khối / chữ**
- Nền sáng sạch; card nền trắng, bo góc 12px, viền mảnh 0.5px.
- Metric tile: nền xám rất nhạt, bo 8px, **không viền**.
- Typography 2 cấp đậm (400 thường / 500 đậm) — không in đậm giữa câu.
- **Bắt buộc có dark mode**: đưa ra biến thể tối cho mọi màu.
- **Bắt buộc đạt WCAG AA**: chữ trên nền màu dùng stop đậm cùng gam (ví dụ chữ teal đậm `#0F6E56` trên nền teal nhạt `#E1F5EE`), không dùng đen/xám thuần trên nền màu. Focus ring rõ ràng cho điều hướng bàn phím.

### 4. Dữ liệu thật sẽ bind vào UI (thiết kế phải vừa đúng các field này, đừng bịa field mới)
Một **mẫu (sample)**: `sample_code` (vd `S20260713-143205-7f3a`) · `batch_lot` (mã lô, vd `LOT-2026-07-13-A`, có thể trống) · `device_id` (vd `aquascope-01`) · `captured_at` (giờ chụp) · `received_at` (giờ server nhận) · `particle_count` (số hạt) · ảnh JPEG · `image_width`/`image_height` · `px_per_mm` (hệ số hiệu chuẩn, vd 14.0) · `raw_metadata_json` (JSON gốc nguyên văn, phục vụ audit).

Một **hạt (particle)**: `blob_index` · `centroid_x`/`centroid_y` · bbox (`bbox_x, bbox_y, bbox_w, bbox_h`, toạ độ theo pixel ảnh gốc) · `area_px` · `size_mm` (vd 1.8) · `label` (một trong plastic/bubble/organic/fiber/unknown) · `confidence` (0–1, vd 0.91).

**Trạng thái QC:** một mẫu là **"Cảnh báo"** khi `particle_count` vượt ngưỡng cấu hình (mặc định: có hạt là cảnh báo), ngược lại là **"Đạt"**.

### 5. Bốn màn hình cần thiết kế

**5.1 `/` — Dashboard** (bố cục lưới module cân bằng, từ trên xuống)
1. Header: logo + tiêu đề "Aqua Scope — bảng điều khiển QC", chip nhỏ "LAN · demo", nút "Xuất CSV".
2. Hàng 4 metric tile: *Mẫu hôm nay · Tổng hạt hôm nay · Tỉ lệ nhựa · Cảnh báo* (thẻ Cảnh báo đổi nền amber nhạt khi > 0).
3. Hàng 2 cột (trái rộng ~1.5, phải ~1):
   - Card **"Mẫu mới nhất"**: ảnh backlit thu nhỏ **có bbox vẽ đè** + chip trạng thái + bảng meta (mã mẫu, mã lô, giờ chụp, số hạt) + link "Xem chi tiết".
   - Card **"Phân bố loại"**: biểu đồ donut theo bảng màu nhãn + chú giải kèm %.
4. Card **"5 mẫu gần nhất"**: bảng mini (mã mẫu · mã lô · giờ · số hạt · trạng thái) + link nổi bật **"Xem tất cả (lịch sử / audit)"**.

**5.2 `/history` — Bảng audit**
- Thanh filter dạng form (khoảng ngày, mã lô) + nút "Xuất CSV" (mang theo đúng filter đang chọn).
- Bảng phân trang, **dense rows** (viền ngang mảnh, KHÔNG bọc card từng dòng): `mã mẫu · mã lô · thời gian chụp · số hạt · phân bố loại (các chip màu) · trạng thái · [chi tiết]`.
- **Tuyệt đối không có nút sửa/xoá ở bất kỳ đâu** — đây là dữ liệu audit append-only. Đừng thêm icon thùng rác/bút chì "cho đẹp".

**5.3 `/samples/{id}` — Chi tiết mẫu** (2 cột)
- **Trái** (sticky khi cuộn): ảnh JPEG gốc + lớp overlay vẽ bbox từng hạt, màu theo nhãn, có chú giải; hover một hạt → tô đậm + tooltip (nhãn, size_mm, confidence).
- **Phải**: bảng từng hạt (nhãn · confidence · size_mm · area_px · centroid) + **histogram phân bố kích thước** (bin cố định 0.3mm, dải 0–5mm) + **chart phân bố loại** + khối **"raw metadata JSON"** thu gọn/mở rộng được để xem JSON gốc.

**5.4 `/stream` — Stream (chế độ demo)**
- Canvas lớn mô phỏng dòng chảy backlit: trường xám sáng, các hạt tối trôi xuống, mỗi hạt có bbox màu theo loại + nhãn.
- Điều khiển: nút **"Bật stream"** (play/pause) + toggle **"Hiện detection"** (để lúc trình chiếu bật lên là bbox hiện đè — cú "reveal") + thanh chỉnh tốc độ.
- HUD live: số hạt đang thấy · chip phân bố loại · chỉ số fps.
- **Banner trung thực bắt buộc** (nổi bật, không giấu): *"Chế độ demo — mô phỏng, không ghi vào lịch sử."* Trang này không phải detection thật và không phải bản ghi audit.

### 6. Trạng thái component phải thiết kế kèm (đừng chỉ vẽ trạng thái "đẹp")
- **Empty state** cho Dashboard và History: minh hoạ nhẹ + một câu mời hành động (vd "Chưa có mẫu nào. Chạy mock_sender.py để nạp dữ liệu demo.") — không để bảng trống trơ.
- **404 thân thiện** khi mở chi tiết một mã mẫu không tồn tại.
- **Loading**: skeleton cho ảnh chưa tải.
- **Lỗi**: dòng thông báo ngắn, không dùng ngôi thứ nhất, không lộ exception (vd "Không tải được dữ liệu. Thử lại").

### 7. Responsive
- Desktop là mặc định (2 cột).
- ≤ 820px: gập 1 cột — Dashboard xếp dọc; trang Chi tiết đưa ảnh lên trên, dữ liệu xuống dưới; **bảng cuộn ngang trong khung riêng**, thân trang không bao giờ cuộn ngang.

### 8. Ràng buộc kỹ thuật ảnh hưởng tới thiết kế (thiết kế phải khả thi trong khung này)
- Frontend sẽ được code bằng **Jinja2 server-rendered + vanilla JS + Chart.js**, **không có build step** (không React/Tailwind/npm) và **chạy LAN offline** (không CDN, không webfont ngoài). → Đừng thiết kế thứ đòi hỏi animation framework nặng, font Google Fonts tải từ mạng, hay component library phức tạp. Ưu tiên hệ thống dựng được bằng CSS thuần + CSS custom properties (dùng cho cả dark mode).
- Chỉ có 3 phần thực sự động: canvas bbox overlay, chart, và mô phỏng stream. Mọi thứ khác là HTML tĩnh render từ server.

### 9. Đầu ra mong muốn
1. Mockup 4 màn hình ở trên (desktop), **light mode + dark mode**.
2. Mockup các trạng thái ở §6 (empty, 404, loading, lỗi).
3. Một bảng design token gọn (màu, bo góc, spacing, cỡ chữ) đủ để lập trình viên dịch thẳng thành CSS custom properties.
4. Ghi chú ngắn cho mỗi màn hình: lý do bố cục, cách hoạt động ở mobile.

## PROMPT (hết)
