# Spec: Hệ thống Web Aqua Scope (traceability dashboard)

> **Vai trò:** đây là **SPEC** (cái gì / tại sao / hợp đồng / yêu cầu) cho toàn bộ hệ thống web.
> Phần **làm thế nào** (lộ trình, phân rã module, verify) nằm ở PLAN: `docs/superpowers/plans/2026-07-14-web-system-plan.md`.
> **Thay thế:** `web_plan.md` (spec+plan gộp cũ) và `docs/superpowers/specs/2026-07-14-web-frontend-design.md` — hai file đó nay là lịch sử; tài liệu này là nguồn sự thật.
> Liên quan: `CLAUDE.md` §Application context / §Operating cycle, `ai_model_plan.md`, memory `firmware-easytarget-port`.

**Trạng thái:** brainstorm + review + redesign qua plugin `superpowers` (2026-07-14). Dừng ở spec — chưa code.

---

## 1. Objective (mục tiêu)

Xây một **dashboard truy xuất nguồn gốc (traceability)** cho trạm Aqua Scope: nhận kết quả đo hạt/rác vĩ mô từ thiết bị (hoặc mock), lưu **bất biến (append-only)** kèm ảnh backlit, và cho phép tra cứu / audit / xuất báo cáo.

- **Người dùng:** nhân viên QC nhà máy chế biến thực phẩm (LAN, desktop) + hội đồng chấm đồ án (trình chiếu demo). Ngôn ngữ UI: **tiếng Việt**.
- **Bối cảnh:** QC nước đầu vào theo lô định kỳ (không 24/7) → yêu cầu bắt buộc là **traceability**: mọi phép đo lưu mã mẫu / thời gian / số hạt / phân bố kích thước để audit về sau (`CLAUDE.md` §Application context).
- **Thành công trông như thế nào:**
  1. Thiết bị/mock POST 1 phép đo → xuất hiện trong DB + dashboard, **atomic** (được cả ảnh lẫn dữ liệu, hoặc không gì cả).
  2. Tra cứu lịch sử có filter theo lô/ngày, xem chi tiết (ảnh + bbox overlay + chart), xuất CSV audit.
  3. Dữ liệu **sống sót qua restart** và **không có đường sửa/xoá** (append-only ở tầng kiến trúc).
  4. Toàn bộ dev + test **không cần phần cứng** (dựa trên mock).
  5. **An toàn đầu vào**: dữ liệu từ thiết bị/mock được coi là untrusted và validate ở biên (xem §6).

---

## 2. Tech stack

| Thành phần | Lựa chọn | Ghi chú |
|---|---|---|
| Backend | **FastAPI** (`>=0.115`) | async, dependency injection |
| ORM/model | **SQLModel** (`>=0.0.22`) | 1 class = bảng DB + schema; giảm boilerplate |
| DB | **SQLite** | single-writer đủ cho ghi thấp, theo lô; không cần DB server |
| Multipart | **python-multipart** | nhận `metadata` + `image` |
| Ảnh | **Pillow** (`>=10.4`) | sanity-check + sinh ảnh mock |
| Frontend | **Jinja2** server-rendered + **vanilla JS** | **không build step** (không React/webpack) |
| Chart | **Chart.js v4**, vendor **local** | không CDN — demo LAN offline |
| Mock client | **requests** + Pillow | script độc lập |
| Test | **pytest** + FastAPI `TestClient` | SQLite in-memory |

**Ràng buộc kiến trúc bất biến:** chạy trong LAN cùng thiết bị (Raspberry Pi/laptop), **không internet-facing**; ESP32 chỉ đẩy dữ liệu lên, không host dashboard; backend là **nguồn sự thật duy nhất**, append-only.

---

## 3. Kiến trúc tổng quan

```
┌──────────────────────┐        ┌──────────────────────────────┐        ┌────────────────────────┐
│ ESP32-S3 (tương lai)  │  POST  │   Backend (FastAPI + SQLite) │  GET   │  Frontend (Jinja2+JS)  │
│ hoặc mock_sender.py   │───────▶│ /api/ingest  → DB + ảnh       │◀───────│ Dashboard / History    │
│  - chụp backlit        │        │ /api/samples → list/detail    │        │ Sample detail          │
│  - CV + classifier    │        │ /api/export.csv → audit       │        │ Stream (demo, FE-only) │
│  - build JSON + ảnh    │        │ (append-only, no PUT/DELETE)  │        │ Export CSV             │
└──────────────────────┘        └──────────────────────────────┘        └────────────────────────┘
```

**Nguyên tắc:** một request ingest **atomic**; count/size **luôn derive**, không nhận từ input; ảnh serve read-only qua `StaticFiles`; frontend chỉ dùng JS cho canvas bbox + chart, còn lại render server-side theo query GET.

---

## 4. Functional requirements

### FR-1 Ingest — `POST /api/ingest`
Multipart: `metadata` (chuỗi JSON) + `image` (JPEG). Hành vi:
- `sample_code` optional → server sinh `S{yyyyMMdd}-{HHmmss}-{4hex}` nếu thiếu.
- **`sample_code` (nếu client gửi) phải khớp `^[A-Za-z0-9._-]{1,64}$`** (xem SEC-1). Không khớp → `422`.
- `count` / `size_distribution` **không nhận từ input** — luôn derive. `particle_count = len(particles)` denormalize vào bảng `sample`.
- Idempotent theo `sample_code`: đã tồn tại → `200 {status:"already_exists"}`.
- Atomic: ghi ảnh + `sample` + `particle` cùng nhau; lỗi → rollback DB **và** xoá ảnh mồ côi.
- **Chuẩn hoá thời gian:** `captured_at` convert sang **UTC** trước khi lưu (xem DATA-1).
- Response: `201 created` / `200 already_exists` / `422` (JSON/field sai) / `400` (thiếu/ảnh hỏng) / `413` (ảnh quá lớn, SEC-3) / `500` (rollback toàn phần).

### FR-2 Read — `GET /api/samples`, `/api/samples/{id}`
- List: phân trang (`page`, `page_size≤200`), filter `batch_lot`/`from`/`to`, **chỉ summary** (không kèm particles), sắp xếp mới nhất trước; DB rỗng → `{items:[],total:0}` (không lỗi).
- Detail: full sample + particles + **histogram kích thước tính lúc đọc** (bin 0.3mm, 0–5mm) + `label_distribution`; id không có → `404`.

### FR-3 Export audit — `GET /api/export.csv`
- 1 dòng/hạt (mẫu 0 hạt vẫn 1 dòng), cùng filter như list.
- **Chống CSV injection** (SEC-2). Truy vấn particle **1 lần** cho tất cả mẫu (không N+1, PERF-1).

### FR-4 Frontend — 4 trang (chi tiết §7)
Dashboard `/`, History/audit `/history`, Detail `/samples/{id}`, **Stream demo `/stream`**. Không route sửa/xoá ở bất kỳ đâu.

### FR-5 Mock sender
Script độc lập (`web/mock_sender.py`), không import backend, POST đúng hợp đồng FR-1; sinh ảnh Pillow (nền xám + elip tối tại bbox) để khớp trực quan với overlay.

### FR-6 Ranh giới firmware (tương lai, ngoài scope code đợt này)
Firmware POST đúng hợp đồng FR-1; lỗi POST **non-fatal** (log Serial, không chặn chu kỳ Stop-Flow vật lý).

---

## 5. Data contract (API)

### 5.1 `POST /api/ingest` — `metadata` JSON
```json
{
  "device_id": "aquascope-01",
  "sample_code": "S20260713-143205-7f3a",
  "batch_lot": "LOT-2026-07-13-A",
  "captured_at": "2026-07-13T14:32:05+07:00",
  "px_per_mm": 14.0,
  "image_width": 640, "image_height": 480,
  "particles": [
    {"blob_index":0,"centroid_x":210.5,"centroid_y":133.2,
     "bbox_x":198,"bbox_y":120,"bbox_w":26,"bbox_h":24,
     "area_px":312.0,"size_mm":1.8,"label":"plastic","confidence":0.91}
  ]
}
```
**Ràng buộc validate (Pydantic, ở biên):**
- `sample_code`: optional, khớp `^[A-Za-z0-9._-]{1,64}$` (SEC-1).
- `confidence` ∈ [0,1]; `size_mm ≥ 0`; `bbox_* ≥ 0`; `area_px ≥ 0` (validate lỏng nhưng chặn giá trị vô nghĩa).
- `label`: chuỗi tự do (class list chưa chốt — không enforce enum); nhãn lạ hiển thị màu `unknown`.
- `captured_at`: ISO 8601, **bắt buộc có/hiểu được offset**; server convert UTC.

### 5.2 Read responses
- `GET /api/samples` → `{items:[SampleSummary], total, page, page_size}`.
- `GET /api/samples/{id}` → sample đầy đủ + `particles[]` + `size_histogram{bin_width_mm,max_mm,bins[]}` + `label_distribution{label:count}`.
- `GET /api/export.csv` → `text/csv`, cột: 8 field mẫu cha + 11 field hạt.

---

## 6. Data model + Security/Robustness requirements

### DATA — Schema
Bảng **`sample`** (`id` PK · `sample_code` unique idx · `batch_lot?` idx · `device_id` · `captured_at` · `received_at`=now-UTC · `particle_count` · `image_path` · `image_width?`/`height?` · `px_per_mm?` · `raw_metadata_json` verbatim).
Bảng **`particle`** (`id` PK · `sample_id` FK idx · `blob_index` · `centroid_x/y` · `bbox_x/y/w/h` · `area_px` · `size_mm` · `label` · `confidence`).
Ảnh lưu `data/images/{sample_code}.jpg` (đặt tên theo `sample_code` **đã validate** — an toàn nhờ SEC-1), serve read-only qua `StaticFiles` tại `/images`. `data/` git-ignored, tạo lúc runtime.

**DATA-1 — Chuẩn hoá thời gian (fix review):** mọi datetime lưu **naive-UTC nhất quán** (`captured_at` convert từ offset về UTC rồi bỏ tzinfo; `received_at` là UTC). Lý do: SQLite bỏ tzinfo → nếu trộn múi giờ thì tính năng audit "`received_at − captured_at` = độ trễ gửi" sẽ **sai đúng bằng offset (vd 7h)** và filter khoảng ngày lệch. Frontend hiển thị đổi sang giờ địa phương.

**SEC-1 — Chặn path traversal (Critical, fix review):** `sample_code` do client gửi được dùng làm tên file → **phải** validate allowlist `^[A-Za-z0-9._-]{1,64}$` ở `IngestPayload` trước khi chạm filesystem. Không có ký tự `/ \ ..` lọt qua.

**SEC-2 — Chặn CSV formula injection (fix review):** ô CSV bắt đầu bằng `= + - @` (tab/CR) → prefix `'`. Áp cho `device_id`, `batch_lot`, `label`, `sample_code`, mọi field chuỗi từ input.

**SEC-3 — Giới hạn kích thước upload (fix review):** từ chối ảnh > `MAX_UPLOAD_BYTES` (config, vd 8MB) → `413`, tránh nạp file khổng lồ vào RAM.

**SEC-4 — Untrusted input:** toàn bộ `metadata`/`image` từ mạng là untrusted; validate ở biên (Pydantic + Pillow sanity-check giữ nguyên). Không log giá trị nhạy cảm.

**PERF-1 — Không N+1:** `export.csv` lấy particle **1 truy vấn** (order by `sample_id, blob_index`) rồi gom theo `sample_id`, thay vì query mỗi mẫu.

---

## 7. Frontend design

### 7.1 Design tokens
- **Palette thương hiệu** (tái dùng từ `so_do/*.svg` + `presentation_aqua_scope.md`): Teal `#1D9E75`/`#0F6E56` (chủ đạo, = "đạt") · Amber `#EF9F27`/`#854F0B` (cảnh báo, gợi đèn nền) · Blue `#378ADD` (dòng chảy/thông tin).
- **Bảng màu nhãn hạt DUY NHẤT** (dùng nhất quán ở bbox + chart + chip): nhựa=teal · bọt khí=blue · hữu cơ=amber · sợi=xám `#888780` · unknown=xám nhạt `#B4B2A9`. Định nghĩa 1 chỗ (CSS custom properties + mirror trong JS).
- Nền sáng sạch, card bo 12px viền 0.5px, 2 cấp đậm (400/500), **sentence case**, dark mode + tương phản WCAG AA.
- Chip trạng thái QC: **Đạt** (teal) / **Cảnh báo** (amber) theo ngưỡng `WARN_PARTICLE_COUNT` trong `config.py`.

### 7.2 Bốn trang
- **`/` Dashboard (lưới module cân bằng):** hàng metric tiles (mẫu hôm nay · tổng hạt · tỉ lệ nhựa · cảnh báo) → card "mẫu mới nhất" (ảnh+bbox+meta) + donut phân bố loại → bảng mini 5 mẫu + lối vào audit. *(Đã duyệt qua mockup 2026-07-14.)*
- **`/history` Audit:** bảng phân trang (mã mẫu·lô·giờ·số hạt·chip loại·trạng thái·chi tiết) + filter GET (ngày/lô) + nút Xuất CSV mang filter. Dense rows, **không nút sửa/xoá**.
- **`/samples/{id}` Chi tiết:** ảnh + `<canvas>` bbox overlay (màu theo nhãn, tooltip hover) + bảng từng hạt + histogram kích thước + chart phân bố loại + khối `raw_metadata_json` mở rộng (`<details>`).
- **`/stream` Stream (demo):** cửa sổ "live" **thuần frontend** (canvas + JS) mô phỏng dòng chảy backlit + bbox vẽ đè thời gian thực; nút "Bật stream" + toggle "Hiện detection" (cú reveal khi demo); HUD số hạt/loại/fps. **KHÔNG endpoint backend mới, KHÔNG ghi DB.** Banner trung thực: "Chế độ demo — mô phỏng, không ghi vào lịch sử." (Mở rộng tương lai: thay nền canvas bằng MJPEG `:81/stream` thật.)

### 7.3 Component & trạng thái (phần plan cũ §5 thiếu)
- **Empty state** mỗi trang (mời hành động, không bảng trơ); **loading** skeleton ảnh; **lỗi** thông báo ngắn, không first-person, không lộ exception.
- `bbox_overlay.js` tự tính scale từ kích thước hiển thị thực so với `image_width/height` gốc → khớp dù responsive.
- Responsive: desktop 2 cột → ≤820px gập 1 cột; bảng cuộn ngang trong khung riêng (body không cuộn ngang).

---

## 8. Commands

```
# Cài
pip install -r web/requirements.txt

# Chạy backend (từ web/backend/)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Mock 15 mẫu theo lô
python web/mock_sender.py --url http://127.0.0.1:8000/api/ingest --count 15 --interval 2

# Test (từ web/backend/)
pytest -q
```

## 9. Project structure

```
web/
├── README.md · requirements.txt · mock_sender.py
└── backend/
    ├── app/
    │   ├── main.py config.py database.py models.py
    │   ├── routers/  ingest.py  samples.py  pages.py
    │   ├── templates/ base index history sample_detail stream .html
    │   └── static/ css/style.css  js/{vendor/chart.umd.min.js, bbox_overlay.js, charts.js, stream_sim.js}
    ├── data/  (aqua_scope.db + images/  — runtime, git-ignored)
    └── tests/ test_module1_smoke.py  test_ingest.py  test_read_api.py  ...
```

## 10. Code style
Theo đúng phong cách các file backend hiện có (là exemplar): module docstring nêu "tại sao" + tham chiếu mục spec; type hint đầy đủ; comment giải thích quyết định (không comment điều hiển nhiên); hàm helper `_snake_case` cho nội bộ; import chuẩn → third-party → local. Không đổi phong cách này.

## 11. Testing strategy
- **Framework:** pytest + FastAPI `TestClient`, DB SQLite in-memory (fixture tạo/huỷ mỗi test), không đụng `data/` thật.
- **Bao phủ (mọi module có test, không chỉ M1):**
  - Ingest: 201/200-already_exists/422/400/413/500; idempotent retry; rollback + xoá ảnh mồ côi; **`sample_code` độc hại bị 422** (SEC-1); count derive đúng.
  - Read: list (phân trang, filter, DB rỗng, thứ tự), detail (histogram bin biên, label_distribution, 404), export (số dòng khớp, mẫu 0 hạt, **CSV injection bị vô hiệu** SEC-2, không N+1).
  - Mock: chạy độc lập, payload hợp lệ theo FR-1.
  - Frontend: smoke render 3 trang với fixture; `/stream` không gọi backend.
  - E2E (M6): kịch bản §PLAN — mock→dashboard→history→detail→CSV→restart persist→100 mẫu phân trang.
- **Ngưỡng:** mỗi endpoint có ≥1 test happy path + ≥1 test lỗi/biên trước khi coi module "xong".

## 12. Boundaries
- **Always:** validate input ở biên (SEC-1..4); derive count/size (không nhận từ input); append-only (không thêm route sửa/xoá); datetime naive-UTC nhất quán (DATA-1); Chart.js vendor local; test happy+lỗi cho mỗi endpoint.
- **Ask first:** đổi DB schema (cần migrate); thêm dependency mới; đổi data contract §5; bỏ ràng buộc "không build step".
- **Never:** commit `data/` (db/ảnh runtime); dùng CDN cho asset; thêm PUT/PATCH/DELETE lên sample/particle; dùng `sample_code` chưa validate làm đường dẫn file; ghi DB từ trang `/stream`.

## 13. Success criteria (kiểm chứng được)
1. `POST /api/ingest` đúng bảng mã trạng thái FR-1; `sample_code="../x"` → **422**, không ghi file ngoài `images/`.
2. `received_at − captured_at` đúng độ trễ thật (cùng UTC), không lệch theo múi giờ.
3. `export.csv` mở bằng bảng tính **không** thực thi công thức; số dòng khớp tổng hạt; sinh với ≤1 truy vấn particle/tập mẫu.
4. 3 trang đọc + `/stream` render đúng dữ liệu mock; overlay bbox khớp ảnh; không có `<script src="http...">`.
5. `pytest -q` xanh; mỗi module có test happy + lỗi.
6. Dừng/chạy lại uvicorn → dữ liệu còn; không có đường sửa/xoá.

## 14. Open questions
- Giá trị default `WARN_PARTICLE_COUNT` (ngưỡng cảnh báo) — chọn hợp lý khi code, dễ đổi.(chưa cần set, sẽ mặc định là có hạt xuất hiện sẽ hiện cảnh báo)
- Class list cuối (`ai_model_plan.md`) — không enum hoá để tránh migrate.(sẽ có 4 nhãn: plastic, bubble, organic, fiber)
- Kích hoạt chu kỳ đo (tự động ESP32 vs nút web gọi ngược) — thuộc firmware Phase 6, chưa quyết ở đợt này.
- `MAX_UPLOAD_BYTES` cụ thể (đề xuất 8MB) — xác nhận khi code.(sẽ tinh chỉnh sau)
