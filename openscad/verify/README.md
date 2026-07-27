# Kiểm & mô phỏng khay Macro-Flow trước khi in

3 công cụ ở đây trả lời 3 câu hỏi khác nhau. `export-stl.sh` (đã có sẵn) chỉ trả
lời câu 0 — không phải là "mô phỏng hoạt động", chỉ là "in được không":

| # | Câu hỏi | Công cụ | Bắt được lỗi loại gì |
|---|---|---|---|
| 0 | STL có in được không (mesh kín, không tự cắt nhau)? | `export-stl.sh` (đã có sẵn) | Lỗ mesh, tam giác suy biến |
| 1 | Hạt 2mm có ĐI QUA được từ cửa vào tới cổng ra không? | `flow_path_probe_001.scad` | Tắc nghẽn hình học (đã từng: miệng loe bị bịt kín) |
| 2 | Có mảnh nào rời khỏi khối chính / thành nào mỏng bất thường không? | `verify_flow_tray.py` | Mảnh trôi nổi (đã từng: vách baffle rời khối), thành mỏng dưới ngưỡng in |
| 3 | Sóng có thực sự dập trong 2s không? Cổng ra có thực sự chống xoáy không? | SimScale (CFD) — xem PHẦN B dưới | Động lực học dòng chảy thật — KHÔNG kiểm được bằng OpenSCAD |

Cả 3 công cụ 0-2 đều là kiểm **hình học tĩnh** — chúng chỉ xác nhận "đường có
thông, thành có đủ dày, không có mảnh rời". Không cái nào mô phỏng NƯỚC THẬT
chảy — muốn biết sóng có dập trong 2 giây hay cổng ra có xoáy hút khí hay
không, bắt buộc phải sang CFD (PHẦN B) hoặc in thử + đổ nước thật.

## PHẦN A — 3 công cụ kiểm hình học (chạy được ngay, không cần tài khoản/cài gì)

### A1. Dò đường nước bằng probe — `flow_path_probe_001.scad`

Dựng 1 chuỗi capsule đường kính = `particle_max` (2mm, đúng bằng hạt lớn nhất
cần đo) đi theo tuyến hẹp nhất đã chốt trong thiết kế (cửa vào → hành lang
3.0mm ngoài vách cong → vùng mở giữa khay → miệng loe → lòng cổng ra). Đổi
`MODE` trong file:

```bash
# MODE = "overlay" → xem trực quan (probe đỏ trong suốt đè lên khay bán trong suốt)
bash .claude/skills/preview-scad/scripts/render-scad.sh openscad/verify/flow_path_probe_001.scad --size 1400x1000 --camera 0,0,3,55,0,25,150 --output openscad/verify/flow_path_probe_001_overlay.png

# MODE = "check" → kiểm số: intersection(flow_tray(), probe) phải RỖNG
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/verify/flow_path_probe_001.scad --output openscad/verify/flow_path_check.stl
# Log kết thúc bằng "Current top level object is empty." = THÔNG (đạt).
# Nếu export ra file STL thật có hình học = TẮC — mở STL đó xem đúng vị trí bị chặn.
```

**Kết quả hiện tại (2026-07-25, `flow_tray_003.scad`): THÔNG — đã xác nhận.**

Khi đổi `baffle_r_mid`/`baffle_angle`/`inlet_gap_w`/bellmouth trong
`constants.scad`, chạy lại đúng 2 lệnh trên để xác nhận đường vẫn thông trước
khi export STL bản in chính thức.

### A2. Kiểm mảnh rời + độ dày thành — `verify_flow_tray.py`

```bash
python -m pip install trimesh rtree numpy   # 1 lần duy nhất
PYTHONIOENCODING=utf-8 python -X utf8 openscad/verify/verify_flow_tray.py openscad/print/print_flow_tray.stl
```

Kiểm 2 việc mà `export-stl.sh` KHÔNG bắt được (cả 2 đều xuất STL "manifold sạch"
dù sai hoàn toàn về công năng — xem PHẦN D trong
`docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md`):
1. **Số khối liên thông** (`body_count`) — phải = 1. >1 nghĩa là có mảnh KHÔNG
   gắn liền vào thân chính (đúng loại lỗi vách baffle từng trôi nổi).
2. **Quét độ dày thành** bằng ray casting pháp tuyến (heuristic, có lọc hit giả
   trên mặt cong nhiều facet — xem comment trong script). Có 2 vùng NGẦM ĐỊNH
   mỏng theo thiết kế nên đừng hoảng khi thấy chúng trong output: gờ kê đĩa
   acrylic (`ledge_plate_t=1.0mm`, ghi rõ "cho phép" trong `constants.scad`) và
   mép cắt phẳng đáy hở tại miệng loe (z=0, chủ ý theo comment đầu
   `flow_tray_003.scad`).

**Kết quả hiện tại: `body_count=1`, `watertight=True`, không điểm nào dưới
0.5mm ngoài 2 vùng ngầm định ở trên.**

### A3. Mặt cắt ngang để soi tay 1 vùng cụ thể — `cross_section_check_001.scad`

Khi A2 báo nghi ngờ ở 1 toạ độ cụ thể, đổi `CUT_Z` trong file này rồi render
top-down để nhìn trực tiếp mặt cắt tại độ cao đó — đúng kỹ thuật
`projection(cut=true)` mà PHẦN D dùng để tìm ra lỗi miệng loe bị bịt trước đây.

---

## PHẦN B — Mô phỏng dòng chảy thật bằng CFD (SimScale)

**Việc này KHÔNG làm được bằng OpenSCAD.** 3 công cụ ở PHẦN A chỉ xác nhận
hình học tĩnh — không cái nào biết nước có thực sự dập sóng trong 2 giây hay
cổng ra có bị "ực nước" (xoáy hút khí) hay không. Đó là 2 câu hỏi CFD mới trả
lời được (docs/research §2 và §4).

Chọn **SimScale** (không phải OpenFOAM cài local) vì máy đang dùng Windows —
OpenFOAM cần WSL2/Linux, SimScale chạy thẳng trên trình duyệt, có gói
Community miễn phí (dự án public), không cần cài gì.

### B0. 2 file STL đã chuẩn bị sẵn

- **`fluid_domain_001.stl`** — hình dạng khối NƯỚC TĨNH lúc settle (chỉ để đối
  chiếu bằng mắt, KHÔNG nạp thẳng vào SimScale).
- **`fluid_domain_full_001.stl`** — khối KHÔNG GIAN TÍNH TOÁN đầy đủ (nước +
  khoảng khí phía trên, cao tới mép khay `tray_depth=12mm`) + ống thẳng nối dài
  20mm ở cả 2 đầu vào/ra (để đặt biên inlet/outlet ổn định, không sát ngay khúc
  cua). **Đây là file nạp vào SimScale.**

Cả 2 đều dựng bằng cách: lấy 1 vùng bao rộng rãi rồi TRỪ đi chính khối nhựa
`flow_tray()` — đảm bảo khớp tuyệt đối với hình học in thật, không vẽ tay lại.
Khi đổi `constants.scad`, chạy lại:
```bash
bash .claude/skills/export-stl/scripts/export-stl.sh openscad/verify/fluid_domain_full_001.scad --output openscad/verify/fluid_domain_full_001.stl
```
(Cảnh báo non-manifold nhẹ — 2 cạnh lỗi trên >22000 cạnh, đúng vị trí mép cắt
phẳng z=0 tại miệng loe đã biết ở PHẦN A2 — không đáng lo, công cụ sửa mesh của
SimScale xử lý được lúc nạp.)

### B1. Tạo tài khoản + tạo project

1. simscale.com → đăng ký tài khoản (gói Community — dự án sẽ ở chế độ public,
   ai cũng xem được, chấp nhận được cho đồ án học tập).
2. New Project → Import geometry → upload `fluid_domain_full_001.stl`.

### B2. Loại mô phỏng

Chọn **Multiphase (Volume of Fluid / free surface)** — đây là bài toán 2 pha
khí-nước có mặt thoáng tự do (dòng hở, không phải ống kín), đúng loại bài toán
VOF chuẩn. (Tên nút chính xác có thể đổi theo phiên bản UI — tìm từ khoá
"Multiphase" hoặc "Free surface" trong danh sách simulation type.)

### B3. Mesh

Dùng mesh tự động trước, rồi thêm 1 vùng tinh chỉnh (refinement region) quanh
cụm chống sóng — kích thước ô lưới nhỏ nhất cần thấy được khe hẹp nhất thiết kế
là `baffle_corridor=3.0mm`, nên đặt ô lưới ~0.4-0.6mm ở đó (quy tắc chung: ≥5 ô
cắt ngang khe hẹp nhất mới tin được kết quả):

- Vùng tinh chỉnh: hộp bao quanh gốc toạ độ, x∈[-25,25], y∈[-25,25], z∈[0,8]
  (trùm vách cong + miệng loe).

### B4. Biên (boundary conditions)

Xác định các mặt bằng toạ độ (khớp `flow_tray_003.scad`, gốc tại tâm sàn khay):

| Mặt | Toạ độ nhận dạng | Loại biên |
|---|---|---|
| Đầu ống vào (mặt tròn Ø6, xa nhất phía −X) | x ≈ −57 | **Velocity inlet** |
| Đầu ống ra (mặt tròn Ø6, xa nhất phía +X) | x ≈ +50 | **Pressure outlet** (hoặc velocity outlet cùng lưu lượng — bơm hút ở đây, nhưng pressure outlet đơn giản hơn cho lần chạy đầu) |
| Mặt trên cùng (z = 12, miệng khay hở) | z = 12 | **Opening** (áp suất khí quyển, 2 chiều — khí có thể ra/vào tự do) |
| Còn lại (thành khay, vách cong, miệng loe...) | — | **Wall, no-slip** |

**Vận tốc inlet** — suy từ lưu lượng bơm RS365 CHƯA ĐO thật (datasheet chung
1.5–2.2 L/min, xem `docs/research/...`), tiết diện lòng ống Ø6mm = 28.3mm²:

```
v = Q / A
1.5 L/min → v ≈ 0.88 m/s
2.2 L/min → v ≈ 1.30 m/s
```

Chạy thử với **v = 1.0 m/s không đổi** trước (đơn giản, xác nhận setup chạy
được đã). Muốn xét đúng nghi vấn cộng hưởng ở §2 tài liệu nghiên cứu, đổi sang
vận tốc DAO ĐỘNG theo thời gian (SimScale cho nhập biểu thức theo `t`):

```
v(t) = v_mean * (1 + 0.4 * sin(2*pi*f_pump*t))
```
với `f_pump` thử lần lượt 5Hz, 7Hz, 10Hz (đúng dải chưa đo thật trong tài liệu
— CFD cho phép quét thử nhiều giá trị mà KHÔNG cần đợi đo bơm thật trước, dù
vẫn cần đo thật sau này để xác nhận số nào đúng).

### B5. Điều kiện ban đầu (initial conditions)

VOF cần biết pha ban đầu ở đâu là nước, đâu là khí — làm NGAY TRONG SimScale
(không cần dựng lại geometry): chọn "Initial conditions" → gán phase fraction
= 1 (nước) cho vùng `z < 6`, = 0 (khí) cho `z ≥ 6`. Trùng khớp `water_depth=6`
trong `constants.scad`.

### B6. Cài đặt chạy (transient)

- **Bước thời gian (time step):** đủ nhỏ để thấy được dao động bơm — nếu thử
  `f_pump=10Hz`, cần ≥20 bước/chu kỳ ⇒ `dt ≤ 0.005s`. An toàn hơn: bật
  adaptive time step nếu SimScale hỗ trợ.
- **Thời gian mô phỏng:** tối thiểu hết 1 chu kỳ Stop-Flow theo firmware thật
  (`firmware/pump_pwm_test/pump_pwm_test.ino`): `fillMs=5000` + `rampDownMs=350`
  + `settleMs=2000` ⇒ chạy **≥ 7.5 giây mô phỏng**.

### B7. Đọc kết quả — trả lời đúng 2 câu hỏi đang treo

1. **Sóng có dập trong 2s SETTLING không?** Đặt 1 "probe point" tại tâm khay
   (x=0,y=0) theo dõi độ cao mặt thoáng (phase fraction=0.5) theo thời gian.
   Sau mốc `fillMs+rampDownMs≈5.35s` (bơm đã tắt hẳn), xem biên độ dao động mặt
   nước có tắt dần về gần 0 trước mốc `+2s` (t≈7.35s) hay không. Nếu KHÔNG dập
   kịp → đúng nghi vấn của tài liệu nghiên cứu §2, cần tăng `baffle_h`/đổi
   `baffle_angle`/xét lại T-Dome (§6, hiện đang hoãn).
2. **Cổng ra có "ực nước" không?** Xem trường vận tốc/streamline quanh miệng
   loe lúc `v_mean` cao (pha FILLING) — tìm dấu hiệu xoáy phễu hút khí xuống
   theo lòng ống (vortex core kéo dài từ mặt thoáng xuống miệng loe). Nếu thấy
   → cần hạ `v_mean` (tức hạ % PWM cruise-duty trong firmware) tới khi hết —
   **đây chính là cách CHỐT SỐ % cruise-duty (mục #7 còn tồn đọng trong PHẦN E
   research doc) bằng mô phỏng TRƯỚC khi cần đo tay trên bơm thật**, dù vẫn nên
   đối chiếu lại với bơm thật sau khi có.

### B8. Vòng lặp "sửa trước khi in"

1. Đổi 1 tham số nghi ngờ trong `constants.scad` (vd `baffle_h`, `baffle_angle`,
   `dc_jack_hole_d`...).
2. Chạy lại A1 (probe) — xác nhận đường vẫn thông cho hạt 2mm.
3. Chạy lại A2 (trimesh) — xác nhận vẫn 1 khối, không thành nào mới mỏng bất
   thường.
4. Export lại `fluid_domain_full_001.stl`, nạp lại SimScale, chạy lại B4-B7 —
   xác nhận sóng vẫn dập kịp / cổng ra vẫn không ực nước.
5. Chỉ khi cả 4 bước trên đều pass mới export bản in `print_flow_tray.stl`
   chính thức.

## Giới hạn cần biết

- A1/A2 là kiểm hình học CẦN, không phải ĐỦ — xác nhận đường thông/không mảnh
  rời, không mô phỏng vật lý dòng chảy.
- CFD (PHẦN B) là mô hình SỐ, không phải đo thật — độ chính xác phụ thuộc trực
  tiếp vào 2 số CHƯA ĐO thật trong tài liệu nghiên cứu (tần số nhịp màng bơm,
  lưu lượng thật). Dùng CFD để LOẠI TRỪ SỚM các thiết kế rõ ràng sai (sóng
  không dập nổi trong biên độ lớn, xoáy rõ rệt ở mọi vận tốc thử) và THU HẸP
  khoảng cần thử khi có bơm thật — không thay thế hoàn toàn việc đo/in thử
  cuối cùng.
