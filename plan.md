# Plan Triển Khai Mô Hình 3D OpenSCAD — Aqua Scope

> **Mục đích file này:** kế hoạch build **thực thi được** cho bộ mô hình OpenSCAD của Aqua Scope
> (baseline "Backlit Silhouette"). Đây là tài liệu để **dựa vào mà tiến hành** — mọi quyết định
> hình học then chốt đã chốt ở §2; thứ tự làm, phương thức, và cổng kiểm chứng ở §4–§7.
>
> Nguồn ràng buộc gốc: [`CLAUDE.md`](CLAUDE.md), [`README.md`](README.md),
> [`implementation_plan.md`](implementation_plan.md) (bảng hằng số), [`technical_specs.md`](technical_specs.md)
> (kích thước STL — nguồn chuẩn cho base/pump), [`thiet_ke_hop_den_nen.md`](thiet_ke_hop_den_nen.md).
>
> Ngày lập: 2026-07-07.

---

## 1. Mục tiêu

Dựng mô hình 3D **tham số** (OpenSCAD) của Aqua Scope theo baseline hiện tại:
khối trụ chụp ảnh NGẮN, camera úp xuống (cự ly nét ~40mm), khay Macro-Flow đáy acrylic tròn,
hộp đèn nền "LED xuôi", bơm màng RS365 tách rời. Đầu ra: các file `.scad` in được + assembly
render được (lắp kín + exploded) + STL các chi tiết in.

**3 KHÔNG** (bất di bất dịch): (1) không sửa lens; (2) không chip vi lưu kín; (3) không can thiệp thủ công.

---

## 2. Quyết định đã CHỐT (không mở lại khi build)

| Mã | Chủ đề | Quyết định | Hệ quả cho model |
|---|---|---|---|
| **G1** | Nguyên lý đèn nền | **LED xuôi**: đầu LED hướng THẲNG LÊN + buồng trộn ~8mm + màng khuếch tán xếp lớp | `light_box.scad` theo hướng này (KHÔNG bounce/baffle). ⚠️ README/implementation_plan còn mô tả "bounce" → **phải sửa** ở Task #14 |
| **G2** | Hình dạng vỏ trụ | **1 ống LIỀN suốt** (imaging + light box chung 1 ống thẳng, thân kéo xuống làm chân đế) | `tube_body` + `light_box` compose vào **cùng 1 khối in** (~70–90mm cao), ghép logic ở mặt gờ kê khay |
| **G3** | Ghép nắp↔thân | **4 vít M3** qua lỗ SẴN của base, bước vuông **30×30mm**, tâm = trục quang (−6.2, 81.5) | Bích đỉnh ống: 4 lỗ Ø3.2 clearance, vít bắt ngược lên lỗ Ø2.8 tự-ren của base |
| **G4** | Ống bơm RS365 | **"8mm" = OD cổng vào/ra máy bơm** (không phải ID ống) | Ống silicone **ID≈8 / OD≈11**; ngạnh cổng RA khay OD≈8, lòng chảy ~6mm (≥3× hạt 2mm) |
| **G5** | Vách đỡ LED | **MIẾNG RỜI** hẳn; thành ống chỉ 2 lỗ ren M3 ngang | Lắp module vào vách rời TRƯỚC rồi bắt ngang; tháo 2 ốc là lấy cả vách+module |
| **Hình dạng trụ** | (chốt trước, 2026-07-06) | Ống **THẲNG**, OD=footprint base (~50mm), **KHÔNG phình cốc**; nắp = base ĐÃ IN tái dùng | `tube_od=50`, `tube_id=46`; khay/cửa sổ/đèn co cho lọt ID46 |
| **Bơm** | (chốt trước) | **Bơm màng RS365 12V chủ động** (bỏ nhu động 28BYJ-48 + bỏ trọng lực); hạt <2mm ĐI QUA bơm | `pump_rs365.scad` = placeholder mua sẵn; điều khiển = **module relay** (MOSFET chỉ khi cần PWM) |
| **Khay** | (chốt trước) | Mục tiêu DUY NHẤT: mọi hạt RA HẾT không đọng; **BỎ lưới giữ hạt** | Khe khuếch tán vào + cổng ra sát đáy + fillet R≥2.5; không chi tiết níu hạt |
| **Xử lý ảnh** | (chốt trước) | Hybrid: classical CV đếm+đo + classifier nhỏ phân loại | (không thuộc mô hình 3D) |

### Tham số CHƯA chốt (build với default, tinh chỉnh sau khi kiểm phần cứng — KHÔNG chặn build)
- `water_depth` = **6mm** (default) — chờ kiểm DOF lens gốc ở 40mm; nếu DOF < 6mm → hạ 5mm. Tham số hóa.
- `tray_win_t` = **3mm** (default, cho cứng chống võng) — có thể 2mm. Tham số hóa.
- Chiều lắp module LED: assemble vào vách rời trước rồi bắt ngang (không còn là ràng buộc nhờ G5).
- Dung sai lỗ module: **+0.4mm** (default), chỉnh theo máy in.

---

## 3. Cấu trúc file

```
openscad/
├── constants.scad            # Hằng số + helper (mount pattern, palette, assert)  [NỀN TẢNG]
├── aqua_scope_assembly.scad  # Lắp ghép tổng, cờ explode / show_pump / show_electronics / show_window
└── components/
    ├── xiao_esp32s3.scad     # Board tham chiếu (OV3660, lens Ø8)
    ├── top_cap.scad          # import() base STL, căn trục quang (−6.2, 81.5)
    ├── tube_body.scad        # Ống thẳng OD50/ID46/H45 + bích M3 đỉnh + gờ kê khay  [LÕI]
    ├── flow_tray.scad        # Khay tròn: khe khuếch tán vào + cổng ra sát đáy + fillet (BỎ lưới)
    ├── acrylic_window.scad   # Đĩa acrylic trong Ø42×3 (tham chiếu/đệm)
    ├── window_retainer.scad  # Vòng ép M2.5 + khe silicon hồ cá
    ├── glass_window_top.scad # Cửa sổ ép phẳng mặt nước (TÙY CHỌN)
    ├── light_box.scad        # Hộp đèn nền LED-xuôi + vách đỡ RỜI (M3 ngang) + chân đế
    ├── led_module.scad       # Mock module LED móc khoá 37.5×10×16
    ├── prescreen.scad        # Lưới thô khe >5mm
    ├── silicone_tube.scad    # Ống dẫn ID8/OD11
    └── pump_rs365.scad       # Placeholder bơm mua sẵn (bbox ~90×40×35, ngạnh Ø8)
```

> **Lưu ý G2:** `tube_body.scad` và `light_box.scad` là 2 file logic nhưng **compose vào CÙNG 1 khối in**
> (ống liền suốt). Chia file để dễ đọc/tham số, không phải để in rời.
>
> **Hai vùng hoàn thiện:** thân trụ quang học (trên đáy khay) = **ĐEN NHÁM**; khoang light box
> (dưới đáy khay) = **TRẮNG mờ**. Chỉ đáy khay (acrylic) là trong.

---

## 4. Thứ tự build theo pha (khớp task list)

| Pha | Task | File / việc | Chặn bởi |
|---|---|---|---|
| **0 · Chốt** | #1 ✅ | Giải 4 cổng quyết định (G1,G2,G4,G5) | — (ĐÃ XONG) |
| **1 · Nền tảng** | #2 | `constants.scad` (+ helper) | — |
| | #3 | `xiao_esp32s3.scad` | #2 |
| | #4 | `top_cap.scad` (import + căn datum) | #2 |
| **2 · Lõi quang** | #5 | `tube_body.scad` | #2 |
| **3 · Khay + cửa sổ** | #6 | `flow_tray.scad` | #1,#2,#5 |
| | #7 | `window_retainer.scad` + `acrylic_window.scad` | #2,#6 |
| | #8 | `glass_window_top.scad` (tùy chọn) | #2 |
| **4 · Đèn nền** | #9 | `light_box.scad` | #1,#2,#5 |
| | #10 | `led_module.scad` | #2 |
| **5 · Phụ kiện** | #11 | `prescreen` + `silicone_tube` + `pump_rs365` | #2 |
| **6 · Lắp + kiểm** | #12 | `aqua_scope_assembly.scad` + render | #3–#11 |
| | #13 | Kiểm DFM + export STL | #12 |
| | #14 | Đồng bộ tài liệu (sửa README đèn nền, v.v.) | #13 |

**Đường tới hạn:** #2 → #5 → (#6, #9) → #12 → #13 → #14.

---

## 5. Đặc tả từng file (checklist khi dựng)

### #2 `constants.scad` — nền tảng (KHÔNG geometry)
- Toàn bộ hằng số baseline (bảng trong `implementation_plan.md §"Bảng Hằng Số Baseline"`):
  `tol=0.2`, `wall_t=2`, `work_dist=40`, `fov_w_est≈46`; `tube_od=50`, `tube_wall=2`, `tube_id=46`, `tube_h=45`;
  `tray_inner=40`, `tray_wall=2`, `tray_outer=44`, `tray_depth=12`, `water_depth=6`;
  `inlet_slot=[20,3]`, `outlet_low_d=8` (ngạnh OD, bore~6), `fillet_r=2.5`, `port_layout=180°`;
  `tray_win_d=42`, `tray_win_t=3`, `ledge_overlap=1.5`, `ledge_depth=3.3`, `win_clr=0.35`, `retainer_screw_d=2.5`;
  `bl_box_h=18`, `bl_diff_d=42`, `bl_mix_h=8` (buồng trộn LED-xuôi), `bl_wall_finish=TRẮNG`;
  `mount_pitch=30`, `mount_center=[-6.2,81.5]`, `mount_hole_base_d=2.8`, `mount_hole_lid_d=3.2`, `cam_aperture=7.5`;
  `pump_barb_od=8`, `sil_tube_id=8`, `sil_tube_od=11`, `pump_bbox=[90,40,35]`;
  `screen_open>5`, `xiao=[21,17.8,2.5]`, `xiao_cam_d=8`.
- **Helper dùng chung:** `m3_mount_pattern()` = 4 lỗ vuông 30×30 **tâm tại (−6.2,81.5)** (trục quang, KHÔNG theo tâm outline −5.4);
  palette màu (`col_plastic` xám, `col_acrylic` xanh trong, `col_pcb` xanh lá, `col_metal` bạc);
  các `assert()` lắp ghép (vd `assert(tray_outer + 2*win_clr < tube_id)`).

### #3 `xiao_esp32s3.scad`
- PCB 21.0×17.8×2.5 + khối lens camera Ø8 (**OV3660**, không phải OV2640) nhô mặt dưới. Chỉ để hiển thị/bố trí.

### #4 `top_cap.scad`
- `import()` `base/Assembly_...base_xiao_9.stl`; xoay/dịch để camera úp xuống, trục quang (−6.2,81.5) về gốc hệ.
- **Verify:** 4 lỗ M3 Ø2.8 tại (−21.2,66.5)(−21.2,96.5)(8.8,66.5)(8.8,96.5) khớp `m3_mount_pattern()`; lỗ camera Ø7.5 ở tâm.
- **BỎ QUA** 3 lỗ Ø8 di sản tại (7.1,95.0)(−19.6,68.0)(−15.7,92.5) — không tái tạo.

### #5 `tube_body.scad`  [lõi]
- Ống THẲNG OD50/ID46/H45, nội thất đen nhám. Đỉnh = bích: 4 lỗ M3 Ø3.2 clearance theo `m3_mount_pattern()`.
- Đáy vùng imaging = gờ kê khay (ledge) cho `flow_tray` rơi vào.
- **Verify:** nón FOV ~46mm tại `work_dist=40` KHÔNG chạm thành ID46 (không vignette); bích thẳng hàng lỗ base.
- Ống này **nối liền** `light_box` bên dưới (G2) — chừa mặt ghép ở gờ kê + 2 lỗ ren M3 ngang cho vách đỡ.

### #6 `flow_tray.scad`  (thiết kế MỚI — bỏ lưới)
- Khay tròn drop-in: `tray_inner=40`, `tray_outer=44`, `tray_depth=12`, `water_depth=6`.
- 2 cổng THÀNH BÊN **đối tâm 180°**: (VÀO) khe khuếch tán ~20×3 SÁT ĐÁY; (RA) cổng rút Ø~8 SÁT ĐÁY (KHÔNG ở đỉnh).
- Fillet R≥2.5 mọi góc đáy–thành; rebate đĩa acrylic Ø42×3 **flush sàn**.
- **TUYỆT ĐỐI KHÔNG** lưới/gờ giữ hạt (khác khay cũ `khay_dong_chay_001` — đã bỏ).
- `weir_h` & van xả đáy = TÙY CHỌN. **Verify:** `tray_outer+2·win_clr < tube_id`; cổng không đụng đĩa acrylic; không góc chết.

### #7 `window_retainer.scad` + `acrylic_window.scad`
- `acrylic_window`: đĩa TRONG Ø42 × 3mm (tham số 2/3), màu xanh trong, chi tiết tham chiếu.
- `window_retainer`: vòng ép in 3D đè viền đĩa, 3–4 vít M2.5, khe silicon; `win_clr=0.35`. Không che vùng ảnh Ø40.

### #8 `glass_window_top.scad`  (tùy chọn)
- Tấm phẳng Ø~42 gác trên gờ TRÊN của khay ép phẳng mặt nước — GÁC GỜ, không thả nổi. Cờ `show_window`.

### #9 `light_box.scad`  (LED xuôi — G1)
- Khoang dưới đáy khay, mặt trong TRẮNG mờ. **LED xuôi:** buồng trộn ~8mm (`bl_mix_h`) + khe xếp lớp màng khuếch tán + đầu LED thẳng lên.
- **Vách đỡ MIẾNG RỜI (G5):** thành ống 2 lỗ ren M3 ngang; vách có lỗ giữa xỏ module (tiết diện 37.5×10 + tol +0.4).
- Thân kéo xuống bọc nửa pin + đáy làm CHÂN ĐẾ. `bl_box_h=18`, `bl_diff_d=42`.
- **Verify:** module fit lỗ vách; khe màng khuếch tán chỉnh được (thêm/bớt lớp); compose liền `tube_body` (G2).

### #10 `led_module.scad`
- Mock khối 37.5×10×16, đầu LED ở mũi + 3 pin cúc. Cắm-tháo ma sát.

### #11 Phụ kiện
- `prescreen`: lưới khe >5mm cổng vào (chặn rác to, không lọc mất hạt 1–5mm).
- `silicone_tube`: ống ID8/OD11 (G4) đi dây trong assembly.
- `pump_rs365`: PLACEHOLDER bbox ~90×40×35 + ngạnh Ø8, chỉ bố trí trạm bơm tách rời (KHÔNG in).

### #12 `aqua_scope_assembly.scad`
- Xếp chồng đúng cao độ: base cap → tube_body → flow_tray (trên gờ) → acrylic window + retainer → light_box → chân đế; bơm tách rời nối ống.
- Cờ: `explode`, `show_pump`, `show_electronics`, `show_window`. Màu theo palette. Render **lắp kín + exploded**.

### #13 Kiểm DFM + export STL
- Chi tiết IN ĐƯỢC (khối vỏ liền = tube_body+light_box, flow_tray, window_retainer, glass frame nếu có): `/export-stl` kiểm manifold/self-intersection/mặt suy biến.
- Xác nhận dung sai (tol=0.2, win_clr=0.35, lỗ module +0.4) hợp lý; thành ≥ wall_t. So bbox base/pump với `technical_specs.md`.
- Ghi rõ chi tiết KHÔNG in: base (in sẵn), acrylic (cắt), LED/pump/ống (mua sẵn).

### #14 Đồng bộ tài liệu
- Sửa README/implementation_plan/thiet_ke_hop_den_nen cho khớp G1–G5 — **đặc biệt giải mâu thuẫn đèn nền: chỉ giữ "LED xuôi"**.
- Cập nhật §"Cấu Trúc Thư Mục" README (openscad/ nay đã tồn tại). Sửa CLAUDE.md nếu cần (OV2640→OV3660, classical-CV-only→hybrid — đã có memory đính chính).

---

## 6. Phương thức tiến hành (workflow mỗi file)

Lặp cho TỪNG component:
1. **Version** — `.claude/skills/openscad/scripts/version-scad.sh <name>` → lấy `<name>_001.scad` (skill `/openscad`).
2. **Viết** — `include <constants.scad>`, kéo mọi số từ đó (KHÔNG hard-code lại); geometry tham số hóa.
3. **Render + soi mắt** — `.claude/skills/preview-scad/scripts/render-scad.sh <file>` → **đọc PNG** so với spec ở §5.
4. **Lặp** `_002`, `_003`… sửa lỗi, so bản trước.
5. **Assert** — nhúng `assert()` số để lỗi kích thước fail ngay khi render.
6. **Export** — chi tiết in được → `/export-stl` (`export-stl.sh`) kiểm manifold.

> OpenSCAD tại `C:\Program Files\OpenSCAD\openscad.exe` (không trên PATH — script đã vá fallback đường dẫn này).

---

## 7. Cổng kiểm chứng (verification gates)

- **Datum quang học:** `top_cap` import base → 4 lỗ M3 (30×30) + lỗ camera Ø7.5 trùng `m3_mount_pattern()` căn tại **(−6.2, 81.5)** (không phải tâm outline −5.4). Bỏ 3 lỗ Ø8 di sản.
- **Không vignette:** nón FOV ~46mm tại `work_dist=40` không chạm thành ID46.
- **Lắp lọt:** `tray_outer(44) + 2·win_clr < tube_id(46)`.
- **Chống đọng khay:** cổng thành bên không đụng đĩa acrylic; fillet R≥2.5 mọi góc đáy–thành; KHÔNG chi tiết giữ hạt.
- **In được:** manifold, thành ≥ `wall_t`, dung sai lỗ hợp lý.
- **Đối chiếu số:** bbox base/pump khớp `technical_specs.md`.
- **Trình bày:** render exploded view + assembled view.

---

## 8. Trạng thái — ✅ BUILD HOÀN TẤT 2026-07-07

Toàn bộ 14 task đã xong. Kết quả: `openscad/` (constants + 9 component + assembly + 6 STL in được,
tất cả manifold ✓). Các quyết định hình học PHÁT SINH khi build (bổ sung vào §2, đã đồng bộ docs):

| Phát sinh | Quyết định | Lý do |
|---|---|---|
| **Lắp từ ĐÁY** | Khay/đĩa/vòng ép/màng/vách LED luồn từ dưới lên; ngạnh thò qua **2 khe dọc** ±X (VÀO 24, RA 12, cao tới z=+7) + **nút bịt khe** | G2 vỏ 1 ống liền → bích đỉnh chặn miệng trên, không thể thả khay từ trên |
| Đĩa acrylic **Ø42** (không phải 43) | `ledge_overlap` thực tế = 1.0mm/cạnh (dẫn xuất) | OD khay 44 chỉ chừa được hốc Ø42.7 + thịt 0.65 — assert bắt được mâu thuẫn bảng gốc |
| Vòng ép **SNAP-FIT 3 tai** | Bỏ vít M2.5 | Mọi vòng tâm vít đều đè lên hốc đĩa với OD44 — bất khả thi hình học (README cho phép ngàm) |
| Gờ kê đĩa **1mm + silicon vê tròn** | `ledge_plate_t=1.0` | "Phẳng sàn tuyệt đối" không thể vừa giữ đĩa; docs sẵn cho phép silicon vê mối nối |
| Bích đỉnh đĩa đặc **lỗ Ø24** | 4 lỗ M3 nằm trên vành bích | Nón FOV hội tụ về ống kính → gần đỉnh chỉ cần lỗ nhỏ, không vignette |
| Ốc vách LED tại **±Y** | — | Tránh 2 khe dọc ±X |
| Chiều cao vỏ **~108mm** (z −61.5..46) | Module LED 37.5 đứng + buồng trộn 8 + màng 4 + khay 18.5 + quang 46 | In được trên máy FDM phổ thông |
| **Biến thể ESP32-CAM** (2026-07-08, tùy chọn) | `top_cap_esp32cam` in mới: hốc chìm board (camera úp, pin lên), CÙNG bích 4×M3 30×30 → thay được base XIAO; **lid Matchboxscope in sẵn** kẹp trên (4 lỗ Ø3.2 đúng pattern); `cam_variant=1` trong assembly | Dự phòng đổi board; baseline XIAO không đổi; lens ESP32-CAM tự vặn nét bù cự ly ~36mm; `e32_lens_off=7` phải ĐO LẠI board thật |
| **Đáy khay MỞ** (2026-07-08, sửa lỗi in — `flow_tray_002`) | Lòng Ø40 khoét XUYÊN SUỐT xuống hốc đĩa; gờ kê 1mm = VÀNH KHUYÊN ID40/OD42.7 | `_001` chỉ khoét từ z=−EPS → sót ĐĨA ĐẶC ~1mm (z −1..0) bít toàn bộ đáy khay khi in — không soi được (phát hiện khi in thật) |
| **BỎ vòng đỡ khay liền vỏ** (2026-07-08, sửa lỗi in — `tube_body_002` + `light_box_002`) | Xóa vòng ID40.5 z=−8..−6.5; khay nay đỡ bằng **2 nút bịt khe KIÊM CỘT ĐỠ chữ L**: thân trượt trong khe dọc ±X (vẫn bịt sáng), gờ ngang thò vào r21.4 đỡ đáy váy khay tại z=−6.5, chân đứng cùng mặt bàn với vành đế; nóc khe dọc nâng 7→7.5 (ngạnh không chạm nóc trước khi khay tì gờ). Thứ tự lắp BẮT BUỘC: khay → 2 nút bịt → vách LED (+module+màng) → 2 ốc ±Y | Khay OD44 luồn từ ĐÁY không thể chui qua vòng ID40.5 — mâu thuẫn lắp ráp `_001` (phát hiện khi in thật). Vỏ đã in theo `_001` tận dụng được: gọt bỏ vòng đỡ + dũa nóc khe +0.5 |
| **Bỏ 3 lỗ Ø4 ngoài cùng trên nắp trụ** (2026-07-08, user yêu cầu — `top_cap_003`) | Trám thêm 3 lỗ Ø4 XUYÊN ở vành ngoài cùng (STL (16.6,74.4),(0,58.5),(−22.5,98.6), r≈23.6–23.9mm) bằng trụ đặc suốt z=0..12, Ø4.6. Kiểm trimesh: chỉ 3 lỗ này rỗng→đặc, 4 lỗ M3 + camera KHÔNG đổi | Lỗ vít di sản Matchboxscope, Aqua Scope không dùng; ngoài footprint board (r>23mm) nên trám đặc an toàn |
| **Khoan thông cả 4 lỗ M3 từ đáy** (2026-07-08, sửa lỗi lắp — `top_cap_004`) | 4 lỗ M3 gốc của base là lỗ tự-ren MỞ TỪ TRÊN, BỊT ĐÁY ~4–5mm → Aqua Scope bắt bích TỪ DƯỚI nên 2/4 lỗ (UL,LR) vít không vào được (LL,UR tình cờ thông vì trùng nút trám di sản). Sửa: `difference()` khoan Ø2.8 XUYÊN SUỐT cả 4 lỗ (z=−1..13). Kiểm trimesh: 4/4 lỗ mở đều 2 mặt | Bích ống bắt từ dưới cần 4 lỗ đều thông đáy; vít bích (dưới) + vít nắp đậy (trên) tự-ren chung lỗ Ø2.8 sâu 12mm |
| **Nắp trụ XIAO in được + nắp đậy trên** (2026-07-08, user yêu cầu) | `print_top_cap_xiao.stl` = base Matchboxscope (import + trám 3 lỗ Ø8 + 3 lỗ Ø4 ngoài) để IN khi không có base đúc sẵn. `top_lid_xiao_001` = **nắp đậy trên cùng MỚI**: tấm bo góc (footprint base + gờ), 4 lỗ M3 Ø3.2 khoét đầu vít (30×30), gờ định vị ôm ngoài miệng base (khe 0.6mm, chắn bụi/sáng), khe cáp USB-C cạnh +X. Vít M3 tự-ren vào NỬA TRÊN 4 lỗ base (nửa dưới cho vít bích; lỗ base sâu 12mm → 2 vít ngắn ≤6mm không chạm) | Đậy/giữ board XIAO ngồi trong nắp trụ; cùng giao diện 4×M3 30×30 như lid Matchboxscope gốc nên tương thích. `show_top_lid` trong assembly |

Bài học DFM đã trả (ghi để lần sau khỏi dẫm): mặt trùng phẳng 0mm và mặt tiếp tuyến với mặt trụ
cong ⇒ non-manifold — luôn cho các khối giao nhau CHỒNG LẤN DƯƠNG (≥0.5mm) hoặc xuyên hẳn qua.
