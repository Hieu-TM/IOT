# Hướng 1 — Nghiên cứu phương pháp tự train model & tích hợp xuống chip mà giữ độ chính xác

> **Phạm vi tài liệu này:** phần **nghiên cứu phương pháp** (Phase nghiên cứu) cho **Hướng 1**
> trong `ml/README.md` — tức nhánh `backend = "local"`: **tự train weights (`.pt`), sở hữu
> model, và là con đường DUY NHẤT đi xuống chip qua TFLite int8**. Hướng 2 (`roboflow`,
> gọi API) đã làm xong và đã chạy thật; hai hướng thay thế được cho nhau khi một bên lỗi
> (xem bảng "Hai hướng model" trong `ml/README.md`).
>
> Tài liệu này **chưa** train gì — hiện **chưa có dataset** (`ml/datasets/` trống, `ml/models/`
> chưa tồn tại). Mục tiêu ở đây là **chốt phương pháp trước khi thu dữ liệu**, để khi có dataset
> thì đi thẳng, không phải làm lại. Liên quan: `ml/README.md` (Phase A–D), `ai_model_plan.md`
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
4. **Đổi runtime / tập toán tử** — TFLite-Micro/ESP-NN không hỗ trợ mọi op; op bị thay thế/xấp xỉ
   có thể lệch kết quả so với TF trên PC.
5. **Train↔deploy mismatch** — không phải "xuống chip" nhưng là thủ phạm số 1 khiến "PC 95%,
   board 60%": khác exposure, khác backlit, khác cách tiền xử lý/normalize crop. (Xem
   `ai_model_plan.md` Phase 10 — điểm này áp dụng y nguyên cho Hướng 1.)

> **Nguyên tắc đo:** không được nói "giữ được độ chính xác" bằng cảm tính. Phải đo **mAP (và
> recall theo từng lớp) trên tập test giữ riêng, ở CHÍNH định dạng int8 sẽ deploy**, rồi so với
> bản float32. Cách đo chi tiết ở §7.

---

## 3. Ràng buộc phần cứng thật (phải biết trước khi chọn kỹ thuật)

Hướng 1 hiện nhắm board **ESP32-CAM (AI-Thinker, OV2640)** theo `ml/README.md` — **không** phải
XIAO ESP32-S3. Đây là khác biệt **quyết định** vì:

- **ESP32 (ESP32-CAM)**: lõi Xtensa LX6, **không có** lệnh vector AI, **không có** ESP-NN SIMD
  int8 tăng tốc. Chạy CNN nặng rất chậm.
- **ESP32-S3** (board của pipeline hybrid trong `ai_model_plan.md`): có lệnh vector + **ESP-NN**
  tăng tốc int8 (Conv/Depthwise/FullyConnected) → nhanh hơn nhiều lần cho cùng model.

Hệ quả: **nếu deploy YOLO trên ESP32-CAM, ngân sách latency/RAM cực chặt**; rất có thể detector
thật không chạy nổi ở tốc độ dùng được và phải lùi về FOMO (mất size per-particle) — đúng như
"quy tắc quyết định" đã ghi trong `ml/README.md` Phase C. **Việc chốt board (ESP32-CAM giữ nguyên
hay chuyển sang S3) nên làm SỚM** vì nó đổi cả lựa chọn kỹ thuật bên dưới.

Con số phải **đo**, không đoán (dùng `ml/benchmark_tflite.py`): kích thước file `.tflite` (≈ flash
cần), tensor arena ước tính (≈ RAM cần, phải nằm trong PSRAM qua `ps_malloc`), latency/ảnh. Lưu ý
benchmark trên PC chỉ là ước tính — ESP32-CAM **chậm hơn nhiều** vì không có accelerator.

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

### 4.5 Chọn runtime/compiler tối ưu cho đúng chip
Cùng một `.tflite` int8, chạy trên runtime khác nhau ra latency khác nhau (accuracy gần như không
đổi, nhưng tốc độ đổi nhiều — mà tốc độ mới là thứ quyết định detector có sống nổi trên MCU không):
- **TFLite-Micro + ESP-NN** (ESP-IDF): ESP-NN tăng tốc int8 **trên ESP32-S3**; trên ESP32-CAM (LX6)
  gần như không có lợi.
- **ESP-DL** (Espressif): thư viện DL tối ưu cho dòng ESP32, có quantize tool riêng.
- **EON Compiler (Edge Impulse)**: sinh mã C gọn hơn interpreter TFLM, kèm **ước tính RAM/flash/
  latency TRƯỚC khi nạp** — rất hợp để chốt nhánh deploy sớm (xem `ai_model_plan.md` §Phase 2, 9).
- **NeuralCasting**: sinh mã C thuần ONNX→C, **nhưng chỉ cho model nhỏ (MLP/GRU/1D-CNN)** — xem §6.

---

## 5. Quy trình đề xuất cho Hướng 1 (khi đã có dataset)

```
[0] Chốt board (ESP32-CAM giữ nguyên? hay chuyển S3 để có ESP-NN?) + chốt px/mm thật của rig
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
        lùi FOMO (mất size) HOẶC chuyển board S3            - distillation (§4.4)
      ↓                                             rồi quay lại [3] đo lại
[6] Deploy: xxd model_int8.tflite → mảng C → TFLM/ESP-NN (S3) hoặc ESP-DL
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
   nếu có thì mã sinh ra cũng không tối ưu bằng ESP-NN/ESP-DL vốn được viết tay cho Conv int8.
3. **Đích khác nhau.** NeuralCasting hợp với nhánh **1D scattering** (nếu sau này làm biến thể đó),
   nơi model đủ nhỏ để nó tỏa sáng. Cho detector ảnh, **TFLite-Micro + ESP-NN / ESP-DL / EON** mới
   là runtime đúng.

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

- **Chưa có dataset thật từ rig** = rủi ro gốc. Dataset công khai (microplastics-m7mf5) chỉ để
  **bootstrap pipeline/kiến trúc**, **không** cho ra con số accuracy thật (domain ảnh khác hẳn
  backlit-silhouette của Aqua Scope — xem `ml/README.md` Phase A mục 3). Số accuracy chỉ có nghĩa
  sau khi train trên ảnh thật (Phase D).
- **Lens chưa nét ở 3–5cm** (`camera-focus-limit`, `ai_model_plan.md` Phase 0): ảnh mờ → model rác,
  không cứu bằng train/quantize. Phải xử lý TRƯỚC khi thu dataset.
- **Board ESP32-CAM không có ESP-NN** → detector int8 có thể vẫn quá chậm. Chốt board sớm (§3).
- **Train↔deploy mismatch** (§2 mục 5): thủ phạm số 1 của "PC cao, board thấp". Cùng exposure, cùng
  backlit, cùng tiền xử lý.
- **`imgsz` deploy quá nhỏ** làm hạt <2mm biến mất — quét & đo, đừng để mặc định 192 nếu chưa kiểm.
- **Representative dataset kém đại diện** làm PTQ int8 tụt nhiều — dùng ảnh train thật, đủ đa dạng.
- **Đừng nhét YOLO vào NeuralCasting** (§6) — sai công cụ, tốn công vô ích.

---

## 9. Việc cần làm tiếp theo (thứ tự)

- [ ] **Chốt board deploy** (ESP32-CAM giữ nguyên vì có OV2640 sẵn, hay chuyển ESP32-S3 để có
      ESP-NN). Quyết định này mở khóa mọi lựa chọn kỹ thuật §4.
- [ ] **Thu dataset ảnh thật từ rig** theo `ai_model_plan.md` Phase 3 (self-labeling "mẫu đã biết
      nhãn", đúng cấu hình exposure/backlit sẽ deploy). **Đây là chặn cứng — chưa có thì các bước
      sau vô nghĩa.**
- [ ] Viết **script tải dataset tự động** (Task 6 — đọc `[dataset]` trong `config.toml`).
- [ ] Chạy pipeline §5 [2]→[3]→[4a] một lượt với dataset (kể cả dataset công khai để **thử pipeline**
      trước khi có ảnh thật), lấy **số benchmark** thật để chốt nhánh deploy (§5[5]).
- [ ] Chỉ khi §5[4b] cần: triển khai QAT / pruning / distillation.
- [ ] Cập nhật `ml/README.md` (bảng "Hướng 1 — chưa làm") khi Hướng 1 chạy được thật.

---

*Tài liệu nghiên cứu, chưa phải mã triển khai. Khi Hướng 1 được build thật, các quyết định ở đây
sẽ được phản ánh vào `ml/README.md` và `config.toml`.*
