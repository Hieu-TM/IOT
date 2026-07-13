# Kế Hoạch Mô Hình 3D OpenSCAD — Aqua Scope (Baseline "Backlit Silhouette")

## Mục tiêu

Dựng mô hình 3D tham số (OpenSCAD) của **Aqua Scope** theo **baseline hiện tại**: khối trụ chụp ảnh NGẮN,
camera úp xuống, **hộp đèn nền (light box) chiếu GIÁN TIẾP (bounce) từ dưới đáy khay acrylic tròn trong suốt**,
xử lý ảnh **hybrid** on-device (classical CV **đếm + đo kích thước** + classifier nhỏ **phân loại từng hạt**) cho
hạt/rác vĩ mô (dải thiết kế 1–5mm; **phạm vi test hiện tại <2mm**) trong dòng chảy.

> Baseline này đã thay thế hoàn toàn bản ý tưởng đầu (UV huỳnh quang + FOMO + kính nổi + cột Z 120mm +
> cự ly 10–15cm). Xem bảng "Lịch sử thiết kế" trong `README.md`/`info.txt`.

### 3 KHÔNG
1. KHÔNG chỉnh sửa thấu kính (lens gốc nét sẵn ở 3–5cm — thực nghiệm).
2. KHÔNG dùng chip vi lưu kín (khay hở + mép tràn).
3. KHÔNG can thiệp thủ công (trừ vệ sinh định kỳ).

### Thông số quyết định (đo trên phần cứng thật)
- **Cự ly nét (camera↔mặt nước): 3–5cm → chọn danh nghĩa `work_dist = 40mm`.**
- Ở 40mm: FOV ngang ~46mm (khay lấp gần đầy khung); 1mm ≈ 35px (UXGA) / ~14px (VGA).
- ⇒ Ống trụ NGẮN ~40–50mm (cứng, dễ in).

> **🔒 QUYẾT ĐỊNH CHỐT (2026-07-06) — hình dạng trụ & nắp:** thân trụ là **ống trụ THẲNG**, đường kính ngoài **= đúng footprint của base Matchboxscope ĐÃ IN (~50×52mm)** — **KHÔNG phình rộng thành "cốc"**. Nắp trụ **chính là base đã in** (tái dùng nguyên bản, bắt vít qua lỗ sẵn), **không dựng nắp tròn Ø60 liền khối mới**. Lý do: thực nghiệm cho thấy ống thẳng cho ảnh **không kém** ống rộng (chất lượng silhouette do nội thất đen nhám + phơi sáng tay quyết định, không do bề rộng ống), nên ưu tiên tái dùng base in sẵn. Hệ quả: `tube_od` giảm 60→~50, kéo theo khay/cửa sổ/đèn nền **co lại cho lọt lòng ống** (vùng nước ảnh hóa ~40mm). Xem bảng hằng số bên dưới.

---

## Bảng Hằng Số Baseline (nội dung dự kiến của `constants.scad`)

| Nhóm | Hằng số | Giá trị | Nguồn |
|---|---|---|---|
| **Dung sai** | `tol` | `0.2` mm | FDM tiêu chuẩn |
| | `wall_t` | `2.0` mm | Tường mặc định |
| **Quang học** | `work_dist` | `40.0` mm | Đo thực tế (nét 3–5cm) |
| | `fov_w_est` | `~46` mm | Ước lượng FOV ngang tại `work_dist` |
| **XIAO ESP32-S3** | `xiao_l` | `21.0` mm | Datasheet Seeed |
| | `xiao_w` | `17.8` mm | Datasheet Seeed |
| | `xiao_h` | `2.5` mm | PCB thickness |
| | `xiao_cam_d` | `8.0` mm | Ống kính OV2640/OV3660 |
| | `cam_hole_d` | `10.0` mm | Lỗ thoát camera (8 + quang sai) |
| **Nắp trụ** = base Matchboxscope **ĐÃ IN** (tái dùng, KHÔNG dựng mới) | `cap_footprint` | `50.45 × 52.0` mm | Base gốc (technical_specs.md) — **quyết định chốt** |
| | `cap_h` | `12.0` mm | Chiều cao base gốc |
| | `cap_mount` | lỗ vít **CÓ SẴN** | Bắt qua lỗ M3 sẵn của base (xem nhóm "Giao diện lắp M3") — KHÔNG khoan mới |
| | *(rãnh giữ XIAO)* | có sẵn trong base | Không cần dựng lại recess/lỗ camera |
| **Giao diện lắp M3** *(đo lại STL bằng trimesh, 2026-07-07 — nguồn: `technical_specs.md`)* | `mount_pattern` | `30.0 × 30.0` mm | 4 lỗ **góc vuông**, tâm cụm = **trục quang** `(−6.2, 81.5)` |
| | `mount_hole_base` | Ø`2.8` mm | Lỗ **tự-ren M3** trên base (nắp trụ) — vít bắt vào đây |
| | `mount_hole_lid` | Ø`3.2` mm | Lỗ **thông M3** (clearance) trên lid |
| | `mount_center` | `(−6.2, 81.5)` | **Lòng ống `tube_id` phải ĐỒNG TÂM điểm này** (lệch ~0.8mm so với tâm outline `−5.4`) — căn theo trục quang, KHÔNG theo outline |
| | `cam_aperture_real` | Ø`7.5` mm | Lỗ camera **THẬT** ở tâm base (khác `cam_hole_d`=10 vốn là số dự phòng cho cắt geometry MỚI) |
| | `legacy_holes` | 3× Ø`8.0` mm | ⚠️ **DI SẢN Matchboxscope cũ — BỎ QUA.** Tại `(7.1,95.0)`,`(−19.6,68.0)`,`(−15.7,92.5)`, vây quanh lỗ camera. KHÔNG tái tạo, KHÔNG nhầm là lỗ luồn cáp/chức năng |
| **Thân trụ** (ống **THẲNG**, OD = base) | `tube_od` | `50.0` mm | ≤ 50.45 (cạnh ngắn base) để base phủ kín miệng — **CHỐT: không phình rộng** |
| | `tube_wall` | `2.0` mm | Ống ngắn nên 2mm đủ cứng; mỏng để giữ `tube_id` không vignette |
| | `tube_id` | `46.0` mm | `tube_od − 2·wall`; ≥ nón FOV (~46mm) tại `work_dist` |
| | `tube_h` | `45.0` mm | ≈ `work_dist` + margin (tham số hóa) |
| **Khay dòng chảy** *(co lại cho lọt `tube_id`=46; giá trị tạm, chốt khi dựng)* | `tray_inner` | `40.0` mm | Vùng nước ảnh hóa; lấp ~87% khung (FOV ~46) |
| | `tray_wall` | `2.0` mm | |
| | `tray_outer` | `44.0` mm | `tray_inner + 2*wall`, lọt `tube_id` (46) có khe |
| | `tray_depth` | `12.0` mm | Chiều sâu thành khay (> mực nước) |
| | `water_depth` | `6.0` mm | ĐỘ DÀY LỚP NƯỚC (mực khi settle, giữ bằng **bơm-tắt/van tự chặn**). ≥ hạt lớn nhất 5mm, giữ MỎNG (xem ghi chú) |
| | `inlet_slot` | `~20 × 3` mm | Cổng VÀO = **khe khuếch tán** ở THÀNH BÊN sát đáy (biến tia→màng rộng, xóa 2 thùy tĩnh, quét mặt đáy) |
| | `outlet_low` | Ø`~8` mm | Cổng RA = **cổng rút SÁT ĐÁY** (KHÔNG ở đỉnh 6mm) → flush được cả hạt CHÌM; nối ống hút bơm |
| | `port_layout` | VÀO ↔ RA **đối tâm 180°** | Dòng quét ngang TOÀN sàn; hạt <2mm theo dòng ra **qua bơm** |
| | `fillet_r` | `≥ 2.5` mm | Bo góc đáy–thành + đĩa acrylic phẳng-sàn + silicon vê tròn: **xóa rãnh/khe bẫy hạt** (chống đọng) |
| | `weir_h` | `6.0` (TÙY CHỌN) | Mép tràn hạ xuống **tùy chọn** (chặn-tràn an toàn khi fill); KHÔNG còn là cơ cấu giữ mực bắt buộc |
| | `drain_port_d` | `8.0` mm | Van XẢ đáy **TÙY CHỌN** (xả cạn/vệ sinh); flush chính do **bơm chạy mạnh** (~1.4 L/min) cuốn hạt ra cổng RA |
| **Đáy acrylic (cửa sổ tròn)** | `tray_win_d` | `42.0` mm | Đĩa acrylic TRONG, > `tray_inner` (40) để chồng lên gờ |
| | `tray_win_t` | `3.0` mm | Dày 2–3mm (đĩa Ø~42 không võng); dùng acrylic ĐÚC (cast) |
| | `ledge_overlap` | `1.5` mm | Gờ kê ăn vào trong mỗi cạnh (đỡ đĩa) |
| | `ledge_depth` | `3.3` mm | ≈ `tray_win_t` + khe silicon ~0.3 |
| | `win_clr` | `0.35` mm | Khe hở quanh đĩa (dung sai in) |
| | `retainer_screw_d` | `2.5` mm | Khung ép giữ đĩa (vít M2.5, 3–4 cái quanh vòng) |
| **Cửa sổ trên (tùy chọn)** | `win_top_d` | `42.0` mm | Đĩa acrylic/lam kính gác gờ ép phẳng mặt nước — KHÔNG thả nổi |
| **Hộp đèn nền (Light Box) — 🔒 CHỐT 2026-07-07: "LED XUÔI"** (bỏ bounce/baffle) | `bl_mix_h` | `8.0` mm | Buồng trộn: đầu LED → màng khuếch tán (khử hotspot) |
| | `bl_diff_d` | `42.0` mm | Màng khuếch tán ngay dưới đáy khay |
| | `bl_diff_gap` | `0–4` mm | Khe XẾP LỚP màng (thêm/bớt lớp chỉnh độ tán) |
| | `led_mod` | `37.5×10×16` mm | CẢ module móc khoá = "1 bóng", DỰNG ĐỨNG, đầu LED hướng LÊN, cắm ma sát (+0.4) |
| | `shelf` | vách RỜI + 2 ốc M3 ngang ±Y | G5; tránh 2 khe dọc ±X (xem `plan.md` §2) |
| | `bl_wall_finish` | TRẮNG mờ | Mặt trong khoang (khác thân trụ đen nhám) |
| **Lưới lọc thô** | `screen_open` | `> 5.0` mm | Khe cho hạt 1–5mm LỌT qua |
| **Ống bơm RS365** | `tube_id_sil` | `8.0` mm | ĐK ống bơm RS365 = **8mm** *(mặc định hiểu là ID; nếu 8mm là OD thì ID~6 — CẦN XÁC NHẬN)* |
| | `tube_od_sil` | `~10–11` mm | Suy từ ID8 (nếu 8mm là OD thì OD8/ID6) |
| **Trạm bơm = bơm màng RS365 (MUA SẴN, KHÔNG in)** | `pump_bbox` | `~90×40×35` mm | Placeholder bounding box RS365 để bố trí lắp; nhu động 28BYJ-48 **ĐÃ LOẠI** (quá chậm) |
| | `pump_barb_id` | `~8` mm | Ngạnh khớp ống bơm RS365 Ø8mm |
| **Điện bơm** | `pump_v` | `12` V | Nguồn adapter 12V/2A; MOSFET IRLZ44N + diode 1N4007 + tụ 470–1000µF; ESP32 5V riêng, **chung GND** |

> **Hai vùng hoàn thiện khác nhau:** thân trụ quang học (phía trên đáy khay) phải **đen nhám** để hút phản xạ lạc;
> nhưng khoang **light box** (phía dưới đáy khay) phải **TRẮNG mờ** để dội sáng đều. Chỉ có đáy khay (acrylic tròn) là trong.

> **Vì sao đáy acrylic tròn (không phải lam kính):** lam kính có kích thước cố định (rộng chỉ 26mm) nên **không phủ được
> khay tròn Ø40** → sẽ phải bóp vùng ảnh thành chữ nhật nhỏ. **Acrylic cắt được thành đĩa tròn Ø bất kỳ** → giữ nguyên
> khay tròn, vùng ảnh **lấp đầy khung**. Chụp silhouette không cần độ trong quang học cao (hạt nằm ngay trên tấm, đèn đã
> khuếch tán) nên acrylic thừa trong. **Tách 2 lớp:** cửa sổ đáy = **acrylic TRONG** (bóng nét); tấm khuếch tán `bl_diff_d`
> = **mica MỜ/giấy can riêng** đặt bên dưới — không gộp làm một.
>
> **Lưu ý vật liệu acrylic:** KHÔNG dán keo 502/cyanoacrylate gần acrylic (làm mờ trắng — fogging); dùng **silicon trung
> tính (keo hồ cá)** hoặc **kẹp cơ khí + gioăng**. Không lau bằng dung dịch gốc amoniac (gây rạn). Acrylic dễ xước → vết
> xước có thể đọc thành "hạt ảo"; thiết kế cửa sổ là **chi tiết thả-vào thay được** và lau nhẹ. Lam kính đang có tận dụng
> cho **cửa sổ trên tùy chọn** hoặc hiệu chuẩn/thử nghiệm.

> **Độ dày lớp nước (`water_depth = 6mm`) — vì sao MỎNG:** hạt nhựa **nổi HOẶC chìm** (PE/PP nổi ở mặt nước, PET/PS chìm
> ở đáy acrylic) → hạt nằm ở **2 mặt phẳng** cách nhau đúng bằng độ dày nước. Nước càng mỏng → 2 mặt càng gần → **cả hạt
> nổi lẫn hạt chìm cùng nằm trong vùng nét (DOF)**; đồng thời **chống hạt xếp chồng** (nước sâu → 2 bóng đè nhau → đếm sai).
> Sàn dưới = hạt lớn nhất 5mm + ~1mm dư ⇒ **6mm**. Kèm theo: **lấy nét ở GIỮA lớp nước (~3mm)** để hạt nổi/chìm cách mặt
> nét đều nhau; và **PHẢI kiểm DOF trên phần cứng** — nếu DOF < 6mm thì hạt nổi nhòe → hạ `water_depth` xuống 5mm (tham số hóa).

> **Cổng nước & chống đọng trên khay TRÒN — yêu cầu DUY NHẤT: mọi hạt phải RA HẾT, không sót** *(hạt sót ở góc → đếm dồn sang mẫu sau → sai truy xuất nguồn gốc)*. 2 cổng chính trên **thành nhựa** (KHÔNG đụng đĩa acrylic), **đối tâm 180°**:
> (1) **VÀO** = `inlet_slot` **khe khuếch tán ~20×3mm sát đáy** biến tia thành **màng rộng** (xóa 2 thùy tĩnh hai bên + quét mặt đáy), qua lưới >5mm nối **nguồn mẫu**; (2) **RA** = `outlet_low` **cổng rút SÁT ĐÁY** (KHÔNG ở đỉnh 6mm) nối **ống hút bơm RS365 → thải** — đặt thấp để flush được **hạt CHÌM** ở đáy.
> **Giữ mực nước khi settle = van màng bơm tự chặn lúc TẮT** (KHÔNG cần mép tràn/standpipe); `weir_h` và `drain_port_d` đều **TÙY CHỌN**.
> **Chống đọng bằng hình học:** bo `fillet_r ≥2.5` góc đáy–thành, **mặt đĩa acrylic phẳng-sàn + silicon vê tròn** mối nối, **KHÔNG lưới/gờ giữ hạt**. **Chống đọng bằng vận tốc:** flush cho vận tốc khay ~10 cm/s (≈ **Q ~1.4 L/min**, RS365 thừa) để nhấc cả hạt nổi lẫn chìm; fill êm (~0.3 L/min) để phân bố đều. **Kiểm nghiệm: thả ~20 hạt (nổi+chìm), chạy 1 flush, đếm hạt sót.**
> **Dòng do BƠM CHỦ ĐỘNG** (RS365 tự mồi, hút chuỗi nguồn→khay→bơm→thải), **KHÔNG dựa trọng lực**. **Hạt <2mm ĐI QUA bơm** (đánh đổi có chủ đích — nút hẹp là van bơm ~2–4mm, không phải ống; nếu quay lại dải 5mm phải xét lại). Bơm là **module RS365 MUA SẴN** (không in), đặt TÁCH RỜI chống rung, nối khay bằng **ống bơm RS365 Ø8mm** *(mặc định ID~8; xác nhận ID/OD)*.

---

## Cấu Trúc File Đề Xuất

```
openscad/                              ✅ ĐÃ DỰNG 2026-07-07 (cấu trúc THỰC TẾ)
├── constants.scad                     ← Hằng số + helper + ASSERT lắp ghép + bố trí dọc
├── aqua_scope_assembly_001.scad       ← Lắp ghép tổng (cờ explode / show_pump / show_electronics / show_window)
├── components/
│   ├── xiao_esp32s3_001.scad          ← Board XIAO mock (OV3660)
│   ├── top_cap_001.scad               ← import() STL base thật + căn trục quang (−6.2, 81.5)
│   ├── tube_body_001.scad             ← Vỏ TRÊN: ống Ø50/46 + bích M3 + vòng chặn/đỡ khay + 2 khe dọc
│   ├── flow_tray_001.scad             ← Khay: khe khuếch tán VÀO (hộp loe) + cổng RA sát đáy + hốc đĩa
│   ├── window_retainer_001.scad       ← Đĩa acrylic Ø42×3 + vòng ép SNAP-FIT 3 tai (M2.5 bất khả thi — xem plan.md)
│   ├── glass_window_top_001.scad      ← Cửa sổ ép phẳng mặt nước (tùy chọn, gác mép khay)
│   ├── light_box_001.scad             ← Vỏ DƯỚI: khoang đèn LED XUÔI + vách RỜI + cột màng + nút bịt khe
│   ├── led_module_001.scad            ← Mock module LED móc khoá 37.5×10×16
│   ├── accessories_001.scad           ← prescreen + silicone_tube (ID8/OD11) + pump_rs365 placeholder
│   ├── esp32cam_001.scad              ← [BIẾN THỂ] Mock board ESP32-CAM AI-Thinker
│   └── top_cap_esp32cam_001.scad      ← [BIẾN THỂ] Nắp adapter IN cho ESP32-CAM (cùng bích 4×M3
│                                         30×30 → THAY THẾ được base XIAO; lid Matchboxscope in sẵn kẹp trên)
└── print/                             ← 7 wrapper in → STL (đã kiểm manifold ✓)
    print_housing / print_flow_tray / print_window_retainer /
    print_led_shelf / print_slot_plugs / print_prescreen / print_top_cap_esp32cam
```

> **Biến thể ESP32-CAM (tùy chọn, 2026-07-08):** bật bằng `cam_variant=1` trong assembly. Board úp
> camera xuống trong hốc chìm (pin header chĩa lên, chìm hẳn), lens trùng trục quang (hốc dịch bù
> `e32_lens_off` — ⚠️ đo lại trên board thật), lid Matchboxscope in sẵn (50.42×52×2, 4 lỗ Ø3.2 đúng
> pattern) làm nắp kẹp. Lens ESP32-CAM vặn chỉnh nét được → bù cự ly ~36mm. Baseline XIAO không đổi.

> **Kiến trúc LẮP TỪ ĐÁY** (hệ quả G2 "vỏ 1 ống liền"): bích đỉnh chặn miệng trên → khay, đĩa,
> vòng ép, màng, vách LED đều luồn/tháo từ DƯỚI; ngạnh ống nước thò qua **2 khe dọc ±X**
> (VÀO rộng 24 cho hộp loe, RA rộng 12) mở từ vành đáy lên z=+7, có **nút bịt** chống lọt sáng.
> Chi tiết quyết định trong `plan.md` §2.

**Đã loại bỏ so với plan cũ:** `z_axis_pillar.scad` (cột conson), `stage_uv_mount.scad` + `led_uv.scad`
(nguyên lý UV), `base_lid.scad`, bước "đèn nền trắng + trừ nền" trong chu trình. `led_white` nay là
`backlight_box` — **hộp đèn bounce** (khoang trắng, chiếu gián tiếp), không phải LED chiếu thẳng.
`flow_tray` nay có **gờ kê đĩa acrylic tròn** + `window_retainer` vòng ép chống rò. Cụm **`pump/*.scad` nhu động
28BYJ-48 ĐÃ LOẠI** → thay bằng 1 placeholder `pump_rs365.scad` (bơm màng **mua sẵn**); khay **bỏ lưới giữ hạt**
(hạt <2mm đi qua bơm).

---

## Sơ Đồ Lắp Ghép (Assembly)

```
        ┌───────────────────────────┐
        │  top_cap = BASE IN SẴN    │  ← Base Matchboxscope 50×52 in sẵn, tháo được
        │  camera OV2640 úp xuống    │     (tái dùng nguyên bản; lỗ camera có sẵn)
        └─────────────┬─────────────┘
                      │  ⇕ work_dist = 40mm (cự ly nét)
        ┌─────────────┴─────────────┐
        │        tube_body           │  ← Ống THẲNG Ø50/ID46, cao ~45mm, đen nhám
        │  ┌──glass_window (opt)──┐   │     (cửa sổ phẳng trên gờ, tùy chọn)
        │  │≈≈ nước dày 6mm (weir) ≈│   │
        │  │      flow_tray        │  │  ← Khay TRÒN, đáy ĐĨA ACRYLIC trên gờ kê, mép tràn 6mm
        │  │ [window_retainer ép]  │  │     3 cổng THÀNH BÊN: vào(>5mm) / tràn-ra→bơm / xả đáy Ø8
        │  └───────────────────────┘  │     (vào ↔ xả đối diện); silicon hồ cá chống rò viền đĩa
        └─────────────┬─────────────┘
        ┌─────────────┴─────────────┐
        │  backlight_box (bounce)    │  ← khoang TRẮNG + 1 LED chếch + baffle
        │  ○→‖ ... ‖ ←→ dội lên      │     + tấm khuếch tán cuối; KHÔNG chiếu thẳng
        └───────────────────────────┘

     ══ ống silicone (OD8/ID6) ══     prescreen (>5mm) ở đầu vào

        ┌───────────────────────────┐
        │  Trạm bơm (tách rời)       │  ← Bơm màng RS365 12V MUA SẴN (chủ động hút);
        │  RS365 ~90×40×35 (mua sẵn)  │     cách ly rung; hạt <2mm ĐI QUA bơm (đánh đổi)
        └───────────────────────────┘
```

**Biến assembly:** `explode` (xem tách rời), `show_pump`, `show_electronics`, `show_window`.
Màu: nhựa in (xám), kính (xanh trong), PCB (xanh lá), kim loại (bạc).

---

## Chu Trình (khớp `README.md`)

Cấp mẫu (**bơm RS365 hút** chuỗi nguồn→khay→thải, qua lưới >5mm) → Đóng băng 1–2s (**tắt bơm**, **van bơm tự chặn giữ mực nước**)
→ Bật đèn nền, chụp ảnh CAO (SXGA/UXGA) → **Hybrid on-device**: classical CV (threshold → connected components →
centroid + diện tích → đếm & đo size) rồi crop từng blob → **classifier** gán loại hạt → Tắt đèn, **bơm chạy mạnh flush** → lặp.

> **Stop-Flow là BẮT BUỘC (không phải di sản bơm nhu động):** dừng dòng vì (1) **rolling shutter** làm hạt trôi méo/nhòe → sai đo size; (2) mặt nước chảy gợn sóng → khúc xạ; (3) cần **mẫu rời rạc thể tích cố định** cho truy xuất nguồn gốc; (4) pipeline `connected-components` là **một-khung** → chảy sẽ đếm đôi. Bơm nhanh làm Stop-Flow **tốt hơn** (chu kỳ ngắn), không thừa. Xem lý giải đầy đủ trong `README.md` (dưới sơ đồ chu trình).

**Ghi chú firmware (không thuộc mô hình 3D nhưng cần cho hệ chạy):** tắt AEC/AEC-DSP/AGC, Gain=0,
Exposure thấp; khuếch tán đèn; cho vùng sáng lấp đầy khung. (Xem `info.txt` §3.)

---

## Thứ Tự Triển Khai

| GĐ | Việc | Files |
|---|---|---|
| **1** | Hằng số + board tham khảo | `constants.scad`, `xiao_esp32s3.scad` |
| **2** | Lõi quang học | `tube_body.scad`, `top_cap.scad`, `flow_tray.scad` |
| **3** | Chiếu sáng + phụ kiện | `backlight_mount.scad`, `glass_window.scad`, `prescreen.scad`, `silicone_tube.scad` |
| **4** | Trạm bơm (placeholder mua sẵn) | `pump_rs365.scad` |
| **5** | Lắp ghép tổng | `aqua_scope_assembly.scad` |

---

## Câu Hỏi Còn Mở (cần chốt trước khi code OpenSCAD)

1. ~~**Nắp trụ:** tái dùng bản in Matchboxscope hay dựng nắp tròn liền khối mới?~~ ✅ **ĐÃ CHỐT (2026-07-06):** tái dùng **base Matchboxscope ĐÃ IN** làm nắp; **thân trụ là ống THẲNG có OD = footprint base (~50mm), KHÔNG phình rộng, KHÔNG dựng nắp Ø60 mới.** Miệng ống có mặt bích khớp lỗ vít sẵn của base. Còn lại chỉ là chi tiết dựng: mặt bích/gờ trên đỉnh ống để bắt base, và co khay/cửa sổ/đèn cho lọt `tube_id`=46.
2. ~~**Ghép nắp↔thân:** ren vặn, bayonet, hay bắt 3–4 vít M3?~~ ✅ **ĐÃ CHỐT (2026-07-07):** **4 vít M3**
   qua lỗ CÓ SẴN của base (bước vuông 30×30, tâm = trục quang), bích đỉnh ống lỗ Ø3.2 clearance.
3. ~~**Bơm:** nhu động 28BYJ-48 hay bơm DC/màng mini?~~ ✅ **ĐÃ CHỐT (2026-07-06):** **bơm màng RS365 12V CHỦ ĐỘNG**
   (mua sẵn, không in); nhu động 28BYJ-48 loại vì quá chậm. Hạt <2mm đi qua bơm. Điện: MOSFET IRLZ44N + diode 1N4007 + tụ, nguồn 12V/2A.
4. **Đáy khay acrylic:** đã chốt **khay TRÒN + đĩa acrylic** trên **gờ kê + vòng ép (`window_retainer`) + silicon hồ cá**.
   Còn chốt: **độ dày đĩa** `tray_win_t` = **2 hay 3mm** (mặc định 3mm cho cứng, chống võng).
5. ~~**Đèn light box:** chếch+baffle hay panel?~~ ✅ **ĐÃ CHỐT (2026-07-07, G1):** **"LED XUÔI"** — module
   móc khoá dựng đứng đầu LED hướng LÊN + buồng trộn 8mm + màng khuếch tán xếp lớp (bỏ bounce/baffle).
6. **Độ dày lớp nước:** đề xuất `water_depth = 6mm` (đã lý giải ở ghi chú hằng số). Cần **kiểm DOF trên phần cứng** để
   xác nhận cả hạt nổi lẫn chìm đều nét; nếu không → hạ về 5mm.

---

## Kiểm Chứng

- Mở từng `.scad` bằng OpenSCAD CLI kiểm cú pháp; render PNG (skill `/preview-scad`) soi bằng mắt.
- So bounding box các chi tiết tham khảo (pump/base) với `technical_specs.md`.
- Kiểm lắp: lỗ vít nắp thẳng hàng với lỗ SẴN của base; `tray_outer` (44) lọt `tube_id` (46); nón FOV (~46mm) tại `work_dist` không chạm thành ống (ID=46 sát mép — kiểm không vignette).
- Render exploded view để trình bày.
