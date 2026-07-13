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

Quy tắc quyết định (đã ghi trong plan đã duyệt): nếu số đo cho thấy khả thi trên
ESP32-CAM ở latency/flash/RAM chấp nhận được → giữ detector thật (có size từ box).
Nếu không → chuyển hướng Edge Impulse FOMO cho ESP32-CAM, chấp nhận mất size
per-particle (ghi rõ hạn chế này, không âm thầm bỏ qua).

## Phase D — Sau này, khi rig chụp ảnh thật được

Xem chi tiết trong plan đã duyệt (`~/.claude/plans/...`) — quay lại đúng project
Roboflow này, upload ảnh thật, auto-label bằng model đã train, fine-tune, đo lại
Phase C, rồi mới cập nhật `CLAUDE.md`/`ai_model_plan.md`.
