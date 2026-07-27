# Hướng Dẫn Lắp Ráp & Hoàn Thiện — Aqua Scope

> Tutorial thực thi: từ các chi tiết đã in/đã mua → lắp thành trạm hoàn chỉnh → nạp firmware →
> canh sáng → chạy thử chu trình Stop-Flow. Bám sát kiến trúc **lắp-từ-đáy** (`plan.md` §2, §8),
> quyết định điện **module L298N** ([[pump-drive-decision]]) và firmware OV2640 (`firmware/`).
>
> ⚠️ **Đọc trước — vấn đề mở phải biết:**
> - **Lấy nét:** test 2026-07-08 cho thấy lens OV2640 của unit thực **KHÔNG nét ở 40mm** — chỉ nét mờ ~1cm
>   ([[camera-focus-limit]]). Hướng dẫn này dựng đúng cơ khí baseline, nhưng **bước 6 (canh nét) có thể thất bại**;
>   xem §9 để xử lý (macro clip-on / đổi cự ly / đổi module AF).
>
> ✅ **Điều khiển bơm — đã gộp vào firmware trạm:** `firmware/aqua_scope_station/` chạy đủ chu trình
> Stop-Flow (FILLING → SETTLING → FLUSHING → COOLDOWN) với soft-start/soft-stop, chỉnh được qua Serial
> **hoặc** HTTP (`/control?var=pump_*`). Chỉ còn **một** firmware, nạp lên chính board ESP32-CAM.
> Firmware test riêng cũ (`firmware/pump_l298n_xiao/`, chạy trên XIAO ESP32-S3 rời) đã bị xoá sau khi gộp.
>
> ⚠️ Chu trình auto **mặc định TẮT** lúc cấp điện (an toàn khi đang lắp/kiểm tra). Bật bằng
> `curl "http://<ip>/control?var=pump_auto&val=1"` hoặc gõ `a` qua Serial.

---

## 0. Chuẩn bị — Bảng vật tư (BOM)

### A. Chi tiết IN 3D (đã có STL trong `openscad/print/`, đã kiểm manifold ✓)

| STL | Vai trò | Ghi chú in |
|---|---|---|
| `print_housing.stl` | **Vỏ 1 ống liền** (thân quang + hộp đèn), cao ~108mm | PLA/PETG đen; thành 2mm; **không cần support** nếu in đứng |
| `print_flow_tray.stl` | Khay dòng chảy tròn (khe khuếch tán vào + cổng ra sát đáy) | In đứng theo trục; kiểm khít gờ kê |
| `print_window_retainer.stl` | Vòng ép **snap-fit 3 tai** giữ đĩa acrylic | In phẳng; 3 tai đủ dẻo |
| `print_led_shelf.stl` | Vách đỡ module LED **rời** | Lỗ module +0.4mm dung sai |
| `print_slot_plugs.stl` | 2 nút bịt **khe dọc** (chống lọt sáng) | In khít khe VÀO 24 / RA 12 |
| `print_prescreen.stl` | Lưới lọc thô khe >5mm ở cổng vào | Khe >5mm để hạt 1–5mm lọt |
| `print_pump_station.stl` | Đế liền + hộp che board L298N (hở nắp) + 2 yên kẹp ôm bơm RS365 + **kênh giấu dây** chạy suốt trong đế | PETG (cần dẻo cho khe lồng yên kẹp); in phẳng, không support |
| `print_pump_station_lid.stl` | Nắp hộp L298N (tháo được, 2 vít M3 tự-ren) | In phẳng |
| `print_pump_station_channel_cover.stl` | **2 thanh nắp đậy kênh giấu dây** (đoạn hộp↔yên gần, yên gần↔yên xa) — in chung 1 lần | In phẳng, PETG; ép vào gờ ray, **không vít** |

> **Cài đặt in gợi ý:** layer 0.2mm, infill ≥30%, vật liệu PETG (kháng nước tốt hơn PLA). Vỏ housing là chi
> tiết cao nhất (~108mm) — kiểm giường in đủ cao.

### B. Chi tiết KHÔNG in (mua/cắt/tái dùng)

| Món | Thông số | Nguồn |
|---|---|---|
| **Nắp trụ** = base Matchboxscope | `base/...base_xiao_9.stl` **đã in sẵn**, tái dùng nguyên bản | Đã có |
| Đĩa acrylic đáy (cửa sổ trong) | **Ø42 × 3mm**, acrylic ĐÚC (cast), trong | Cắt laser |
| Màng khuếch tán | Ø~42, mica mờ / giấy can — **1–3 lớp xếp chồng** | Cắt |
| Module LED móc khoá | **37.5×10×16mm**, đầu LED hướng lên, cắm ma sát | Mua sẵn |
| ESP32-CAM (AI-Thinker) | Cảm biến **OV2640** 2MP (board XIAO ESP32-S3 Sense là biến thể cũ, xem §2) | Mua sẵn |
| Bơm màng **RS365 12V** | Tự mồi, bbox ~90×40×35, ngạnh Ø8 | Mua sẵn |
| Ống silicone | **ID≈8 / OD≈11mm** | Mua sẵn |

### C. Điện (BOM tối thiểu chạy được — [[pump-drive-decision]])

- **Module L298N** (cầu H) — driver bơm CHỐT ([[pump-drive-decision]]). Điều khiển bằng PWM vào chân **ENA**
  (phải **tháo jumper ENA** trên board), chiều quay cố định bằng IN1/IN2.
- **Adapter 12V/2A** (dư cho inrush RS365 vọt 2–3A lúc khởi động).
- **Jack DC cái → terminal vặn vít** (rẽ nguồn không cần hàn). *Nằm NGOÀI hộp in — không có lỗ panel-mount
  trên hộp L298N; đây là lựa chọn có chủ đích, xem spec `2026-07-25-pump-station-wire-shroud-design.md`.*
- **Tụ gốm 0.1µF** hàn ngang 2 cực bơm (BẮT BUỘC — dập nhiễu chổi than để ảnh sạch).
- (Khuyến nghị) **Tụ bulk 470–1000µF** trên rail 12V (bù inrush, chống sụt áp → chống brownout ESP32).
- Dây jumper đực-cái (không cần hàn — kênh giấu dây và các khe đã nới đủ rộng cho đầu nhựa dupont).
- Cáp USB-C (nạp + nuôi ESP32 5V riêng), **chung GND bắt buộc**.

> **Vì sao L298N chứ không phải relay/MOSFET:** relay chỉ bật/tắt, không chỉnh được lưu lượng — mà chu trình
> Stop-Flow cần **soft-start/soft-stop** để chống búa nước và sóng mặt nước (xem
> `docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md`). Bản MOSFET IRLZ44N cũ vẫn hợp lệ về điện
> nhưng **hộp in hiện tại làm theo kích thước board L298N** — dùng MOSFET thì phải tự làm giá đỡ khác.
>
> ⚠️ **L298N sụt áp ~1.8–2.5V** qua transistor nội → bơm chỉ nhận ~9.5–10V. Nếu bơm yếu: tăng `fillDuty`
> hoặc dùng adapter 14–15V.

---

## 1. Hoàn thiện bề mặt chi tiết in (làm TRƯỚC khi lắp)

Đây là bước quyết định chất lượng ảnh silhouette — đừng bỏ qua.

1. **Thân quang (nửa TRÊN đáy khay) → ĐEN NHÁM.** Phủ sơn/nhũ đen mờ mặt trong lòng ống để hút phản xạ lạc.
   Bất kỳ điểm bóng nào cũng thành "hạt ảo".
2. **Khoang light box (nửa DƯỚI đáy khay) → TRẮNG MỜ.** Mặt trong khoang đèn phủ trắng để dội sáng đều.
3. Chỉ **đáy khay (đĩa acrylic)** là **trong** — lau sạch, không để xước (xước đọc thành hạt ảo).
4. Khử ba-via ở gờ kê khay, mép khe dọc, lỗ ren M3 ngang.

---

## 2. Lắp cụm camera vào nắp (base)

> ⚠️ **Baseline hiện tại dùng ESP32-CAM (AI-Thinker), không phải XIAO.** Các bước dưới đây mô tả rãnh giữ
> **XIAO ESP32-S3 Sense** trong base gốc — vẫn đúng nếu bạn build biến thể tham khảo cũ. Cho board
> **ESP32-CAM** thật đang dùng, lắp qua chi tiết in `top_cap_esp32cam` (`cam_variant=1` trong
> `openscad/aqua_scope_assembly_001.scad`) thay vì rãnh XIAO này — kiểm lại số đo/lỗ trên chi tiết đó
> trước khi lắp, vì hướng dẫn §2 chưa được viết lại cho biến thể ESP32-CAM.

1. Đặt **XIAO ESP32-S3 Sense** vào rãnh giữ sẵn trong base, **camera úp thẳng xuống**, ống kính chui qua lỗ Ø7.5 ở tâm base.
2. Kiểm trục quang: tâm cụm lỗ **(−6.2, 81.5)** chính là trục camera ([[base-mount-interface]]).
3. **BỎ QUA** 3 lỗ Ø8 di sản quanh camera — không dùng, không luồn cáp qua đó.
4. Chưa siết vào ống vội (còn phải nạp firmware ở §6); có thể để hờ để dễ cắm USB.

---

## 3. Ghép nắp ↔ thân (4 vít M3)

1. Đặt base lên **miệng trên** của `print_housing` sao cho 4 lỗ thẳng hàng (bước vuông **30×30mm**).
2. Vít **M3 từ trên xuống**: qua lỗ **Ø3.2 clearance** ở bích đỉnh ống → bắt vào lỗ **Ø2.8 tự-ren** của base.
3. Base che kín miệng ống (chặn sáng ngoài). Đây là mối **tháo được** để bảo trì — không dán keo.

> Từ đây trở đi mọi thứ **lắp từ ĐÁY lên** (vì bích đỉnh đã chặn miệng trên — kiến trúc bottom-loading, `plan.md` §8).

---

## 4. Lắp khay + cửa sổ acrylic (luồn từ đáy)

1. **Luồn `print_flow_tray` từ dưới lên**, thả vào **gờ kê** trong lòng ống (khay Ø44 lọt ID46 có khe `win_clr`).
2. Đặt **đĩa acrylic Ø42×3** vào hốc rebate đáy khay (flush sàn). Vê một đường **silicon trung tính (keo hồ cá)**
   quanh mép để chống rò — **TUYỆT ĐỐI KHÔNG keo 502/cyanoacrylate** (làm mờ trắng acrylic).
3. Ấn **`print_window_retainer` (snap-fit 3 tai)** đè viền đĩa cho tới khi 3 tai ngàm khớp. Vòng ép **không che vùng ảnh Ø40**.
4. **Đưa ngạnh ống nước qua 2 khe dọc ±X:** khe **VÀO** (rộng 24, phía hộp loe khuếch tán) và khe **RA** (rộng 12,
   cổng rút sát đáy). Sau khi luồn ống, **đóng `print_slot_plugs`** vào 2 khe để **chống lọt sáng**.
5. Kiểm: khay **KHÔNG** còn lưới/gờ giữ hạt (mọi hạt phải ra hết — [[tray-flow-design]]); fillet đáy–thành bo tròn.

---

## 5. Lắp hộp đèn nền (LED xuôi)

1. Xếp **màng khuếch tán** (1–3 lớp) vào khe ngay **dưới đáy khay acrylic**. Thêm/bớt lớp để chỉnh độ tán —
   mục tiêu **trường xám ĐỀU, không hotspot**, camera không bao giờ thấy bóng LED trần.
2. Cắm **module LED móc khoá** vào lỗ của **`print_led_shelf`** (đầu LED hướng **LÊN**), cắm ma sát (dung sai +0.4).
3. Luồn cụm vách+module từ đáy, bắt **2 vít M3 ngang** vào 2 lỗ ren ở thành ống (đặt ở **±Y** để tránh 2 khe dọc ±X).
   Tháo 2 ốc này là lấy được cả vách + module để bảo trì.
4. Buồng trộn ~8mm giữa đầu LED và màng khuếch tán làm nhiệm vụ khử hotspot.

---

## 6. Nạp firmware & canh sáng (calibration)

### 6.1 Nạp firmware (Arduino IDE)
1. Cài Arduino IDE + gói board **esp32 by Espressif (≥3.0)**.
2. Mở `firmware/aqua_scope_station/` (firmware chính thức hiện tại — gộp cả camera lẫn điều khiển bơm, xem callout đầu file).
3. Tools: Board **AI Thinker ESP32-CAM** · **PSRAM: Enabled** · Partition **Huge APP (3MB No OTA/1MB SPIFFS)**.
4. Cắm USB-TTL (ESP32-CAM không có USB-C onboard, cần adapter rời) → chọn Port → **Upload**. Lỗi upload thì giữ nút **BOOT/IO0** khi cắm.

> Bước trên dành cho board **ESP32-CAM** đang dùng. `firmware/aqua_scope_cam/aqua_scope_cam.ino` (board `XIAO_ESP32S3`, có sẵn USB-C) là firmware cho biến thể XIAO cũ — chỉ dùng nếu bạn build lại biến thể tham khảo đó.

### 6.2 Canh phơi sáng thủ công (qua WiFi — khuyến nghị)
1. Board phát WiFi **`AquaScope`** (mật khẩu `aquascope`) → nối điện thoại/laptop → mở **http://192.168.4.1**.
2. **Bật đèn nền.** Kéo slider **Exposure/Gain**: mục tiêu nền **xám đều**, hạt = **bóng đen rõ**.
   - Firmware đã **TẮT AEC / AEC-DSP / AGC** sẵn; giữ **Gain=0**, **Exposure thấp** (mặc định `t100`, `g0`).
3. Chọn **độ phân giải** cao khi chụp phân tích: **SXGA/UXGA** — để hạt nhỏ không biến mất.
4. Ưng ý → bấm **LƯU CỨNG vào flash** (cắm điện lần sau tự chạy đúng thông số).

> Serial (115200): `t<exposure>` `g<gain>` `f<framesize>` (12=SXGA,13=UXGA,17=QXGA) `s`=lưu `x`=chụp 1 frame phân tích.

> ⚠️ **Nếu ảnh mờ ở MỌI exposure** → không phải lỗi phơi sáng mà là **giới hạn lấy nét** ([[camera-focus-limit]]).
> Chuyển sang §9 trước khi đi tiếp.

---

## 7. Đấu điện & trạm bơm (tách rời chống rung)

Sơ đồ đấu dây đầy đủ (chung GND **bắt buộc**) — khớp với
`firmware/aqua_scope_station/aqua_pump.cpp`:

```
   ESP32-CAM AI-Thinker         Module L298N              Bơm RS365 12V
   ────────────────────         ─────────────             ──────────────
   GPIO13        ─────PWM────► ENA  (THÁO jumper!)
   3.3V          ────────────► IN1  (giữ mức HIGH)
   GND           ────────────► IN2  (giữ mức LOW)  → chiều quay cố định
                                OUT1 ──────────────────► cực (+) bơm
                                OUT2 ──────────────────► cực (−) bơm
   Adapter 12V/2A (+) ────────► +12V
   Adapter 12V/2A (−) ────────► GND
   GND ESP32-CAM ═══ CHUNG GND ═══════ GND L298N ═══════ GND adapter

   Tụ gốm 0.1µF     ── hàn NGAY 2 cực motor bơm (sát motor nhất có thể)
   Tụ bulk 470–1000µF ── trên rail 12V (gánh dòng khởi động đỉnh ~2A)
```

> ⚠️ **THÁO JUMPER ENA.** Board L298N xuất xưởng có jumper nhựa nối ENA lên 5V (= bơm luôn chạy full tốc).
> Không rút ra thì PWM vô tác dụng. Rút xong, cắm dây PWM vào trụ phía **gần IN1/IN2**; trụ còn lại bỏ trống.
>
> ⚠️ **Thiếu chung GND = L298N không nhận lệnh** (tín hiệu PWM không có đường về).
>
> ⚠️ **Bơm chạy ngược nước?** Đảo 2 dây OUT1/OUT2, hoặc đổi IN1↔IN2.
>
> Chọn GPIO13 vì camera AI-Thinker đã chiếm GPIO 0, 5, 18, 19, 21, 22, 23, 25, 26, 27, 32, 34–36, 39 (và
> GPIO4 là đèn flash). GPIO13 chỉ trùng HS2_DATA3 của khe thẻ SD — firmware này không dùng khe SD nên rảnh,
> lại không phải chân strapping nên an toàn lúc boot.

**Trình tự gá vào trạm bơm (`print_pump_station.stl`) — đi dây TRƯỚC, đậy nắp SAU:**

1. Đặt bơm **tách rời** khối quang (cách ly rung). Nối ống theo chuỗi ở §8.
2. Hàn **tụ 0.1µF** ngang 2 cực bơm (chống nhiễu chổi than — nếu không, ảnh sẽ nhiễu và ESP32 dễ treo).
3. **Lồng board L298N** vào hộp — board tựa lên 4 gờ góc, *không* cần khớp lỗ vít. Khoang cố ý rộng bất đối
   xứng (8mm hai cạnh có domino vít, 4mm hai cạnh còn lại) để đủ chỗ bẻ dây quanh domino.
4. **Ép thân trụ động cơ RS365 từ TRÊN xuống** vào 2 yên kẹp (khe hẹp hơn Ø lỗ — PETG hơi dẻo, ép nhẹ tay).
   Trước khi ép hẳn, **xoay bơm sao cho 2 chân điện hướng xuống khe nhỏ ở đáy máng kẹp** (hoặc hướng lên khe
   lồng trên đỉnh — cả hai lối đều thông xuống kênh dây). Lòng máng hình trụ nên bơm xoay tự do: **ngạnh ống
   hướng nào cũng lắp được**, không bị chốt cứng một chiều. Nếu lỏng, luồn zip-tie qua rãnh trên đỉnh yên.
5. **Luồn dây động cơ:** từ domino OUT của L298N chui qua khe mức sàn ở cạnh +X của hộp → nằm thẳng vào
   **kênh giấu dây** trong đế → chạy suốt dưới 2 yên kẹp → trồi lên qua khe đáy máng tới chân bơm. Khe OUT
   đặt ngang mặt sàn (không phải ở miệng hộp) để dây đi thẳng, **không phải vòng lên rồi xuống lại** —
   đây chính là nguyên nhân "không tính đủ độ dài dây" ở bản in v1.
6. **Luồn bó dây logic** (ENA/IN1/IN2/GND) qua khe rộng ở cạnh +Y hộp, **vòng qua trụ neo** ngay bên ngoài
   khe một vòng rồi mới đi tự do lên ESP32. Trụ neo chịu lực kéo thay cho chân cắm trên board.
   Bọc đoạn dây hở giữa 2 cụm bằng **ống gen xoắn (spiral wrap)** — biến 4 dây rời thành 1 bó gọn.
7. **Đậy nắp:** ép 2 thanh `print_pump_station_channel_cover.stl` vào gờ ray của kênh dây (ép chặt bằng đàn
   hồi PETG, không vít), rồi bắt `print_pump_station_lid.stl` bằng 2 vít M3 tự-ren. Xong: nhìn từ trên xuống
   không còn thấy dây nào ngoài bó gen xoắn đi lên ESP32.

> ⚠️ Kích thước board L298N (43×43×27mm) và Ø thân bơm (31.5mm) trong model là **ƯỚC TÍNH, CHƯA ĐO hàng
> thật** — nếu lệch nhiều, sửa `l298n_l/w/h` và `pump_motor_od` trong `openscad/constants.scad` rồi in lại
> (không cần sửa gì khác; mọi kích thước hộp/yên/đế đều dẫn xuất từ các hằng số này).
>
> Nắp kênh dây quá lỏng hoặc quá chặt: chỉnh `wire_cover_fit_interference` trong `constants.scad`.

Đường ống (chuỗi nối tiếp, bơm **hút** từ đầu ra):

```
   Nguồn mẫu ─(qua prescreen >5mm)→ Khe VÀO khay ─… khay …─ Cổng RA sát đáy → Bơm RS365 → Thải
```

> **Chạy thử bơm:** nạp `firmware/aqua_scope_station/` (board *AI Thinker ESP32-CAM*, Arduino-ESP32
> core **3.x** — core 2.x không biên dịch được vì dùng API `ledcAttach`). Mở Serial 115200, gõ `?` xem menu.
> Chu trình **không** tự chạy lúc khởi động (an toàn khi đang lắp): gõ `a` để bắt đầu, `0` để dừng khẩn.
> Từ xa thì dùng `curl "http://<ip>/control?var=pump_auto&val=1"` / `&val=0`.
>
> **Dò `fillDuty`:** chạy `a`, nhìn mặt nước lúc FILLING. Còn nghe "ục ục" hoặc thấy xoáy phễu ở miệng xả →
> hạ `d` xuống 5% rồi thử lại. Lấy mức **thấp nhất** mà vẫn đẩy đủ nước trong `fillMs`.
>
> **Bước sau (chưa làm):** để pha SETTLING tự kích chụp ảnh. Hiện firmware chỉ *lộ* pha hiện tại trong
> `GET /device` (`pump.phase`) — script trên PC phải tự đọc trường đó rồi gọi `/capture` đúng lúc.

---

## 8. Chạy thử chu trình Stop-Flow

Chu trình mục tiêu (README): **Bơm ON** (hút nguồn→khay→bơm→thải, đầy tới mức settle) → **Bơm OFF 1–2s**
(van màng tự chặn giữ mực, mặt nước lặng) → **bật đèn nền, chụp ảnh cao (SXGA/UXGA)** → chạy pipeline hybrid
(CV đếm+đo → classifier phân loại) → **tắt đèn, bơm chạy mạnh flush hạt ra cổng RA** → lặp.

Kiểm nghiệm cơ khí (làm thủ công trước khi tự động hoá):
1. **Kiểm kín:** cấp nước, xác nhận không rò ở viền đĩa acrylic và 2 khe dọc.
2. **Kiểm giữ mực:** bơm ON đầy khay → OFF → mực nước **đứng yên** (van bơm tự chặn), không tụt.
3. **Kiểm chống đọng (quan trọng):** thả **~20 hạt** (cả loại nổi PE/PP lẫn chìm PET/PS), chạy **1 flush mạnh**,
   **đếm hạt sót**. Mục tiêu: **0 hạt sót** (sót → dồn sang mẫu sau → sai truy xuất nguồn gốc). Nếu sót ở góc →
   tăng vận tốc flush (~10 cm/s ≈ Q ~1.4 L/min) hoặc kiểm lại fillet/cổng ra.
4. **Kiểm ảnh:** với mực nước ~6mm, lấy nét ở **giữa lớp nước (~3mm)** để hạt nổi + chìm cùng nằm trong DOF.

---

## 9. Xử lý vấn đề lấy nét (nếu §6 cho ảnh mờ)

Theo [[camera-focus-limit]], lens OV2640 của unit thực không nét ở 40mm. Ba hướng (thử theo thứ tự rẻ→tốn):

- **(a) Macro clip-on lens** gắn trước lens hiện tại — rẻ, không phá; thử canh nét ở ~4cm. **Thử đầu tiên.**
- **(b) Đổi cự ly làm việc về ~1–2cm** để khớp điểm nét thật — được độ phân giải cao (~100+px/mm) nhưng **phải
  dựng lại cơ khí** ống/khay ngắn lại (nước sát lens → rủi ro bắn/đọng hơi, cần cửa sổ ép).
- **(c) Thay module autofocus** (vd OV5640 VCM AF 5MP) — cần kiểm tương thích connector XIAO Sense + firmware AF.
  Nếu unit hiện tại **vẫn mờ ngay cả ở ~1cm** sau khi lau sạch → nghi module lỗi, ưu tiên thay.

> Trước khi kết luận "cần đổi phần cứng": bóc màng film bảo vệ lens, lau IPA cả mặt sau lens + kính cảm biến,
> xoay lens hết tầm — đã làm trong test 2026-07-08 nhưng nên xác nhận lại trên unit đang lắp.

---

## 10. Truy xuất nguồn gốc (yêu cầu chức năng, không bỏ)

Bối cảnh QC nước đầu vào nhà máy thực phẩm ([[application-context]]) → **mỗi lần đo phải ghi log**:
**Sample ID + timestamp + số hạt đếm được + phân bố kích thước** (và loại hạt nếu classifier bật), để audit về sau.
Đây là yêu cầu chức năng thật — không chỉ "đếm rồi thôi". Có thể ghi qua Serial/USB hoặc WiFi burst mỗi chu kỳ.

---

## Phụ lục — Thứ tự lắp tóm tắt (checklist)

- [ ] Hoàn thiện bề mặt: lòng ống trên = đen nhám; khoang đèn = trắng mờ; acrylic sạch
- [ ] ESP32-CAM vào base qua `top_cap_esp32cam`, camera úp xuống (§2)
- [ ] Base ↔ ống: 4 vít M3 (§3)
- [ ] *(từ đáy)* Khay → đĩa acrylic + silicon → vòng ép snap-fit (§4)
- [ ] Luồn ống qua 2 khe dọc → đóng nút bịt khe (§4)
- [ ] Màng khuếch tán → module LED vào vách rời → 2 vít M3 ngang ±Y (§5)
- [ ] Prescreen ở cổng vào
- [ ] Nạp firmware → canh phơi sáng → LƯU CỨNG (§6)
- [ ] Đấu L298N (THÁO jumper ENA) + tụ 0.1µF + chung GND + nguồn 12V/2A (§7)
- [ ] Luồn dây vào kênh giấu dây → ép 2 nắp kênh → bắt nắp hộp L298N (§7)
- [ ] Nối ống: nguồn→khay→bơm→thải (§7–§8)
- [ ] Kiểm kín / giữ mực / thả 20 hạt đếm sót / kiểm nét (§8)
```
