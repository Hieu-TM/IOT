# Spec — Nhánh 1: dịch vụ inference chạy trên PC (Aqua Scope)

**Ngày:** 2026-07-15
**Phạm vi:** Nhánh 1 của [ml/deploy_options.md](../../../ml/deploy_options.md) — ESP32-CAM chỉ
chụp, PC chạy full detector (train bằng Roboflow). Deploy nhúng để **sau** (Nhánh 2 / Phase C–D).

## Context

Aqua Scope cần đếm/đo/phân loại hạt rác trong nước. Model detection đã (sẽ) được train trên
Roboflow (dataset public `microplastics-m7mf5` + ảnh rig sau này). ESP32-CAM (ESP32 gốc, không
có lệnh vector AI) nhiều khả năng **không chạy nổi** detector đầy đủ on-device, nên hướng khả thi
ngay là: **chạy suy luận trên PC**. Rig thật hiện **chưa chụp nét được** (memory
`camera-focus-limit`), nên giai đoạn này input là ảnh test trong thư mục; đường ESP32 live để chờ.

Web backend **đã có sẵn** contract nhận kết quả: `POST /api/ingest`
([web/backend/app/routers/ingest.py](../../../web/backend/app/routers/ingest.py)) — multipart
`metadata` JSON + ảnh, mỗi particle theo `ParticleIn`
([web/backend/app/models.py](../../../web/backend/app/models.py)). Dịch vụ này chỉ cần **sinh ra
đúng payload đó**; không sửa web backend.

## Quyết định đã chốt

| Hạng mục | Quyết định |
|---|---|
| Nguồn ảnh | Folder trên PC (bây giờ) + ESP32 `/capture` (sau) — abstraction chuyển đổi được |
| Model | Export weights `.pt` từ Roboflow, chạy local bằng Ultralytics (khớp `ml/` đã scaffold). Đặt tại `ml/models/best.pt` (gitignore — tái tạo được, ghi nguồn Roboflow trong README) |
| Đầu ra | POST `/api/ingest` của web backend đã có → tự lên dashboard Module 5+6 |
| Cách chạy | CLI một phát: xử 1 ảnh hoặc cả folder rồi thoát |
| Cấu trúc | Package phân lớp `ml/infer/` (5 unit lõi + `preview.py` phụ, test độc lập) |
| Stream | Đường phụ **live annotated preview** (visualization thuần, KHÔNG ghi DB) |

## Kiến trúc — package `ml/infer/`

```
ml/infer/
  __init__.py
  source.py         # ImageSource abstraction; FolderSource (nay), Esp32CaptureSource (sau)
  detector.py       # bọc YOLO(best.pt).predict → list Detection thô
  mapper.py         # Detection[] + ngữ cảnh ảnh → IngestPayload (schema particles)
  ingest_client.py  # POST /api/ingest multipart, phân loại response
  cli.py            # `python -m ml.infer` — ghép source→detector→mapper→ingest, in tổng kết
  preview.py        # `python -m ml.infer.preview` — đường phụ, live annotated, KHÔNG import ingest_client
```

Mỗi unit một việc, giao tiếp qua kiểu dữ liệu rõ ràng:
- `source.py`: `ImageSource.frames() -> Iterator[Frame]`, `Frame = {image_bytes, sample_code, captured_at}`.
  `FolderSource` glob `*.jpg/*.jpeg/*.png`; `captured_at` = mtime file (gắn tz local → ISO 8601 có offset).
  `Esp32CaptureSource` (thêm sau) chỉ cần cài cùng interface, không đụng phần còn lại.
- `detector.py`: `Detector(weights).run(image_bytes) -> list[Detection]`,
  `Detection = {bbox_xywh, class_name, confidence}`. Chỉ chỗ này biết Ultralytics.
- `mapper.py`: hàm thuần (không mạng/không model) → dễ unit test.
- `ingest_client.py`: `post(api_url, payload, image_bytes) -> IngestResult{status}`.
- `cli.py`: điều phối + đếm kết quả + exit code.

## Luồng dữ liệu (một lần chạy CLI)

```
python -m ml.infer <ảnh|folder> --weights best.pt --api-url http://localhost:8000 \
       --device-id pc-infer --px-per-mm <n> [--batch-lot L] [--dry-run]
  │
  ├─ source.frames() → (image_bytes, sample_code, captured_at) cho từng ảnh
  ├─ detector.run(image_bytes) → [Detection...]
  ├─ mapper.build(detections, ctx) → IngestPayload
  ├─ ingest_client.post(...) → created | already_exists | failed
  └─ in tổng kết: N created / M already_exists / K failed (+ tên ảnh failed); exit≠0 nếu có failed
```

## Map Detection → schema `particles`

| Trường ingest | Nguồn | Ghi chú trung thực |
|---|---|---|
| `blob_index` | STT detection | 0,1,2… |
| `centroid_x/y` | tâm bbox `x+w/2, y+h/2` | xấp xỉ (không có tâm khối thật) |
| `bbox_x/y/w/h` | box detector | int, ≥0 |
| `area_px` | `w*h` (diện tích bbox) | **XẤP XỈ** — không phải diện tích blob thật (detector không có mask). Ghi chú trong `mapper.py` + đây |
| `size_mm` | `max(w,h) / px_per_mm` | Feret-diameter xấp xỉ; `max(w,h)` cho ổn định |
| `label` | tên lớp | free string (fiber/film/fragment/pellet) |
| `confidence` | conf box | ∈ [0,1] |

`sample_code` **suy từ tên file** rồi sanitize khớp `^[A-Za-z0-9._-]{1,64}$`
(cùng ràng buộc SEC-1 mà [models.py](../../../web/backend/app/models.py) yêu cầu) → chạy lại cùng
folder là **idempotent** (server trả `already_exists`, không nhân đôi).

### Ba điểm trung thực bắt buộc (không âm thầm bịa số)
1. **`px_per_mm` với ảnh dataset public là vô nghĩa** (ảnh không có tỉ lệ thật). `--px-per-mm` khai
   báo có chủ đích; nếu thiếu → dùng `config.PX_PER_MM_DEFAULT` **và in cảnh báo** "size_mm là
   placeholder, không phải mm thật". Tỉ lệ thật chỉ có sau khi calib rig (Phase D).
2. **`area_px = w*h` là diện tích bbox**, không phải diện tích hạt — lệch với hạt tròn/thuôn. Ghi rõ
   để sau này thay bằng diện tích blob thật nếu thêm bước CV/segmentation.
3. **`captured_at`** phải kèm offset (ingest reject nếu thiếu); `device_id` là tham số CLI (mặc định
   `pc-infer`) để dashboard phân biệt nguồn "chạy PC" với thiết bị thật.

## Đường phụ — live annotated preview (stream)

**Vì sao stream KHÔNG dùng để đếm/đo:** `/stream` là MJPEG low-res (hạt <2mm biến mất) và nước
đang chảy (đếm trùng qua nhiều khung). Đếm/đo bản chất là **single-frame high-res tĩnh** trong cửa
sổ Pump-OFF của Stop-Flow → đó là đường `/capture`/folder, không phải stream.

`preview.py` (tách biệt, **không import `ingest_client`** → không thể ghi DB):
- `python -m ml.infer.preview --source <stream-url | webcam:0 | video.mp4> --weights best.pt --fps 2`
- Kéo khung → `detector.run` → vẽ box/label bằng OpenCV → hiển thị (`cv2.imshow`).
- **Throttle** (`--fps`, mặc định ~2): detector không cần theo kịp 25fps.
- Nhãn hiển thị ghi rõ **"PREVIEW — not logged"**; số đếm trên khung là tức thời, không phải con số
  kiểm toán.
- Giai đoạn này test bằng webcam/video (rig chưa có stream); cắm URL `/stream` khi rig lên.

## Error handling
- Load model lỗi / thiếu weights → **fail fast** đầu chương trình (chưa xử ảnh nào).
- Mỗi ảnh độc lập: detect/POST lỗi → log, `failed++`, **chạy tiếp** (không abort cả folder).
- Phân loại response ingest: `201`→created; `200 already_exists`→skipped (bình thường khi chạy lại);
  `422/413`→log lỗi validate + failed; lỗi mạng/`5xx`→failed.
- Cuối mẻ: tổng kết + list failed; exit code ≠0 nếu có failed (script hoá được).
- `--dry-run`: in kết quả + (tuỳ chọn) lưu ảnh vẽ box ra `ml/infer_out/`, **không** POST.

## Testing
- `mapper.py` — unit thuần: detection giả → assert `bbox/area_px/size_mm/centroid`; assert **cảnh báo
  px_per_mm** khi thiếu.
- sanitize `sample_code` — tên file có space/ký tự lạ/`..` → ra chuỗi khớp regex.
- `ingest_client.py` — test với FastAPI `TestClient` (dựng app ở
  [main.py](../../../web/backend/app/main.py)) hoặc mock httpx: 201/200/422 → đếm đúng.
- `detector.py` — smoke test: có `best.pt` thì 1 ảnh ra ≥0 box đúng định dạng; không có weights → `skip`.

## Verify end-to-end (bằng chứng thật)
1. Dựng web backend local (`uvicorn app.main:app` ở [web/backend](../../../web/backend)).
2. Có `best.pt` (Phase B) + vài ảnh test trong 1 folder.
3. `python -m ml.infer <folder> --weights ml/models/best.pt --api-url http://localhost:8000 --device-id pc-infer --px-per-mm <n>`.
4. Mở dashboard (Module 5+6) → sample mới xuất hiện, count/label/size hiển thị, ảnh xem được.
5. **Chạy lại y hệt** → tất cả thành `already_exists`, dashboard **không** nhân đôi (chứng minh idempotent).

## Ngoài phạm vi (YAGNI)
- `Esp32CaptureSource` code thật (chỉ để interface chờ sẵn — Phase D, khi rig chụp nét).
- Service chạy nền theo chu kỳ Stop-Flow.
- Export/benchmark TFLite, deploy nhúng (Nhánh 2 / Phase C).
- Không sửa web backend; không đổi schema `particles`.
