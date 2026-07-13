# Plan mô hình OpenSCAD — Đầu dò quang 1D (Optofluidic Sensor Head)

> Hợp đồng dựng model cho biến thể 1D (xem [`01_bien_the_1D_ke_hoach.md`](01_bien_the_1D_ke_hoach.md)).
> Phạm vi hạt: **1–5mm** (đã đổi từ <2mm). Ưu tiên số 1: **DỄ CHẾ TẠO**.
> Model để RIÊNG dưới `variants/openscad_1d/` — **KHÔNG chạm** baseline `openscad/`.
> Đơn vị mm. Quy ước theo dự án: `constants_1d.scad` (hằng số + assert), components versioned
> (`*_001.scad`, latest wins), một file assembly có flag.

---

## 0. Nguyên tắc "dễ chế tạo" (quyết định nền)

1. **Kênh dòng chảy = ỐNG TRONG MUA SẴN, KHÔNG in.** Nhựa in FDM không trong suốt quang.
   → mặc định **ống tròn trong OD 10 / ID 8mm** (acrylic/PC/thuỷ tinh, hoặc ống vinyl trong).
   ID 8mm cho hạt 5mm lọt thoải mái (biên 3mm). *Tuỳ chọn tốt hơn quang học:* ống **vuông trong
   10×10** (vách phẳng, đỡ méo chùm) — cùng họ "mua sẵn", đổi được qua tham số.
2. **Phần in = KHỐI GÁ QUANG (clamshell 2 nửa) tách ở MẶT PHẲNG QUANG z=0.** Mọi lỗ quang nằm
   ngang trong mặt tách → thành **rãnh nửa tròn** → **in phẳng, KHÔNG cần support**, thả linh kiện
   vào rồi kẹp 4 vít M3. Đây là điểm "dễ chế tạo" quan trọng nhất.
3. **Linh kiện phổ thông:** laser diode 650nm dạng barrel Ø6 (ưu tiên **line laser** để phủ tiết
   diện ống), photodiode **BPW34** hoặc PD đóng gói Ø5 (cắm như LED 5mm).
4. **Không keo phần quang** — ma sát + vít, tháo lắp/vệ sinh được.
5. **Dòng chảy THẲNG ĐỨNG, chảy xuống** — trọng lực cuốn hạt 1–5mm qua, chống đọng/nghẽn.
6. Đầu dò **tách rời** hẳn baseline camera; dùng chung bơm RS365 + ống mềm.

---

## 1. Hệ trục (assembly)

- Gốc **O = ĐIỂM CẢM BIẾN** = giao của chùm laser với trục ống.
- **Z** = thẳng đứng = trục dòng chảy; +Z lên, nước chảy −Z.
- **X** = trục chùm laser; laser ở **−X**, PD hấp thụ ở **+X** (đối trục).
- **Y** = trục tán xạ; PD tán xạ ở **+Y**, góc **90°** so chùm (ngoài đường sáng trực tiếp).
- Cả 3 phần tử quang nằm trong **mặt phẳng ngang z=0** → chính là **mặt tách clamshell**.

---

## 2. Danh sách chi tiết

| # | Part | In? | Vai trò |
|---|---|---|---|
| 1 | `sensor_block` (2 nửa: `_upper` + `_lower`) | ✅ In | Khối gá quang, kín sáng, rãnh giữ ống+laser+2 PD, 4 vít M3 |
| 2 | `clear_tube` (mock) | ❌ Mua | Kênh dòng chảy OD10/ID8, dọc trục Z, thò 2 đầu nối ống bơm |
| 3 | `laser_module` (mock) | ❌ Mua | Barrel Ø6 line-laser 650nm ở −X |
| 4 | `photodiode` ×2 (mock) | ❌ Mua | PD hấp thụ (+X) + PD tán xạ (+Y), gói Ø5 (BPW34) |
| 5 | `foot`/đế (tuỳ chọn) | ✅ In | Giữ khối đứng, hoặc bắt vào trạm bơm |

Chùm laser dạng **màn mỏng theo Y, mỏng theo Z** (line laser) để hạt ở bất kỳ vị trí Y nào rơi qua
cũng cắt chùm đúng 1 lần → 1 xung. (Nếu dùng chùm bút: đơn giản hơn cho tán xạ 90° nhưng hạt lệch
tâm dễ trượt — ghi rõ hạn chế; mặc định model chừa **khẩu độ khe** để hỗ trợ màn.)

---

## 3. Bảng hằng số (`constants_1d.scad`)

| Nhóm | Hằng số | Giá trị | Ghi chú |
|---|---|---|---|
| In/dung sai | `tol` | 0.2 | khe trượt FDM |
| | `wall` | 3.0 | thành tối thiểu quanh lỗ (kín sáng) |
| Ống kênh | `tube_od` | 10.0 | ống mua sẵn |
| | `tube_id` | 8.0 | hạt 5mm lọt (biên 3) |
| | `tube_clr` | 0.3 | khe lỗ ôm ống |
| | `tube_len` | 60.0 | thò 2 đầu nối ống bơm |
| | `part_max` | 5.0 | hạt lớn nhất (kiểm nghẽn) |
| Khối | `block_w` (X) | 50.0 | đủ chứa barrel laser + PD 2 bên |
| | `block_d` (Y) | 44.0 | đủ chứa PD tán xạ +Y |
| | `block_h` (Z) | 36.0 | 2 nửa mỗi 18 |
| | `split_z` | 0.0 | mặt tách = mặt phẳng quang |
| Laser | `laser_dia` | 6.0 | barrel |
| | `laser_len` | 20.0 | đoạn thân nằm trong rãnh |
| | `laser_ap` | 2.5 | khẩu độ ra sát ống (giới hạn sáng) |
| PD | `pd_dia` | 5.0 | gói Ø5 (BPW34/LED-package) |
| | `pd_len` | 8.0 | thân PD trong rãnh |
| | `pd_ap` | 3.0 | khẩu độ PD nhìn điểm O |
| | `scatter_ang` | 90 | góc PD tán xạ |
| Vít | `m3_clear` | 3.4 | lỗ thông nửa trên |
| | `m3_tap` | 2.8 | lỗ tự-ren nửa dưới |
| | `screw_inset` | 5.0 | vít cách mép |
| Màu | `col_*` | — | mượn palette baseline |

---

## 4. Hình học `sensor_block` (clamshell z=0)

- **Khối đặc** `block_w × block_d × block_h`, tâm O ở giữa, trừ đi:
  - **Bore ống** dọc Z: trụ Ø `tube_od+tube_clr` xuyên suốt tại (0,0).
  - **Rãnh laser** −X: trụ nằm ngang Ø `laser_dia` từ mặt −X vào, dừng cách O để chừa vách;
    nối tiếp **khẩu độ** Ø `laser_ap` xuyên tới bore ống.
  - **Rãnh PD hấp thụ** +X: đối xứng (Ø `pd_dia` + khẩu độ `pd_ap`).
  - **Rãnh PD tán xạ** +Y: Ø `pd_dia` từ mặt +Y, khẩu độ `pd_ap` nhắm O, trục 90°.
  - **4 lỗ M3** 4 góc (thẳng đứng): nửa trên `m3_clear`, nửa dưới `m3_tap`.
- **Tách 2 nửa** ở z=0: `difference` khối với nửa không gian z>0 (ra `_lower`) / z<0 (ra `_upper`).
  Các rãnh ngang nằm ở z=0 → mỗi nửa thấy **nửa rãnh** → in úp mặt tách xuống, không support.
- **Kín sáng:** chỉ hở 2 đầu bore ống. Ghi chú lắp: bọc/che 2 đầu ống ngoài khối, hoặc dùng ống bơm
  đục — nếu không, sáng môi trường lọt qua ống làm hỏng nền tối của PD tán xạ.
- Mặt trong rãnh + khoang: **đen nhám** (như thân quang baseline).

---

## 5. Assembly & flags

`assembly_1d_001.scad`: `explode`, `show_tube`, `show_optics` (laser+PD), `half` (upper/lower/both).
Đặt mock ống dọc Z, laser −X, PD +X và +Y; kiểm 3 trục giao đúng O + FOV chùm.

---

## 6. Assert lắp ghép (fail sớm)

- `tube_id - part_max >= 2` → hạt 5mm còn biên ≥2mm (chống nghẽn).
- `laser_ap < laser_dia` và `pd_ap < pd_dia` → khẩu độ nhỏ hơn linh kiện (có vai chặn).
- rãnh laser/PD + khẩu độ **không xuyên thủng** sang mặt đối diện ngoài ý muốn.
- lỗ vít M3 4 góc **không chạm** bore ống / rãnh quang (`screw_inset` đủ xa).
- `wall` quanh mọi lỗ ≥ 3 (kín sáng + cứng).
- mặt tách z=0 cắt **đúng tâm** mọi rãnh ngang (các rãnh phải đặt tâm ở z=0).

---

## 7. Phân đoạn công việc

- **P1 — constants_1d.scad:** bảng §3 + assert §6 + helper (m3 pattern 4 góc, palette). Render echo OK.
- **P2 — mocks:** `clear_tube`, `laser_module`, `photodiode` (khối đơn giản để canh trục).
- **P3 — sensor_block_001:** khối + các bore/rãnh + tách 2 nửa; render mặt tách kiểm không support.
- **P4 — assembly_1d_001:** ráp mock + 2 nửa, flag explode; render 3 hướng kiểm giao trục tại O.
- **P5 — export STL:** 2 nửa khối (kiểm manifold). Ống/laser/PD KHÔNG in.
- **P6 (sau):** đế giữ đứng / giá bắt trạm bơm; cân nhắc ống vuông cho quang tốt hơn.

---

## 8b. Review & sửa lỗi 2026-07-12 (sau khi đọc `variants/README.md`)

### Lỗi VẬT LÝ (đối chiếu README variants)
1. **Cấu hình tán xạ chưa tối ưu.** README ưu tiên **che-khuất (obscuration) + tán xạ góc hẹp tới
   (FSC)** cho SNR, và **tán xạ ngược (BSC)** để phân biệt vật liệu (chiết suất nước 1.33 vs nhựa
   ~1.59). Model _001 chốt cứng PD tán xạ **90° (SSC)** = thiên hình thái. → **Sửa:** `scatter_ang`
   THAM SỐ HOÁ (`sensor_block_002`), đặt được FSC (~25°), SSC (90°), hay BSC (~150°); mặc định 90°
   (dễ giữ nền tối). Trục che-khuất −X/+X giữ nguyên làm kênh chính.
2. **Không có hội tụ thủy động (sheath flow).** README mô tả ép hạt vào tâm, vận tốc không đổi.
   Ống thẳng của ta KHÔNG có → hạt qua ở vị trí & vận tốc thay đổi. Hệ quả: **độ rộng xung phụ
   thuộc cả vận tốc** (không chỉ size) → đo size bằng độ rộng sẽ sai. → **Giảm nhẹ:** ưu tiên
   **biên độ** (ít phụ thuộc vận tốc) để suy size; muốn chuẩn cần **2 chùm đo vận tốc (time-of-flight)**.
   (Sheath flow micron-scale không hợp macro 1–5mm — cố ý bỏ.)
3. **Chùm bút Ø2.5 vs ống Ø8 → thiên lệch theo size.** Hạt 5mm gần như luôn cắt chùm; hạt 1mm phải
   qua trong ±1.75mm quanh tâm → **hạt nhỏ bị đếm thiếu** → phân bố size lệch. Ghi để hiệu chuẩn.
   (Không dùng "màn Y" vì màn trải Y KHÔNG tương thích PD tán xạ trong-mặt-phẳng — xem §8.)

### Lỗi KHỚP KÍCH THƯỚC giữa module
4. **_001 thiếu định vị 2 nửa.** Khe vít M3 (Ø3.4) cho phép 2 nửa xê dịch ~0.4mm → **lệch nửa-rãnh
   quang**. → **Sửa:** **2 chốt Ø3 rời** cắm cả 2 nửa (`dowel_pos`), khử xê dịch.
5. **Ống chỉ giữ bằng ma sát** trong bore 36mm → dễ tuột khi cắm ống bơm. → **Sửa:** thêm **vít giữ
   ống** (tự-ren Ø2.5, mặt −Y, nửa trên).
6. **Đầu vít lồi mặt trên.** → **Sửa:** khoét chìm `cbore` cho đầu M3.
7. **⚠️ CHƯA sửa — cần xác minh phần cứng:** `pd_dia=5` (tròn) KHÔNG khớp **BPW34 thực tế ~5.4×4.3mm
   CHỮ NHẬT**. → hoặc dùng **photodiode đóng gói tròn Ø5** (khớp bore), hoặc đổi bore thành **hốc
   chữ nhật**. Tương tự phải đo **barrel laser thật** (Ø/dài) và **ống trong thật** (OD/ID) trước khi in.

## 8c. NGUỒN GỐC BẢNG HẰNG SỐ (§3) — không có kích thước nào từ bài báo

> Bài báo 1D + README variants là về **dữ liệu tổng hợp + compiler**, **KHÔNG dựng phần cứng** →
> **không cung cấp kích thước cơ khí/quang nào**. Toàn bộ số trong §3 là **giả định kỹ thuật** của
> tôi theo 4 nguồn dưới; các mục ⚠️ **phải đo lại linh kiện thật**.

| Hằng số | Nguồn gốc | Loại |
|---|---|---|
| `part_max=5` | **Đề bài người dùng** (hạt 1–5mm) | Yêu cầu |
| Cấu hình che-khuất/FSC/BSC, `scatter_ang`, 41 mẫu, chiết suất 1.33/1.59 | **README/bài báo** (vật lý) | Tham chiếu |
| `tol=0.2`, palette màu | **Baseline dự án** (`openscad/constants.scad`) | Chuẩn dự án |
| `wall=3` | Baseline dùng 2; tôi **nâng lên 3** cho kín sáng + cứng | Phán đoán |
| `m3_clear=3.4`, `m3_tap=2.8` | Chuẩn M3 in nhựa (baseline dùng 3.2/2.8) | Chuẩn FDM |
| `tube_od=10`, `tube_id=8` | **Ống trong phổ biến** + ràng buộc hạt 5mm lọt biên ≥2 | ⚠️ Đo ống thật |
| `laser_dia=6`, `laser_len=20` | **Module laser Ø6 phổ thông** (ước lượng) | ⚠️ Đo laser thật |
| `pd_dia=5`, `pd_len=8` | PD tròn Ø5 / xấp xỉ BPW34 | ⚠️ Sai gói BPW34 — đo PD thật |
| `laser_ap=2.5`, `pd_ap=3`, `ap_len=3` | **Phán đoán** (khẩu độ < linh kiện, giới hạn sáng) | Phán đoán |
| `laser_shoulder_x`, `pd_shoulder`, `tube_bore_r`, `ledge...` | **Phái sinh** bằng công thức từ số trên | Dẫn xuất |
| `block_w/d/h=50/44/36` | **Định cỡ để chứa** barrel+PD+wall (không nguồn ngoài) | Phán đoán |
| `tube_clr=0.3`, dowel/cbore/setscrew | **Phán đoán cơ khí** (khe lắp, định vị) | Phán đoán |

## 8. Hạn chế đã biết (ghi để bảo vệ)

- Ống tròn gây **hiệu ứng thấu kính trụ** (méo chùm) — chấp nhận cho demo; ống vuông khắc phục.
- Chùm bút: hạt lệch tâm có thể trượt → dùng **line laser** phủ tiết diện, hoặc thu hẹp vùng đo.
- Kín sáng phụ thuộc **che 2 đầu ống**; nền tối PD tán xạ nhạy sáng môi trường.
- ID 8mm cho 1–5mm: hạt nhỏ 1mm tín hiệu yếu hơn (SNR) — bù bằng Rf lớn ở TIA (xem 01 §3b).
