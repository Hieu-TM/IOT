# Hai hướng deploy model detection cho Aqua Scope

Tài liệu này tách rõ **2 nhánh** deploy (theo yêu cầu), để Phase C trong
[README.md](README.md) chốt bằng số đo thật thay vì đoán. Cả hai nhánh **dùng chung**
model train ở Phase B — chỉ khác nơi chạy suy luận.

Ràng buộc phần cứng nền: **ESP32-CAM AI-Thinker** = ESP32 gốc (2 core Xtensa 240MHz,
~520KB SRAM, thường 4MB PSRAM), **KHÔNG có lệnh vector AI** như ESP32-S3 → chạy CNN
nặng rất chậm. Firmware hiện tại (`firmware/aqua_scope_cam/aqua_scope_cam.ino`) đã có
sẵn endpoint HTTP `/capture` (trả 1 JPEG) và `/stream`, cùng hook rỗng `runVision(fb)`
— là 2 điểm bám cho 2 nhánh dưới đây.

---

## Nhánh 1 — Offload: ESP32-CAM chỉ chụp, xử lý ở phần cứng ngoài

ESP32-CAM = "camera node" thuần: chụp ảnh độ phân giải cao trong cửa sổ Pump-OFF của
chu kỳ Stop-Flow, gửi ảnh qua WiFi cho một máy xử lý bên ngoài chạy full detector
(giữ nguyên độ chính xác + **giữ được size** từ box width/height), nhận kết quả về để
log (yêu cầu traceability của QC nước đầu vào).

### Luồng dữ liệu
```
ESP32-CAM  --(WiFi, JPEG)-->  Bộ xử lý ngoài  --(JSON: count/size/class)-->  log/dashboard
  (chụp SXGA/UXGA,             (chạy YOLO đầy đủ)      (web dashboard Module 5+6 đã có)
   manual exposure)
```

### Cách nối cụ thể (tận dụng cái đã có)
- **Kéo ảnh:** máy ngoài `GET http://<esp32-cam-ip>/capture` để lấy 1 JPEG mỗi lần
  chụp (endpoint đã tồn tại). Hoặc ESP32-CAM chủ động `POST` JPEG lên server sau mỗi
  lần Pump-OFF (cần thêm ~30 dòng vào firmware).
- **Bộ xử lý ngoài — chọn 1 theo mức "self-contained" mong muốn:**
  - **PC/laptop** chạy 1 server nhỏ (FastAPI/Flask) gọi `ultralytics` `model.predict()`
    trên chính `best.pt` của Phase B. Rẻ nhất để dựng, hợp demo đồ án.
  - **Raspberry Pi / mini-PC trên cùng LAN** — "edge server" đúng nghĩa, vẫn nội bộ,
    không phụ thuộc internet; hợp bối cảnh nhà máy.
  - **Roboflow Hosted Inference API** (hoặc self-host `roboflow-inference` bằng Docker
    trên LAN) — deploy thẳng model đã train ở Roboflow, gửi ảnh lên, nhận JSON box.
    Nhanh nhất để có kết quả, nhưng ràng buộc license CC BY-NC-SA (phi thương mại) +
    dữ liệu rời máy nếu dùng bản hosted.
- **Trả kết quả về:** JSON `{sampleID, timestamp, count, size_dist, per_class}` →
  đẩy vào đúng đường log/dashboard web đã code (Module 5+6, memory `web-frontend-impl`).

### Ưu / nhược
| Ưu | Nhược |
|---|---|
| Model đầy đủ → **giữ được size per-particle** | Cần WiFi ổn định + 1 thiết bị ngoài (không self-contained) |
| Dựng nhanh, dùng thẳng `best.pt` Phase B | Latency phụ thuộc đường truyền; ảnh rời thiết bị |
| Không bị giới hạn RAM/flash của ESP32 | Thêm 1 điểm hỏng (server ngoài) vào chu kỳ |
| Fit tự nhiên cửa sổ Pump-OFF (không cần realtime) | (Nếu dùng cloud) ràng buộc license + quyền riêng tư |

> Nhánh này **an toàn nhất về mặt "chắc chạy được"** và giữ trọn deliverable count+size+class.
> Là phương án nền (fallback) nếu Nhánh 2 đo ra không khả thi.

---

## Nhánh 2 — On-device: vẫn chạy trên ESP32-CAM, nhưng phải tối ưu

Muốn giữ suy luận ngay trên chip thì phải hạ tải model xuống vừa ESP32-CAM. Có mấy
phương pháp tối ưu, **xếp từ ít-đánh-đổi đến nhiều-đánh-đổi**; nhiều khả năng phải
**kết hợp vài cái**:

### 2a. FOMO (Edge Impulse) + khôi phục size bằng CV — *khuyến nghị thử trước*
FOMO là kiến trúc detect siêu nhẹ, chạy được thật trên ESP32-CAM, nhưng **chỉ trả về
tâm điểm + lớp, mất size**. Cách gỡ đúng tinh thần "tối ưu tận dụng":
- FOMO lo **phát hiện + phân loại** từng hạt (fiber/film/fragment/pellet).
- **Classical CV chạy ngay trên cùng khung ảnh** (threshold nghịch → connected
  components → diện tích blob) lo **đếm + đo size** — đây chính là hook `runVision()`
  đang rỗng, và cũng chính là pipeline gốc trong `ai_model_plan.md`.
- Ghép theo toạ độ: gán mỗi tâm FOMO với blob CV gần nhất → có đủ {vị trí, lớp, size}.

→ Bản chất: quay lại **hybrid một phần** (CV đo size + NN phân loại), nhưng lần này NN
là detector-grid thay vì classifier-crop. Đây là "phương pháp tối ưu" thực dụng nhất
để **vừa on-device vừa không mất size**.

### 2b. Thu nhỏ input + int8 + ít lớp/ít grid
- Input nhỏ nhất vẫn còn thấy hạt ~2mm (theo px/mm, memory `camera-focus-limit`):
  thử 96×96 → 160×160, đo mAP tụt bao nhiêu.
- Quantize **int8 full-integer** (bắt buộc), giảm số lớp nếu gộp được, giảm grid.

### 2c. Tiling — giữ độ phân giải mà input model vẫn nhỏ
Chụp SXGA/UXGA rồi **cắt thành ô (tile)**, chạy model nhỏ trên từng ô, ghép kết quả.
Giữ được chi tiết hạt nhỏ mà không cần input model lớn; đổi lại tốn nhiều lần suy luận
/khung → chậm hơn (chấp nhận được vì Stop-Flow không cần realtime).

### 2d. Two-stage: CV đề xuất ROI → tiny model chỉ nhìn crop
CV rẻ tìm blob trước (ROI), model nhỏ chỉ chạy trên vài crop có hạt thay vì cả khung.
Đây gần đúng kiến trúc hybrid classifier-crop gốc — nhẹ nhất về suy luận, và **giữ size
từ CV**. Nếu Nhánh 2 buộc phải ép tối đa, đây là đích hội tụ.

### 2e. Trình biên dịch TinyML chuyên dụng
File `../Efficient_Detection_of_Microplastics_on_Edge_Devices_With_Tailored_Compiler_for_TinyML_Applications.pdf`
trong repo **đúng chủ đề này** (detection microplastics trên edge device + compiler
TinyML riêng). Đọc để lấy kiến trúc/kỹ thuật/số đo tham chiếu trước khi tự mò —
có thể tiết kiệm rất nhiều thời gian ở 2a–2d.

### Ưu / nhược nhánh 2
| Ưu | Nhược |
|---|---|
| **Self-contained**, không cần server ngoài / WiFi để suy luận | Kỹ thuật khó hơn nhiều; nhiều vòng thử-sai |
| Không có ảnh rời thiết bị (riêng tư) | FOMO thuần mất size → phải ghép CV (2a/2d) mới đủ deliverable |
| Đúng tinh thần "TinyML on-device" của đồ án | Rủi ro cao model vẫn quá chậm/quá to → phải hạ chất lượng |

---

## Cách quyết định (Phase C) — không chọn cảm tính

1. Chạy `export_tflite.py` + `benchmark_tflite.py` (Phase C) để có **flash/tensor-arena/
   latency** của detector đầy đủ ở input nhỏ nhất còn thấy hạt 2mm.
2. So với ngân sách ESP32-CAM (≈ vài trăm KB SRAM cho arena, flash 4MB, 1 khung/cửa sổ
   Pump-OFF nên latency tới ~1–2s vẫn chấp nhận được):
   - **Nếu detector đầy đủ vừa** → Nhánh 2 chạy detector thật on-device (lý tưởng).
   - **Nếu không vừa (khả năng cao)** → chọn:
     - Ưu tiên **chắc chạy + giữ size** → **Nhánh 1 (offload)**.
     - Ưu tiên **self-contained** → **Nhánh 2a** (FOMO + CV đo size) hoặc **2d**.
3. Lập bảng số cụ thể (như plan yêu cầu) rồi mới chốt. Có thể **làm song song cả hai để
   so ở buổi báo cáo**: Nhánh 1 làm baseline "đầy đủ", Nhánh 2a làm minh chứng "chạy
   được trên chip".

> Lưu ý xuyên suốt: mọi con số ở Phase B/C đến từ **dataset công khai** (domain có thể
> lệch ảnh rig thật). Chỉ sau Phase D (ảnh thật + fine-tune) mới là số đáng tin để chốt
> cứng nhánh nào cho sản phẩm.
