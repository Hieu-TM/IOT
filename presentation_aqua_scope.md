---
marp: true
theme: default
class: lead
paginate: true
backgroundColor: #ffffff
---

# Slide 1: Tiêu đề
# Aqua Scope
## Trạm Quan Trắc & Đếm Hạt/Rác Thải Vĩ Mô Trong Dòng Chảy (1mm–5mm)
*Dự án hệ thống nhúng & IoT*

---

# Slide 2: Tổng quan Dự án
# Tổng quan Dự án
- **Mục tiêu:** Chuyển đổi vi điều khiển kèm camera (XIAO ESP32-S3 Sense) thành một trạm chụp ảnh tự động.
- **Chức năng:** Phát hiện, đếm và đo kích thước rác thải/hạt vi nhựa ở kích cỡ 1mm – 5mm.
- **Phương pháp:** Phân tích ảnh bóng đổ (silhouette) của hạt được chụp trong một dòng nước hở.

---

# Slide 3: Bối cảnh Ứng dụng
# Bối Cảnh Ứng Dụng (Use Case)
- **Vị trí hoạt động:** Điểm lấy nước đầu vào của nhà máy chế biến thực phẩm.
- **Tại sao cần thiết?** Kiểm soát chất lượng nguồn nước trước khi đi vào dây chuyền sản xuất chính.
- **Đặc trưng dòng nước:** Nước máy/nguồn cấp cơ bản đã tương đối sạch và ổn định, không phải nước thải biến động mạnh.

---

# Slide 4: Yêu Cầu Thiết Kế Từ Thực Tế
# Hệ Quả Cho Thiết Kế
- **Mẫu ổn định:** Cho phép sử dụng nền sáng đều, áp dụng ngưỡng hóa (threshold) cố định, không cần bù trừ phông nền phức tạp.
- **Lấy mẫu định kỳ:** Lấy mẫu theo lô (batch) thay vì 24/7, phù hợp chu trình **Stop-Flow**.
- **Truy xuất nguồn gốc:** Bắt buộc lưu trữ mã mẫu, thời gian, số lượng hạt và phổ phân bố kích thước.

---

# Slide 5: Tiêu Chí Cốt Lõi (3 KHÔNG)
# Tiêu Chí Cốt Lõi (3 KHÔNG)
1. **KHÔNG chỉnh sửa thấu kính:** Giữ nguyên lens gốc OV2640 (tự động lấy nét macro sắc nét ở khoảng cách 3-5cm).
2. **KHÔNG dùng ống vi lưu kín:** Hạt 1-5mm dễ gây tắc nghẽn → Dùng khay dòng chảy hở (Macro-Flow Stage).
3. **KHÔNG can thiệp thủ công:** Quá trình bơm nước, chụp ảnh, tính toán và xả mẫu diễn ra hoàn toàn tự động.

---

# Slide 6: Kiến Trúc Vật Lý
# Kiến Trúc Vật Lý Tổng Thể
- **Khối trụ chụp ảnh (Imaging Tube):** 
  - Nắp trụ chứa camera chụp thẳng xuống đáy.
  - Thân trụ chắn sáng tạo buồng tối (dài 4-5cm).
  - Đáy khay dòng chảy bằng acrylic trong suốt.
  - Hộp đèn nền hắt sáng từ dưới lên.
- **Trạm bơm (Tách rời):** Bơm màng RS365 chủ động điều tiết dòng nước.

---

# Slide 7: Vai Trò Của Khối Trụ Chắn Sáng
# Vai Trò Khối Trụ Chắn Sáng
- **Thước đo chuẩn (Datum):** Cố định cứng cự ly camera - mặt nước, giúp tỷ lệ `mm/pixel` không đổi.
- **Buồng tối:** Chặn ánh sáng môi trường gây nhiễu, giữ thông số phơi sáng đáng tin cậy.
- **Bệ đỡ vững chắc:** Trụ ngắn, cứng cáp chống rung, cho ảnh sắc nét nhất.
- **Nội thất đen nhám:** Hút các tia phản xạ lạc, gia tăng chất lượng ảnh bóng đổ.

---

# Slide 8: Kỹ Thuật Chiếu Sáng
# Kỹ Thuật: Bóng Đổ Nền Sáng
*(Backlit Silhouette)*
- **Nguyên lý:** Đèn LED trắng nằm dưới đáy khay chiếu ngược lên camera qua lớp nước.
- **Kết quả:** Vật thể (hạt rác/nhựa) trở thành **bóng đen cực nét trên phông nền sáng đều**.
- **Ưu điểm:** Đây là phương pháp đo lường hình thái kinh điển, mang lại độ tương phản cực cao hỗ trợ tối đa cho Computer Vision.

---

# Slide 9: Thiết Kế Hộp Đèn Nền
# Cấu Trúc Hộp Đèn Nền (Light Box)
- **LED Xuôi (Upward LED):** Module LED hướng chiếu thẳng lên trên, không dùng vách phản xạ (bounce).
- **Buồng trộn sáng (~8mm):** Giúp khử các điểm chói sáng (hotspot).
- **Màng khuếch tán:** Xếp lớp giấy can hoặc mica mờ ngay dưới đáy khay để dàn đều ánh sáng.
- **Chống chập chờn:** Sử dụng nguồn sáng trắng tĩnh (static white).

---

# Slide 10: Tối Ưu Hóa Tránh Cháy Sáng
# Tối Ưu Phơi Sáng Camera
- **Thiết lập thủ công:** Bắt buộc tắt Tự động phơi sáng (AEC) và Tự động khuếch đại (AGC).
- **Gain = 0, Phơi sáng (Exposure) thấp:** Ngăn tình trạng cháy sáng khung hình.
- **Viền khung ảnh:** Vùng sáng phải lấp đầy khung hình, tránh viền đen lớn đánh lừa cảm biến đo sáng tự động.

---

# Slide 11: Hệ Dòng Chảy Chủ Động
# Hệ Dòng Chảy Chủ Động
- **Sử dụng bơm màng RS365 (12V):** Thay thế bơm nhu động chậm chạp hoặc dòng chảy trọng lực yếu.
- **Sơ đồ:** Hút chủ động theo chuỗi `Nguồn -> Khay đo -> Bơm -> Đường xả`.
- **Chống tắc nghẽn:** Sử dụng đường ống lớn (Đường kính trong >6mm, gấp 3 lần hạt 2mm).
- **Lọc rác sơ cấp:** Lưới thô lỗ >5mm để loại rác quá khổ (cành, lá), giữ lại hạt mục tiêu.

---

# Slide 12: Thiết Kế Đáy Khay & Mực Nước
# Thiết Kế Mực Nước
- **Nước mỏng lý tưởng (~6mm):**
  - Giữ hạt nổi trên mặt (PE/PP) và hạt chìm dưới đáy (PET/PS) cùng chung một vùng lấy nét ảnh (DOF).
  - Tránh hiện tượng rác xếp chồng lên nhau gây đếm sai.
- **Chống đọng/Bẫy rác:** Các góc trong khay được bo tròn (fillet) và xử lý silicon, đảm bảo xả sạch sẽ không sót hạt nào cho lần đo kế tiếp.

---

# Slide 13: Chu Trình Stop-Flow
# Chu Trình Vận Hành: Tổng Quan
Hệ thống vận hành gián đoạn để tối ưu ảnh chụp:
1. **Cấp mẫu (Fill):** Bơm đưa nước lên khay đạt mực nước chuẩn.
2. **Đóng băng (Settle):** Tắt bơm 1-2s, van tự chặn giúp mặt nước tĩnh lặng.
3. **Chụp ảnh (Capture):** Camera độ phân giải cao ghi lại ảnh.
4. **Xử lý (Process):** Đếm, đo, phân loại hạt (On-device).
5. **Xả sạch (Flush):** Bơm hết công suất xả rác và nước dơ ra ngoài.

---

# Slide 14: Tại Sao Bắt Buộc Dùng Stop-Flow?
# Tầm Quan Trọng Của Stop-Flow
- **Rolling shutter:** Tránh vật thể bị nhòe và méo hình do hạt trôi nhanh hơn tốc độ quét của cảm biến camera.
- **Loại bỏ nhiễu khúc xạ:** Mặt nước phẳng lặng không tạo gợn sóng làm sai lệch bóng hạt.
- **Mẫu rời rạc, cố định:** Chỉ đếm rác trong thể tích nước xác định (quy ra nồng độ rác).
- **Tránh đếm lặp:** Các hạt không bị đếm thành 2 hạt nếu di chuyển giữa các khung hình liên tiếp.

---

# Slide 15: Pipeline Xử Lý Ảnh (Hybrid)
# Thuật Toán Xử Lý: Hybrid AI / CV
Mô hình chạy trực tiếp trên thiết bị (On-device) tại XIAO ESP32-S3:
1. **Classical Computer Vision:** 
   - Ngưỡng hóa vùng tối/sáng.
   - Khoanh vùng (Connected Components).
   - Xuất ra Toạ độ tâm & Kích thước từng hạt.
2. **Machine Learning (TinyML):** 
   - Cắt riêng lẻ từng khối (Crop).
   - Đưa qua mạng Nơ-ron phân loại đó là rác loại nào.

---

# Slide 16: Ưu Điểm Phương Pháp Hybrid
# Tại Sao Chọn Hybrid?
- **Độ chính xác kích thước:** Thuật toán CV cổ điển đo chu vi/diện tích hạt chuẩn xác, vượt trội so với định dạng "khung giới hạn" (bounding box) của AI.
- **Tiết kiệm RAM & CPU:** ESP32 không gánh nổi các mô hình AI phát hiện vật thể (Object Detection) ở độ phân giải cao.
- **Xử lý vi mô thông minh:** Chia nhỏ vùng ảnh cho mạng TinyML giúp tăng tốc độ phân loại đáng kể.

---

# Slide 17: Tại Sao Không Dùng Object Detection?
# Hạn Chế Của AI Phát Hiện (Như FOMO)
- **Thiếu chi tiết (Downsampling):** Chạy FOMO yêu cầu đưa ảnh về cỡ nhỏ (96x96), rác 1mm chỉ bằng 1 chấm pixel, rất dễ bị bỏ qua.
- **Mất thông tin kích thước:** Các mạng AI nhẹ như FOMO chỉ trả về toạ độ hạt, không thể biết kích cỡ của hạt để tổng hợp phân bố dòng rác.

---

# Slide 18: Lịch Sử Cải Tiến
# Hành Trình Cải Tiến Thiết Kế
| Phiên Bản Cũ | Baseline Mới |
|---|---|
| Chiếu tia cực tím (UV) | Chụp bóng ngược sáng nền trắng |
| Chỉ dùng mô hình AI (FOMO) | Thuật toán lai CV đếm đo + ML phân loại |
| Kính thủy tinh che mặt nước bị chìm | Cửa sổ cố định hoặc đĩa acrylic tràn |
| Bơm nhu động siêu chậm | Bơm màng RS365 áp suất mạnh, cực nhanh |

---

# Slide 19: Hướng Mở Rộng Tương Lai
# Tiềm Năng Mở Rộng
- **Phân định tính chất hóa học:** Kết hợp nhuộm huỳnh quang đặc thù (Nile Red) và đèn UV 365nm để phân biệt chắc chắn vi nhựa và tạp chất tự nhiên.
- **Scale kích thước rác:** Thay đổi cụm bơm xả công nghiệp để theo dõi dị vật lớn hơn.
- **Đo tự động liên tục (Continuous flow):** Nâng cấp lên module camera Global Shutter tích hợp đèn chớp (Strobe Light) để không cần dừng bơm.

---

# Slide 20: Kết Luận Dự Án
# Lời Kết
- **Aqua Scope** là minh chứng của một giải pháp Edge AI/IoT kết hợp cơ khí, vật lý quang học và trí tuệ nhân tạo.
- Khẳng định giá trị của việc dùng **CV cổ điển** đúng lúc đúng chỗ để giải quyết bài toán đo đạc vật lý.
- Thiết kế phần cứng tuy đơn giản (3 KHÔNG) nhưng **kiểm soát được mọi điều kiện môi trường chụp ảnh**, nền tảng cho độ tin cậy của phần mềm.
