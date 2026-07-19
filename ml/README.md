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

## Chạy nhanh

### Đo mẫu thật từ board (đường chạy chính)

```bash
# 1. Bật backend web (terminal riêng)
cd web/backend && python -m uvicorn app.main:app --port 8000

# 2. Kiểm tra cấu hình — không gọi API, không in API key
python -m ml.infer --check-config

# 3. Chụp từ board → suy luận → ghi sổ audit, một lệnh
python -m ml.infer --from-board 192.168.1.50 --count 5 --interval 2
```

Board phải chạy [`firmware/aqua_scope_station/`](../firmware/aqua_scope_station/).
IP lấy từ Serial Monitor 115200. Đặt `[station].host` trong `ml/config.local.toml`
thì khỏi gõ `--from-board` mỗi lần.

`device_id` ghi vào sổ audit là **tên board tự báo** (ví dụ `aqua-cam-a1b2c3`),
không phải hằng `ingest.device_id` — trừ khi bạn ép bằng `--device-id`.

### Chạy lại trên ảnh đã có

```bash
python -m ml.infer <thư-mục-ảnh>            # ghi vào DB
python -m ml.infer <thư-mục-ảnh> --dry-run  # chỉ đếm thử, KHÔNG ghi
```

Dashboard: `http://localhost:8000`

**Dùng `--dry-run` khi thử nghiệm.** DB là sổ audit truy xuất nguồn gốc — mỗi
lần chạy thật là một bản ghi vĩnh viễn, không nên tạo rác trong đó. `--dry-run`
vẫn chụp thật từ board nhưng không gửi gì đi.

Hai điều phải nhớ khi đọc kết quả:

- **`size_mm` là placeholder** cho tới khi bạn đo được px/mm thật trên rig. CLI in
  cảnh báo mỗi lần chạy. Với ảnh dataset công khai, số mm hiện ra **không có nghĩa
  vật lý** — đừng trích nó vào báo cáo như số đo thật.
- **Nhãn là hình thái, không phải "nhựa hay không nhựa".** Model chỉ có 4 lớp
  `fiber/film/fragment/pallet`, đều là nhựa. Nó **không có** lớp nào cho bọt khí hay
  chất hữu cơ, nên gặp bọt khí nó vẫn gán vào một trong 4 lớp đó. Vì vậy dashboard
  báo "Loại nhiều nhất" chứ không báo "tỉ lệ nhựa" — model không đo được tỉ lệ đó.

## Hai hướng model (2 backend, cùng một pipeline)

Cùng dùng chung `ml/infer/` (source → detector → mapper → ingest). Chỉ khác ở
tầng detector, chọn bằng `--backend`:

| | Hướng 1 — `local` | Hướng 2 — `roboflow` |
|---|---|---|
| Trạng thái | Chưa làm (hoãn) | **Đã làm xong, đã chạy thật** |
| Weights local | Cần (tự train ra) | Không cần |
| Mạng khi chạy | Không | Có (+ API key) |
| Xuống chip (TFLite) | **Được** | Không |
| Chạy được ngay | Sau khi train | Ngay |

Hai hướng **không** nằm ở hai thư mục khác nhau. Chúng là hai file detector cạnh nhau
trong cùng `ml/infer/`:

```
ml/infer/
├── detector.py           ← hướng 1 (ultralytics, weights .pt)
├── detector_roboflow.py  ← hướng 2 (Roboflow Workflow API)
├── cli.py  mapper.py  ingest_client.py  source.py   ← dùng chung
```

Chỉ hai file detector là khác. Đọc ảnh, quy đổi kích thước, gửi lên web, ghi DB,
dashboard — tất cả dùng chung và **không biết** mình đang chạy hướng nào. Chốt chặn
nằm ở `build_detector()` trong `cli.py`: cả hai detector trả về cùng một kiểu
`DetectionResult`, nên đổi hướng không phải sửa gì phía sau.

Hệ quả cần biết: hai hướng có thể lệch nhau ở **hạt sát mép ảnh**. Roboflow trả về
toạ độ tâm chưa clamp nên hạt chạm mép cho ra toạ độ âm, `detector_roboflow.py` phải
tự clamp; ultralytics thì clamp sẵn. Chênh lệch ở biên là bình thường, không phải bug.

### Đổi hướng chạy

Sửa **`ml/config.local.toml`**:
```toml
[general]
backend = "roboflow"   # hoặc "local"
```

Hoặc tạm thời cho một lần chạy: `python -m ml.infer <thư mục> --backend local`

> **Bẫy hay gặp:** đừng sửa `backend` trong `ml/config.toml`. File `config.local.toml`
> luôn thắng, nên sửa `config.toml` sẽ **không có tác dụng gì** nếu `config.local.toml`
> cũng khai `backend`. Muốn biết cái nào đang thật sự có hiệu lực thì chạy
> `python -m ml.infer --check-config`.

### Cấu hình tập trung

Yeu cau Python 3.11+ (dung tomllib trong thu vien chuan).

Mọi thiết lập nằm ở **`ml/config.toml`** (được commit, tài liệu hoá đầy đủ mọi
khoá — mở file này ra là biết cần cấu hình gì).

Thứ tự ưu tiên: `cờ CLI` > `biến môi trường` > `ml/config.local.toml` > `ml/config.toml` > mặc định trong code.

API key **không bao giờ** để trong `config.toml`. Tạo `ml/config.local.toml` (đã gitignore):
```toml
[general]
backend = "roboflow"

[roboflow]
api_key = "rf_xxxxxxxx"
workspace = "<workspace-slug>"
workflow_id = "<workflow-slug>"
predictions_key = "predictions"   # xem phần probe bên dưới

# Tham số gửi kèm ảnh cho workflow (tuỳ workflow của bạn khai báo gì).
[roboflow.extra_inputs]
model_id = "<project>/<version>"
```
Hoặc dùng biến môi trường: `AQUA_ROBOFLOW_API_KEY`, `AQUA_ROBOFLOW_WORKSPACE`, `AQUA_INGEST_API_URL`, ...

Kiểm tra cấu hình đã đủ chưa (không chạy inference, **không in ra API key**):
```bash
python -m ml.infer --check-config
python -m ml.infer --check-config --backend roboflow
```

### Hướng 2 — Roboflow Workflow API (đã làm xong)

```bash
pip install requests pillow numpy
python -m ml.infer <ảnh|thư mục> --backend roboflow --px-per-mm <n>
```
Không cần weights, không cần ultralytics. Cần mạng + `roboflow.api_key` + `workspace` + `workflow_id`.

**Hệ toạ độ — đã kiểm chứng (2026-07-19):** toạ độ trả về nằm trong hệ toạ độ của
**ảnh gốc**. Xác nhận bằng cách so `image.width/height` trong response với kích thước
decode cục bộ (640×640 == 640×640). Nếu sau này bạn thêm bước resize/crop vào workflow
thì giả định này hỏng — code sẽ **cảnh báo** khi hai kích thước lệch nhau, đừng bỏ qua
dòng cảnh báo đó vì nó làm sai `size_mm` một cách âm thầm.

**Bước bắt buộc lần đầu — dò tên output của workflow.** Không có khoá `predictions`
cố định: mỗi phần tử được khoá theo **tên output do chính workflow đặt**. Chạy probe
một lần để xem cấu trúc thật (chỉ in tên khoá + kiểu, **không in blob base64**):
```bash
python -m ml.infer.probe path/to/anh.jpg
```
Rồi điền tên khoá vừa thấy vào `roboflow.predictions_key` (hỗ trợ đường dẫn có dấu
chấm, vd `model_predictions.predictions`). Để trống thì code **tự dò**.

Cấu trúc response thật (Roboflow serverless bọc kết quả trong `outputs`, khác với
tài liệu chính thức mô tả là một list phẳng):
```
{"outputs": [{"<tên-output>": {"image": {...}, "predictions": [...]}}],
 "profiler_trace": []}
```
Đây từng là một **bug thật**: lớp bọc `outputs` không được bóc, nên đặt
`predictions_key` **đúng theo tài liệu** lại cho ra 0 hạt — và mẫu 0 hạt trong sổ
audit trông y hệt nước sạch. Cơ chế tự dò che mất lỗi này. Giờ đã bóc đúng và
cảnh báo khi `predictions_key` không khớp.

**Đổi model mà không sửa workflow.** Nếu workflow khai `model_id` là `WorkflowParameter`,
đặt nó trong `[roboflow.extra_inputs]` là xong — train model mới chỉ cần đổi một dòng
config, không phải vào UI Roboflow:
```toml
[roboflow.extra_inputs]
model_id = "microplastics-m7mf5-eallk/3"
confidence = 0.5
```
`extra_inputs` cố ý là một bảng mở, không phải các trường đặt tên sẵn: workflow khai
tham số gì là do người dựng workflow quyết. Xem workflow của bạn khai báo gì rồi điền
đúng tên đó.

> **Lưu ý về base workflow:** workflow do Roboflow tự sinh cho project (`… — Base
> Workflow`) **hard-code `model_id` và bị platform khoá không cho sửa**
> (`Cannot modify a project base workflow`). Muốn `model_id` đổi được thì phải **tự tạo
> workflow riêng**. Đừng thử cách bọc base workflow bằng `inner_workflow` rồi truyền
> `model_id` vào — workflow con không khai tham số đó nên sẽ lỗi 500 mọi lần gọi.

**Workflow đang dùng: `aqua-scope-infer`** (tự tạo 2026-07-19). Nó khai `model_id`,
`confidence`, `iou_threshold`, `class_agnostic_nms`, `max_detections` làm
`WorkflowParameter`, nên đổi model = sửa một dòng config.

Trong workspace còn sót workflow `…-logic` **hỏng** (500, đúng lỗi mô tả ở khung trên).
Nó không được dùng và không ảnh hưởng gì tới code, nhưng nên xoá trên UI Roboflow cho
khỏi bấm nhầm — API Roboflow không có endpoint xoá workflow. **Đừng xoá `… — Base
Workflow`**: nó do platform sinh cho project dataset, không phải rác.

### Hướng 1 — tự train (CHƯA LÀM)

Roboflow bản miễn phí **không cho tải weights** đã train trên nền tảng họ, nhưng
**cho tải dataset**. Hướng này tải dataset về, tự train, sở hữu luôn `.pt` — và là
đường **duy nhất** đi tiếp xuống chip (TFLite).

Phần này chưa triển khai (Task 5 + 6 trong plan, đang hoãn). Trạng thái thật hiện tại:

| Thứ cần | Có chưa |
|---|---|
| `ml/models/best.pt` | **chưa** — thư mục `ml/models/` chưa tồn tại |
| `ultralytics` | **chưa cài** |
| Script tải dataset tự động | **chưa có** (Task 6) — `[dataset]` trong config mới chỉ là tham số ghi sẵn, chưa code nào đọc |
| `ml/train_detector.py`, `ml/export_tflite.py` | có |

Nên đổi `backend = "local"` lúc này sẽ **không chạy được** — nhưng nó báo lỗi rõ ràng
(thiếu weights ở đường dẫn nào, cách tạo ra), không phải crash. Backend `local` trong
CLI đã sẵn sàng nhận `ml/models/best.pt` khi có weights:
```bash
python -m ml.infer <ảnh|thư mục> --backend local --weights ml/models/best.pt --px-per-mm <n>
# hoặc bỏ --backend / --weights nếu ml/config.toml đã set general.backend="local"
# và local.weights đúng đường dẫn (mặc định sẵn là ml/models/best.pt)
```
Phase A–C ở trên (fork dataset Roboflow → train → export TFLite) mô tả cách tạo ra
`ml/models/best.pt` này khi hướng 1 được triển khai thật.

### Ghi chú chung

- `--px-per-mm` bỏ trống → dùng mặc định 14.0 **kèm cảnh báo**: `size_mm` chỉ là
  placeholder, không phải hiệu chuẩn thật (với ảnh dataset công khai thì đúng là vậy).
- `--dry-run`: chỉ detect + in số hạt, không POST.
- Chạy lại cùng thư mục là idempotent (sample_code suy từ tên file) → server trả `already_exists`.
- Hai file khác nhau ra cùng `sample_code` (vd `a.jpg` và `a.png`) sẽ bị báo
  `[warn] collision` và **không gửi** — đổi tên file rồi chạy lại.

Preview trực quan (chỉ backend `local`, KHÔNG ghi DB):
```bash
python -m ml.infer.preview --source webcam:0 --weights ml/models/best.pt --fps 2
# hoặc --source http://<esp32-ip>/stream  |  --source video.mp4
```
Preview cố ý không dùng backend `roboflow`: gọi API mỗi khung hình sẽ rất tốn và dễ đụng rate limit.

### Kiểm thử end-to-end

> **Hướng 2 đã chạy thật ngày 2026-07-19** với API key thật: 3 ảnh → Roboflow →
> backend web → SQLite → dashboard. Kết quả 12/12/14 = 38 hạt, chạy lại ra
> `0 created / 3 already_exists`, dashboard hiện `Màng 10/38 · 26%` khớp đúng số
> detector trả về (fiber 9, film 10, fragment 10, pallet 9).
> **Hướng 1 thì chưa** — chưa có weights.

Bước này cần backend đã sẵn sàng (`python -m ml.infer --check-config [--backend ...]`
phải báo `Config OK`) và backend web đang chạy.

1. Chạy backend web:
   ```bash
   cd web/backend && python -m uvicorn app.main:app --reload
   ```
2. Chuẩn bị stack cho backend muốn test:
   - `local`: đảm bảo `ml/models/best.pt` tồn tại (tải/train từ Roboflow).
   - `roboflow`: đảm bảo `ml/config.local.toml` (hoặc biến môi trường) đã có
     `api_key` + `workspace` + `workflow_id` thật, và đã chạy `ml.infer.probe`
     một lần để set `predictions_key`.
   Chuẩn bị 2–3 ảnh test trong một thư mục, ví dụ `ml/_e2e/`.
3. Từ thư mục gốc repo, chạy (ví dụ backend `roboflow`):
   ```bash
   python -m ml.infer ml/_e2e --backend roboflow \
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
