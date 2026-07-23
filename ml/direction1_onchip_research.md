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
| **Hướng 1** (tài liệu này) | **Ảnh 2D** (backlit silhouette) | Object detector (YOLO `yolo11n`) tự train → TFLite int8 | `ml/infer/detector.py`, `ml/train_detector.py`, `ml/export_tflite.py` | **Chưa làm** (hoãn, chờ dataset) |
| **Hướng 2** | Ảnh 2D | Detector chạy trên Roboflow Workflow API (hosted) | `ml/infer/detector_roboflow.py` | **Xong, đã chạy thật** |
| **Biến thể NeuralCasting / 1D** | **Tín hiệu điện áp 1D** (photodiode → TIA → ADC, cửa sổ 41 mẫu) | MLP/GRU/1D-CNN cực nhỏ, PTQ int8, compile ONNX→C thuần | `variants/` (chỉ là nghiên cứu phương án) | Nghiên cứu, chưa build |

**Điểm mấu chốt bạn đã nêu đúng:** bài NeuralCasting và Hướng 1 là **hai bài toán trên hai
model xử lý khác hẳn nhau** — một bên xử lý **chuỗi 1D 41 mẫu**, một bên xử lý **ảnh 2D**.
Vì vậy NeuralCasting **tham khảo được về triết lý** (int8, sinh mã C tĩnh, model tí hon) nhưng
**không áp dụng thẳng** cho detector ảnh của Hướng 1 (lý do kỹ thuật cụ thể ở §6).

Toàn bộ phần còn lại của tài liệu chỉ nói về **Hướng 1** (detector ảnh 2D).

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

→ **Cách chốt thật:** export int8 → `benchmark_tflite.py` lấy size/arena/latency PC → nhân hệ số an
toàn cho LX6 → đối chiếu cadence Stop-Flow thật. Nếu latency×số-khung **≤ thời gian rảnh giữa hai mẻ**
→ đi tiếp YOLO. Nếu không → FOMO (mất size) **hoặc** offload sang Hướng 2 (§3.2 cuối).

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
- **Bắt buộc: đo accuracy trước/sau PTQ trên tập test.** Detector int8 thường tụt vài %; nếu tụt
  nhiều (ví dụ recall hạt nhỏ sập) → sang QAT hoặc xem lại imgsz/rep-dataset.

**QAT (Quantization-Aware Training) — làm khi PTQ tụt quá ngưỡng.**
- Chèn "fake quantization" vào lúc train để model **học cách chịu đựng int8**; thường lấy lại
  phần lớn accuracy mà PTQ đánh mất.
- Đắt hơn (phải train lại có mô phỏng quantize), pipeline phức tạp hơn. **Chỉ dùng khi PTQ không
  đạt** — đừng nhảy thẳng vào QAT.

> Quy tắc: **PTQ → đo → (nếu tụt) QAT**. Không làm ngược.

### 4.2 Giảm độ phân giải đầu vào (con dao hai lưỡi)
`imgsz` nhỏ giảm mạnh RAM/latency (chi phí ~ bình phương cạnh) nhưng **là nơi hạt <2mm chết**.
- `config.toml` train `imgsz=416`, export `tflite_imgsz=192`. **Phải kiểm chứng 192 vẫn phân giải
  được hạt ~2mm** ở px/mm thật của rig — nếu không, tăng imgsz (đánh đổi latency) hoặc dùng
  **tiling** (cắt ảnh lớn thành ô nhỏ, chạy detector từng ô) để giữ độ phân giải mà không phình RAM.
- Đây là siêu tham số phải **quét và đo**, không chọn bừa.

### 4.3 Pruning (cắt tỉa)
Bỏ bớt trọng số/kênh ít quan trọng để giảm kích thước & tăng tốc.
- **Structured pruning** (bỏ cả kênh/filter) mới thật sự nhanh hơn trên MCU; **unstructured**
  (bỏ trọng số lẻ) chủ yếu giảm size, ít tăng tốc nếu runtime không hỗ trợ sparse.
- Sau prune **phải fine-tune lại** để hồi accuracy. Thường kết hợp: prune → fine-tune → PTQ/QAT.
- Với `yolo11n` vốn đã nhỏ, lợi ích pruning có thể khiêm tốn — cân nhắc chỉ khi cần ép thêm.

### 4.4 Knowledge Distillation (chưng cất tri thức)
Train một model "teacher" to/chính xác trên PC, rồi dạy "student" nhỏ (cái sẽ xuống chip) bắt chước
teacher. Student nhỏ thường **đạt accuracy cao hơn so với train student trực tiếp**.
- Hữu ích khi model nhỏ nhất vẫn phải giữ recall cao. Đắt về công train, để dành khi các cách trên
  chưa đủ.

### 4.5 Chọn runtime/compiler tối ưu cho ESP32-CAM
Cùng một `.tflite` int8, chạy trên runtime khác nhau ra latency khác nhau (accuracy gần như không
đổi, nhưng tốc độ đổi nhiều — mà tốc độ mới là thứ quyết định detector có sống nổi trên ESP32-CAM
không). Lưu ý: ESP32-CAM là ESP32 thường (LX6), **không có** accelerator, nên đừng kỳ vọng cú tăng
tốc int8 SIMD như trên dòng có accelerator — các runtime dưới đây chỉ giúp trong giới hạn của LX6:
- **ESP-DL** (Espressif): thư viện DL tối ưu cho dòng ESP32, có kernel int8 viết tay và quantize
  tool riêng — lựa chọn runtime chính cho ESP32-CAM.
- **TFLite-Micro** (ESP-IDF): interpreter chuẩn, chạy được trên ESP32-CAM nhưng kernel int8 chỉ ở
  mức C tham chiếu (không có SIMD của LX6) → thường chậm hơn ESP-DL cho cùng model.
- **EON Compiler (Edge Impulse)**: sinh mã C gọn hơn interpreter TFLM, kèm **ước tính RAM/flash/
  latency TRƯỚC khi nạp** — rất hợp để chốt nhánh deploy sớm (xem `ai_model_plan.md` §Phase 2, 9).
- **NeuralCasting**: sinh mã C thuần ONNX→C, **nhưng chỉ cho model nhỏ (MLP/GRU/1D-CNN)** — xem §6.

---

## 5. Quy trình đề xuất cho Hướng 1 (khi đã có dataset)

```
[0] Board đã chốt: ESP32-CAM. Chốt px/mm thật của rig + chốt imgsz deploy (§4.2)
      ↓
[1] Có dataset ảnh THẬT từ rig (backlit, manual exposure, đúng cấu hình deploy)
      → gán nhãn (Roboflow) → export YOLO → ml/datasets/<version>/
      ↓
[2] Train float32:  python ml/train_detector.py --data .../data.yaml --model yolo11n.pt
      → đo mAP + recall/lớp trên TEST giữ riêng   =  đường cơ sở (baseline float32)
      ↓
[3] PTQ int8:  python ml/export_tflite.py --weights best.pt --imgsz <chốt ở [2]> --data .../data.yaml
      → ĐO LẠI mAP/recall trên TEST ở bản int8    =  so với baseline
      ↓  (nếu tụt trong ngưỡng)                     ↓  (nếu tụt quá ngưỡng)
[4a] benchmark_tflite.py → size/arena/latency     [4b] cứu accuracy, theo thứ tự:
      → so ngân sách ESP32-CAM                            - rà lại representative dataset (§4.1)
      ↓                                                    - tăng imgsz / dùng tiling (§4.2)
[5] Nếu latency/RAM KHÔNG đạt trên ESP32-CAM:              - QAT (§4.1)
      → theo quy tắc ml/README.md Phase C:                 - pruning + fine-tune (§4.3)
        lùi FOMO (mất size per-particle) trên ESP32-CAM     - distillation (§4.4)
      ↓                                             rồi quay lại [3] đo lại
[6] Deploy: model_int8.tflite → ESP-DL (hoặc TFLM) trên ESP32-CAM
      → tensor_arena trong PSRAM (ps_malloc), đăng ký đúng op resolver
      ↓
[7] Kiểm trên board thật: chạy vài ảnh test đã biết nhãn, so số hạt board vs PC.
      Chênh trong ngưỡng → xong. Lệch nhiều → nghi train↔deploy mismatch (§2 mục 5) TRƯỚC khi
      nghi model.
```

Các script đã có: `train_detector.py`, `export_tflite.py`, `benchmark_tflite.py`. **Chưa có**:
script tải dataset tự động (Task 6 — `[dataset]` trong `config.toml` mới là tham số ghi sẵn, chưa
code nào đọc), và bước QAT/pruning/distillation (chỉ triển khai nếu §5[4b] cần tới).

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
2. **Metric detector:** mAP@0.5 và **recall theo từng lớp** (`fiber/film/fragment/pallet` — hoặc
   class list chốt sau khi có dữ liệu thật). Với bài này **recall hạt nhỏ** quan trọng hơn mAP tổng
   vì bỏ sót hạt = đếm thiếu = sai deliverable "đếm & phân bố kích thước".
3. **Đo ở đúng bản sẽ deploy:** float32 (baseline) → int8 TFLite (`imgsz` deploy) → (nếu đo được)
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
- **ESP32-CAM không có accelerator** (§3) → detector int8 có thể vẫn quá chậm; đây là ràng buộc cố
  định, phải đo latency sớm (`benchmark_tflite.py`) và sẵn sàng lùi FOMO nếu không đạt.
- **Train↔deploy mismatch** (§2 mục 5): thủ phạm số 1 của "PC cao, board thấp". Cùng exposure, cùng
  backlit, cùng tiền xử lý.
- **`imgsz` deploy quá nhỏ** làm hạt <2mm biến mất — quét & đo, đừng để mặc định 192 nếu chưa kiểm.
- **Representative dataset kém đại diện** làm PTQ int8 tụt nhiều — dùng ảnh train thật, đủ đa dạng.
- **Đừng nhét YOLO vào NeuralCasting** (§6) — sai công cụ, tốn công vô ích.

---

## 9. Việc cần làm tiếp theo (thứ tự)

- [x] **Board deploy đã chốt: ESP32-CAM** (AI-Thinker, OV2640). Mọi lựa chọn kỹ thuật §4 bám ràng
      buộc board này (§3).
- [x] **Dataset đã có** (ở máy). Việc còn lại là xác nhận **domain-match** với ảnh rig (§8).
- [ ] **Đo khả thi TRƯỚC khi train nhiều** (§3.1): export thử int8 → `benchmark_tflite.py` lấy
      size/arena/latency → nhân hệ số LX6 → đối chiếu cadence Stop-Flow. Đây là **cổng đi/không**
      quyết định giữ YOLO on-device hay lùi FOMO / offload Hướng 2.
- [ ] Viết **script tải dataset tự động** (Task 6 — đọc `[dataset]` trong `config.toml`) — chỉ cần
      nếu muốn tái tạo dataset từ Roboflow; nếu dataset đã ở máy thì bỏ qua.
- [ ] Chạy pipeline §5 [2]→[3]→[4a] một lượt với dataset đang có, lấy **số benchmark** thật để chốt
      nhánh deploy (§5[5]).
- [ ] Chỉ khi §5[4b] cần: triển khai QAT / pruning / distillation.
- [ ] Cập nhật `ml/README.md` (bảng "Hướng 1 — chưa làm") khi Hướng 1 chạy được thật.

---

*Tài liệu nghiên cứu, chưa phải mã triển khai. Khi Hướng 1 được build thật, các quyết định ở đây
sẽ được phản ánh vào `ml/README.md` và `config.toml`.*
