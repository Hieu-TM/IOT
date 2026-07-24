# Nghiên cứu lặng sóng khay Stop-Flow — bản hợp nhất & đã sửa lỗi

**Nguồn gốc:** hợp nhất 3 bài nghiên cứu AI-generated do người dùng cung cấp —
"...B.pdf" (v1, giả định bơm đẩy trước khay — sai cấu hình), "...B v2.pdf" (v2, sửa
đúng cấu hình bơm hút sau khay), "...B v3.pdf" (v3, tự sửa thêm lỗi MOSFET + thêm
giải pháp cổng ra). Tài liệu này **kiểm chứng lại từng công thức bằng tay**, giữ
phần đúng, sửa lỗi tính toán/logic tìm được, cộng thêm 1 phát hiện thực tế của người
dùng không có trong cả 3 bản PDF (§7).

**Không dùng tài liệu AI-generated nguyên văn** — đây là nền tảng đã kiểm chứng cho
spec thiết kế tiếp theo (`flow_tray_003.scad` + firmware bơm), không phải bản dịch
lại PDF.

---

## PHẦN A — TÓM TẮT QUYẾT ĐỊNH CUỐI CÙNG

| # | Hạng mục | Quyết định | Trạng thái |
|---|---|---|---|
| 1 | Vách cong tiêu năng ở rìa khay | **DÙNG** — arc baffle bán kính 17.6mm, góc 90°, cao 5mm | Cần vẽ SCAD kiểm tra va chạm |
| 2 | Lưới cột trụ thay khe khuếch tán vào | **DÙNG** — Ø1.2mm, khe hở 2.5mm | Cần test thực nghiệm hạt dạng sợi |
| 3 | Bellmouth ở cổng ra | **DÙNG** — bo R=3mm, Ø6mm→Ø12mm | Rủi ro thấp, ưu tiên làm trước |
| 4 | PWM soft-stop (MOSFET) | **DÙNG** — IRLZ44N, 20kHz, ramp 300-400ms | Đã đủ dữ liệu, có thể triển khai |
| 5 | PWM cruise-duty trong pha FILLING | **DÙNG nguyên tắc**, chưa có số cụ thể | Cần thực nghiệm để chốt % duty |
| 6 | T-Dome dập xung phía hút (cổ hẹp Ø1.2mm) | **CÂN NHẮC NGHIÊM TÚC** (không còn "hoãn") | Cần in thử lỗ Ø1.2mm + chốt V_air |
| 7 | Lệch góc cổng ra tạo xoáy (phương án a) | **KHÔNG DÙNG** làm giải pháp chính | — |
| 8 | Nâng cổng ra thành mép tràn (phương án b) | **LOẠI BỎ** | Vi phạm ràng buộc cứng |
| 9 | Tách khay 2 khoang qua khe hẹp (phương án d) | **LOẠI BỎ** | Vi phạm ràng buộc cứng |

**2 việc phải đo thật trước khi chốt số liệu cuối** (không thể tính suông trên giấy):
- Tần số nhịp màng bơm RS365 thật (giả định 5-10Hz trong PDF chưa kiểm chứng — quyết
  định cả nguy cơ cộng hưởng §2 lẫn thiết kế T-Dome §6 phụ thuộc số này).
- Ngưỡng gây "ực nước" ở cổng ra thật để chốt % PWM cruise-duty (không có công thức
  lý thuyết đơn giản, phụ thuộc đường cong bơm thật).

---

## PHẦN B — CƠ SỞ VÀ CHI TIẾT KỸ THUẬT

## 1. Thông số đầu vào (đã khớp `constants.scad` thật của dự án)

| Thông số | Giá trị | Nguồn |
|---|---|---|
| Bán kính lòng nước khay | R = 20mm (Ø40mm) | `tray_inner` |
| Mực nước khi settle | h = 6mm | `water_depth` |
| Đường kính ngoài khay | Ø44mm | `tray_outer` |
| Chiều cao thành khay | 12mm | `tray_depth` |
| Cấu hình bơm | RS365 12V màng, đặt SAU khay, HÚT (source→tray→pump→waste) | CLAUDE.md, đã chốt |
| Lưu lượng bơm | 1.5–2.2 L/min — **chưa đo thật** | datasheet chung R365 |
| Tần số nhịp màng | 5–10Hz — **chưa đo thật** | datasheet chung R365 |
| Hạt cần đo | 1–2mm | CLAUDE.md |
| Ràng buộc cứng | Không chi tiết giữ hạt; mọi hạt phải ra hết khi flush | `flow_tray_002.scad` |
| Cổng ra hiện tại | Ø6mm (`outlet_bore`), sát đáy `port_z=3mm` | `constants.scad:59` |

## 2. Cơ sở vật lý sóng — đáng tin cậy (giống nhau ở cả 3 bản PDF)

Lý thuyết sóng nông chuẩn (công thức tắt dần Miles 1967 cho bể hình trụ), khớp đúng
kích thước khay thật (R=20mm, h=6mm):

| | Mode ngang (1,1) | Mode hướng tâm (0,1) |
|---|---|---|
| Tần số riêng tự nhiên | **3.495 Hz** | **7.037 Hz** |
| Hệ số tắt dần tổng γ_total | 0.468 s⁻¹ | 0.492 s⁻¹ |
| Biên độ còn lại sau 2s | 39.2% A₀ | ~38% A₀ |
| Thời gian dập 99% (tự nhiên) | 9.85s | 9.36s |

**Kết luận:** pha SETTLING 2 giây **không đủ** nếu chỉ trông chờ ma sát nhớt tự
nhiên — phải giảm biên độ kích thích ban đầu A₀ ngay từ đầu (hình học khay + cách
tắt bơm), không thể chỉ kéo dài thời gian chờ.

**Nguy cơ cộng hưởng (tự suy ra, không có trong PDF):** tần số riêng 3.5Hz/7.0Hz —
và fn≈5-6Hz của hệ T-Dome (§6) — đều nằm trong/sát dải tần bơm màng 5-10Hz (số
chưa đo thật). Đây là lý do §1 xếp việc đo tần số bơm thật vào ưu tiên cao nhất.

## 3. Hình học khay — 6 phương án (a-f), đánh giá và chọn

| # | Phương án | Kết luận | Lý do |
|---|---|---|---|
| a | Lệch cổng ra 90°/120° (tạo xoáy) | Không dùng làm chính | Tạo dòng xoáy bền, quay lâu mới dừng → vẫn méo ảnh do khúc xạ mặt nước không phẳng (nhận định định tính trong PDF, không có công thức chứng minh) |
| b | Nâng cổng ra thành mép tràn (weir) | Loại bỏ | Vi phạm ràng buộc cứng: hạt chìm sát đáy bị bỏ lại khi dòng xả lướt phía trên |
| c | Vách cong ngầm sát rìa khay (arc baffle) | **Dùng — chính** | Đủ nhỏ để lọt Ø44mm (r≈17.6mm, không phải kiểu 3 tầng 25mm của v1 — v1 sai vì lấy tỷ lệ từ bể xử lý nước cỡ lớn). Không chắn vùng ảnh trung tâm. Tự làm sạch khi flush |
| d | Tách khay 2 khoang qua khe hẹp | Loại bỏ | Khe hẹp = điểm kẹt hạt 1-2mm, vi phạm ràng buộc cứng |
| e | Lưới cột trụ thay khe khuếch tán (Porous Post Grid) | **Dùng — kết hợp (c)** | Chia tia nước thành tia siêu nhỏ tiêu năng lượng nhanh hơn khe hở lớn hiện tại |
| f | PWM soft-stop | **Dùng — bắt buộc** | Xem §5 |

### 3.1 Thông số thiết kế — vách cong (c) + lưới cột trụ (e)

```
post_diameter = 1.2   mm   // cột trụ đứng tại cổng vào (thay khe 20×3mm)
post_gap      = 2.5   mm   // khe hở GIỮA các cột — PHẢI > hạt lớn nhất (2mm)
post_h        = 6.0   mm   // bằng mực nước tĩnh

baffle_thickness = 1.2 mm  // 3 đường in FDM 0.4mm/perimeter
baffle_r_mid     = 17.6 mm // bán kính đặt vách cong (khay lòng nước bán kính 20mm)
baffle_angle      = 90  °  // góc quét cung chắn, đặt trước khe vào để chắn tia thẳng
baffle_h          = 5.0 mm // thấp hơn mực nước tĩnh (6mm) 1mm để thoát bọt khí
fillet_r          = 2.0 mm // bo tròn 2 đầu mút vách — chống kẹt hạt khi flush
```

**Việc còn cần làm khi vẽ SCAD thật:**
- Kiểm tra va chạm hình học: vách cong 90° so với hộp loe (plenum rộng 22mm, đã có
  trong `flow_tray_002.scad`) và 3 cửa sổ ngàm snap-fit (90°/210°/330° theo
  `flow_tray_002.scad:86`) — góc đặt vách phải né các cửa sổ này.
- Đánh đổi diện tích ảnh: vách chiếm hành lang bán kính 17.6-20mm → vùng ảnh trung
  tâm còn Ø34mm thay vì Ø40mm gốc (giảm ~15% đường kính, ~28% diện tích khung hình).
  **Cần người dùng xác nhận chấp nhận đánh đổi này.**
- Khoảng hở 2.5mm cho hạt 2mm chỉ chừa 0.5mm dư — đủ cho hạt tròn/gọn nhưng hạt dạng
  sợi (fiber) có thể mắc ngang qua nhiều cột. Cần kiểm tra thực nghiệm.

## 4. Cổng ra — Bellmouth Outlet (giải quyết hiện tượng "nghẹn miệng cống")

**Vấn đề (quan sát thực tế của người dùng, không có trong PDF gốc):** cổng ra là lỗ
tròn Ø6mm sát đáy — **bằng chính xác** mực nước tĩnh 6mm. Khi bơm chạy nhanh (relay,
không giảm tốc), nước dồn ứ tại miệng lỗ rồi dội ngược vào khay, gây sóng liên tục —
giống hiện tượng "hút ừng ực" khi xả bồn tắm (lỗ thoát nhỏ so với mực nước + tốc độ
hút cao → mực nước sát miệng lỗ tụt cục bộ, tạo xoáy hút khí kiểu phễu).

Bài v3 độc lập tự phát hiện đúng hiện tượng này (gọi là "dồn ứ thủy lực + vena
contracta tại cổng xả sắc cạnh") — 2 nguồn độc lập (quan sát thực tế + phân tích lý
thuyết) hội tụ cùng 1 vấn đề, tăng độ tin cậy.

**Giải pháp đã kiểm chứng — Bellmouth (miệng loe hình phễu):**
```
outlet_d            = 6.0  mm  // giữ nguyên (ràng buộc cứng chống kẹt hạt)
outlet_bellmouth_r   = 3.0  mm  // bo loe miệng lỗ phía trong khay, sát đáy acrylic
// → miệng loe hiệu dụng mở rộng thành Ø12mm (outlet_d + 2×outlet_bellmouth_r)
```
Hệ số tổn thất cửa vào K giảm từ ~0.5 (lỗ sắc cạnh, số liệu tiêu chuẩn cơ lưu chất)
xuống <0.05 (bellmouth, r/d=3/6=0.5 — vượt xa ngưỡng khuyến nghị r/d≥0.15-0.2). Đây
là kỹ thuật **"pump suction bellmouth"** tiêu chuẩn công nghiệp (chống xoáy hút khí ở
đầu hút bơm ly tâm) — đã kiểm chứng đúng cả về công thức lẫn thực hành phổ biến.

**Đánh giá:** rủi ro thấp — chỉ là bo tròn mép lỗ đã có, không thêm chi tiết mới,
không có rủi ro in 3D đáng kể. **Ưu tiên cao nhất trong các hạng mục còn lại, nên
làm ngay ở bản đầu.**

**Còn cần làm:** kiểm tra bellmouth Ø12mm đủ chỗ tại vị trí cổng ra (gần thành khay,
r=20mm) mà không làm mỏng thành quá mức — cần vẽ thử OpenSCAD.

**Bổ sung điều khiển (mở rộng PWM §5):** nên thêm giới hạn duty cycle "cruise" thấp
hơn 100% trong suốt pha FILLING (không chỉ lúc dừng) để giảm vận tốc hút trung bình
dưới ngưỡng gây xoáy — giá trị cụ thể cần xác định bằng thực nghiệm.

## 5. Điều khiển bơm — PWM soft-stop

**Lỗi đã sửa (giống nhau ở v1 và v2):** cả 2 bản đề xuất MOSFET **IRF540N**
("Standard-level", cần V_GS≈10V để mở hoàn toàn — ESP32 chỉ có 3.3V, không đủ, gây
nóng bất thường). Bản v3 tự sửa đúng ngay từ đầu.

**Chốt dùng: IRLZ44N** (Logic-level, mở gần hết cỡ ở 3.3-5V) — khớp GPIO ESP32 và
đúng BOM đã chốt sẵn của dự án (memory `pump-drive-decision`).

```
pwm_frequency   = 20000   // 20kHz — ngoài ngưỡng nghe, dòng cuộn cảm liên tục
ramp_down_time  = 300–400 // ms — giảm duty 100%→0% tuyến tính trước khi tắt hẳn
                          // (tránh búa nước — xung áp suất khi dừng đột ngột)
```

Bổ sung an toàn (cùng nguyên tắc đã áp dụng cho relay trong `pump_stopflow_test.ino`):
thêm **điện trở kéo xuống (pulldown) ~10kΩ giữa Gate và GND** để MOSFET mặc định TẮT
khi ESP32 reset/boot và GPIO trôi nổi.

## 6. T-Dome — bộ dập xung phía hút (cân nhắc nghiêm túc, không còn "hoãn")

**Lịch sử sửa lỗi qua các phiên bản:**
- v1: giả định bơm đẩy, đặt bộ dập xung TRƯỚC khay — sai vị trí so với cấu hình thật.
- v2: sửa đúng vị trí (sau khay, phía hút) nhưng **toán sai 1000×** (nhầm đơn vị d⁴):
  R báo cáo 314 Pa·s/m³ (đúng phải ≈314,000), τ báo cáo 47ns (đúng phải ≈47µs). Cổ
  nối KHÔNG thắt hẹp (Ø6mm, bằng ID ống chính) → tôi tính lại cho thấy thiết kế này
  **không lọc được** rung bơm 5-10Hz (tần số cắt thực tế ≈3.4kHz, cao hơn tần số cần
  lọc 340-680 lần). Kích thước bình khí cũng sai (120mm chỉ chứa ~6mL, không đủ 15mL
  mục tiêu — cần ~298mm).
- v3: đổi sang **cổ nối THẮT HẸP Ø1.2mm×10mm** (chỉ ở nhánh đứng không có hạt qua,
  đường chính Ø6mm không đổi) + bình khí Ø16mm cao 50-75mm (đã sửa đúng bài toán thể
  tích của v2). Dùng mô hình bậc 2 đầy đủ (RLC — có quán tính chất lỏng), tính hệ số
  cản ζ thay vì chỉ tần số cắt — **cách làm chính xác hơn** so với ước tính bậc 1 tôi
  tự làm trước đó (tôi từng ước tính cần lỗ ~0.5mm, rủi ro in cao — nay rút lại, số
  đúng của v3 là Ø1.2mm, khả thi hơn nhiều).

**Đã kiểm chứng tay — hầu hết đúng:**

| Đại lượng | v3 | Tính lại | Đánh giá |
|---|---|---|---|
| R_throat (Ø1.2mm×10mm) | 1.97×10⁸ Pa·s/m³ | 1.97×10⁸ | Đúng |
| R_fluid1 (ống chính Ø6mm×200mm) | 6.29×10⁶ | 6.29×10⁶ | Đúng |
| L_fluid1 (quán tính cột nước) | 7.07×10⁶ kg/m⁴ | 7.07×10⁶ | Đúng |
| τ nhánh khí (V=15mL) | 0.0295s | 0.0295s | Đúng |
| Hệ số cản ζ (V=15mL) | 0.467 | 0.468 | Đúng |
| Kích thước bình khí Ø16mm | 50mm(10mL)/75mm(15mL) | Khớp chính xác | Đúng |
| ωn=97 rad/s ↔ fn=4.88Hz | — | Tự mâu thuẫn: 2π×4.88Hz=30.7 rad/s, không phải 97. fn đúng, ωn sai | Lỗi nhỏ, không đổi kết luận |

**Lỗi nội bộ chưa được báo cáo tự nhận ra:** bảng thông số cuối cùng chọn
`dampener_volume_ml = 10.0` nhưng ζ=0.47 lại tính từ 15mL. Với đúng 10mL: **ζ≈0.38**,
**fn≈5.98Hz** (nằm giữa dải nghi vấn cộng hưởng 5-10Hz, sát hơn số 4.88Hz báo cáo
dùng). ζ=0.38 vẫn tốt hơn nhiều so với ζ=0.014 nếu không thắt cổ — kết luận chung
(cổ hẹp giúp tránh cộng hưởng) vẫn đứng vững, nhưng cần **chốt 1 bộ số nhất quán**
(10 hay 15mL) trước khi đưa vào SCAD.

**Khuyến nghị hiện tại:** đáng cân nhắc nghiêm túc cho bản đầu, với 2 điều kiện:
1. In thử xác nhận lỗ Ø1.2mm×10mm ổn định (không nghẹt do stringing).
2. Đo tần số nhịp màng bơm thật — vì toàn bộ lập luận chống cộng hưởng dựa trên giả
   định 5-10Hz chưa kiểm chứng.

**Hạn chế thực tế (không có trong PDF, tự bổ sung):** bộ tích áp kiểu "túi khí hở"
(không màng ngăn/bladder) theo thời gian có xu hướng hòa tan khí vào nước hoặc bị
hút ngược ra qua phía hút chân không — cần bổ sung khí định kỳ hoặc chấp nhận hiệu
quả giảm dần.

---

## PHẦN C — VẤN ĐỀ CÒN TỒN ĐỌNG (cần quyết định trước khi vẽ SCAD/viết firmware)

1. **Phạm vi sửa file:** tạo `flow_tray_003.scad` mới (giữ `_002` để so sánh) hay
   sửa thẳng `_002`? *(Chưa quyết)*
2. **Góc đặt chính xác của vách cong (c):** cần vẽ thử trong OpenSCAD để né hộp loe
   + 3 cửa sổ snap-fit, chưa chốt bằng số trên giấy. *(Chưa quyết)*
3. **Đánh đổi diện tích ảnh Ø40→Ø34mm** do vách cong (c) chiếm chỗ — cần người dùng
   xác nhận chấp nhận. *(Chưa quyết)*
4. **Đo thật tần số nhịp màng bơm RS365** — ảnh hưởng cả nghi vấn cộng hưởng khay
   (§2) lẫn thiết kế T-Dome (§6, fn≈5.98Hz nằm giữa dải nghi vấn). *(Chưa đo)*
5. **Chốt V_air cho T-Dome (10 hay 15mL)** — cần nhất quán trước khi tính lại ζ/fn
   chính xác để đưa vào SCAD. *(Chưa quyết)*
6. **Có làm T-Dome ở bản đầu hay không** — dù đã hạ mức rủi ro xuống "cân nhắc
   nghiêm túc", vẫn là 1 chi tiết mới + 1 lỗ nhỏ cần in thử trước. *(Chưa quyết)*
7. **% PWM cruise-duty trong pha FILLING** để né hiện tượng ực nước — không có công
   thức tính trước, cần thực nghiệm giảm dần từ 100% tới khi hết hiện tượng.
   *(Chưa có số — cần đo)*
8. **Kiểm tra bellmouth Ø12mm** đủ chỗ tại vị trí cổng ra thật không mỏng thành quá
   mức. *(Chưa vẽ)*

**Không còn tồn đọng (đã chốt, có thể triển khai luôn):** vách cong (c) + lưới cột
(e) như thiết kế hình học đề xuất ở §3.1; bellmouth outlet ở §4; MOSFET IRLZ44N +
tần số PWM 20kHz + ramp 300-400ms ở §5.

---

## PHẦN D — 6 lỗi phát hiện thêm khi DỰNG HÌNH HỌC (2026-07-23)

Sáu lỗi dưới đây chỉ lộ ra khi tính va chạm hình học thật, không lộ khi kiểm chứng
công thức. Số đã sửa nằm trong `openscad/constants.scad` §CHỐNG SÓNG; chi tiết lý do
trong `docs/superpowers/plans/2026-07-23-khay-lang-song-v003.md`.

*(Ghi chú bản này: mục PHẦN D ban đầu chỉ liệt kê 4 lỗi #1-4, phát hiện trong lúc
viết `constants.scad` — trước khi khay được dựng thành khối 3D thật. Sau khi dựng
`flow_tray_003.scad` và xuất STL, có thêm 2 lỗi Critical #5-6 lộ ra ở chính bước
dựng khối và kiểm manifold. Bổ sung vào cùng bảng dưới đây cho đủ.)*

| # | Số của tài liệu | Vấn đề | Số đã sửa |
|---|---|---|---|
| 1 | `baffle_r_mid = 17.6` | Hành lang sau vách chỉ 1.8mm < hạt 2mm. Đây là lối thoát DUY NHẤT của túi cổng vào ⇒ hạt kẹt vĩnh viễn ⇒ **vi phạm ràng buộc cứng** | `16.4` (hành lang 3.0mm) |
| 2 | `baffle_h = 5.0` | Thấp hơn mực nước 6mm ⇒ diện tích tràn qua nóc (~27.6mm²) còn lớn hơn diện tích đi vòng 2 đầu (~21.6mm²) ⇒ ~50% lưu lượng xả động năng thẳng vào MẶT NƯỚC. Lý do "thoát bọt" không áp dụng vì vách hở 2 đầu | `7.0` (> mực nước) |
| 3 | `post_gap = 2.5` | Chỉ dư 0.5mm so hạt 2mm, ngay CỬA VÀO. Nghẽn ở đây = hạt không vào khay = không đếm được (hỏng chính phép đo) | `inlet_gap_w = 3.5` |
| 4 | `fillet_r = 2.0` bo đầu mút vách | Bất khả thi trên vách dày 1.2mm (tối đa = 0.6mm) | bo bán nguyệt `0.6` |

**Giá phải trả đã chấp nhận (lỗi #1):** vách tại r=16.4 làm vùng ảnh hóa giảm Ø40 →
**Ø31.6mm** (~62% diện tích cũ). Không giảm độ phân giải hạt (vẫn ~14px/mm ở VGA),
chỉ giảm lượng nước soi được mỗi lần chụp. `baffle_r_mid` để dạng tham số, chỉnh lại
được sau in thử.

### Lỗi #5 và #6 — phát hiện sau khi dựng khối 3D thật, không lộ ở bước viết hằng số

Hai lỗi #1-4 ở trên lộ ra khi so công thức/kích thước trên giấy. Hai lỗi dưới đây
KHÁC HẲN về bản chất: chúng chỉ lộ ra khi thật sự dựng `flow_tray_003.scad` thành
khối solid và soi bằng CGAL/mặt cắt — bản thân các con số hình học (r, h, độ dày)
đều đúng như đã chốt ở bảng trên, nhưng CÁCH DỰNG khối lại sai.

| # | Giả định/cách làm ban đầu | Vấn đề | Đã sửa bằng |
|---|---|---|---|
| 5 | `arc_baffle()` được coi là đúc LIỀN với sàn khay (giống mọi chi tiết khác của khay) | Khay này **không có sàn in liền** — lòng Ø40 khoét XUYÊN SUỐT, đáy là đĩa acrylic rời lắp từ dưới lên (xem `tray_shell()`). Vách cong đặt tại bán kính 15.8–17.0mm, hành lang hạt 3.0mm cố ý chừa hở với thành, phía đối diện là bellmouth — nên vách **không chạm bất cứ thứ gì**. CGAL báo `Volumes: 3` (đúng ra 1 khối in liền phải là 2). In ra sẽ là 1 mảnh nhựa rời trôi tự do trong khay, có thể trôi vào và kẹt cổng ra Ø6mm — **chính cụm chống sóng biến thành thứ rác mà nó phải ngăn**, vi phạm thẳng ràng buộc cứng "không chi tiết nào được giữ hạt" | Thêm 3 gờ nối vách↔thành tại góc 150°/180°/210°, đặt ở z = 6.0–7.0mm — **hoàn toàn TRÊN mực nước 6mm**, nên hạt ngập nước luôn đi lọt phía dưới gờ và hành lang vẫn thông suốt trọn chiều sâu ngập nước. Đây cũng chính là lý do vách được chốt cao hơn mực nước 1mm ngay từ đầu (lỗi #2). Đã xác nhận: CGAL báo lại `Volumes: 2` |
| 6 | Vỏ ngoài bellmouth (`bell_outer()`) dựng bằng cách DỊCH bán kính profile ra `bell_wall` tại cùng góc quét, không phải offset theo pháp tuyến thật | Tại miệng loe, tiếp tuyến của profile lại chính là phương bán kính, nên phép dịch này suy biến gần về 0 — đo được thành thật chỉ còn **0.231mm**, dưới cả 1.2mm bề dày in tối thiểu. Sửa bằng `offset()` 2D thật (dựng vỏ theo pháp tuyến chuẩn) — nhưng đúng lúc đó lộ lỗi MỚI, nặng hơn: `offset()` bo luôn góc gấp sắc tại mép miệng loe, quét tràn vật liệu xuống dưới mặt phẳng miệng, đúng chỗ phần khoét rỗng (void) không có hình học để trừ đi ⇒ **bịt kín hẳn miệng loa kèn** (đặc hoàn toàn từ X=15.9 tới 16.9 tại tâm lòng ống) | Kẹp profile ngoài bằng điều kiện `y >= 0` sau bước `offset()` |

### Bài học rút ra — ghi lại cho lần dựng hình học tiếp theo

Cả 3 lỗi Critical của đợt này — thành mỏng knife-edge 0.231mm, lòng cổng ra bị bịt
kín hoàn toàn, và vách baffle trôi nổi — đều xuất STL "sạch", **không hề bị CGAL báo
non-manifold**. Manifold hợp lệ là điều kiện CẦN nhưng gần như không nói lên được gì
về việc một đường thoát có thực sự thông hay không, một thành có đủ dày để in hay
không, hay một chi tiết có thực sự gắn liền vào khối chính hay không — 3 lỗi trên
đều là solid kín, khép mặt, vẫn "manifold" theo đúng định nghĩa hình học, nhưng sai
hoàn toàn về công năng. Những tính chất đó phải được chứng minh riêng, bằng mặt cắt
(cross-section), dò giao cắt bằng khối thăm dò (probe intersection), hoặc đọc số
`Volumes:` do CGAL báo — không thể suy ra từ kết quả "manifold OK" của bước export.
