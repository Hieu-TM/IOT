// ============================================================================
// constants.scad — Aqua Scope (baseline "Backlit Silhouette")
// ----------------------------------------------------------------------------
// TOÀN BỘ hằng số của hệ. KHÔNG chứa geometry (chỉ helper module dùng chung).
// Nguồn: plan.md §5#2, implementation_plan.md §"Bảng Hằng Số Baseline",
//        technical_specs.md (đo STL), các quyết định G1–G5 (plan.md §2).
//
// HỆ TRỤC CHUNG (assembly):
//   - Gốc O = TÂM QUANG HỌC tại MẶT SÀN KHAY (mặt trên đĩa acrylic đáy).
//   - Trục Z = trục quang; +Z hướng LÊN camera.
//   - Nước: z = 0 .. water_depth (mặt nước z = water_depth).
//   - Ống kính camera: z = water_depth + work_dist (= 46 danh nghĩa).
//   - Mỗi component có gốc cục bộ riêng tiện dựng; assembly chịu trách nhiệm đặt.
// ============================================================================

// ---------------------------------------------------------------- Dung sai / in
tol        = 0.2;   // dung sai FDM tiêu chuẩn (khe lắp trượt mỗi bên)
wall_t     = 2.0;   // bề dày tường mặc định
fit_clr    = 0.4;   // dung sai lỗ cắm ma sát (lỗ module LED qua vách) — G5

// ---------------------------------------------------------------- Quang học
work_dist  = 40.0;  // cự ly ống kính ↔ MẶT NƯỚC (đo thật: nét 3–5cm → chọn 40)
fov_w_est  = 46.0;  // FOV ngang ước lượng tại work_dist (~46mm)

// ---------------------------------------------------------------- XIAO ESP32-S3 Sense
xiao_l     = 21.0;  // dài PCB
xiao_w     = 17.8;  // rộng PCB
xiao_h     = 2.5;   // dày PCB
xiao_cam_d = 8.0;   // Ø ống kính camera (cảm biến OV3660 — KHÔNG phải OV2640)

// ---------------------------------------------------------------- Nắp trụ = base Matchboxscope ĐÃ IN (tái dùng, KHÔNG dựng mới)
cap_l          = 50.45; // footprint base (X) — technical_specs.md
cap_w          = 52.0;  // footprint base (Y)
cap_h          = 12.0;  // chiều cao base
cam_aperture   = 7.5;   // Ø lỗ camera THẬT ở tâm base (đo STL)
// Giao diện lắp M3 (đo lại STL bằng trimesh 2026-07-07):
mount_pitch    = 30.0;            // bước lỗ vuông 30×30
mount_center   = [-6.2, 81.5];    // tâm cụm lỗ = TRỤC QUANG (toạ độ STL gốc!)
                                  // (lệch ~0.8mm so tâm outline −5.39 — căn theo TRỤC QUANG)
mount_hole_base_d = 2.8;  // lỗ TỰ-REN M3 trên base (vít bắt vào đây)
mount_hole_lid_d  = 3.2;  // lỗ THÔNG M3 (clearance) trên chi tiết đối ứng (bích ống)
// ⚠️ 3 lỗ Ø8 quanh lỗ camera trong STL là DI SẢN Matchboxscope — BỎ QUA, không tái tạo.

// ---------------------------------------------------------------- Thân trụ (ống THẲNG — G2: 1 ống liền suốt)
tube_od    = 50.0;  // ≤ 50.45 (cạnh ngắn base) để base phủ kín miệng — KHÔNG phình cốc
tube_wall  = 2.0;
tube_id    = tube_od - 2*tube_wall;  // = 46, ≥ nón FOV ~46 tại work_dist
tube_h     = 45.0;  // đoạn quang học (bích đỉnh → gờ kê khay), ≈ work_dist + margin

// ---------------------------------------------------------------- Khay dòng chảy (Macro-Flow, thiết kế MỚI — KHÔNG chi tiết giữ hạt)
tray_inner   = 40.0;  // Ø vùng nước ảnh hóa (lấp ~87% khung)
tray_wall    = 2.0;
tray_outer   = tray_inner + 2*tray_wall;  // = 44, lọt tube_id=46 có khe
tray_depth   = 12.0;  // chiều cao thành khay trên sàn (> mực nước)
water_depth  = 6.0;   // mực nước khi settle (giữ bằng van bơm tự chặn) — CHƯA CHỐT 5/6, tham số
inlet_slot_w = 20.0;  // cổng VÀO: khe khuếch tán ~20×3 SÁT ĐÁY (tia → màng rộng)
inlet_slot_h = 3.0;
outlet_barb_od = 8.0; // cổng RA: ngạnh OD=8 SÁT ĐÁY (G4: 8mm là OD cổng bơm — dùng chung cỡ)
outlet_bore    = 6.0; // lòng chảy trong ngạnh (~6 ≥ 3× hạt 2mm)
fillet_r     = 2.5;   // bo góc đáy–thành ≥2.5 (chống đọng)
// port_layout: VÀO ↔ RA đối tâm 180° (VÀO tại −X, RA tại +X trong hệ khay)
weir_h       = 6.0;   // mép tràn TÙY CHỌN (chặn-tràn an toàn) — không bắt buộc
drain_port_d = 8.0;   // van xả đáy TÙY CHỌN (vệ sinh) — không thuộc chu trình

// ---------------------------------------------------------------- CHỐNG SÓNG (2026-07-23)
// Nguồn: docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md
// ⚠️ 4 số dưới đây LỆCH CÓ CHỦ Ý so với tài liệu nghiên cứu — lý do ghi tại chỗ.
particle_max = 2.0;    // hạt lớn nhất trong phạm vi test (CLAUDE.md: <2mm)

// (e) Cửa vào ĐỤC LỖ — thay khe hở liền 20×3 bằng N cửa sổ ngăn bởi gân.
// Chia tia nước lớn thành nhiều tia nhỏ → tiêu tán động năng nhanh hơn nhiều.
inlet_rib_t  = 1.2;    // bề dày gân giữa 2 cửa sổ (3 perimeter × nozzle 0.4)
inlet_gap_w  = 3.5;    // ⚠️ LỆCH tài liệu (2.5): 2.5 chỉ dư 0.5mm so hạt 2mm, NGAY
                       // CỬA VÀO. Hạt nghẽn ở đây = không vào khay = không đếm được
                       // (hỏng chính phép đo, tệ hơn kẹt ở cửa ra). 3.5 = 1.75× hạt.
inlet_n_gap  = 4;      // số cửa sổ
inlet_pitch  = inlet_gap_w + inlet_rib_t;                              // = 4.7
inlet_span   = inlet_n_gap * inlet_gap_w + (inlet_n_gap - 1) * inlet_rib_t;  // = 17.6

// (c) VÁCH CONG tiêu năng — chắn đường đi thẳng cổng vào → cổng ra (short-circuiting)
baffle_t     = 1.2;    // bề dày vách (3 perimeter FDM)
baffle_r_mid = 16.4;   // ⚠️ LỆCH tài liệu (17.6): 17.6 → hành lang chỉ 1.8mm < hạt
                       // 2mm ⇒ hạt KHÔNG lọt, kẹt trong túi cổng vào (lối thoát duy
                       // nhất) ⇒ vi phạm ràng buộc cứng "mọi hạt ra hết".
                       // GIÁ PHẢI TRẢ: vùng ảnh hóa Ø40 → Ø31.6. Chỉnh tham số này
                       // sau khi in thử nếu muốn đổi cân bằng.
baffle_h     = 7.0;    // ⚠️ LỆCH tài liệu (5.0): 5.0 < mực nước 6 ⇒ ~50% lưu lượng
                       // tràn qua NÓC vách, xả động năng thẳng vào MẶT NƯỚC (chỗ cần
                       // phẳng nhất). Lý do "thoát bọt" của tài liệu không áp dụng vì
                       // vách là HÀNG RÀO HỞ 2 ĐẦU, bọt thoát tự do quanh 2 đầu mút.
baffle_angle = 90;     // góc quét cung (độ), tâm tại −X (đối diện cổng vào)
                       // Bo 2 đầu mút: bán nguyệt r = baffle_t/2 = 0.6 — ⚠️ tài liệu
                       // ghi fillet_r=2.0 là BẤT KHẢ THI trên vách dày 1.2mm.
baffle_corridor = tray_inner/2 - (baffle_r_mid + baffle_t/2);  // DẪN XUẤT = 3.0

// (Bellmouth) MIỆNG LOE cổng RA — chống dồn ứ + dội sóng ngược tại miệng lỗ xả
// Nhô VÀO lòng khay (KHÔNG khoét lõm vào thành): thành chỉ dày 2mm, khoét lõm bo
// R=3 sẽ ăn hết thịt quanh ngạnh OD8 (còn ~0.25mm) → vỡ khi in/dùng.
bell_fillet_r = 3.0;   // bán kính bo loe (r/d = 0.5 ≫ ngưỡng 0.15 ⇒ K: 0.5 → <0.05)
bell_wall     = 1.2;   // bề dày vỏ loa kèn (3 perimeter)
bell_steps    = 24;    // số đoạn xấp xỉ cung 90° khi revolve

// ---------------------------------------------------------------- Đáy acrylic (cửa sổ tròn) + vòng ép
tray_win_d = 42.0;   // đĩa acrylic TRONG, > tray_inner để chồng gờ
                     // (Ø42 là TỐI ĐA khả thi: OD khay 44 − 2×(0.35 khe + 0.65 thịt hốc);
                     //  ledge_overlap=1.5 của bảng gốc bất khả thi với OD44 — thực tế 1.0)
tray_win_t = 3.0;    // dày đĩa — CHƯA CHỐT 2/3, mặc định 3 chống võng; acrylic ĐÚC (cast)
ledge_overlap = (tray_win_d - tray_inner) / 2; // gờ kê ăn vào mỗi cạnh (DẪN XUẤT = 1.0)
ledge_depth   = tray_win_t + 0.3;  // sâu hốc = dày đĩa + khe silicon ~0.3
win_clr       = 0.35;              // khe hở quanh đĩa (dung sai in)
ledge_plate_t = 1.0;               // gờ kê TRÊN đĩa dày 1mm (bậc nhỏ, silicon vê tròn — docs cho phép)
retainer_t    = 2.2;               // bề dày vòng ép SNAP-FIT
// ⚠️ Vòng ép VÍT M2.5 bất khả thi hình học với OD khay 44 (vòng tâm vít nào cũng
// đè lên hốc đĩa) → dùng NGÀM SNAP-FIT 3 tai cài vào cửa sổ ở váy khay
// (README cho phép "vít M2.5 HOẶC ngàm snap-fit").
snap_tab_n    = 3;
// Đĩa lắp TỪ DƯỚI LÊN vào hốc rebate dưới sàn khay; vòng ép snap-fit đẩy đĩa
// ép lên gờ + silicon; mặt đĩa thấp hơn sàn đúng ledge_plate_t, silicon vê tròn mối nối.

// ---------------------------------------------------------------- Cửa sổ trên (TÙY CHỌN — ép phẳng mặt nước)
win_top_d = 42.0;    // đĩa acrylic/lam kính GÁC GỜ (không thả nổi — kính chìm)
win_top_t = 2.0;

// ---------------------------------------------------------------- Hộp đèn nền (G1: LED XUÔI — thẳng lên + buồng trộn + màng khuếch tán)
bl_diff_d   = 42.0;  // Ø tấm khuếch tán CUỐI ngay dưới đáy khay
bl_diff_gap = 4.0;   // khe xếp lớp màng khuếch tán 0–4mm (thêm/bớt lớp chỉnh độ tán)
bl_mix_h    = 8.0;   // buồng trộn: đầu LED → màng khuếch tán (khử hotspot nguồn điểm)
// Module LED móc khoá = "1 bóng" (mua sẵn): dựng đứng, đầu LED hướng LÊN
led_mod_w   = 10.0;  // tiết diện module (ngang)
led_mod_d   = 16.0;  // tiết diện module (sâu)
led_mod_h   = 37.5;  // chiều cao module (dựng đứng)
led_head_h  = 6.0;   // phần "mũi" chứa LED ở đầu trên (ước lượng, chỉ để mock)
// Vách đỡ module (G5: MIẾNG RỜI, bắt 2 ốc M3 XUYÊN NGANG thành ống)
shelf_t        = 3.0;   // bề dày vách đỡ
shelf_clr      = 0.3;   // khe quanh vách để thả vào lòng ống
shelf_screw_d  = 2.8;   // lỗ tự-ren M3 ở MÉP vách (ốc xuyên thành ống vào đây)
shelf_hole_clr = fit_clr; // lỗ giữa vách = tiết diện module + fit_clr (cắm ma sát)
// Mặt trong khoang đèn: TRẮNG mờ (khác thân trụ quang học ĐEN NHÁM — 2 vùng hoàn thiện)

// ---------------------------------------------------------------- Lưới lọc thô (đầu vào)
screen_open = 6.0;   // khe > 5mm: hạt 1–5mm LỌT qua, chỉ chặn rác to

// ---------------------------------------------------------------- Ống dẫn & bơm (G4: "8mm" = OD CỔNG BƠM)
sil_tube_id = 8.0;   // ống silicone trùm lên ngạnh OD8 → lòng ống ~8
sil_tube_od = 11.0;
pump_bbox   = [90, 40, 35]; // placeholder bơm màng RS365 12V MUA SẴN (không in)
pump_barb_od = 8.0;         // ngạnh cổng vào/ra bơm (OD)
// Điện (không thuộc mô hình): relay module 1 kênh (demo), 12V/2A, tụ 0.1µF ngang bơm.

// ---------------------------------------------------------------- BIẾN THỂ ESP32-CAM (tùy chọn — KHÔNG ảnh hưởng baseline XIAO)
// Nắp adapter in mới `top_cap_esp32cam` thay cho base Matchboxscope khi dùng
// board ESP32-CAM (AI-Thinker); CÙNG giao diện bích 4×M3 30×30 → thay thế được.
// Lid Matchboxscope IN SẴN (50.42×52×2, 4 lỗ Ø3.2 đúng pattern — đo trimesh
// 2026-07-08) tái dùng làm NẮP KẸP đậy hốc board từ trên.
e32_pcb_w      = 27.0;   // PCB ESP32-CAM (AI-Thinker) — bề ngang
e32_pcb_l      = 40.5;   // bề dài (trục lens lệch dọc theo cạnh này)
e32_pcb_t      = 1.6;
e32_lens_d     = 8.0;    // barrel lens OV2640 (vặn chỉnh nét được)
e32_lens_off   = 7.0;    // tâm lens lệch khỏi tâm PCB dọc trục dài — ⚠️ ĐO LẠI board thật trước khi in
e32_cam_blk    = 9.0;    // khối module camera vuông (dưới PCB khi úp xuống)
e32_hdr_h      = 11.0;   // 2 hàng pin header chĩa LÊN (khi camera úp xuống)
e32_clr        = 0.4;    // khe hốc quanh PCB
cap_e32_t      = 15.0;   // dày nắp adapter (hốc 13 nuốt board+pin, sàn 2)
cap_e32_pocket = 13.0;   // sâu hốc từ mặt trên
cap_e32_screw  = 6.0;    // sâu lỗ tự-ren M3 Ø2.8 hai đầu (dưới: bích; trên: lid kẹp); vách ngăn 3

// ---------------------------------------------------------------- Outline base/nắp (dùng chung)
cap_outline     = [50.4, 52.0];  // footprint rounded-rect của base Matchboxscope (đo trimesh)
cap_corner_r    = 8.0;           // bán kính bo góc footprint
cap_outline_off = [0.82, 0.03];  // tâm outline LỆCH trục quang (gốc) — như biến thể esp32cam

// ---------------------------------------------------------------- Nắp đậy TRÊN CÙNG baseline XIAO (top_lid_xiao — CHI TIẾT IN MỚI)
// Đậy board XIAO ESP32-S3 Sense ngồi trong top_cap (base). CÙNG giao diện 4×M3 30×30
// (Ø3.2 thông) như lid Matchboxscope in sẵn, nhưng IN DÀY hơn cho cứng + có khe cáp
// USB-C + gờ định vị ôm ngoài miệng base (chắn bụi/sáng). Vít M3 tự-ren vào NỬA TRÊN
// 4 lỗ base (nửa dưới đã dành cho vít bích ống — lỗ base sâu 12mm, 2 vít không chạm nhau).
lid_x_t        = 3.0;    // dày tấm nắp
lid_x_lip_h    = 3.0;    // gờ định vị thò xuống ôm ngoài miệng base (top 3mm của base)
lid_x_lip_wall = 2.0;    // bề dày vách gờ
lid_x_lip_clr  = 0.6;    // khe gờ↔cạnh base (rộng rãi — 4 vít định vị chính, gờ chỉ chắn sáng)
lid_x_usb_w    = 12.0;   // rộng khe cáp USB-C ở cạnh +X (board USB-C hướng +X — chỉnh nếu xoay board)
lid_x_screw_d  = mount_hole_lid_d;  // 3.2 lỗ thông cho vít M3 xuyên nắp xuống base
lid_x_cbore_d  = 6.2;    // khoét đầu vít (đầu M3 chìm bớt cho gọn)
lid_x_cbore_h  = 1.6;    // sâu khoét đầu vít

// ---------------------------------------------------------------- Màu (palette assembly)
col_plastic  = [0.42, 0.42, 0.46];       // nhựa in (thân đen nhám → xám đậm cho dễ nhìn)
col_plastic_w= [0.92, 0.92, 0.90];       // vùng khoang đèn TRẮNG mờ
col_acrylic  = [0.65, 0.88, 0.95, 0.35]; // acrylic trong
col_diffuser = [1.0, 1.0, 1.0, 0.75];    // màng khuếch tán mờ
col_pcb      = [0.10, 0.45, 0.22];       // PCB xanh lá
col_metal    = [0.75, 0.75, 0.78];       // kim loại
col_water    = [0.35, 0.65, 0.90, 0.30]; // nước
col_led      = [1.0, 1.0, 0.75];         // module LED

// ---------------------------------------------------------------- Cao độ hệ + bố trí dọc (derived)
// KIẾN TRÚC LẮP TỪ ĐÁY (hệ quả bắt buộc của G2 "1 ống liền"): bích đỉnh chặn miệng
// trên → khay + đĩa + màng + vách LED đều luồn/tháo từ DƯỚI lên. Ngạnh ống nước của
// khay thò ra qua 2 KHE DỌC mở từ mép đáy vỏ (±X) — khe kiêm đường dẫn ống.
// Vòng chặn khay (stop ring) kiêm CHẮN SÁNG khe hở khay↔lòng ống.
z_water_top  = water_depth;               // mặt nước (= 6)
z_lens       = water_depth + work_dist;   // ống kính camera (= 46)
z_tube_top   = z_lens;                    // mặt bích đỉnh ống (base úp lên đây)

flange_t       = 3.0;    // bích đỉnh: đĩa đặc z 43..46, lỗ giữa Ø24
flange_hole_d  = 24.0;   // đủ rộng cho nón FOV gần đỉnh (cần r≈1.5+đồng tử tại z=43)
                         //  + đủ thịt cho 4 lỗ M3 tại r=21.2

stop_ring_t    = 2.0;    // vòng chặn khay (trong lòng ống): z 12..14
stop_ring_id   = tray_inner + 0.5;        // = 40.5: không che vùng nước Ø40
z_stop_lo      = tray_depth;              // mặt dưới vòng chặn = mép khay z=12

z_tray_bot     = -(ledge_plate_t + ledge_depth + retainer_t);  // đáy cụm khay = −6.5
// ⚠️ VÒNG ĐỠ KHAY LIỀN VỎ ĐÃ BỎ (từ _002): khay OD44 luồn từ ĐÁY không thể chui
// qua vòng ID40.5 — mâu thuẫn lắp ráp (phát hiện khi in thật 2026-07-08).
// Khay nay ĐỠ BẰNG 2 NÚT BỊT KHE KIÊM CỘT ĐỠ chữ L (slot_plug trong light_box):
// gờ ngang đỡ đáy váy khay tại z_tray_bot, chân nút đứng cùng mặt bàn với vành đế.
// z_seat_* GIỮ LẠI làm ranh giới đoạn vỏ (tube_body ↔ light_box) + datum màng khuếch tán.
seat_ring_t    = 1.5;    // (di sản tên gọi) bề dày ranh giới đoạn vỏ: z −8..−6.5
z_seat_top     = z_tray_bot;              // mặt trên ranh giới
z_seat_bot     = z_seat_top - seat_ring_t;  // = −8

z_diff_top     = z_seat_bot;                       // màng khuếch tán áp dưới vòng đỡ
z_diff_bot     = z_diff_top - bl_diff_gap;         // = −12 (xếp 0–4mm lớp)
z_led_tip      = z_diff_bot - bl_mix_h;            // = −20 (buồng trộn 8mm — G1)
z_shelf_top    = z_led_tip - led_mod_h/2;          // = −38.75 (vách kẹp giữa module)
shelf_screw_z  = z_shelf_top - shelf_t/2;          // tâm 2 ốc M3 ngang (±Y!)
z_mod_bot      = z_led_tip - led_mod_h;            // = −57.5 (đáy module/pin)
z_housing_bot  = z_mod_bot - 4.0;                  // = −61.5: vành đáy = CHÂN ĐẾ, hở giữa

slot_w_out     = 12.0;   // khe dọc +X (phía RA): ngạnh OD8 + khe
slot_w_in      = 24.0;   // khe dọc −X (phía VÀO): hộp loe khe khuếch tán rộng ~22 + khe
slot_top       = 7.5;    // khe mở từ mép đáy vỏ lên z=+7.5 (< mép khay 12: giữ buồng tối)
                         // = đỉnh ngạnh (7) + 0.5 khe hở: ngạnh KHÔNG được chạm nóc khe
                         // trước khi khay tì lên cột đỡ (nút bịt) — tránh kênh khay
port_z         = 3.0;    // tâm cổng RA (lòng Ø6 → sát đáy z=0..6); khe VÀO z=0..3

// Nút bịt khe KIÊM CỘT ĐỠ KHAY (từ light_box_002 — thay vòng đỡ liền vỏ đã bỏ):
plug_top_z     = -1.2;   // đỉnh thân nút: dưới đáy ngạnh/hộp loe (−1) chừa 0.2 khe
plug_tab_d     = 1.7;    // gờ đỡ thò vào lòng ống: tới r=21.4 — đỡ vành váy khay
                         // (r 21.35..22), KHÔNG lấn cột sáng Ø40 (r20), màng Ø42 (r21) lọt qua
plug_tab_h     = 2.0;    // chiều cao gờ đỡ (mặt trên = z_tray_bot)

// Ốc vách LED đặt ±Y để tránh 2 khe dọc ±X
assert(slot_top < tray_depth, "khe dọc phải thấp hơn mép khay (chắn sáng)");
assert(stop_ring_id >= tray_inner, "vòng chặn không được che vùng nước");
assert(slot_top >= port_z + outlet_barb_od/2 + 0.4, "nóc khe phải cao hơn đỉnh ngạnh + khe hở");
assert(plug_top_z <= port_z - outlet_barb_od/2 - 0.15, "đỉnh thân nút bịt phải dưới đáy ngạnh");
assert(tube_id/2 + 0.1 - plug_tab_d < tray_outer/2, "gờ đỡ nút bịt phải với vào dưới vành váy khay");
assert(tube_id/2 + 0.1 - plug_tab_d > tray_inner/2 + 1.0, "gờ đỡ không được lấn cột sáng Ø40");

// ============================================================================
// HELPER dùng chung (không phải geometry chi tiết)
// ============================================================================

// 4 vị trí lỗ M3 bước vuông 30×30, TÂM = TRỤC QUANG (gốc toạ độ hệ).
// Dùng: m3_mount_pattern() cylinder(d=mount_hole_lid_d, h=...);
module m3_mount_pattern() {
    for (dx = [-mount_pitch/2, mount_pitch/2])
        for (dy = [-mount_pitch/2, mount_pitch/2])
            translate([dx, dy, 0]) children();
}

// Phép đặt STL base về hệ chung: đưa TRỤC QUANG (mount_center trong toạ độ STL)
// về trục Z. Việc xoay úp/ngửa + cao độ do top_cap.scad chốt sau khi soi hướng STL.
function base_align_xy() = [-mount_center[0], -mount_center[1], 0];

// Nón FOV từ ống kính xuống mặt nước (để kiểm vignette trực quan trong assembly)
module fov_cone() {
    color([1, 0.9, 0.2, 0.15])
        translate([0, 0, 0])
            cylinder(h = z_lens, r1 = fov_w_est/2, r2 = 1.0);
}

// ============================================================================
// ASSERT lắp ghép — fail ngay khi render nếu kích thước mâu thuẫn
// ============================================================================
assert(tube_od <= cap_l, "tube_od phải ≤ cạnh ngắn base (50.45) để base phủ kín miệng");
assert(tray_outer + 2*win_clr < tube_id, "khay phải lọt lòng ống có khe");
assert(tray_win_d + 2*win_clr < tube_id, "đĩa acrylic phải lọt lòng ống");
assert(tray_win_d > tray_inner, "đĩa acrylic phải chồng lên gờ (win_d > tray_inner)");
assert(tray_inner + 2*ledge_overlap <= tray_win_d + 0.01, "gờ kê ăn vào đủ đỡ đĩa");
assert(fov_w_est <= tube_id + 0.01, "nón FOV không được chạm thành ống (vignette)");
assert(water_depth < tray_depth, "mực nước phải thấp hơn thành khay");
assert(outlet_bore >= 3 * 2.0 - 0.01, "lòng cổng ra ≥ 3× hạt 2mm (chống kẹt)");
assert(bl_diff_d >= tray_inner, "tấm khuếch tán phải phủ hết vùng ảnh hóa");

// --- Assert an toàn hạt cho cụm chống sóng (2026-07-23) ---
assert(inlet_gap_w >= 1.5 * particle_max,
       "cửa sổ vào phải ≥1.5× hạt — nghẽn ở CỬA VÀO nghĩa là hạt không vào được khay, hỏng phép đếm");
assert(inlet_span <= inlet_slot_w,
       "cụm cửa sổ + gân phải nằm gọn trong bề rộng khe vào 20mm");
assert(baffle_corridor >= 1.5 * particle_max,
       "hành lang sau vách cong phải ≥1.5× hạt — đây là lối thoát DUY NHẤT của túi cổng vào");
assert(baffle_h > water_depth,
       "vách phải CAO HƠN mực nước, nếu không dòng tràn qua nóc đập thẳng vào mặt nước");
assert(baffle_r_mid + baffle_t/2 < tray_inner/2 - 0.01,
       "vách cong phải nằm trong lòng khay");
assert(bell_fillet_r >= 0.15 * outlet_bore,
       "bo loe phải đủ tròn (r/d ≥ 0.15) mới hạ được hệ số tổn thất K");

assert(led_mod_w + 2*shelf_hole_clr < tray_inner, "lỗ vách module phải nằm gọn trong lòng");

echo(str("== Aqua Scope constants OK == tube OD/ID/H = ", tube_od, "/", tube_id, "/", tube_h,
         " | z_lens = ", z_lens, " | tray outer/inner = ", tray_outer, "/", tray_inner));
