# Hướng 1 — Nghiên cứu phương pháp tự train model & tích hợp xuống chip mà giữ độ chính xác

> **Phạm vi tài liệu này:** phần **nghiên cứu phương pháp** (Phase nghiên cứu) cho **Hướng 1**
> trong `ml/README.md` — tức nhánh `backend = "local"`: **tự train weights (`.pt`), sở hữu
> model, và là con đường DUY NHẤT đi xuống chip qua TFLite int8**. Hướng 2 (`roboflow`,
> gọi API) đã làm xong và đã chạy thật; hai hướng thay thế được cho nhau khi một bên lỗi
> (xem bảng "Hai hướng model" trong `ml/README.md`).
>
> **Dataset đã có** (để ở máy — `ml/datasets/` đã gitignore nên không thấy trong repo). Vì vậy
> chặn cứng không còn là "thiếu dữ liệu"; hai câu hỏi thật lúc này là: **(a)** model tự train có
> **chạy nổi trên ESP32-CAM** để ra kết quả cuối không, và khi ghép thêm các tác vụ khác (camera,
> WiFi, CV, bơm) thì vướng gì (→ §3.1, §3.2); **(b)** dataset đó có **khớp domain deploy** (ảnh
> backlit-silhouette từ chính rig) không — nếu là dataset công khai thì số accuracy chỉ có nghĩa
> sau khi fine-tune trên ảnh thật (§8). Liên quan: `ml/README.md` (Phase A–D), `ai_model_plan.md`
> (pipeline hybrid & Track A/B), `variants/README.md` (bài NeuralCasting/1D — xem §6).

---

## 1. Ba thứ đừng nhầm lẫn với nhau

Trong repo này có **ba** con đường AI khác nhau. Chúng dễ bị gộp làm một khi nói "model":

| | Modality (dữ liệu vào) | Model | Ở đâu | Trạng thái |
|---|---|---|---|---|
| **Hướng 1** (tài liệu này) | **Ảnh 2D** (backlit silhouette) | Object detector (YOLO `yolo11n`) tự train → TFLite int8 | `ml/infer/detector.py`, `ml/train_detector.py`, `ml/export_tflite.py` | **Chưa làm** (weights đang chờ) |
| **Hướng 2** | Ảnh 2D | Detector chạy trên Roboflow Workflow API (hosted) | `ml/infer/detector_roboflow.py` | **Xong, đã chạy thật** |
| **Biến thể NeuralCasting / 1D** | **Tín hiệu điện áp 1D** (photodiode → TIA → ADC, cửa sổ 41 mẫu) | MLP/GRU/1D-CNN cực nhỏ, PTQ int8, compile ONNX→C thuần | `variants/` (chỉ là nghiên cứu phương án) | Nghiên cứu, chưa build |

**Phân biệt CHẠY Ở ĐÂU (mấu chốt, đã rõ sau nghiên cứu §3.0):** cả Hướng 1 và Hướng 2 hiện đều
chạy trên **PC** (`ml/infer/` là code PC — YOLO detector trên PC cho count/size/type). Việc **"xuống
chip" ESP32-CAM** là mục tiêu tương lai và là chủ đề của tài liệu này. Nghiên cứu khả thi (§3.0) kết
luận: **YOLO end-to-end KHÔNG chạy nổi on-device trên ESP32-CAM**; con đường on-device khả thi là
**pipeline HYBRID** (classical CV lo đếm+size, một **Tiny classifier tự train** lo phân loại). Do đó:
- **YOLO tự train (`train_detector.py`)** vẫn hữu ích — nhưng cho **inference trên PC / offload**
  (đúng như `ml/infer` đang chạy), **không** phải để nạp xuống ESP32-CAM.
- **"Tự train xuống chip" trên ESP32-CAM** = train **Tiny classifier** ở Giai đoạn 2 của hybrid,
  không phải train YOLO. (Trùng kiến trúc hybrid của `ai_model_plan.md`.)

**Về NeuralCasting:** bài NeuralCasting và bài toán ảnh 2D là **hai model xử lý khác hẳn nhau** —
một bên **chuỗi 1D 41 mẫu**, một bên **ảnh 2D**. NeuralCasting **tham khảo được về triết lý** (int8,
sinh mã C tĩnh, model tí hon) nhưng **không áp dụng thẳng** (lý do kỹ thuật ở §6).

---

## 2. Bài toán cốt lõi: "giữ độ chính xác khi xuống chip" thực chất là gì

Train xong trên PC (float32) thì model đạt độ chính xác X. Khi ép nó chạy trên MCU, ta buộc phải
**thu nhỏ / lượng tử hóa / đổi runtime**, và mỗi bước đều có thể làm tụt X. "Giữ độ chính xác"
= **kiểm soát cho X không tụt quá ngưỡng chấp nhận** qua từng bước biến đổi. Các nguồn làm tụt:

1. **Lượng tử hóa float32 → int8** — nguồn tụt phổ biến & lớn nhất. Trọng số và activation bị
   ép về 256 mức. Detector (nhiều lớp, activation dải rộng) nhạy hơn classifier nhỏ.
2. **Giảm độ phân giải đầu vào** (train `imgsz=416` → export `imgsz=192`, xem `config.toml`
   `[export].tflite_imgsz`). Hạt <2mm chỉ vài px; giảm imgsz làm hạt nhỏ **biến mất** → tụt recall.
3. **Thu nhỏ kiến trúc** (pruning / chọn model nhỏ hơn) — bớt tham số thì bớt sức biểu diễn.
4. **Đổi runtime / tập toán tử** — TFLite-Micro / ESP-DL không hỗ trợ mọi op; op bị thay thế/xấp xỉ
   có thể lệch kết quả so với TF trên PC.
5. **Train↔deploy mismatch** — không phải "xuống chip" nhưng là thủ phạm số 1 khiến "PC 95%,
   board 60%": khác exposure, khác backlit, khác cách tiền xử lý/normalize crop. (Xem
   `ai_model_plan.md` Phase 10 — điểm này áp dụng y nguyên cho Hướng 1.)

> **Nguyên tắc đo:** không được nói "giữ được độ chính xác" bằng cảm tính. Phải đo **mAP (và
> recall theo từng lớp) trên tập test giữ riêng, ở CHÍNH định dạng int8 sẽ deploy**, rồi so với
> bản float32. Cách đo chi tiết ở §7.

---

## 3. Ràng buộc phần cứng thật (phải biết trước khi chọn kỹ thuật)

**Board deploy đã chốt: ESP32-CAM (AI-Thinker, OV2640)** — theo `ml/README.md`. Toàn bộ tài liệu
này giả định đích là ESP32-CAM; mọi lựa chọn kỹ thuật bên dưới đều bám ràng buộc của board này.

Đặc điểm phần cứng quyết định của ESP32-CAM:

- Lõi **Xtensa LX6** (ESP32 thường), **không có** lệnh vector AI, **không có** accelerator int8
  → chạy CNN nặng rất chậm. Ngân sách latency/RAM vì thế **cực chặt**.
- Có **PSRAM** (thường 4MB trên module AI-Thinker) — dùng để chứa `tensor_arena` và buffer ảnh
  (`ps_malloc`); nhưng PSRAM chậm hơn SRAM nội, càng siết thêm latency.

Hệ quả: **deploy YOLO trên ESP32-CAM có ngân sách latency/RAM cực chặt**; rất có thể detector thật
không chạy nổi ở tốc độ dùng được và phải lùi về FOMO (mất size per-particle) — đúng như "quy tắc
quyết định" đã ghi trong `ml/README.md` Phase C. **Đây là ràng buộc cố định, không phải lựa chọn
board** — mọi kỹ thuật §4 dưới đây là để ép model vừa với ESP32-CAM, không phải để đổi sang board mạnh hơn.

### 3.0 KẾT LUẬN NGHIÊN CỨU KHẢ THI — chốt kiến trúc HYBRID

> Nguồn: báo cáo deep-research `Thiet_Ke_TinyML_ESP32CAM.pdf` (sinh từ prompt
> `ml/research_prompt_esp32cam_cv.md`, 2026-07). Các số dưới đây là **ước tính bậc độ lớn** của báo
> cáo (một số trích blog/Reddit) — cùng bậc với phân tích §3.1/§3.2, **vẫn phải đo trên board** bằng
> `benchmark_tflite.py` + test thật trước khi coi là số chốt. Không trích các số này vào báo cáo cuối
> như số đo thực.

**Kết luận: kiến trúc on-device khả thi duy nhất trên ESP32-CAM là PIPELINE HYBRID**, không phải
YOLO end-to-end. Bảng so sánh ba ứng viên (số từ báo cáo):

| Chỉ số | YOLOv8-nano int8 @160 (end-to-end) | **HYBRID (CV + Tiny classifier)** ✅ | FOMO 96×96 |
|---|---|---|---|
| Độ trễ toàn hệ | **12.5–18.2 giây/khung** → quá nhiệt, brownout | **250–550 ms** (mẻ ~15 hạt) | ~862 ms |
| Tensor arena | 650–900KB (**buộc PSRAM**) | **12–24KB** (CV) + 16KB (classifier) → **SRAM nội** | vài chục–~trăm KB |
| Flash | ~2.5MB | **25–60KB** | nhỏ |
| Giữ được SIZE? | Có nhưng **kém** (imgsz nén mạnh) | **Có, chính xác tuyệt đối** (đo trên VGA gốc, sai số <0.07mm) | **KHÔNG** (chỉ centroid) |
| Ổn định | Thấp (nóng, sụt áp) | **Cực cao** (CPU chạy chu kỳ ngắn) | Trung bình |

**Kiến trúc hybrid (chốt):**
- **Giai đoạn 1 — Classical CV** (không AI): ảnh **VGA 640×480 grayscale** → **ngưỡng Otsu thích nghi**
  → **Connected Components (Union-Find)** quét line-by-line, chỉ **<5KB SRAM nội**, **120–250ms** →
  xuất **count + bounding box + diện tích + chu vi** (đếm & phân bố kích thước, chính xác trên ảnh gốc).
- **Giai đoạn 2 — Tiny classifier** (đây là thứ "tự train xuống chip"): mỗi blob → crop **32×32
  grayscale** → Tiny CNN hoặc MLP → nhãn loại. Arena **12–24KB nằm trong SRAM nội**, không đụng PSRAM.

Điều này **hòa giải** đúng với `ai_model_plan.md` (vốn đã mô tả hybrid CV + classifier crop) và với
Track A/B ở đó: **Track A** (đặc trưng hình học thủ công + classifier tí hon) đủ tách **bubble**
(circularity C≈1.0, tỉ lệ sáng tâm R_I≫1.0) và **fiber** (aspect ratio AR≥4.5); **Track B (CNN)**
chỉ **bắt buộc cho ranh giới khó plastic vs organic** (khác nhau ở texture/độ trong, hình học thủ
công không biểu diễn được). → Làm Track A trước, chỉ leo Track B khi cần.

Con số phải **đo**, không đoán (dùng `ml/benchmark_tflite.py`): kích thước file `.tflite` (≈ flash
cần), tensor arena ước tính (≈ RAM cần, phải nằm trong PSRAM qua `ps_malloc`), latency/ảnh. Lưu ý
benchmark trên PC chỉ là ước tính — ESP32-CAM **chậm hơn nhiều** vì không có accelerator.

### 3.1 Model có chạy nổi trên ESP32-CAM không? (ước tính ngân sách)

> **Các số dưới đây là ước tính bậc độ lớn (order-of-magnitude) để RA QUYẾT ĐỊNH ĐI/KHÔNG, không
> phải số đo.** Số thật phải lấy từ `benchmark_tflite.py` + đo trên board. Nhưng ngay cả ước tính
> thô cũng đủ để thấy trước "có khả thi hay không".

**Ngân sách phần cứng ESP32-CAM (AI-Thinker):**

| Tài nguyên | Có | Ghi chú siết chặt |
|---|---|---|
| **SRAM nội** | ~520KB tổng | Sau khi IDF + WiFi + camera driver khởi động, **heap trống chỉ còn ~150–250KB**, lại phân mảnh. DMA cần RAM nội liền mạch. |
| **PSRAM** | 4MB (QSPI ~80MHz) | Chậm hơn SRAM nội nhiều lần; chứa framebuffer + weights + tensor arena — nhưng **không đủ cho tất cả cùng lúc** (xem §3.2). |
| **Flash** | 4MB | Chứa code + weights + web assets. Weights model int8 ăn phần lớn nếu để nguyên. |
| **CPU** | 2× Xtensa LX6 @240MHz | **Không SIMD, không vector, không NN-accel.** Conv int8 chạy bằng ALU số nguyên vô hướng → chậm. |

**Ứng viên A — YOLO `yolo11n` int8 @ imgsz 192 (detector thật, giữ được size):**
- Trọng số: `yolo11n` ~2.6M tham số → int8 ~**2.6MB** → vừa 4MB flash nhưng chật; nên nạp vào PSRAM.
- Tensor arena (activation đỉnh): ước tính ~**0.5–1.5MB** → bắt buộc PSRAM.
- Tính toán: ở 192×192 ~**0.5–0.6 GMAC/ảnh**. Với throughput int8 vô hướng thực tế của LX6 (lạc quan
  ~50–100 MMAC/s), một lần suy luận ≈ **~5–12 giây** (có thể hơn). → **Quá chậm cho video/real-time.**

**Ứng viên B — FOMO 96×96 grayscale (phương án lùi, MẤT size per-particle):**
- Model tí hon (vài chục KB), arena vài chục–~trăm KB (có thể nhét RAM nội hoặc PSRAM).
- Latency trên ESP32-CAM (không accel) ước ~**0.5–2 giây/ảnh** (số EI công bố ~vài trăm ms là trên
  dòng CÓ accel; LX6 chậm hơn vài lần).
- Đánh đổi: chỉ trả **tâm hạt (centroid), không có bounding box → mất phân bố kích thước** — đúng
  hạn chế đã ghi ở `ml/README.md` Phase C & `CLAUDE.md`.

**Kết luận đi/không:**
1. **YOLO thật on-device ESP32-CAM: gần như KHÔNG khả thi ở latency dùng được** nếu cần nhiều
   khung/giây. Đây chính là lý do `ml/README.md` Phase C đặt sẵn quy tắc "lùi FOMO".
2. **NHƯNG chu kỳ Stop-Flow cứu bàn thua:** hệ này **không phải video real-time**. Chu kỳ là
   bơm→dừng 1–2s→**chụp 1 khung→suy luận→xả→lặp**, lấy mẫu **theo mẻ/định kỳ** (xem `application-context`
   trong `CLAUDE.md`). Nếu mỗi mẫu chỉ cần **vài khung** và cadence lấy mẫu là **vài phút/mẻ**, thì
   một lần suy luận **3–8 giây vẫn có thể CHẤP NHẬN được**. → Với QC nước đầu vào theo mẻ, **detector
   chậm-mà-đúng có thể vẫn dùng được** — điều mà nếu đây là camera giám sát 30fps thì đã loại thẳng.
3. Điều kiện để (2) đúng: **số khung/mẫu nhỏ** (latency nhân lên theo số khung), và **cho phép khối
   suy luận chạy tuần tự** không bị tác vụ khác chen (§3.2).

4. **Nhưng đừng dựa vào (2) khi có lựa chọn tốt hơn:** báo cáo `Thiet_Ke_TinyML_ESP32CAM.pdf` ước
   tính YOLO thật ~**12–18 giây/khung** (chậm hơn ước tính lạc quan ~5–12s ở trên do băng thông
   PSRAM QSPI ~40MB/s + latency truy cập activation), đủ để **quá nhiệt/brownout** ngay cả trong chu
   kỳ Stop-Flow. → Vì vậy §3.0 **chốt HYBRID**: classical CV (120–250ms) lo đếm+size, Tiny classifier
   (arena 12–24KB SRAM nội) lo loại → tổng **250–550ms**, giữ nguyên size. Đây mới là con đường
   on-device thật; YOLO on-device chỉ là "về lý thuyết có thể nếu cadence đủ rộng", không nên chọn.

→ **Cách chốt thật:** với **Tiny classifier** (hybrid) → export int8 → `benchmark_tflite.py` lấy
size/arena/latency PC → nhân hệ số an toàn cho LX6 → xác nhận arena vừa SRAM nội. Với **classical CV**
→ đo thời gian CCL trên VGA thật trên board. Nếu vẫn không đủ (RAM/latency) → FOMO (mất size) **hoặc**
offload NN sang Hướng 2 (§3.2 cuối).

### 3.2 Khi thêm các tác vụ khác — tranh chấp tài nguyên

Model không chạy một mình. Hệ đầy đủ còn có: **(1)** chụp camera (JPEG) · **(2)** giải nén JPEG →
xám/RGB cho CV · **(3)** classical CV (threshold + connected components: đếm + size) · **(4)** suy
luận NN · **(5)** WiFi + HTTP đẩy kết quả lên `web/` backend · **(6)** điều khiển bơm/MOSFET theo
thời gian · **(7)** ghi log truy xuất. Ghép chúng lại sinh các xung đột **không thấy khi chạy model lẻ**:

1. **Tràn PSRAM (dung lượng):** framebuffer camera + weights (2.6MB) + arena (~1MB) **không cùng
   sống trong 4MB PSRAM** được. Riêng giải nén UXGA→RGB565 đã là 1600×1200×2 = **3.84MB** → nuốt gần
   hết PSRAM. → **Bắt buộc:** làm việc ở VGA, và **giải phóng buffer camera trước khi cấp arena** (không
   giữ đồng thời).
2. **RAM nội × WiFi (thủ phạm kinh điển của ESP32-CAM):** stack WiFi/TCP cần ~40–50KB **RAM nội liền
   mạch**; camera driver cũng cần RAM nội cho DMA descriptor. Hai bên giành nhau → lỗi quen thuộc
   "camera init fail / no mem / Guru Meditation khi bật WiFi". → **Bắt buộc:** đặt framebuffer trong
   PSRAM (`CAMERA_FB_IN_PSRAM`), giữ heap nội càng trống càng tốt.
3. **Băng thông PSRAM (tranh chấp bus):** DMA camera ghi framebuffer vào PSRAM **cùng lúc** inference
   đọc weights/activation từ PSRAM → cả hai chậm lại (chung bus QSPI). → **đừng chụp và suy luận song song.**
4. **Flash/XIP:** nếu weights nằm trong flash (mmap), inference đọc weights **giành cache với việc nạp
   lệnh** (XIP) → CPU stall. → **nạp weights vào PSRAM một lần lúc boot.**
5. **Hai lõi (dual-core):** ghim WiFi/giao tiếp vào core 0, CV+inference vào core 1. Nhưng một lần
   suy luận vài giây **ôm trọn core 1** → **watchdog (TWDT) có thể bắn** → phải feed WDT hoặc chia
   nhỏ/yield trong vòng suy luận.
6. **Điện/brownout:** camera + WiFi TX + CPU 240MHz + đóng cắt MOSFET bơm 12V → đỉnh dòng lớn; board
   rẻ hay **sụt áp reset**. → nguồn 5V/2A chắc + tụ bù (đã ghi ở điện của bơm trong `CLAUDE.md`),
   và tránh phát WiFi **đúng lúc** chụp/suy luận.
7. **Timing chu kỳ:** khối suy luận vài giây **chặn vòng Stop-Flow** → phải thiết kế chu kỳ **quanh**
   latency đó, và log timestamp cho đúng (yêu cầu traceability).

**Kiến trúc khuyến nghị trên ESP32-CAM = máy trạng thái TUẦN TỰ, không đa nhiệm đồng thời:**
```
[dừng bơm, lắng 1–2s] → [chụp → PSRAM] → [giải nén VGA xám] → [CV: đếm + size]
   → [giải phóng framebuffer] → [inference: whole-frame HOẶC từng crop] → [giải phóng arena]
   → [bật WiFi → upload web/ → tắt WiFi] → [xả bơm] → lặp
```
Chỉ **một** hộ tiêu thụ bộ nhớ lớn sống tại mỗi thời điểm → tránh sạch mục 1–3.

**Nếu tuần tự vẫn không đủ (latency×khung > thời gian mẻ, hoặc RAM vẫn tràn):** đây đúng là lý do
**Hướng 2 tồn tại như phương án thay thế** — ESP32-CAM chỉ **chụp + (tuỳ chọn) CV + upload ảnh**,
còn NN nặng để **offload** (web backend / Roboflow / một máy đồng hành). Đổi lại: mất tính tự trị,
cần mạng. **Đây chính là tiêu chí chọn Hướng 1 (on-device) vs Hướng 2 (offload):** số đo §3.1 +
tranh chấp §3.2 quyết định, không phải sở thích.

---

## 4. Danh mục kỹ thuật giữ độ chính xác (xếp theo thứ tự nên thử)

### 4.0 Chọn kiến trúc "nhỏ từ gốc" (đòn bẩy lớn nhất, rẻ nhất)
Cách rẻ nhất để không phải cứu accuracy là **đừng bắt đầu bằng model quá to rồi ép nhỏ**. Chọn
backbone nhỏ ngay từ đầu:
- Hiện `config.toml` chọn `yolo11n.pt` (nano) — đúng hướng. Có thể cân nhắc các biến thể "picodet /
  yolo-nano / nas nhỏ" nếu `n` vẫn quá nặng cho ESP32-CAM.
- **Tỉ lệ chi phí/độ chính xác thường tốt hơn khi chọn model nhỏ + train kỹ**, so với model to rồi
  prune/quantize mạnh tay.

### 4.1 Lượng tử hóa — PTQ trước, QAT khi cần (bắt buộc để xuống chip)
Hai nhánh:

**PTQ (Post-Training Quantization) — làm TRƯỚC.**
- Là cái `ml/export_tflite.py` đang làm: `model.export(format="tflite", int8=True, imgsz=..., data=...)`.
  Ultralytics tự dùng `data.yaml` để lấy **representative dataset** hiệu chỉnh thang int8.
- **Full-integer int8** (weight + activation int8) là bản chạy nhanh nhất trên MCU; cần
  representative dataset **đại diện đúng phân bố ảnh thật** (vài trăm ảnh train). Rep dataset kém
  đại diện = thang đo sai = tụt accuracy nhiều.
- **Bắt buộc: đo accuracy trước/sau PTQ trên tập test.** Số từ báo cáo: với **Tiny classifier
  silhouette 32×32** (đặc trưng dựa trên hình thái biên, tương phản cao) PTQ int8 chỉ **tụt 0.5–1.2%**
  so với FP32 — rất nhỏ. Ngược lại PTQ cho **YOLO end-to-end** tụt **mAP 4–8%** vì các đầu hồi quy
  bounding box rất nhạy với sai số lượng tử. → Thêm một lý do nữa để hybrid (train classifier) thắng
  YOLO on-device.

**QAT (Quantization-Aware Training) — làm khi PTQ tụt quá ngưỡng.**
- Chèn "fake quantization" vào lúc train để model **học cách chịu đựng int8**; báo cáo ước tính QAT
  hồi được **1.5–3.0%** accuracy mà PTQ thô đánh mất, nhưng pipeline **đắt** (cần TF Model
  Optimization Toolkit, train lâu gấp nhiều lần).
- Với ảnh **silhouette tương phản cao, PTQ đã đủ** → thường **không cần QAT**. Chỉ cân nhắc khi
  classifier bị thu nhỏ tối đa (<10K tham số) hoặc phải tách các lớp ranh giới cực mờ.

> Quy tắc: **PTQ → đo → (nếu tụt) QAT**. Không làm ngược. Với hybrid classifier, nhiều khả năng dừng ở PTQ.

### 4.2 Độ phân giải — chụp VGA, KHÔNG tiling cho khâu phát hiện (chốt theo báo cáo)
Với hybrid, "độ phân giải model" tách làm hai: (a) ảnh **CV nhìn** để đếm+size, (b) crop **classifier
nhìn**. Số từ báo cáo (ở ~14 px/mm, working distance 40mm):

| Độ phân giải chụp | Hạt 2.0mm | Hạt 0.5mm | RAM (xám 1B/px) | CCL |
|---|---|---|---|---|
| **VGA 640×480** ✅ | 28 px (đủ chi tiết) | 7.0 px (đủ nhận biên) | 307KB | khả thi (stream/PSRAM) |
| QVGA 320×240 | 14 px (mất biên) | 3.5 px (dễ nhầm nhiễu) | 77KB | dễ (SRAM nội) |
| QQVGA 160×120 | 7 px (biến dạng) | 1.7 px (**biến mất**) | 19KB | dễ nhưng **không đo được** |

- → **VGA là tối thiểu bắt buộc** cho khâu đo size; QVGA/QQVGA làm hạt <1mm biến mất/răng cưa → sai
  phân bố kích thước.
- **Tiling bị LOẠI cho khâu phát hiện:** báo cáo tính SXGA→ô 160×160 ≈ 70 ô × 150ms = **10.5 giây**
  + phức tạp ghép biên (IoU toàn cục, dễ tràn đệm). Thay vào đó: **CCL vô hướng quét line-by-line
  trực tiếp trên VGA từ PSRAM** (không tiling, không phình SRAM), rồi mới crop 32×32 cho classifier.

### 4.3 Pruning (cắt tỉa)
Bỏ bớt trọng số/kênh ít quan trọng để giảm kích thước & tăng tốc.
- **Bắt buộc structured pruning** (bỏ cả kênh/filter) trên LX6: báo cáo nêu rõ **LX6 không có bộ
  tăng tốc ma trận thưa** nên **unstructured pruning (đưa trọng số lẻ về 0) KHÔNG tăng tốc thực tế**
  — chỉ structured (bỏ hẳn filter) mới giảm được số phép tích chập vô hướng của CPU.
- Sau prune **phải fine-tune lại** để hồi accuracy. Với Tiny classifier vốn đã nhỏ, prune chỉ khi cần ép thêm.

### 4.4 Knowledge Distillation (chưng cất tri thức)
Train một model "teacher" to/chính xác trên PC (vd MobileNetV2 alpha 0.5), rồi dạy "student" Tiny CNN
(vài lớp conv nhẹ, cái sẽ xuống chip) bắt chước phân bố logits của teacher → student đạt accuracy
**vượt trội so với train từ đầu**. Báo cáo đề xuất **thứ tự kết hợp tối ưu**:
```
Train Teacher (FP32) → Distill sang Student (FP32) → Structured Pruning → Fine-tune (FP32) → PTQ (INT8)
```
- Hữu ích khi Tiny classifier vẫn phải giữ recall cao. Đắt về công train, để dành khi PTQ thẳng chưa đủ.

### 4.5 Chọn runtime/compiler tối ưu cho ESP32-CAM
Cùng một `.tflite` int8, chạy trên runtime khác nhau ra latency khác nhau (accuracy gần như không
đổi, nhưng tốc độ đổi nhiều — mà tốc độ mới là thứ quyết định detector có sống nổi trên ESP32-CAM
không). Lưu ý: ESP32-CAM là ESP32 thường (LX6), **không có** accelerator, nên đừng kỳ vọng cú tăng
tốc int8 SIMD như trên dòng có accelerator — các runtime dưới đây chỉ giúp trong giới hạn của LX6.
Bảng so sánh (theo báo cáo):

| | ESP-DL | TFLite-Micro | **EON Compiler (Edge Impulse)** ✅ |
|---|---|---|---|
| Hỗ trợ op | Hạn chế (model mẫu của hãng) | Rất rộng | Rộng (qua bộ chuyển đổi EI) |
| Tốc độ trên LX6 | Thấp (mã tối ưu hướng LX7/S3) | Thấp (op reference vô hướng) | **Cao nhất** (C++ tĩnh phẳng, bỏ interpreter) |
| RAM | Trung bình | Lớn (interpreter động) | **Thấp nhất** (tiết kiệm 25–65% nhờ lịch đệm tĩnh) |
| Flash | ~150KB | 100–180KB (thư viện interpreter) | **Thấp nhất** (chỉ op thực dùng, −10–35%) |
| Ước tính tài nguyên trước khi nạp | Khó | Phải chạy mới biết arena | **Dễ** (báo RAM/ROM tĩnh khi biên dịch) |

- **Khuyến nghị: EON Compiler** cho Tiny classifier trên ESP32-CAM — sinh **C++ tĩnh phẳng**, loại bỏ
  interpreter động của TFLM → tiết kiệm tối đa SRAM nội quý giá. ESP-DL tối ưu cho LX7/S3 nên **kém
  trên LX6**; TFLM rộng op nhưng chậm + nặng RAM.
- **Bố trí bộ nhớ (memory map) bắt buộc:** trọng số model để ở **Flash XIP — TUYỆT ĐỐI không nạp vào
  RAM**; **SRAM nội** = driver WiFi/DMA + tensor arena tí hon (classifier); **PSRAM** = framebuffer
  camera + bộ đệm ảnh VGA xám. Khai báo đệm CCL + arena dạng **mảng static** (cấm `malloc()` động
  trong vòng lặp → chống phân mảnh heap gây sập sau vài ngày chạy).
- **NeuralCasting**: sinh mã C thuần ONNX→C, **nhưng chỉ cho model nhỏ (MLP/GRU/1D-CNN)** — xem §6.
  (Triết lý "sinh C tĩnh, bỏ interpreter" của nó chính là cái EON Compiler làm cho ảnh.)

---

## 5. Quy trình đề xuất — TÁCH hai đường: PC/offload (YOLO) và on-device (hybrid)

Sau §3.0, "Hướng 1" tách làm hai đích khác nhau, dùng model khác nhau:

### 5A. Đường PC / offload — YOLO detector (đã có script, cho Hướng 1 `local` chạy trên PC)
```
[1] Dataset → gán nhãn → export YOLO → ml/datasets/<version>/
[2] Train:  python ml/train_detector.py --data .../data.yaml --model yolo11n.pt
      → đo mAP + recall/lớp trên TEST giữ riêng (baseline float32)
[3] (tuỳ chọn) PTQ int8:  python ml/export_tflite.py ...  → benchmark_tflite.py
[4] Chạy inference trên PC:  python -m ml.infer <thư mục> --backend local --weights ml/models/best.pt
```
Đây là những gì `ml/infer` đang hướng tới — YOLO trên PC/offload cho count/size/type. **KHÔNG nạp
YOLO này xuống ESP32-CAM** (§3.0: 12–18s, không khả thi).

### 5B. Đường on-device ESP32-CAM — HYBRID (đây là "tự train xuống chip" thật)
```
[0] Board = ESP32-CAM. Chốt px/mm thật của rig. Chụp VGA 640×480 grayscale (§4.2).
      ↓
[1] Giai đoạn 1 — Classical CV (KHÔNG train): Otsu thích nghi → Connected Components (Union-Find)
      quét line-by-line trên VGA → count + bbox + area + perimeter (đếm & phân bố kích thước).
      Viết bằng C on-device; đối chiếu logic với extract_crops trên PC để khớp train↔deploy.
      ↓
[2] Dataset crop 32×32 grayscale cho classifier: cắt theo bbox của Giai đoạn 1 (đúng logic sẽ chạy
      trên chip). CHIA train/val/test Ở CẤP ẢNH VGA GỐC trước khi cắt (chống data leakage — §7).
      ↓
[3] Train Tiny classifier (float32): Track A (đặc trưng hình học + MLP/DecisionTree) TRƯỚC;
      chỉ leo Track B (Tiny CNN) cho ranh giới plastic↔organic. (Tuỳ chọn: distillation §4.4.)
      → đo accuracy + recall/lớp (đặc biệt bubble, hạt <0.5mm) trên TEST giữ riêng.
      ↓
[4] PTQ int8 (thường đủ, tụt 0.5–1.2% §4.1) → ĐO LẠI accuracy ở bản int8.
      ↓  (đạt)                                   ↓  (tụt quá ngưỡng)
[5] Export runtime: EON Compiler (khuyến nghị)   → cứu: rà rep-dataset → QAT (§4.1)
      → C++ tĩnh, arena 12–24KB trong SRAM nội          → structured pruning + fine-tune (§4.3)
      ↓                                            rồi quay lại [4]
[6] Tích hợp máy trạng thái tuần tự (§3.2): capture→CV→crop→classifier→upload→xả.
      Weights ở Flash XIP; đệm CCL + arena là mảng static; feed watchdog trong vòng CCL.
      ↓
[7] Kiểm trên board thật: so count/size/nhãn của board vs đếm tay. Lệch nhiều → nghi
      train↔deploy mismatch (§2 mục 5) hoặc logic CV khác giữa PC↔chip, TRƯỚC khi nghi model.
```

**Trạng thái script:** `train_detector.py`/`export_tflite.py`/`benchmark_tflite.py` phục vụ **5A
(YOLO/PC)**. Đường **5B (hybrid on-device)** **chưa có script**: cần (a) CV+crop bằng C on-device,
(b) train Tiny classifier (Keras/scikit-learn) + PTQ, (c) export EON/firmware — tất cả là việc mới.

---

## 6. NeuralCasting — tham khảo được gì, và tại sao KHÔNG áp dụng thẳng

Nguồn: `variants/README.md` (bản tổng hợp bài báo, kèm citation: `alecerio/NeuralCasting`,
"NeuralCasting: A Front-End Compilation Infrastructure for Neural Networks").

**NeuralCasting là gì:** một **front-end compiler** (Python, chạy offline trên PC) đọc model
**ONNX**, dựng DAG các toán tử, **khớp khuôn mẫu** cho các Q-Unit (QuantizeLinear / DequantizeLinear
/ QGemm / QLinearMatMul), rồi **sinh mã C/C++ thuần** (vòng lặp `for` lồng nhau, chỉ thư viện C
chuẩn, **không cần inference engine trung gian**), với **cấp phát bộ nhớ tĩnh** (nạp thẳng weight
vào Data Segment → triệt tiêu phân mảnh heap). Kết quả: "vi hạt AI" chỉ vài KB, chạy được cả trên
MCU siêu thấp (Arduino Nano 33 BLE / Cortex-M4). Bài gốc đạt **99.1%** với **MLP 8-bit** trên tín
hiệu tán xạ **1D** (cửa sổ 41 mẫu).

**Tham khảo được (triết lý đáng học cho Hướng 1):**
- **int8 tĩnh + sinh mã C trực tiếp** loại bỏ interpreter → nhẹ RAM, hết rủi ro tràn/phân mảnh.
  Cùng tinh thần với EON Compiler và ESP-DL ở §4.5.
- **Cấp phát tĩnh trong Data Segment** là mẹo hay khi RAM là tử huyệt (đối chiếu `tensor_arena`
  trong PSRAM ở §5[6]).
- Quy trình chuẩn hóa qua **ONNX** như một định dạng trao đổi trung gian.

**Tại sao KHÔNG áp dụng thẳng cho Hướng 1 (lý do kỹ thuật, không phải cảm tính):**
1. **Khác modality.** NeuralCasting sinh cho model ăn **vector 1D cố định 41 mẫu**. Hướng 1 là
   **object detector trên ảnh 2D** — input, kiến trúc, output (bounding box + class + score) khác
   hoàn toàn. Không phải "đổi định dạng file" là chạy.
2. **Chỉ compile được model nhỏ (MLP/GRU/1D-CNN).** `variants/00_huong_1D_va_holoscope.md` ghi rõ:
   *"NeuralCasting chỉ compile được model nhỏ (MLP/GRU)"*. Một YOLO có Conv2D/nhiều tầng/NMS **vượt
   xa** phạm vi khuôn mẫu toán tử của nó — nó không có template cho toàn bộ op của một detector, và
   nếu có thì mã sinh ra cũng không tối ưu bằng ESP-DL vốn có kernel Conv int8 viết tay cho ESP32.
3. **Đích khác nhau.** NeuralCasting hợp với nhánh **1D scattering** (nếu sau này làm biến thể đó),
   nơi model đủ nhỏ để nó tỏa sáng. Cho detector ảnh trên ESP32-CAM, **ESP-DL / TFLite-Micro / EON**
   mới là runtime đúng.

> **Kết luận về NeuralCasting:** giữ nó như **tài liệu tham khảo cho biến thể 1D** (`variants/`)
> và như **nguồn ý tưởng** (int8 tĩnh, sinh mã C, cấp phát tĩnh) — **không** đưa vào pipeline
> deploy của Hướng 1. Nếu một ngày dự án rẽ sang nhánh 1D scattering thì NeuralCasting mới trở lại
> đúng chỗ của nó.

---

## 7. Cách ĐO "giữ được độ chính xác" (không đo = không có kết luận)

1. **Tách tập test giữ riêng ngay từ đầu**, chia **theo ảnh gốc/mẻ**, không theo crop/box (tránh
   data leakage — cùng ảnh nằm cả train lẫn test cho accuracy ảo). Không đụng test cho tới báo cáo cuối.
2. **Metric:** với **hybrid on-device**, đếm/size do CV lo (đo sai số kích thước bằng vật chuẩn
   đã biết mm), còn classifier đo **accuracy + recall theo từng lớp**. Theo dõi riêng **recall
   bubble** (đừng đếm bọt thành nhựa) và **recall hạt <0.5mm**. Với **YOLO/PC (5A)** thì mAP@0.5 +
   recall/lớp. Bỏ sót hạt = đếm thiếu = sai deliverable "đếm & phân bố kích thước".
3. **Đo ở đúng bản sẽ deploy:** float32 (baseline) → **int8** (bản EON/tflite sẽ nạp) → (nếu đo được)
   trên board thật. Ghi lại **delta** từng bước để biết bước nào làm tụt.
4. **Confusion matrix** để thấy cặp lớp hay nhầm, thay vì chỉ nhìn một con số accuracy.
5. **Ngưỡng chấp nhận phải chốt trước** (ví dụ: int8 tụt ≤ 2–3% mAP so với float32; recall hạt nhỏ
   ≥ mục tiêu). Chốt ở §Phase 1.3 của `ai_model_plan.md` tinh thần tương tự.

---

## 8. Rủi ro & cạm bẫy (đã gặp / dễ gặp)

- **Dataset đã có, nhưng khớp domain deploy tới đâu?** Rủi ro không còn là "thiếu dữ liệu" mà là
  **domain-match**: nếu dataset là ảnh công khai (vd microplastics-m7mf5) thì nó tốt để
  **bootstrap pipeline/kiến trúc** nhưng **không** cho con số accuracy thật (domain khác hẳn
  backlit-silhouette của Aqua Scope — `ml/README.md` Phase A mục 3); số accuracy chỉ có nghĩa sau
  khi **fine-tune trên ảnh thật từ rig**. Nếu dataset **đã là ảnh từ chính rig** ở đúng cấu hình
  exposure/backlit sẽ deploy thì rủi ro này biến mất — cứ đi thẳng pipeline §5.
- **Lens chưa nét ở 3–5cm** (`camera-focus-limit`, `ai_model_plan.md` Phase 0): ảnh mờ → model rác,
  không cứu bằng train/quantize. Phải xử lý TRƯỚC khi thu dataset.
- **Đừng cố nạp YOLO xuống ESP32-CAM** (§3.0): 12–18s/khung, quá nhiệt/brownout. On-device = hybrid
  (CV + Tiny classifier). YOLO chỉ dùng ở PC/offload (5A).
- **Train↔deploy mismatch** (§2 mục 5): thủ phạm số 1 của "PC cao, board thấp". Với hybrid, còn thêm
  một biến thể: **logic CV trên chip (C) phải KHỚP logic crop khi train** (cùng Otsu/ngưỡng, cùng
  pad/resize 32×32). Lệch là accuracy sập dù classifier tốt.
- **Chụp dưới VGA** (QVGA/QQVGA) làm hạt <1mm biến mất → sai phân bố kích thước. Giữ **VGA tối thiểu** (§4.2).
- **Representative dataset kém đại diện** làm PTQ int8 tụt nhiều — dùng crop thật, đủ đa dạng.
- **`malloc()` động trong vòng lặp** → phân mảnh heap SRAM nội → sập sau vài ngày. Dùng mảng static (§4.5).
- **WiFi TX cùng lúc chụp/suy luận** → brownout reset. Tách bằng máy trạng thái + tụ 470µF‖0.1µF (§3.2).
- **Đừng nhét Tiny classifier/CNN ảnh vào NeuralCasting** (§6) — nó chỉ cho MLP/GRU/1D-CNN nhỏ; dùng EON.

---

## 9. Việc cần làm tiếp theo (thứ tự)

- [x] **Board deploy đã chốt: ESP32-CAM** (AI-Thinker, OV2640).
- [x] **Dataset đã có** (ở máy). Việc còn lại: xác nhận **domain-match** với ảnh rig (§8).
- [x] **Kiến trúc on-device đã chốt: HYBRID** (classical CV đếm+size + Tiny classifier loại) — §3.0.
      YOLO chỉ dùng cho PC/offload (5A), không nạp xuống ESP32-CAM.
- [ ] **Giai đoạn 1 CV trên chip:** viết Otsu + Connected Components (Union-Find) bằng C, quét
      line-by-line trên VGA; đo thời gian thật trên board (mục tiêu 120–250ms). Xuất crop 32×32.
- [ ] **Train Tiny classifier (5B[3]):** Track A (đặc trưng hình học + MLP/DecisionTree) trước; đo
      accuracy + recall bubble/hạt nhỏ. Chỉ leo Track B (Tiny CNN) nếu plastic↔organic chưa tách được.
- [ ] **PTQ int8 → đo lại → EON Compiler** (5B[4]→[5]); kỳ vọng tụt 0.5–1.2%, nhiều khả năng không cần QAT.
- [ ] **Tích hợp máy trạng thái tuần tự** (§3.2) + memory map (weights Flash XIP, arena SRAM nội, static).
- [ ] (Song song, tuỳ chọn) Đường 5A YOLO/PC: chạy `train_detector.py` với dataset để có baseline offload.
- [ ] Cập nhật `ml/README.md` (bảng "Hướng 1 — chưa làm") khi 5B chạy được thật trên board.

---

*Tài liệu nghiên cứu, chưa phải mã triển khai. Khi Hướng 1 được build thật, các quyết định ở đây
sẽ được phản ánh vào `ml/README.md` và `config.toml`.*
