# Thiết kế Frontend — Aqua Scope QC Dashboard

> ⚠️ **ĐÃ GỘP (superseded) 2026-07-14.** Nội dung frontend này đã được fold vào SPEC hệ thống: `docs/superpowers/specs/2026-07-14-web-system-design.md` §7. Giữ lại để tra lịch sử; đừng sửa file này — sửa SPEC hệ thống.

> **Phạm vi:** thiết kế UI/UX tầng frontend (thị giác + tương tác) cho dashboard traceability của Aqua Scope.
> Đây là phần mà `web_plan.md` §5 còn thiếu — §5 mô tả *chức năng*, tài liệu này bổ sung *thiết kế thị giác thực thụ*.
> **Không thay đổi** kiến trúc backend/data-contract đã chốt ở `web_plan.md` §1–§4, §9 (những phần đó đã trên chuẩn).
> **Ràng buộc kế thừa:** Jinja2 server-rendered + vanilla JS + Chart.js vendor local, **không build step**, chạy LAN offline.
> Liên quan: `web_plan.md` (spec+plan backend), `CLAUDE.md` §Application context / §Operating cycle, `ai_model_plan.md`.

**Trạng thái:** đã brainstorm & duyệt qua plugin `superpowers` (brainstorming) ngày 2026-07-14. Dừng ở spec — chưa code frontend (Module 5).

---

## 0. Bối cảnh & quyết định đã chốt

Khảo sát repo tại thời điểm viết:

- Backend Module 1–3 (`config`, `database`, `models`, `main`, `routers/ingest`, `routers/samples`) đã code theo `web_plan.md`.
- **Module 4 (`mock_sender.py`), Module 5 (Frontend), Module 6 (wiring) chưa làm** — frontend là phần trắng.
- Chưa có `docs/superpowers/` nào trước tài liệu này → plan cũ viết ngoài quy trình superpowers.

**Quyết định người dùng đã chốt trong buổi brainstorm (2026-07-14):**

| # | Quyết định | Giá trị chốt |
|---|---|---|
| 1 | Phạm vi | Vừa chuẩn hoá tài liệu theo superpowers, vừa nâng cấp thiết kế UI/UX |
| 2 | Đầu ra buổi này | Dừng ở **bản thiết kế (spec)** — chưa build frontend |
| 3 | Trọng tâm dashboard | **Cân bằng** giám sát mẫu mới nhất + lối vào audit |
| 4 | Phong cách thị giác | **Hiện đại, thoáng, ấn tượng demo** |
| 5 | Information architecture trang chủ | **Hướng B — lưới module cân bằng** |
| 6 | Tính năng Stream | **Mock/replay cho demo, thuần frontend, KHÔNG ghi DB** |

**Người dùng đích:** nhân viên QC nhà máy thực phẩm (LAN, desktop) + hội đồng chấm đồ án (trình chiếu). **Ngôn ngữ UI: tiếng Việt.**

---

## 1. Hệ thiết kế (design tokens)

### 1.1 Bảng màu

Tái dùng bộ nhận diện sẵn có trong repo (trích từ `so_do/*.svg` + `presentation_aqua_scope.md`):

| Vai trò | Màu | Ý nghĩa |
|---|---|---|
| Thương hiệu / "Đạt" | Teal `#1D9E75` (đậm `#0F6E56`, nền nhạt `#E1F5EE`) | Nước/quang học — hợp tên "Aqua"; đồng thời là màu trạng thái QC đạt |
| Cảnh báo | Amber `#EF9F27` (đậm `#854F0B`, nền nhạt `#FAEEDA`) | Gợi đèn nền backlit; màu cảnh báo QC |
| Thông tin / dòng chảy | Blue `#378ADD` (nền nhạt `#E8F1FC`) | Nước/flow, link, thông tin trung tính |
| Trung tính | Xám `#888780` + các sắc nền sáng | Cấu trúc, chữ phụ |

### 1.2 Bảng màu nhãn hạt (DÙNG NHẤT QUÁN mọi nơi)

Một bảng màu **duy nhất** cho `label`, áp dụng đồng thời ở: bbox overlay, chart phân bố loại, chip trong bảng. Người xem học 1 lần, đọc được ở mọi chỗ.

| Nhãn | Màu |
|---|---|
| `plastic` (nhựa) | Teal `#1D9E75` |
| `bubble` (bọt khí) | Blue `#378ADD` |
| `organic` (hữu cơ) | Amber `#EF9F27` |
| `fiber` (sợi) | Xám `#888780` |
| `unknown` | Xám nhạt `#B4B2A9` |

> Class list chưa chốt cứng (`ai_model_plan.md`). Bảng màu định nghĩa 1 chỗ trong `static/css/style.css` (CSS custom properties) + mirror trong `charts.js`/`bbox_overlay.js`; thêm nhãn mới chỉ sửa 1 nơi. Nhãn lạ ngoài danh sách → màu `unknown`.

### 1.3 Nền, bố cục, typography

- Nền sáng sạch; card `background` trắng, bo góc 12px, viền `0.5px`.
- Metric tile: nền xám rất nhạt (`--surface-1`), không viền, bo 8px.
- Typography: 2 cấp đậm (400 thường / 500 đậm), **sentence case**, không ALL CAPS, không in đậm giữa câu.
- Khoảng trắng rộng rãi (ưu tiên "thoáng" theo quyết định #4).

### 1.4 Trạng thái QC

- Chip **"Đạt"** (chữ teal đậm trên nền teal nhạt) / **"Cảnh báo"** (chữ amber đậm trên nền amber nhạt).
- Ngưỡng cảnh báo (ví dụ `particle_count > N`) là **hằng số cấu hình trong `config.py`** (`WARN_PARTICLE_COUNT`), không hard-code trong template. Khớp `web_plan.md` §10 (ngưỡng cảnh báo còn để ngỏ) — đặt default hợp lý, dễ đổi.

### 1.5 Dark mode + accessibility (baseline bắt buộc)

- Mọi màu định nghĩa qua CSS custom properties có biến thể sáng/tối; không hard-code hex trong template.
- Chữ trên nền màu luôn dùng stop **đậm cùng gam** (không dùng đen/xám thuần) → đạt tương phản WCAG AA.
- Điều hướng bằng bàn phím; focus ring rõ; `aria-label` cho nút chỉ-có-icon; canvas bbox có mô tả text thay thế.

---

## 2. Bốn trang

### 2.1 `/` — Dashboard (Hướng B: lưới module cân bằng)

Thứ tự khối từ trên xuống (đã duyệt qua mockup trực quan 2026-07-14):

1. **Header**: logo + tên "Aqua Scope — bảng điều khiển QC", chip "LAN · demo", nút "Xuất CSV".
2. **Hàng metric tiles** (lưới `auto-fit`, 4 thẻ): *Mẫu hôm nay · Tổng hạt hôm nay · Tỉ lệ nhựa · Cảnh báo* (thẻ cảnh báo dùng nền amber nhạt khi >0).
3. **Hàng 2 cột** (`minmax(0,1.5fr)` + `minmax(0,1fr)`):
   - **Card "Mẫu mới nhất"**: ảnh backlit thu nhỏ + bbox + chip trạng thái + bảng meta (mã mẫu, mã lô, giờ chụp, số hạt) + link "Xem chi tiết".
   - **Card "Phân bố loại"**: donut theo bảng màu nhãn + chú giải %.
4. **Card "5 mẫu gần nhất"**: bảng mini (mã mẫu · mã lô · giờ · số hạt · trạng thái) + link nổi bật **"Xem tất cả (lịch sử / audit)"**.

### 2.2 `/history` — Bảng audit

- Bảng phân trang đầy đủ: `mã mẫu · mã lô · thời gian chụp · số hạt · phân bố loại (chip) · trạng thái · [chi tiết]`.
- **Thanh filter** (khoảng ngày, mã lô) dạng form GET → server render lại (không client-side state). Khớp `web_plan.md` §2.2.
- Nút **"Xuất CSV"** mang theo đúng filter hiện tại (trỏ `/api/export.csv?...`).
- Hàng kiểu "dense rows" (viền ngang mảnh), **không** bọc card từng dòng.
- **Không có nút sửa/xoá ở bất kỳ đâu** — enforce append-only ở cả tầng UI (song song với việc backend không có route PUT/PATCH/DELETE).

### 2.3 `/samples/{id}` — Chi tiết mẫu

- Bố cục 2 cột: **trái** = ảnh JPEG đã lưu + `<canvas>` overlay bbox (sticky khi cuộn); **phải** = dữ liệu.
- Overlay bbox: màu theo `label` + chú giải; hover blob → tô đậm + tooltip (label, size_mm, confidence).
- Bảng từng hạt: label · confidence · size_mm · area_px · centroid.
- 2 chart (Chart.js): **histogram kích thước** (bin cố định, ví dụ 0.3mm/bin từ 0–5mm — khớp phạm vi thiết kế) + **phân bố loại** (bar/donut).
- Khối **"raw metadata JSON"** mở rộng được (`<details>`) — hiển thị `raw_metadata_json` nguyên văn phục vụ audit đầy đủ.

### 2.4 `/stream` — Stream (demo)

**Bản chất:** cửa sổ "live" **thuần frontend** (canvas + vanilla JS) mô phỏng dòng chảy backlit với hạt trôi + bbox/nhãn vẽ đè thời gian thực. **Không endpoint backend mới, không ghi DB** → thuộc trọn Module 5, bảo toàn nguyên tắc append-only.

**Lý do thuần client-side (thay vì nhúng MJPEG thật):** người dùng chọn mock/replay → an toàn tuyệt đối khi trình chiếu, không phụ thuộc ESP32 có mặt/nối WiFi.

**Tái dùng logic mock:** hạt trôi dùng đúng bảng màu nhãn (§1.2) + hệ số `PX_PER_MM=14` như `mock_sender.py` (`web_plan.md` §6) → stream và ảnh tĩnh trông "cùng một hệ".

**Bố cục & tương tác:**
- Khu canvas lớn: trường xám sáng, hạt trôi xuống (mô phỏng dòng chảy), mỗi hạt có bbox màu theo loại + nhãn.
- Nút **"Bật stream"** (play/pause) + toggle **"Hiện detection"** → cho phép cú "reveal" khi demo: bật stream thấy dòng chảy, gạt detection thì bbox hiện đè lên.
- HUD live: số hạt đang thấy · chip phân bố loại cập nhật · chỉ số fps · thanh chỉnh tốc độ.
- **Banner trung thực (bắt buộc):** "Chế độ demo — mô phỏng, không ghi vào lịch sử." Nêu rõ đây **không** phải detection thật và **không** phải bản ghi audit.

**Điểm mở rộng tương lai (không thuộc scope buổi này):** thay lớp nền canvas bằng `http://<esp32>:81/stream` thật, giữ nguyên lớp overlay; hoặc nối bbox thật khi `runVision()` on-device hoàn thiện (Phase 6).

---

## 3. Component & các trạng thái (phần `web_plan.md` §5 còn thiếu)

- **Empty state** mỗi trang: minh hoạ nhẹ + 1 câu mời hành động, ví dụ "Chưa có mẫu nào. Chạy `mock_sender.py` để nạp dữ liệu demo." — **không** để bảng trống trơ. (Áp dụng cho Dashboard, History, và trang Chi tiết khi id không tồn tại → 404 thân thiện.)
- **Bbox overlay (`bbox_overlay.js`)**: tự tính hệ số scale từ kích thước hiển thị thực của `<img>` so với `image_width/height` gốc lưu trong `sample` → overlay khớp dù ảnh co giãn responsive. Dùng lại cho cả trang Chi tiết (ảnh tĩnh) và card Dashboard (thu nhỏ).
- **Chart (`charts.js`)**: Chart.js **vendor local** dưới `static/js/vendor/chart.umd.min.js` (không CDN — khớp quyết định "demo LAN offline" của `web_plan.md` §5). Màu lấy từ bảng nhãn thống nhất (§1.2).
- **Loading/lỗi**: ảnh chưa tải → skeleton; gọi API lỗi → dòng thông báo ngắn, không first-person, không lộ exception (ví dụ "Không tải được dữ liệu. Thử lại").

---

## 4. Responsive

- **Desktop** (mặc định): Dashboard lưới 2 cột; Chi tiết 2 cột (ảnh sticky).
- **≤ 820px**: gập 1 cột — card mẫu / donut xếp dọc; Chi tiết đưa ảnh lên trên, dữ liệu xuống dưới; bảng cuộn ngang **trong khung riêng** (`overflow-x:auto`), **không** để body trang cuộn ngang.
- Đơn vị tương đối (`rem`, `%`, `minmax(0,1fr)`), ảnh `max-width:100%`.

---

## 5. Cây file frontend (Module 5) — khớp `web_plan.md` §4

Không phát sinh file backend mới. Toàn bộ nằm trong phạm vi Module 5 đã định ở `web_plan.md` §9 (owner: `routers/pages.py`, `templates/*`, `static/**`), **cộng thêm** trang Stream:

```
web/backend/app/
├── routers/
│   └── pages.py                 # GET /, /history, /samples/{id}, /stream  (Jinja2 TemplateResponse)
├── templates/
│   ├── base.html                # layout chung + nav (Dashboard · Lịch sử · Stream demo)
│   ├── index.html               # Dashboard (§2.1)
│   ├── history.html             # Bảng audit (§2.2)
│   ├── sample_detail.html       # Chi tiết (§2.3)
│   └── stream.html              # Stream demo (§2.4)
└── static/
    ├── css/style.css            # design tokens §1 (CSS custom properties, dark mode)
    └── js/
        ├── vendor/chart.umd.min.js
        ├── bbox_overlay.js      # §3
        ├── charts.js            # §3
        └── stream_sim.js        # mô phỏng dòng chảy + detection cho /stream (§2.4)
```

**Ảnh hưởng Module 6 (wiring):** `main.py` include thêm route `/stream` (nằm trong `pages.py` nên không phát sinh router mới); nav trong `base.html` có 3 mục.

---

## 6. Chuẩn hoá tài liệu theo superpowers (phần "cả hai")

Cách xử lý gọn nhất, **không phá `web_plan.md`**:

- Tài liệu này (`docs/superpowers/specs/2026-07-14-web-frontend-design.md`) là **spec tầng frontend** — thứ §5 còn thiếu.
- `web_plan.md` giữ vai trò **spec + plan hợp nhất của backend** (đã trên chuẩn superpowers; §9 phân rã module còn tốt hơn output writing-plans thông thường) — **không tách nhỏ**.
- Thêm một dòng trỏ ở đầu `web_plan.md` §5: *"Thiết kế thị giác chi tiết + trang Stream demo: xem `docs/superpowers/specs/2026-07-14-web-frontend-design.md`."*

**Kết quả audit `web_plan.md` so với chuẩn superpowers (để đối chiếu):**

| Tiêu chí | Đánh giá |
|---|---|
| Tách spec khỏi plan | ⚠️ Gộp chung — chấp nhận được, vì backend nhỏ và data-contract đã chốt cứng |
| Ý định validate qua Q&A | ⚠️ Plan gốc tự viết; buổi brainstorm này bù lại phần frontend |
| Acceptance criteria mỗi task | ✅ §7, §9 có cột "Kiểm tra" |
| Phân rã module ranh giới rõ | ✅ §9 xuất sắc, vượt chuẩn |
| Data contract làm hợp đồng | ✅ §2–§3 rất tốt |
| Thiết kế UI/UX thực thụ | ❌ §5 chỉ mô tả chức năng → **tài liệu này khắc phục** |

---

## 7. Ngoài phạm vi (ghi rõ để không trôi scope)

- **Không** code frontend trong buổi này (người dùng chọn dừng ở spec).
- **Không** detection thật/real-time — trang Stream là mock/replay thuần frontend.
- **Không** đổi kiến trúc backend, data contract, DB schema (`web_plan.md` §1–§4 giữ nguyên).
- **Không** thêm auth/multi-user — vẫn là demo/lab rig chạy LAN theo `CLAUDE.md`.

---

## 8. Việc chưa chốt / cần xác nhận khi bắt đầu code frontend

- Giá trị default của ngưỡng cảnh báo `WARN_PARTICLE_COUNT` (§1.4) — chọn con số hợp lý khi code, dễ đổi.(chưa cần set, sẽ mặc định là có hạt xuất hiện sẽ hiện cảnh báo)
- Class list cuối cùng (`ai_model_plan.md`) — bảng màu §1.2 định nghĩa 1 chỗ, thêm nhãn không phải sửa nhiều nơi.(sẽ có 4 nhãn: plastic, bubble, organic, fiber)
- Tốc độ/độ dày hạt mặc định của `stream_sim.js` — tinh chỉnh cho "đẹp mắt khi trình chiếu" lúc code.(sẽ tinh chỉnh sau)
