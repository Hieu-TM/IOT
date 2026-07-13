# Biến thể 1D — Kế hoạch chi tiết (Optofluidic Light-Scattering + TinyML)

> Hướng ĐÃ CHỐT 2026-07-12: **chỉ cảm biến quang 1D (photodiode), KHÔNG camera, KHÔNG holography.**
> Deliverable yêu cầu: **đếm + phân bố size + phân loại.**
> File này là kế hoạch thiết kế, **chưa dựng phần cứng**. Nền tảng: xem [`00_huong_1D_va_holoscope.md`](00_huong_1D_va_holoscope.md).
> Bài gốc: Cerioli et al., *Efficient Detection of Microplastics on Edge Devices…*, IEEE Access 2025.
> Code bài gốc: https://github.com/alecerio/microplastic

---

## 1. Nguyên lý — đây là một "optical particle counter" dòng chảy

Một chùm sáng hẹp (LED hội tụ hoặc laser diode) chiếu ngang một **kênh dòng chảy mảnh**. Mỗi hạt
băng qua vùng cảm biến tạo **một xung tín hiệu theo thời gian** trên photodiode. Đọc chuỗi xung này
bằng ADC của ESP32-S3 → mỗi hạt = 1 waveform (~41 mẫu như bài gốc).

Đây là họ thiết bị **Coulter-counter/flow-cytometer quang học**, khác hẳn baseline camera-silhouette.
Điểm mấu chốt: **đếm HẠT-TỪNG-HẠT theo thời gian** trong lúc nước vẫn chảy.

### Hệ quả kiến trúc lớn: BỎ Stop-Flow
Baseline dùng Stop-Flow vì đếm bằng **1 khung ảnh** (rolling shutter — memory `stopflow-rationale`).
1D đếm liên tục khi hạt trôi qua → **không cần dừng bơm để chụp**. Chảy đều, đếm liên tục cho **độ
phủ thể tích tốt hơn** một khung ảnh tĩnh. (Vẫn giữ tuỳ chọn dừng bơm để xả/vệ sinh.)

---

## 2. Hoà giải deliverable với giới hạn thật của 1D

| Deliverable | 1D làm được? | Cách làm | Ghi chú thẳng |
|---|---|---|---|
| **Đếm** | ✅ Tốt | Đếm số xung / thể tích. Cần **lưu lượng bơm** → thể tích để ra nồng độ (hạt/mL). | Lỗi trùng (coincidence) nếu >1 hạt trong chùm cùng lúc → cần kênh đủ hẹp. |
| **Phân bố size** | ✅ Được (ta TỰ THÊM) | **Biên độ + độ rộng xung ∝ kích thước.** Hiệu chuẩn bằng **hạt chuẩn** (bi polystyrene/thuỷ tinh đường kính biết trước) → map biên độ→size → **histogram**. | Bài gốc KHÔNG làm phần này (chỉ nhị phân). Đây là đóng góp riêng của đồ án. |
| **Phân loại loại hạt** | ⚠️ Chỉ THÔ | Xem §4. Thực tế nhất: **hạt rắn vs bọt khí** + phân lớp theo size, KHÔNG phải loại polymer. | **Mắt xích yếu nhất.** Không phân biệt được hoá học. Phải nói rõ khi bảo vệ. |

**Kết luận trung thực:** 1D-only đáp ứng **đếm + phân bố size rất tốt**; "phân loại" nên hạ kỳ vọng
xuống mức **phân biệt hạt rắn / bọt khí / (tuỳ chọn) lớp size**, không hứa phân loại polymer.

---

## 3. Phần cứng cảm biến (cần TỰ DỰNG — bài gốc chỉ mô phỏng synthetic)

- **Nguồn sáng:** laser diode rẻ (vd 650nm) hoặc LED + thấu kính hội tụ → **chùm/màn sáng hẹp**
  cắt ngang kênh. Laser cho vùng cảm biến gọn, tín hiệu ổn định.
- **Kênh dòng chảy:** ống/khe trong suốt **đủ hẹp để hạt qua gần như từng-hạt-một** nhưng không
  nghẽn. ⚠️ Mâu thuẫn cần giải: test scope hiện <2mm, nhưng thiết kế gốc nói debris tới 5mm và
  pre-screen >5mm. Kênh hẹp cho <2mm sẽ **không hợp với hạt 5mm** — chốt lại phạm vi trước khi
  định đường kính kênh.
- **Đầu dò (khuyến nghị 2 kênh để cứu phân loại):**
  - **Extinction/obscuration:** photodiode thẳng trục → hạt che chùm → **xung âm (dip)**. Tốt cho
    hạt lớn, cho "diện tích cản sáng".
  - **Scatter:** photodiode lệch góc (vd 90°) → bắt ánh sáng tán xạ → **xung dương (peak)**. Nhạy
    hạt nhỏ (cách của bài gốc).
  - **Tỉ số scatter/extinction** là đặc trưng mạnh để **tách bọt khí** (chiết suất ~1.0, tán xạ
    kiểu khác) khỏi hạt rắn.
- **Khuếch đại + số hoá:** transimpedance amplifier (op-amp) → ADC. ADC nội ESP32-S3 có thể đủ cho
  tốc độ thấp; nếu hạt qua nhanh cần **ADC ngoài SPI** để lấy đủ ~41 mẫu/xung.
- **Bơm:** tái dùng **RS365 12V** của baseline (memory `pump-drive-decision`) — chạy **liên tục**,
  cần đo/khoá lưu lượng để quy đổi thể tích.

### 3b. Bảng linh kiện + cơ chế (giải thích cho prototype)

Chuỗi tín hiệu: `Laser → nước/hạt → Photodiode (sáng→dòng) → TIA (dòng→áp) → ADC (41 mẫu) → NeuralCasting`.

| Khối | Cơ chế | Thông số / linh kiện gợi ý | Ghi chú |
|---|---|---|---|
| **Nguồn sáng** | Chùm hẹp cắt ngang kênh | Laser diode 650nm ~5mW (hoặc LED + thấu kính hội tụ) | Laser cho vùng đo gọn, ổn định |
| **Photodiode** | Sáng → dòng (photocurrent); hạt che/tán xạ → dòng đổi = tín hiệu | Si PIN, vd **BPW34** (~7.5mm², ~0.35A/W@650nm, ~100ns); mắc **reverse bias** | Đỉnh nhạy phải trùng bước sóng laser |
| **Kênh dòng chảy** | Ép hạt qua từng-hạt-một; định thể tích cảm biến | Ống trong **ID ~2–3mm** (scope <2mm), acrylic/thuỷ tinh/FEP; chùm cắt vuông góc | Hẹp→tách tốt/dễ nghẽn; rộng→trùng hạt |
| **Đầu dò (hình học)** | Đặt PD quyết định loại tín hiệu | **Hấp thụ:** PD đối trục → dip. **Tán xạ:** PD lệch 90° → peak (nhạy hạt nhỏ) | Dùng **cả 2** → tỉ số scatter/extinction tách bọt khí vs rắn |
| **Khuếch đại (TIA)** | Dòng nA–µA → áp: **Vout = I×Rf** | Op-amp **MCP6001/LM358** (demo) hoặc **OPA381**; **Rf 100k–1MΩ** đặt độ nhạy; Cf đặt băng thông | Rf lớn = nhạy hơn nhưng chậm/nhiễu hơn |
| **Số hoá** | Lấy 41 mẫu/xung | ADC nội ESP32-S3 12-bit, hoặc **MCP3201** SPI nếu cần nhanh | Đủ nhanh để bắt trọn xung |

### 3c. Chọn bước sóng + linh kiện laser/TIA (2026-07-12)

**Bước sóng — chọn 650nm đỏ (KHÔNG dùng 400–450nm):** hạt 1–5mm có tham số kích thước
x=πd/λ ≈ 5.000–24.000 → **chế độ quang hình học**, Qext≈2 **không phụ thuộc bước sóng** → tín hiệu
che-khuất như nhau. Đỏ còn LỢI: photodiode Si đáp ứng ~0.4 A/W @650nm (gấp ~2× so ~0.2 @450nm),
rẻ, dễ căn, an toàn mắt hơn. Xanh/UV chỉ đáng cân nhắc nếu chuyển sang vi nhựa micron thật hoặc
huỳnh quang Nile-Red (ngoài phạm vi). Lưu ý nước hấp thụ vài mm: không đáng kể cả hai.

**Diode laser 650nm:** ⭐ **module dot Ø6mm 650nm 5mW 5V** (có driver dòng sẵn, chỉ cấp 5V+GND —
**khớp `laser_dia=6`**). Thay thế: KY-008 (PCB Arduino), hoặc module **line-laser** (chỉ nếu chuyển
sang che-khuất thuần phủ hết tiết diện — không hợp tán xạ 90°). Module rẻ có nhiễu cường độ/trôi nền
→ bù bằng trừ-nền firmware hoặc AC-coupling.

**Photodiode (cần 2 con: che-khuất + tán xạ):** phải là **PIN photodiode silicon bản TRONG**
(KHÔNG dùng phototransistor/quang trở — chậm, phi tuyến; ⚠️ **KHÔNG dùng bản kính lọc IR đen "-F/-P"
vì chặn luôn 650nm**).
- ⭐ **SFH203** (bản trong) — gói **5mm tròn kiểu LED → khớp thẳng `pd_dia=5`, không sửa model.**
- **BPW34** (bản trong, KHÔNG phải BPW34F) — rẻ nhất, đúng loại bài báo, diện tích lớn (tín hiệu
  mạnh) NHƯNG **chữ nhật ~5.4×4.3 → phải đổi bore thành hốc chữ nhật** (mục ⚠️ ở §8b/#7).
- Kênh **tán xạ** tín hiệu yếu hơn → dùng cùng PD nhưng **Rf lớn hơn** (2–4.7MΩ) hoặc PD diện tích lớn hơn.

**Mạch TIA (Vout = I_ph × Rf + Vref):**
- Op-amp: ⭐ **MCP6002** (CMOS ~1pA bias, rail-to-rail, nguồn đơn 3.3V — hợp ESP32; 2 op-amp/vỏ,
  con thứ 2 làm lọc/đệm). Tốt hơn: OPA381. Cuối: LM358 (bias cao, chỉ khi tín hiệu lớn).
- **Rf ≈ 1MΩ** (chỉnh 100k–1M theo độ lớn tín hiệu). **Cf ≈ 5–15pF** song song Rf (ổn định +
  cắt băng thông ~kHz; xung hạt chậm ~10–100Hz nên tha hồ lọc nhiễu).
- **Vref = ½ nguồn** vào chân + (nguồn đơn) → đầu ra nằm giữa 0–3.3V. Che-khuất: nền cao, xung sụt;
  tán xạ: nền thấp, xung nhô. PD **zero-bias** (đơn giản, ít nhiễu — băng thông thấp không cần reverse).
- ADC: ESP32 12-bit đủ cho xung ms (giữ 0.1–3.0V tránh phi tuyến); cần nhanh → MCP3201/3208 SPI
  (ADS1115 quá chậm 860 SPS).

---

## 4. Model & pipeline on-device

Giữ tinh thần bài gốc (model nhỏ, PTQ int8, NeuralCasting) NHƯNG nâng bài toán từ nhị phân → đa nhiệm:

1. **Phát hiện xung (classical):** threshold + cửa sổ hoá → cắt waveform 41 mẫu quanh mỗi hạt.
2. **Đo size (hồi quy / bin):** từ biên độ + độ rộng (+ diện tích xung) → size, dùng bảng hiệu chuẩn.
   Có thể chỉ cần công thức hiệu chuẩn cổ điển, không cần NN.
3. **Phân loại (NN nhỏ):** đưa waveform thô (hoặc đặc trưng scatter/extinction) vào **1D-CNN hoặc
   GRU nhỏ** → nhãn: {hạt rắn, bọt khí, nhiễu} (+ tuỳ chọn lớp size). Vẫn đủ nhỏ để **NeuralCasting
   compile ONNX→C**, chạy µs-ms trên ESP32-S3.
4. **Tổng hợp:** đếm theo nhãn + thể tích → **nồng độ + histogram size + tỉ lệ loại** cho mỗi mẫu.
5. **Truy xuất (requirement nhà máy — memory `application-context`):** log sample ID / timestamp /
   count / phân bố size / phân loại cho mỗi mẻ.

**NeuralCasting còn dùng được** vì model vẫn nhỏ (MLP/GRU/1D-CNN) — đây là lợi thế giữ nguyên so với
holography (backpropagation nặng, không dùng được NeuralCasting).

---

## 5. Rủi ro & việc cần chốt

1. **Dataset:** bài gốc là **synthetic** (mô phỏng theo Sasso 2024). Muốn số liệu thật cần **tự thu
   dữ liệu hiệu chuẩn** bằng hạt chuẩn, hoặc dựng simulator riêng. → khối lượng công việc chính.
2. **Phạm vi hạt (chốt trước khi thiết kế kênh):** <2mm hay tới 5mm? Ảnh hưởng đường kính kênh +
   nguy cơ nghẽn + coincidence.
3. **Coincidence / lưu lượng:** cần kênh hẹp + lưu lượng vừa để hạt qua từng-hạt; và đo lưu lượng để
   ra nồng độ.
4. **Phân loại chỉ thô:** không hứa loại polymer. Hạ kỳ vọng xuống rắn/bọt/size-class.
5. **Điểm bán khi bảo vệ:** biến thể HƠN baseline camera ở đâu? → (a) **né blocker lấy nét**
   `camera-focus-limit` (photodiode không cần nét); (b) **đếm liên tục, không cần Stop-Flow**;
   (c) RAM/Flash/điện cực nhỏ, on-device trọn vẹn nhờ NeuralCasting. ĐỔI LẠI: mất ảnh từng hạt và
   phân loại type chỉ ở mức thô.

---

## 6. Việc tiếp theo (đề xuất)

- [ ] Chốt phạm vi hạt (<2mm vs 5mm) → khoá kích thước kênh + lưu lượng.
- [ ] Chốt cấu hình đầu dò: chỉ scatter (rẻ) hay scatter+extinction 2 photodiode (phân loại tốt hơn).
- [ ] Dựng mạch: laser/LED + photodiode + TIA + ADC → test xung thật với hạt mẫu.
- [ ] Thu/sinh dataset waveform có nhãn (size + loại) để train.
- [ ] Train MLP/1D-CNN/GRU → PTQ int8 → NeuralCasting → đo latency/RAM trên ESP32-S3.
- [ ] Thiết kế cơ khí kênh dòng chảy + gá quang (thay cho ống ảnh + khay + hộp đèn nền của baseline).
