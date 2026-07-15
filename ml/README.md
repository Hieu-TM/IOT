# Aqua Scope — object-detection model (Roboflow + microplastics-m7mf5)

Đây là thư mục làm việc cho hướng **object detection end-to-end** (đảo lại quyết định
"hybrid CV + classifier crop" trong `CLAUDE.md`/`ai_model_plan.md` — xem lý do ở phần
Context của plan đã duyệt). Mục tiêu board: **ESP32-CAM (AI-Thinker, OV2640)**, không
phải XIAO ESP32-S3.

> Tham khảo thêm: `../Efficient_Detection_of_Microplastics_on_Edge_Devices_With_Tailored_Compiler_for_TinyML_Applications.pdf`
> (đã có sẵn trong repo, chưa đọc được bằng công cụ ở đây vì máy thiếu poppler/pdftoppm —
> tự mở file này, rất có thể đã có sẵn số liệu RAM/latency cho đúng bài toán "microplastics
> detection trên thiết bị nhúng" mà Phase C bên dưới cần).

## Phase A — Dựng project Roboflow + gộp dataset (làm tay trong Roboflow UI)

Bước này cần tài khoản Roboflow của bạn — Claude không tự đăng nhập/tạo tài khoản hộ được.

1. Đăng nhập https://roboflow.com (hoặc tạo workspace mới nếu chưa có).
2. Mở https://universe.roboflow.com/iam/microplastics-m7mf5 → bấm **Fork Dataset**
   → chọn workspace của bạn. Đặt tên project mới, ví dụ `aqua-scope-debris-detector`
   (Object Detection).
3. **Trước khi làm gì khác: lướt qua vài chục ảnh mẫu trong project vừa fork.**
   Xác nhận xem ảnh có giống kiểu backlit-silhouette-chụp-từ-trên-xuống-dòng-nước
   của Aqua Scope hay không (nhiều khả năng là ảnh nhựa chụp trên bàn/qua kính hiển vi
   — domain khác hẳn). Ghi lại nhận xét — nó quyết định việc dataset này có dùng để
   train "thật" được hay chỉ để bootstrap kiến trúc/pipeline.
4. (Tuỳ chọn) Đổi tên lớp `pallet` → `pellet`: **Health Check** hoặc **Classes** tab
   → rename. Không cần vẽ lại nhãn.
5. Bấm **Generate** → chọn augmentation "hợp lệ vật lý":
   - Rotate: 0–360°
   - Flip: horizontal + vertical
   - Brightness/Exposure: nhẹ (±10–15%)
   - Slight zoom/crop: ±10%
   - Gaussian noise: nhẹ
   - **KHÔNG** dùng: perspective warp mạnh, hue/saturation shift (ảnh cuối sẽ là grayscale).
   - Train/Val/Test split: dùng mặc định hoặc chỉnh về ~70/15/15.
6. **Export** dataset version → format **YOLOv8** (hoặc YOLO Darknet/COCO nếu muốn dùng
   script khác) → copy đoạn code `pip install roboflow` + snippet download, hoặc tải
   zip về và giải nén vào `ml/datasets/<tên-version>/`.

Cấu trúc export YOLOv8 thường có dạng:
```
ml/datasets/<version>/
  data.yaml
  train/images, train/labels
  valid/images, valid/labels
  test/images, test/labels
```

### Nơi đặt model weights
- Weights train/tải từ Roboflow đặt tại **`ml/models/best.pt`** (thư mục `ml/models/`
  do bạn tạo khi tải về). Các script/CLI trỏ tới đường này qua `--weights ml/models/best.pt`.
- `ml/models/`, `ml/datasets/`, `runs/`, `*.pt`, `*.tflite` **đã được gitignore** — weights
  và dataset **tái tạo được**, không commit (tránh phình repo).
- Thay vào đó, ghi **nguồn** ở đây để ai cũng tải lại được:
  - Roboflow project: `<workspace>/<project>` (điền sau khi tạo ở Phase A)
  - Dataset version dùng để train: `v<N>`
  - Base model: `yolo11n.pt` (hoặc model bạn chọn)

## Phase B — Train prototype trên PC

```bash
pip install -r ml/requirements.txt
python ml/train_detector.py --data ml/datasets/<version>/data.yaml --epochs 100 --imgsz 416 --model yolo11n.pt
```

Xem kết quả trong `runs/detect/train*/` (confusion matrix, PR curve, `weights/best.pt`).
Nhắc lại: vì ảnh (còn) là dataset public, đây là bài kiểm tra pipeline/kiến trúc,
không phải con số độ chính xác thật ngoài đời — chỉ có ý nghĩa thật sau Phase D
(ảnh thật từ rig).

## Phase C — Export TFLite + đo số thật để chốt nhánh deploy

```bash
python ml/export_tflite.py --weights runs/detect/train/weights/best.pt --imgsz 192 --data ml/datasets/<version>/data.yaml
python ml/benchmark_tflite.py --model best_int8.tflite
```

`benchmark_tflite.py` in ra: kích thước file (≈ flash cần), ước tính tensor arena,
và latency/ảnh đo trên máy (chỉ là ước tính cận trên/dưới — thực tế trên ESP32-CAM sẽ
chậm hơn nhiều vì không có AI accelerator như S3, cần cộng biên độ an toàn).

**Hai nhánh deploy được tách chi tiết trong [deploy_options.md](deploy_options.md)**
(Nhánh 1 = offload xử lý ra phần cứng ngoài, giữ nguyên size; Nhánh 2 = vẫn on-device
trên ESP32-CAM nhưng tối ưu — FOMO+CV / tiling / two-stage / int8). Đọc file đó để
chọn nhánh theo số đo Phase C.

Quy tắc quyết định (đã ghi trong plan đã duyệt): nếu số đo cho thấy khả thi trên
ESP32-CAM ở latency/flash/RAM chấp nhận được → giữ detector thật (có size từ box).
Nếu không → chuyển hướng Edge Impulse FOMO cho ESP32-CAM, chấp nhận mất size
per-particle (ghi rõ hạn chế này, không âm thầm bỏ qua).

## Nhánh 1 — chạy inference trên PC (offload)

Chạy detector đã train trên ảnh (folder/1 ảnh) rồi đẩy kết quả vào dashboard đã có.

```bash
pip install -r ml/requirements.txt
# đặt weights tải từ Roboflow tại ml/models/best.pt
python -m ml.infer <ảnh|folder> --weights ml/models/best.pt \
    --api-url http://localhost:8000 --device-id pc-infer --px-per-mm <n>
```
- `--px-per-mm`: bỏ trống → dùng mặc định 14.0 kèm cảnh báo (size_mm chỉ là placeholder cho ảnh dataset).
- `--dry-run`: chỉ detect + in số hạt, không POST.
- Chạy lại cùng folder là idempotent (sample_code suy từ tên file) → server trả `already_exists`.

Preview trực quan (chỉ để xem, KHÔNG ghi DB):
```bash
python -m ml.infer.preview --source webcam:0 --weights ml/models/best.pt --fps 2
# hoặc --source http://<esp32-ip>/stream  |  --source video.mp4
```

### Kiểm thử end-to-end (thủ công, cần stack thật)

Bước này cần `ml/models/best.pt` thật (tải từ Roboflow), package `ultralytics`
cài được, và backend web đang chạy — **không** chạy được trong môi trường CI/agent
không có các thứ đó; làm tay khi kiểm thử trên máy có đủ điều kiện.

1. Chạy backend web:
   ```bash
   cd web/backend && python -m uvicorn app.main:app --reload
   ```
2. Đảm bảo `ml/models/best.pt` tồn tại (tải từ Roboflow) và chuẩn bị 2–3 ảnh test
   trong một thư mục, ví dụ `ml/_e2e/`.
3. Từ thư mục gốc repo, chạy:
   ```bash
   python -m ml.infer ml/_e2e --weights ml/models/best.pt \
       --api-url http://localhost:8000 --device-id pc-infer --px-per-mm 14
   ```
   Kỳ vọng: mỗi ảnh in một dòng `[created] ... -> <code>` và cuối cùng
   `Summary: N created, 0 already_exists, 0 failed`.
4. Mở dashboard (`http://localhost:8000/`) và xác nhận các sample mới xuất hiện
   đủ count/label/size và ảnh xem được.
5. **Chạy lại đúng lệnh ở bước 3.** Kỳ vọng: mỗi dòng giờ là `[already_exists]`,
   `Summary: 0 created, N already_exists, 0 failed`, và dashboard **không** có
   sample trùng lặp.

`ml/models/` và `ml/_e2e/` là thư mục cục bộ, không commit (`ml/models/` đã có
trong `ml/.gitignore`; nếu tạo `ml/_e2e/` để test, nhớ không add nó vào git).

## Phase D — Sau này, khi rig chụp ảnh thật được

Xem chi tiết trong plan đã duyệt (`~/.claude/plans/...`) — quay lại đúng project
Roboflow này, upload ảnh thật, auto-label bằng model đã train, fine-tune, đo lại
Phase C, rồi mới cập nhật `CLAUDE.md`/`ai_model_plan.md`.
