# Prompt nghiên cứu — Thiết kế model Computer Vision tích hợp trên ESP32-CAM (edge device)

> **Cách dùng:** copy nguyên khối trong khung `───` bên dưới, dán vào công cụ deep-research / LLM.
> Prompt được viết **self-contained** (đã nhét sẵn ràng buộc phần cứng + bối cảnh Aqua Scope), nên
> chạy được kể cả khi công cụ không thấy repo này. Nếu công cụ có đọc repo, nó tham chiếu thêm
> `ml/direction1_onchip_research.md`, `ai_model_plan.md`, `CLAUDE.md`.

---

```text
VAI TRÒ
Bạn là kỹ sư TinyML / Embedded Computer Vision cấp cao, chuyên triển khai mô hình thị giác
máy tính trên vi điều khiển tài nguyên thấp. Nhiệm vụ: NGHIÊN CỨU và ĐỀ XUẤT thiết kế một
model computer vision chạy được TRÊN THIẾT BỊ (on-device) trên board ESP32-CAM, cho bài toán
mô tả dưới đây. Ưu tiên số liệu định lượng có trích dẫn hơn là nhận định chung chung.

BỐI CẢNH PHẦN CỨNG (cố định, không đổi board)
- Board: ESP32-CAM AI-Thinker. SoC ESP32 (KHÔNG phải ESP32-S3).
- CPU: 2× Xtensa LX6 @ 240MHz. KHÔNG có SIMD/vector, KHÔNG có NN accelerator, KHÔNG hưởng
  tăng tốc int8 SIMD của ESP-NN (thứ chỉ có trên ESP32-S3). Conv int8 chạy bằng ALU vô hướng.
- RAM: ~520KB SRAM nội (sau khi IDF + WiFi + camera driver khởi động, heap trống thực tế chỉ
  còn ~150-250KB, phân mảnh, một phần cần DMA-capable liền mạch) + 4MB PSRAM ngoài (QSPI ~80MHz,
  chậm hơn SRAM nội nhiều lần).
- Flash: 4MB (chứa firmware + trọng số model + tài nguyên khác).
- Camera: OV2640 (tối đa UXGA 1600×1200), lens factory lấy nét ở ~3-5cm.
- Nguồn: dễ brownout khi camera + WiFi TX + CPU 240MHz cùng đỉnh dòng.

BÀI TOÁN ỨNG DỤNG (trạm quan trắc hạt/rác vĩ mô trong dòng nước — QC nước đầu vào)
- Ảnh: BACKLIT SILHOUETTE — đèn LED trắng khuếch tán chiếu từ dưới lên qua đáy trong suốt;
  hạt hiện thành SILHOUETTE TỐI trên nền sáng đều. Manual exposure (AEC/AGC OFF, gain thấp).
- Mục tiêu đo:
  (1) ĐẾM số hạt và PHÂN BỐ KÍCH THƯỚC (size distribution) — cần bounding box / diện tích blob,
      KHÔNG được chỉ trả centroid.
  (2) PHÂN LOẠI TỪNG HẠT theo hình thái (vd: plastic / bubble / organic / fiber — danh sách lớp
      chưa chốt). Đây là phân loại theo HÌNH DẠNG/HÌNH THÁI, không phải hóa học.
- Kích thước hạt cần đo: hiện <2mm (thiết kế tới 5mm). Ở ~40mm working distance, độ phân giải
  ~14 px/mm ở VGA → hạt 2mm ≈ 28px; hạt nhỏ chỉ vài px → RẤT nhạy với việc giảm độ phân giải.
- Chu kỳ vận hành: STOP-FLOW, LẤY MẪU THEO MẺ/ĐỊNH KỲ (KHÔNG phải video real-time 30fps):
  bơm ON → dừng 1-2s cho lắng → chụp 1 khung độ phân giải cao → xử lý → xả → lặp. Cadence lấy
  mẫu cỡ vài phút/mẻ. HỆ QUẢ QUAN TRỌNG: một lần suy luận vài giây CÓ THỂ chấp nhận được nếu
  số khung/mẫu nhỏ — hãy khai thác đặc điểm này khi đánh giá khả thi.
- Yêu cầu traceability: mỗi mẫu phải log sample_id / timestamp / count / size_dist / phân bố loại.

RÀNG BUỘC THIẾT KẾ (3 KHÔNG — kiểm mọi đề xuất theo đây)
1. KHÔNG chỉnh/thay lens (giữ lens factory, đặt mẫu ở 3-5cm).
2. KHÔNG dùng chip vi lưu kín (hạt 1-5mm gây tắc). Dùng khay hở, mực nước cố định bằng weir.
3. KHÔNG can thiệp thủ công (bơm/đèn/chụp/đếm/xả tự động).

CÁC CÂU HỎI NGHIÊN CỨU (trả lời từng nhóm, có số liệu + trích dẫn khi có)

A. KIẾN TRÚC MODEL — so sánh các lựa chọn cho ĐÚNG bài toán này trên ESP32-CAM:
   A1. Object detector nhỏ end-to-end (vd YOLO-nano/PicoDet/NanoDet, tinySSD): có khả thi về
       latency/RAM trên LX6 không? Đưa ước tính GMAC, kích thước int8, tensor arena, latency.
   A2. Pipeline HYBRID: classical CV (threshold → connected components → count + size) chạy trên
       MCU cho khâu đếm/kích thước, RỒI một classifier nhỏ (tiny CNN / MLP trên đặc trưng thủ
       công) chỉ chạy trên crop từng hạt cho khâu phân loại. So chi phí/độ chính xác vs A1.
   A3. FOMO (Edge Impulse) hoặc heatmap-centroid: rẻ nhưng MẤT bounding box → mất size. Khi nào
       chấp nhận đánh đổi này? Có cách nào lấy lại size gần đúng không?
   A4. Với ảnh SILHOUETTE (nhị phân gần như đen-trắng), liệu đặc trưng HÌNH HỌC thủ công (area,
       circularity, aspect ratio, solidity, tỉ lệ sáng ở tâm để bắt bọt khí…) + classifier cực
       nhỏ có ĐỦ thay cho CNN không? Chỗ nào (plastic vs organic) buộc phải dùng CNN?
   → Kết luận: kiến trúc nào là "sweet spot" cho ĐẾM+SIZE+LOẠI trên ESP32-CAM, và vì sao.

B. ĐỘ PHÂN GIẢI ĐẦU VÀO:
   B1. Đánh đổi imgsz (RAM/latency ~ bình phương cạnh) vs khả năng phân giải hạt <2mm.
   B2. Kỹ thuật TILING (cắt ảnh lớn thành ô, chạy model từng ô) để giữ độ phân giải mà không
       phình RAM — chi phí latency và cách ghép kết quả biên.
   B3. Nên chụp/suy luận ở độ phân giải nào (VGA? SXGA rồi tile?) để hạt nhỏ không biến mất.

C. NÉN & LƯỢNG TỬ HÓA GIỮ ĐỘ CHÍNH XÁC:
   C1. PTQ int8 full-integer: quy trình, representative dataset, mức tụt accuracy điển hình cho
       detector vs classifier nhỏ trên bài silhouette.
   C2. QAT: khi nào cần, lấy lại được bao nhiêu accuracy so với PTQ, chi phí pipeline.
   C3. Pruning (structured vs unstructured) và Knowledge Distillation: lợi ích thực trên MCU
       không có sparse-accel; thứ tự kết hợp (prune → fine-tune → PTQ/QAT).
   C4. Cách ĐO việc "giữ accuracy": mAP + recall theo lớp (đặc biệt recall hạt nhỏ và bubble) đo
       trên tập test giữ riêng, ở CHÍNH bản int8 sẽ deploy; tránh data leakage (chia theo ảnh gốc).

D. RUNTIME / TRIỂN KHAI TRÊN ESP32-CAM:
   D1. So sánh ESP-DL vs TFLite-Micro (không có SIMD LX6) vs EON Compiler (Edge Impulse): độ hỗ
       trợ op, latency, RAM, khả năng ước tính trước khi nạp. Cái nào hợp ESP32-CAM nhất?
   D2. Bố trí bộ nhớ: nạp trọng số vào PSRAM (tránh XIP flash contention), tensor arena trong
       PSRAM (ps_malloc), giữ SRAM nội trống cho WiFi/DMA. Con số arena tối đa hợp lý.
   D3. Op nào của detector (Conv2D, DW-Conv, NMS, Resize…) hay thiếu/chậm trên các runtime này.

E. TRANH CHẤP KHI GHÉP CÁC TÁC VỤ KHÁC (đây là phần dễ bị bỏ qua khi test model lẻ):
   Các tác vụ đồng thời: chụp camera (JPEG) · giải nén → xám/RGB · classical CV · suy luận NN ·
   WiFi + HTTP upload · điều khiển bơm/MOSFET theo thời gian · ghi log.
   E1. Tràn PSRAM: framebuffer + trọng số + arena không cùng sống trong 4MB — cách tuần tự hóa,
       giải phóng buffer camera trước khi cấp arena, làm việc ở VGA thay vì UXGA-RGB.
   E2. RAM nội × WiFi (lỗi kinh điển "camera init fail / no mem khi bật WiFi"): cách bố trí
       framebuffer trong PSRAM, giữ heap nội trống, thứ tự khởi tạo.
   E3. Băng thông PSRAM: DMA camera ghi vs inference đọc cùng bus QSPI → không chụp+suy luận
       song song. Ước lượng mức chậm khi tranh chấp.
   E4. Dual-core: ghim WiFi core 0, CV+inference core 1; watchdog (TWDT) bắn khi suy luận vài
       giây ôm core — cách feed WDT / chia nhỏ.
   E5. Flash/XIP contention; brownout (nguồn 5V/2A + tụ bù, tránh WiFi TX đúng lúc chụp).
   E6. Đề xuất KIẾN TRÚC MÁY TRẠNG THÁI TUẦN TỰ cho toàn chu kỳ Stop-Flow sao cho chỉ một hộ
       tiêu thụ bộ nhớ lớn sống tại mỗi thời điểm.

F. ON-DEVICE vs OFFLOAD (tiêu chí quyết định, không cảm tính):
   F1. Với ngân sách latency của cadence Stop-Flow, khi nào detector on-device là khả thi, khi
       nào phải lùi FOMO (mất size) HOẶC offload NN ra ngoài (ESP32-CAM chỉ chụp+CV+upload)?
   F2. Nêu tiêu chí định lượng: latency × số_khung ≤ thời_gian_rảnh_giữa_mẻ; ngưỡng RAM/flash.

YÊU CẦU VỀ CÂU TRẢ LỜI
- Định lượng: đưa con số (GMAC, KB/MB, ms/giây, % accuracy) kèm nguồn/benchmark khi có; nói rõ
  cái nào là ĐO THẬT vs ƯỚC TÍNH bậc độ lớn.
- Phân biệt rạch ròi ESP32-CAM (LX6, không accel) với ESP32-S3 (có ESP-NN) — ĐỪNG trích số của
  S3 rồi gán cho ESP32-CAM mà không cảnh báo.
- Không bịa: nếu không chắc, nói "cần đo", đừng chế số.
- Tôn trọng 3 KHÔNG và yêu cầu ĐẾM+SIZE+LOẠI (đừng đề xuất giải pháp bỏ mất size mà không nêu rõ
  đó là đánh đổi).
- Kết thúc bằng: (1) bảng so sánh các kiến trúc ứng viên (A) theo [khả thi latency | RAM | giữ
  được size? | độ chính xác kỳ vọng | độ phức tạp]; (2) MỘT kiến trúc khuyến nghị + lý do; (3)
  checklist các phép ĐO cần làm để xác nhận khả thi trước khi train nhiều; (4) danh sách rủi ro.
- Ngôn ngữ: tiếng Việt.
```

---

*Ghi chú: prompt này chỉ để NGHIÊN CỨU/định hướng thiết kế — không thay cho việc đo thật bằng
`ml/benchmark_tflite.py` + test trên board. Kết quả nghiên cứu nên được đối chiếu và ghi lại vào
`ml/direction1_onchip_research.md` (§3.1, §3.2, §4).*
