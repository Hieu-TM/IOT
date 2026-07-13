# Web & Backend Plan — Aqua Scope

> **Phạm vi tài liệu này:** chỉ bàn phần **web + backend** (dashboard truy xuất nguồn gốc / traceability).
> Phần CV/classifier chạy on-device xem `ai_model_plan.md`; phần cơ khí/quang học xem `README.md`, `plan.md`.
> Liên quan: `CLAUDE.md` §"Application context", §"Operating cycle", memory `firmware-easytarget-port`.

---

## 0. Bối cảnh & hiện trạng

Khảo sát repo tại thời điểm viết tài liệu này cho thấy:

- **Chưa tồn tại thư mục `web/` nào** — đây là phần hoàn toàn mới, không có code/tài liệu nào trước đó.
- **Chưa có ảnh hạt mẫu thật nào trong repo** dùng làm dữ liệu demo (`so_do/` chỉ có sơ đồ SVG kiến trúc, không phải ảnh chụp thật).
- `firmware/aqua_scope_cam/aqua_scope_cam.ino` là sketch thật, chạy được (WiFi AP/STA, `esp_http_server` phục vụ `/`, `/capture`, `/control`, `/status`, MJPEG stream cổng 81, cấu hình exposure/gain thủ công, lưu config qua NVS `Preferences`) — nhưng hook `runVision(camera_fb_t* fb)` (nơi CV/classifier sẽ chạy) **hiện đang rỗng**, chỉ log kích thước frame. README của thư mục này đã phác thảo (chưa code) một state machine `Phase` (`FILLING → SETTLING → CAPTURING → DRAINING → COOLDOWN`) — đây chính là chỗ bước "gửi kết quả lên backend" sẽ được gắn vào sau này.
- Không có thư viện serialize JSON hay HTTP client outbound nào trong firmware hiện tại (`esp32-cam-webserver`'s `jsonlib` chỉ đọc/parse, không ghi).

**Hệ quả cho kế hoạch:** vì `runVision()` chưa có kết quả thật và không có ảnh mẫu thật, **toàn bộ việc xây dựng và kiểm thử backend + frontend phải dựa trên một bộ mock data** (§6) cho đến khi firmware CV/classifier hoàn thiện (việc đó tách riêng, xem §7 Phase 6). Mock không phải giải pháp tạm bợ để vứt đi — nó là công cụ phát triển/test lâu dài, độc lập phần cứng.

---

## 1. Kiến trúc tổng quan

```
┌─────────────────────┐        ┌──────────────────────────────┐        ┌────────────────────────┐
│  ESP32-S3 (tương lai)│        │   Backend (FastAPI+SQLite)   │        │  Frontend (Jinja2+JS)  │
│  hoặc mock_sender.py │  POST  │                              │  GET   │                        │
│  (hiện tại)          │───────▶│ /api/ingest  → lưu DB + ảnh  │◀───────│  Dashboard             │
│                      │        │                              │        │  History (audit table) │
│  - chụp ảnh backlit  │        │ /api/samples → đọc danh sách │        │  Sample detail         │
│  - classical CV      │        │ /api/samples/{id} → chi tiết │        │  (ảnh + bbox overlay    │
│  - classifier         │        │ /api/export.csv → xuất báo   │        │   + chart)              │
│  - build JSON+ảnh    │        │   cáo audit                  │        │  Export CSV             │
└─────────────────────┘        └──────────────────────────────┘        └────────────────────────┘
```

**Nguyên tắc kiến trúc:**
- ESP32 (hoặc mock) **chỉ đẩy dữ liệu lên**, không tự host dashboard — tránh gánh nặng cho ESP32-CAM vốn đã bận chụp ảnh + chạy CV/classifier.
- Backend là **nguồn sự thật duy nhất** cho traceability — mọi bản ghi bất biến (append-only), không có API sửa/xoá.
- Chạy trong LAN cùng ESP32 (Raspberry Pi hoặc laptop), **không cần deploy internet-facing** — đúng quy mô demo/lab rig của đồ án.
- Frontend server-rendered (Jinja2, có sẵn trong FastAPI), JS thuần chỉ cho phần thực sự cần tương tác (canvas vẽ bbox, chart) — không cần build step (không React/webpack).

---

## 2. Data contract / API design

### 2.1 `POST /api/ingest` — nhận dữ liệu từ thiết bị (hoặc mock)

Request `multipart/form-data` gồm 2 phần:
- `metadata` — chuỗi JSON (form field, không phải file)
- `image` — file JPEG

**Ví dụ `metadata`:**

```json
{
  "device_id": "aquascope-01",
  "sample_code": "S20260713-143205-7f3a",
  "batch_lot": "LOT-2026-07-13-A",
  "captured_at": "2026-07-13T14:32:05+07:00",
  "px_per_mm": 14.0,
  "image_width": 640,
  "image_height": 480,
  "particles": [
    {
      "blob_index": 0,
      "centroid_x": 210.5,
      "centroid_y": 133.2,
      "bbox_x": 198,
      "bbox_y": 120,
      "bbox_w": 26,
      "bbox_h": 24,
      "area_px": 312.0,
      "size_mm": 1.8,
      "label": "plastic",
      "confidence": 0.91
    }
  ]
}
```

**Quyết định thiết kế & lý do:**

| Quyết định | Lý do |
|---|---|
| Multipart (JSON string + file) thay vì 2 request riêng | 1 request atomic — hoặc thành công cả ảnh lẫn metadata, hoặc thất bại cả hai. Đơn giản cho `HTTPClient` trên ESP32 (không cần 2 round-trip qua WiFi hay lỗi). |
| `sample_code` optional trong payload | Nếu thiếu, server tự sinh `S{yyyyMMdd}-{HHmmss}-{4 hex}`. Vừa dùng được cho mock_sender vừa dùng được cho firmware dù có/không tự quản lý ID. |
| `batch_lot` (mã lô sản xuất) — field mới | Khớp bối cảnh QC nước đầu vào nhà máy thực phẩm (`CLAUDE.md` §Application context) — cho phép đối chiếu 1 lô sản xuất với các mẫu QC liên quan. Nullable. |
| `count` / `size_distribution` **không nhận từ input**, luôn derive | `particle_count = len(particles)` (denormalize vào bảng `sample` lúc ghi để list nhanh); phân bố kích thước tính **lúc đọc** từ bảng `particle` — tránh 2 nguồn sự thật lệch nhau, và cho phép đổi bin size sau này mà không cần sửa dữ liệu đã lưu. |
| `size_mm` tính phía thiết bị, không phải backend | Chỉ thiết bị (hoặc mock) biết độ phân giải chụp thật + hệ số hiệu chuẩn px/mm tại thời điểm đó. Backend lưu lại `px_per_mm` đã dùng để phục vụ audit ("giá trị mm này được suy ra từ hiệu chuẩn nào"), không tự tính lại. |
| Nhãn (`label`) không hard-reject giá trị lạ | Class list (`plastic/bubble/organic/fiber/unknown`) theo `ai_model_plan.md` **chưa chốt cứng** — backend chấp nhận string tự do, validate lỏng. |
| Ngưỡng confidence → `unknown` | Xử lý phía thiết bị/mock theo đúng logic đã định trong `ai_model_plan.md` ("dưới ngưỡng → gán unknown"); backend chỉ lưu lại nhãn cuối cùng. |

**Response:**
- `201 Created` — `{"id": 42, "sample_code": "...", "particle_count": 7, "status": "created"}`
- `200 OK` + `"status": "already_exists"` — nếu `sample_code` đã tồn tại (idempotent retry — hữu ích khi thiết bị gửi lại do timeout mà không biết lần trước có thành công không).
- `422 Unprocessable Entity` — `metadata` không phải JSON hợp lệ / thiếu field bắt buộc.
- `400 Bad Request` — thiếu phần `image`, hoặc ảnh không mở được (`PIL.Image.open` kiểm tra sanity).
- `500` — lỗi DB không lường trước; toàn bộ transaction (sample + particles + file ảnh) rollback cùng nhau, không bao giờ ghi dở dang.

**Xử lý mất kết nối thiết bị:** đây là **việc của firmware tương lai** (Phase 6, §7), không phải backend phải tự lo ngay — ghi chú lại để hợp đồng dữ liệu không mâu thuẫn với hướng đó: firmware nên coi POST thất bại là non-fatal (log Serial, tiếp tục chu kỳ xả/nạp lại bình thường), không được để việc log lên backend chặn chu kỳ Stop-Flow vật lý.

### 2.2 Read endpoints — phục vụ frontend

```
GET /api/samples?page=1&page_size=20&batch_lot=...&from=...&to=...
GET /api/samples/{id}
GET /api/export.csv?from=...&to=...&batch_lot=...
```

- `GET /api/samples` → `{"items": [...], "total": N, "page": 1, "page_size": 20}` — chỉ trả về dòng tóm tắt (không kèm particles) để bảng lịch sử load nhanh.
- `GET /api/samples/{id}` → đầy đủ sample + mảng particles + histogram phân bố kích thước tính sẵn (bin cố định, ví dụ 0.3mm/bin từ 0–5mm, khớp phạm vi thiết kế trong `CLAUDE.md`).
- **Không có route PUT/PATCH/DELETE ở bất kỳ đâu** — đây là cách enforce yêu cầu append-only ở tầng kiến trúc, không chỉ là quy ước UI.

---

## 3. Database schema

**Lựa chọn: SQLite qua SQLModel** (không dùng SQLAlchemy thuần + Pydantic schema riêng). Lý do: SQLModel (cùng tác giả FastAPI) cho phép 1 class vừa định nghĩa bảng DB vừa định nghĩa schema (de)serialize API — giảm một nửa boilerplate cho schema 2 bảng của đồ án sinh viên, tích hợp tự nhiên với dependency injection của FastAPI.

**Vì sao SQLite đủ dùng:** đây là trạm demo/lab đo theo lô định kỳ (không giám sát liên tục 24/7 theo `CLAUDE.md`), một nguồn ghi tại một thời điểm, tần suất ghi thấp — mô hình single-writer của SQLite không phải vấn đề, và không cần cài đặt server DB riêng trên Raspberry Pi/laptop.

### Bảng `sample`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | int, PK, autoincrement | ID nội bộ |
| `sample_code` | str, unique, indexed | mã mẫu; server tự sinh nếu không được gửi lên |
| `batch_lot` | str, nullable | mã lô sản xuất (field mới đề xuất) |
| `device_id` | str | trạm nào gửi (dự phòng multi-station sau này) |
| `captured_at` | datetime | thời điểm thiết bị báo cáo đã chụp |
| `received_at` | datetime, default=now() | thời điểm server nhận — chênh lệch với `captured_at` lộ ra việc gửi trễ/mất kết nối tạm thời, phục vụ audit |
| `particle_count` | int | denormalize từ `len(particles)`, phục vụ sort/list nhanh |
| `image_path` | str | đường dẫn tương đối dưới `data/images/` |
| `image_width` / `image_height` | int, nullable | frontend cần để scale canvas overlay đúng tỉ lệ |
| `px_per_mm` | float, nullable | hệ số hiệu chuẩn dùng cho mẫu này — audit "mm suy ra từ đâu" |
| `raw_metadata_json` | text | JSON gốc nguyên văn, lưu mãi mãi kể cả khi schema chuẩn hóa đổi sau — đây là bản ghi audit-proof thật sự |

### Bảng `particle`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | int, PK | |
| `sample_id` | int, FK → `sample.id`, indexed | |
| `blob_index` | int | thứ tự trong frame |
| `centroid_x` / `centroid_y` | float | |
| `bbox_x` / `bbox_y` / `bbox_w` / `bbox_h` | int | |
| `area_px` | float | |
| `size_mm` | float | |
| `label` | str | plastic/bubble/organic/fiber/unknown — không enforce bằng DB constraint vì class list chưa chốt |
| `confidence` | float | |

**Lưu ảnh:** `web/backend/data/images/{sample_code}.jpg` — đặt tên theo `sample_code` (không phải `id` tự tăng) vì `sample_code` đã biết trước khi insert DB xong, tránh phải insert-rồi-đổi-tên-file. Serve read-only qua FastAPI `StaticFiles` mount tại `/images`.

**Lưu ý:** cần thêm `web/backend/data/` vào `.gitignore` khi bắt đầu code (Phase 1, §7) — không phải việc của tài liệu kế hoạch này.

---

## 4. Cấu trúc thư mục backend (sẽ tạo ở phase code)

```
web/
├── README.md                          # hướng dẫn chạy backend + mock sender
├── requirements.txt                   # fastapi, uvicorn[standard], sqlmodel, python-multipart, jinja2, pillow, requests
├── mock_sender.py                     # script độc lập, chỉ cần requests+pillow để chạy
└── backend/
    └── app/
        ├── main.py                    # FastAPI() instance, include_router, mount static/images
        ├── config.py                  # BASE_DIR, DB_PATH, IMAGES_DIR, PX_PER_MM_DEFAULT, CLASS_LIST, CONFIDENCE_THRESHOLD
        ├── database.py                # engine, get_session(), create_db_and_tables()
        ├── models.py                  # SQLModel: Sample, Particle + IngestPayload validation models
        ├── routers/
        │   ├── ingest.py              # POST /api/ingest
        │   ├── samples.py             # GET /api/samples, /api/samples/{id}, /api/export.csv
        │   └── pages.py               # GET /, /history, /samples/{id} (Jinja2 TemplateResponse)
        ├── templates/
        │   ├── base.html
        │   ├── index.html             # dashboard
        │   ├── history.html           # bảng audit
        │   └── sample_detail.html     # ảnh + bbox overlay + chart
        └── static/
            ├── css/style.css
            └── js/
                ├── vendor/chart.umd.min.js   # Chart.js v4 vendor local, không CDN
                ├── bbox_overlay.js            # vẽ bbox lên canvas theo tọa độ gốc
                └── charts.js                  # khởi tạo chart phân bố kích thước + phân bố loại
```

`web/backend/data/` (chứa `aqua_scope.db` + `images/`) được tạo lúc runtime, không commit vào git.

---

## 5. Frontend design

Server-rendered Jinja2 (built-in FastAPI, không cần build step) + JS thuần chỉ cho 2 phần thực sự cần tương tác client-side: canvas vẽ bbox và chart. Bảng/filter/phân trang đều render trực tiếp từ Jinja2 theo query-string GET — đơn giản nhất có thể, không cần client-side routing/state.

- **`/` (Dashboard):** mẫu gần nhất (sample_code, batch_lot, captured_at, particle_count), vài số liệu nhanh (số mẫu hôm nay, tổng hạt hôm nay), bảng mini 5 mẫu gần nhất, link sang History.
- **`/history` (bảng audit):** bảng phân trang — `mã mẫu | mã lô | thời gian chụp | số hạt | phân bố loại (chip) | link chi tiết`. Filter (khoảng ngày, mã lô) qua query param GET, server render lại. Nút "Xuất CSV" trỏ tới `/api/export.csv` với cùng filter. **Không có nút sửa/xoá nào** — enforce append-only ở cả tầng UI.
- **`/samples/{id}` (chi tiết):** ảnh JPEG đã lưu + `<canvas>` overlay vẽ bbox từng hạt (màu theo `label`, kèm chú giải), bảng từng hạt (label, confidence, size_mm, area_px, centroid), chart phân bố kích thước (histogram, bin cố định), chart phân bố loại (bar/pie), khối "raw metadata" có thể mở rộng để xem JSON gốc — phục vụ audit đầy đủ.
- **Thư viện chart: Chart.js**, vendor local dưới `static/js/vendor/` (tải về 1 lần, không fetch từ CDN) — lý do: mục tiêu là demo LAN offline ổn định, một `<script src="https://...">` phụ thuộc CDN sẽ gãy demo khi không có internet, mâu thuẫn với quyết định kiến trúc "không cần deploy internet-facing". Chart.js được chọn vì không cần build step, chỉ cần 1 thẻ `<script>` với global `Chart`, hỗ trợ sẵn bar/histogram/pie đủ cho phạm vi này.
- Toạ độ bbox truyền theo độ phân giải gốc (`image_width`/`image_height` lưu trong `sample`); `bbox_overlay.js` tự tính hệ số scale từ kích thước hiển thị thực tế của `<img>` so với độ phân giải gốc, để overlay luôn khớp dù ảnh responsive co giãn theo trình duyệt.

---

## 6. Chiến lược mock data (`web/mock_sender.py`)

Vì `runVision()` chưa có kết quả thật và repo không có ảnh hạt mẫu nào dùng được, backend + frontend **phải được xây dựng và test dựa trên mock** trước khi tích hợp firmware thật.

Script độc lập, không import code của backend (chỉ dùng `requests` + `pillow`) — nói chuyện thuần qua HTTP giống hệt một client firmware thật sau này sẽ làm.

**CLI:** `python mock_sender.py --url http://127.0.0.1:8000/api/ingest --count 15 --interval 2 --device-id aquascope-mock`

**Mỗi mẫu sinh ra:**
- `sample_code` = `MOCK-{yyyyMMdd-HHmmss}-{4 hex ngẫu nhiên}`, `batch_lot` ngẫu nhiên một trong `["LOT-A", "LOT-B", None]`.
- Số hạt: ngẫu nhiên 3–15.
- Mỗi hạt: `label` theo trọng số (`plastic` 40%, `bubble` 25%, `organic` 20%, `fiber` 10%, `unknown` 5%), `size_mm` ngẫu nhiên đều trong [0.3, 4.5]mm (khớp phạm vi thiết kế 1–5mm / phạm vi test hiện tại <2mm trong `CLAUDE.md`), `confidence` ngẫu nhiên 0.6–0.99 (thỉnh thoảng ép xuống dưới ngưỡng 0.5 rồi gán lại `unknown` để test đường đó).
- `bbox`/`area_px`: suy từ `size_mm` qua hằng số `PX_PER_MM = 14.0` (khớp con số ~14px/mm ở VGA nêu trong `CLAUDE.md`), có jitter tỉ lệ khung nhỏ để hạt `fiber` ra hình thuôn dài rõ rệt.
- **Sinh ảnh bằng Pillow** (vì không có ảnh hạt thật nào trong repo): nền xám sáng mô phỏng trường backlit đều + vẽ elip tối đúng tại centroid/bbox đã sinh ra — để ảnh khớp trực quan với bbox-overlay khi xem trang chi tiết, thay vì ảnh placeholder vô nghĩa.
- POST `metadata` (chuỗi JSON) + `image` (bytes JPEG qua `io.BytesIO`) dạng multipart tới `/api/ingest` bằng `requests`.

**Mock có xoá sau khi có firmware thật không?** Không — giữ vĩnh viễn trong `web/mock_sender.py`, ghi rõ trong `web/README.md` rằng script này vẫn hữu ích để test backend độc lập không cần bật phần cứng, kể cả sau khi tích hợp firmware xong.

---

## 7. Lộ trình triển khai theo pha

1. **Phase 1 — Backend skeleton + DB.** Tạo cây `web/`, `requirements.txt`, `config.py`, `database.py` (SQLModel engine + `create_db_and_tables()`), `models.py` (`Sample`, `Particle`). `main.py` ráp mọi thứ, mount `/static` và `/images`. Kiểm tra: `uvicorn app.main:app --reload` chạy sạch, `aqua_scope.db` được tạo, `GET /` trả trang "chưa có mẫu nào".
2. **Phase 2 — Ingest endpoint.** `routers/ingest.py`: parse multipart, validate `metadata` bằng Pydantic `IngestPayload`, lưu ảnh vào `data/images/{sample_code}.jpg`, insert `Sample` + `Particle` theo transaction, xử lý idempotent retry theo `sample_code`. Kiểm tra: POST thử 1 request multipart tay, xác nhận có dòng mới trong DB.
3. **Phase 3 — Mock sender.** Build `web/mock_sender.py` theo §6. Kiểm tra: chạy nhắm vào endpoint Phase 2, xác nhận N dòng dữ liệu hợp lý xuất hiện.
4. **Phase 4 — Read API + frontend pages.** `routers/samples.py`, `routers/pages.py`, templates, vendor Chart.js, `bbox_overlay.js`/`charts.js`. Kiểm tra: duyệt `/`, `/history`, `/samples/{id}` với dữ liệu mock.
5. **Phase 5 — Export/audit.** `GET /api/export.csv` (dùng module `csv` chuẩn, mỗi dòng 1 hạt kèm field mẫu cha, filter theo cùng tham số ngày/lô như History). Gắn nút "Xuất CSV". Kiểm tra: tải file, mở bằng ứng dụng bảng tính, đối chiếu số dòng.
6. **Phase 6 (tương lai, tách riêng khỏi web_plan — không nằm trong scope tài liệu này):** thêm `HTTPClient` + build JSON (ArduinoJson hoặc `snprintf` tay) vào `loopCycle()`/sau `runVision()` của `aqua_scope_cam.ino`, POST đúng contract mà `mock_sender.py` đã dùng, lưu backend URL qua `Preferences` (NVS) có sẵn. Lỗi POST không được chặn chu kỳ Stop-Flow vật lý (log Serial, tiếp tục xả/nạp lại).

---

## 8. Kế hoạch kiểm thử (không cần phần cứng thật)

1. `pip install -r web/requirements.txt`
2. Từ `web/backend/`: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
3. Terminal khác: `python web/mock_sender.py --count 15 --interval 2` — mô phỏng 15 mẫu theo lô định kỳ.
4. Mở `http://localhost:8000/` → dashboard hiện mẫu mới nhất trong 15 mẫu.
5. Mở `http://localhost:8000/history` → bảng liệt kê đủ 15 dòng; thử filter theo ngày/mã lô.
6. Vào trang chi tiết 1 mẫu → xác nhận ảnh hiển thị, bbox overlay khớp với các elip tối trong ảnh mock, chart phân bố kích thước + phân bố loại đều render đúng dữ liệu.
7. Bấm "Xuất CSV" → mở file tải về, đối chiếu số dòng khớp tổng `particle_count` hiển thị trên UI.
8. Dừng và chạy lại `uvicorn` → xác nhận dữ liệu vẫn còn (chứng minh SQLite file + thư mục ảnh sống sót qua restart process — đây mới thực sự là yêu cầu "backend", độc lập phần cứng).
9. (Tuỳ chọn) `python web/mock_sender.py --count 100` → xác nhận phân trang ở trang History vẫn hoạt động tốt.

---

## 9. Chia module để nhiều agent triển khai song song

Mục tiêu: chia Phase 1–5 (§7) thành các **module độc lập, ranh giới file rõ ràng, không đè lên nhau**, để nhiều agent có thể code song song thay vì phải làm tuần tự từng phase. Vì toàn bộ data contract (API shape, JSON schema, DB schema) đã **chốt cứng ở §2–§3**, một module không cần chờ module khác *code xong* — chỉ cần dựa vào hợp đồng đã viết trong tài liệu này. Ràng buộc thật sự duy nhất là **Python import**: router nào `import` từ `models.py`/`config.py` thì phải chờ Module 1 tồn tại (không cần chạy đúng, chỉ cần file tồn tại với đúng tên class/hàm).

### Sơ đồ phụ thuộc

```
Module 1 (Backend Core)  ──┬──▶ Module 2 (Ingest API)   ──┐
   [GATE — làm trước]      │                               ├──▶ Module 6 (Wiring + Verify)
                           └──▶ Module 3 (Read API)      ──┘
Module 4 (Mock Sender)     ── không phụ thuộc code — chạy song song ngay từ đầu ──▶ (dùng để test M2 ở M6)
Module 5 (Frontend)        ── không phụ thuộc code — chạy song song ngay từ đầu ──▶ (nối vào M3 ở M6)
```

### Bảng module

| # | Module | File sở hữu (không module nào khác được sửa) | Phụ thuộc | Input hợp đồng | Deliverable / tiêu chí xong |
|---|---|---|---|---|---|
| **1** | **Backend Core & Data Layer** (làm trước, là gate) | `web/requirements.txt`, `web/backend/app/config.py`, `web/backend/app/database.py`, `web/backend/app/models.py`, `web/backend/app/main.py` (khung rỗng: tạo `FastAPI()`, gọi `create_db_and_tables()` lúc startup, chưa include router nào) | Không | §3 (schema `sample`/`particle`) | `uvicorn app.main:app` chạy được, tạo `data/aqua_scope.db` với đúng 2 bảng, `GET /` trả về không lỗi (kể cả 404 tạm cũng được, miễn không crash) |
| **2** | **Ingest API** | `web/backend/app/routers/ingest.py` | Module 1 (import `Sample`, `Particle`, `get_session`, config) | §2.1 (request/response) | `POST /api/ingest` đúng hành vi: 201/200-already_exists/422/400/500, transaction rollback khi lỗi, lưu ảnh vào `data/images/{sample_code}.jpg` |
| **3** | **Read API** | `web/backend/app/routers/samples.py` | Module 1 (import model) | §2.2 (list/detail/csv) | `GET /api/samples`, `/api/samples/{id}`, `/api/export.csv` đúng shape response đã tả ở §2.2, kể cả khi DB rỗng (trả `{"items": [], "total": 0}` chứ không lỗi) |
| **4** | **Mock Sender** | `web/mock_sender.py` | **Không phụ thuộc code nào** — chỉ cần hợp đồng §2.1 | §2.1 + §6 (class weight, size range, sinh ảnh Pillow) | Chạy độc lập, POST tới bất kỳ URL nào implement đúng §2.1; tự test bằng cách trỏ vào 1 server giả (`http.server` + in ra request nhận được) nếu Module 1–2 chưa xong |
| **5** | **Frontend Pages & Assets** | `web/backend/app/routers/pages.py`, `web/backend/app/templates/*.html`, `web/backend/app/static/**` | **Không phụ thuộc code** lúc phát triển UI — dùng JSON mẫu tĩnh (fixture) khớp đúng shape §2.2 để dựng template trước; chỉ cần Module 3 thật khi nối dây ở Module 6 | §2.2 (response shape để bind vào Jinja2/JS), §5 (danh sách trang, hành vi bbox overlay + chart) | 3 trang `/`, `/history`, `/samples/{id}` render đúng với dữ liệu fixture; `chart.umd.min.js` đã vendor local, không có `<script src="http...">` nào |
| **6** | **Wiring & Verification** (làm sau cùng, không song song được) | chỉnh `main.py` (include_router cho M2/M3/M5, mount `/static` `/images`), `.gitignore` (thêm `web/backend/data/`) | Module 1–5 | §8 (kịch bản test) | Chạy đủ 9 bước ở §8: mock sender → dashboard → history → detail (ảnh khớp bbox) → export CSV → restart persist → phân trang 100 mẫu |

### Gợi ý brief giao cho từng agent (copy trực tiếp khi spawn)

- **Agent Module 1:** "Đọc `web_plan.md` §3 và §4. Tạo `web/requirements.txt`, `web/backend/app/{config,database,models,main}.py` theo đúng schema 2 bảng `sample`/`particle` đã mô tả. `main.py` chỉ cần khung tối thiểu (chưa include router). Không tạo router/template — các phần đó do agent khác làm."
- **Agent Module 2:** "Đọc `web_plan.md` §2.1. Giả định `web/backend/app/{models,database,config}.py` đã tồn tại với các tên class/hàm đúng như §3 mô tả (nếu chưa tồn tại, tạo stub tối thiểu đủ để import, đừng định nghĩa lại schema). Chỉ được sửa `web/backend/app/routers/ingest.py`."
- **Agent Module 3:** tương tự Module 2 nhưng cho §2.2, chỉ sửa `web/backend/app/routers/samples.py`.
- **Agent Module 4:** "Đọc `web_plan.md` §2.1 và §6. Viết `web/mock_sender.py` độc lập hoàn toàn, không import bất kỳ file nào trong `web/backend/`. Test bằng cách tự dựng 1 HTTP server tối giản in ra request nhận được nếu chưa có backend thật để bắn vào."
- **Agent Module 5:** "Đọc `web_plan.md` §2.2 và §5. Dựng 3 trang Jinja2 + JS dùng dữ liệu fixture (tự viết 1 file JSON mẫu khớp đúng shape §2.2 làm dữ liệu giả để dựng UI) — không cần chờ backend thật chạy. Vendor Chart.js local vào `static/js/vendor/`, tuyệt đối không dùng CDN."
- **Agent Module 6 (chạy cuối, sau khi 1–5 xong):** "Ráp toàn bộ: include router thật vào `main.py`, thay fixture ở Module 5 bằng gọi thật tới Module 3, chạy đủ kịch bản kiểm thử §8."

---

## 10. Việc chưa chốt / cần xác nhận khi bắt đầu code thật

- Class list cuối cùng cho classifier (`plastic/bubble/organic/fiber/unknown` hay khác) — hiện dùng tạm theo `ai_model_plan.md`, backend không hard-code enum để tránh phải migrate DB khi đổi.
- Ngưỡng cảnh báo hiển thị trên dashboard (ví dụ: count vượt X thì tô đỏ) — chưa có yêu cầu cụ thể, để trống cho đến khi có tiêu chí QC rõ ràng.
- Cách kích hoạt chu kỳ đo: tự động theo lịch trên ESP32, hay có nút "Chạy" từ web gọi ngược lại thiết bị — thuộc Phase 6 (tích hợp firmware), chưa cần quyết định ở giai đoạn viết backend/frontend này.
