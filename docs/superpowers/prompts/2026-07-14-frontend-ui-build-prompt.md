# Prompt: build Frontend UI (Module 5) — Aqua Scope QC Dashboard

> Copy toàn bộ khối dưới đây, dán vào một session Claude Code mới **mở tại thư mục repo này**.
> Prompt đã tự chứa hợp đồng dữ liệu quan trọng, nhưng vẫn yêu cầu Claude đọc SPEC gốc trước khi code.

---

Bạn đang làm việc trong repo Aqua Scope. Nhiệm vụ: **code Module 5 — toàn bộ Frontend** cho traceability dashboard, đúng theo thiết kế đã chốt. Backend Module 1–3 (ingest + read API) đã xong; **không sửa backend**, chỉ thêm tầng trình bày.

## Việc cần đọc trước khi gõ dòng code đầu tiên
1. `docs/superpowers/specs/2026-07-14-web-system-design.md` — **nguồn sự thật**. Đọc kỹ **§7 (Frontend design)** + §5 (data contract) + §12 (Boundaries) + §13 (Success criteria).
2. `CLAUDE.md` §Application context, §Operating cycle — bối cảnh QC nước đầu vào, yêu cầu traceability.
3. `web/backend/app/routers/samples.py` và `models.py` — để dùng **đúng tên field** API trả về (đừng đoán).

## Ngôn ngữ & người dùng
- **Toàn bộ UI tiếng Việt.** Người dùng: nhân viên QC nhà máy thực phẩm (LAN, desktop) + hội đồng chấm đồ án (trình chiếu). Phong cách: **hiện đại, thoáng, ấn tượng khi demo**, sentence case (không ALL CAPS).

## Ràng buộc kiến trúc (bất biến — vi phạm là sai)
- Jinja2 server-rendered + **vanilla JS** + **Chart.js v4 vendor LOCAL**. **KHÔNG build step** (không React/webpack/npm), **KHÔNG CDN** (`<script src="http...">` là cấm — chạy LAN offline).
- **Append-only ở tầng UI:** tuyệt đối **không** có nút/ form sửa/xoá mẫu ở bất kỳ trang nào.
- Trang `/stream` là **mock thuần frontend**: KHÔNG gọi endpoint backend mới, **KHÔNG ghi DB**.
- Không thêm dependency Python mới, không đổi DB schema, không đổi data contract §5. Nếu thấy cần — **hỏi trước**.

## Hợp đồng dữ liệu API (khớp code backend hiện tại)
- `GET /api/samples?page=&page_size=&batch_lot=&from=&to=` → `{items:[SampleSummary], total, page, page_size}`.
  - `SampleSummary`: `id, sample_code, batch_lot?, device_id, captured_at, received_at, particle_count, image_path`.
- `GET /api/samples/{id}` → `SampleDetail`: các field summary + `image_width?, image_height?, px_per_mm?, raw_metadata_json, particles[], size_histogram{bin_width_mm,max_mm,bins:[{start,end,count}]}, label_distribution{label:count}`.
  - `ParticleOut`: `blob_index, centroid_x, centroid_y, bbox_x, bbox_y, bbox_w, bbox_h, area_px, size_mm, label, confidence`.
- `GET /api/export.csv?...` (cùng filter) → tải CSV audit.
- Ảnh serve read-only tại `/images/...` (giá trị `image_path` đã là đường dẫn tương đối, vd `images/S....jpg`).
- **Datetime** trả về là **naive-UTC** (DATA-1). Frontend phải **đổi sang giờ địa phương** khi hiển thị.

## Design tokens (định nghĩa 1 chỗ trong `static/css/style.css` = CSS custom properties, mirror sang JS)
- **Palette thương hiệu:** Teal `#1D9E75`/`#0F6E56` (chủ đạo, = trạng thái "Đạt") · Amber `#EF9F27`/`#854F0B` (cảnh báo, gợi đèn nền backlit) · Blue `#378ADD` (dòng chảy/thông tin) · Xám `#888780` (trung tính).
- **Bảng màu nhãn hạt DUY NHẤT** — dùng nhất quán ở bbox overlay + chart + chip bảng (người xem học 1 lần):
  `plastic`=teal `#1D9E75` · `bubble`=blue `#378ADD` · `organic`=amber `#EF9F27` · `fiber`=xám `#888780` · `unknown`=xám nhạt `#B4B2A9`. Nhãn lạ ngoài danh sách → màu `unknown`. (Class list chốt: plastic, bubble, organic, fiber.)
- Nền sáng sạch; card trắng bo 12px viền 0.5px; metric tile nền `--surface-1` bo 8px không viền; 2 cấp đậm (400/500); khoảng trắng rộng.
- **Dark mode + WCAG AA bắt buộc:** mọi màu qua CSS custom properties có biến thể sáng/tối; chữ trên nền màu dùng stop đậm cùng gam; focus ring rõ; `aria-label` cho nút chỉ-icon; canvas bbox có mô tả text thay thế; điều hướng bàn phím được.
- **Chip trạng thái QC:** "Đạt" (teal) / "Cảnh báo" (amber). Ngưỡng là hằng số `WARN_PARTICLE_COUNT` trong `config.py` (**default: cảnh báo khi `particle_count > 0`** — có hạt là cảnh báo). Không hard-code ngưỡng trong template.

## Bốn trang phải build (chi tiết ở SPEC §7.2)
1. **`/` Dashboard** — lưới module cân bằng:
   - Header: logo + "Aqua Scope — bảng điều khiển QC" + chip "LAN · demo" + nút "Xuất CSV".
   - Hàng 4 metric tiles (`auto-fit`): Mẫu hôm nay · Tổng hạt hôm nay · Tỉ lệ nhựa · Cảnh báo (thẻ cảnh báo nền amber nhạt khi >0).
   - Hàng 2 cột `minmax(0,1.5fr)+minmax(0,1fr)`: card **"Mẫu mới nhất"** (ảnh backlit thu nhỏ + bbox overlay + chip trạng thái + bảng meta + link "Xem chi tiết") | card **"Phân bố loại"** (donut theo bảng màu nhãn + chú giải %).
   - Card **"5 mẫu gần nhất"**: bảng mini + link nổi bật "Xem tất cả (lịch sử / audit)".
2. **`/history` Audit** — bảng phân trang (`mã mẫu·lô·thời gian·số hạt·chip loại·trạng thái·[chi tiết]`); **thanh filter dạng form GET** (khoảng ngày, mã lô) → server render lại (không client-side state); nút "Xuất CSV" mang đúng filter hiện tại; dense rows (viền ngang mảnh, không bọc card từng dòng); **không nút sửa/xoá**.
3. **`/samples/{id}` Chi tiết** — 2 cột: trái = ảnh JPEG + `<canvas>` overlay bbox (sticky khi cuộn, màu theo `label`, hover blob → tô đậm + tooltip label/size_mm/confidence); phải = bảng từng hạt (label·confidence·size_mm·area_px·centroid) + **histogram kích thước** (Chart.js, bin từ `size_histogram`) + **chart phân bố loại** (từ `label_distribution`) + khối `<details>` "raw metadata JSON" hiển thị `raw_metadata_json` nguyên văn.
4. **`/stream` Stream (demo)** — canvas + vanilla JS mô phỏng dòng chảy backlit: trường xám sáng, hạt trôi xuống, mỗi hạt bbox màu theo loại + nhãn (dùng đúng bảng màu §1.2 + `PX_PER_MM=14` để "cùng một hệ" với ảnh tĩnh). Nút "Bật stream" (play/pause) + toggle "Hiện detection" (cú reveal khi demo). HUD live: số hạt đang thấy · chip phân bố loại · fps · thanh chỉnh tốc độ. **Banner trung thực bắt buộc:** "Chế độ demo — mô phỏng, không ghi vào lịch sử."

## Component & trạng thái (phần plan cũ còn thiếu — phải làm)
- **Empty state** mỗi trang (Dashboard/History/Detail-404): minh hoạ nhẹ + 1 câu mời hành động, vd "Chưa có mẫu nào. Chạy `mock_sender.py` để nạp dữ liệu demo." — không để bảng trơ.
- **`bbox_overlay.js`**: tự tính hệ số scale từ kích thước hiển thị thực của `<img>` so với `image_width/height` gốc → overlay khớp dù ảnh co giãn responsive. Dùng lại cho cả trang Chi tiết và card Dashboard.
- **`charts.js`**: Chart.js vendor local `static/js/vendor/chart.umd.min.js`; màu lấy từ bảng nhãn thống nhất.
- **Loading/lỗi:** ảnh chưa tải → skeleton; API lỗi → dòng thông báo ngắn, không first-person, không lộ exception (vd "Không tải được dữ liệu. Thử lại").
- **Responsive:** desktop 2 cột → **≤820px gập 1 cột**; bảng cuộn ngang **trong khung riêng** (`overflow-x:auto`), body trang **không** cuộn ngang; đơn vị tương đối (`rem`, `%`, `minmax(0,1fr)`), ảnh `max-width:100%`.

## Cây file cần tạo (Module 5, không phát sinh file backend mới)
```
web/backend/app/
├── routers/pages.py            # GET /, /history, /samples/{id}, /stream (Jinja2 TemplateResponse)
├── templates/ base.html · index.html · history.html · sample_detail.html · stream.html
└── static/
    ├── css/style.css           # design tokens (custom properties, dark mode)
    └── js/ vendor/chart.umd.min.js · bbox_overlay.js · charts.js · stream_sim.js
```
Wiring Module 6: `main.py` include router `pages.py`; nav trong `base.html` có 3 mục (Dashboard · Lịch sử · Stream demo). Thêm `WARN_PARTICLE_COUNT` vào `config.py`.

## Phong cách code
Theo đúng exemplar các file backend hiện có: module docstring nêu "tại sao" + trỏ mục spec; type hint đầy đủ; comment giải thích quyết định (không comment điều hiển nhiên); helper `_snake_case`. Xem SPEC §10.

## Định nghĩa "xong" (kiểm chứng được — SPEC §13)
- 3 trang đọc + `/stream` render đúng dữ liệu mock; overlay bbox khớp ảnh (kể cả khi resize); donut/histogram đúng số liệu.
- **Không** có `<script src="http...">` bất kỳ đâu; Chart.js chạy từ vendor local.
- Không có đường sửa/xoá; `/stream` không gọi backend, có banner trung thực.
- Dark mode hoạt động; bàn phím điều hướng được; tương phản đạt AA.
- Có smoke test render 3 trang với fixture + test `/stream` không gọi backend (SPEC §11).

## Cách làm việc
Đề xuất chạy qua skill `superpowers:writing-plans` (hoặc `agent-skills:plan`) để phân rã Module 5 thành các bước nhỏ verify được, rồi build tuần tự. Trước khi build, xác nhận với tôi: giá trị default `WARN_PARTICLE_COUNT` và có cần mock data sẵn (chạy `mock_sender.py`) để xem UI không.
