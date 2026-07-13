# Hướng Dẫn Lắp Ráp & Hoàn Thiện — Aqua Scope

> Tutorial thực thi: từ các chi tiết đã in/đã mua → lắp thành trạm hoàn chỉnh → nạp firmware →
> canh sáng → chạy thử chu trình Stop-Flow. Bám sát kiến trúc **lắp-từ-đáy** (`plan.md` §2, §8),
> quyết định điện **module relay** ([[pump-drive-decision]]) và firmware OV3660 (`firmware/`).
>
> ⚠️ **Đọc trước — 2 vấn đề mở phải biết:**
> 1. **Lấy nét:** test 2026-07-08 cho thấy lens OV3660 của unit thực **KHÔNG nét ở 40mm** — chỉ nét mờ ~1cm
>    ([[camera-focus-limit]]). Hướng dẫn này dựng đúng cơ khí baseline, nhưng **bước 6 (canh nét) có thể thất bại**;
>    xem §9 để xử lý (macro clip-on / đổi cự ly / đổi module AF).
> 2. **Điều khiển bơm:** firmware hiện tại **chưa** có mã bật/tắt bơm (mục duty-cycle mới là prototype trong
>    `firmware/.../README.md`). Ở bản demo này bơm được điều khiển **thủ công / mạch relay rời**; §7 nêu cách đấu sẵn sàng cho bước tự động hoá sau.

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

> **Cài đặt in gợi ý:** layer 0.2mm, infill ≥30%, vật liệu PETG (kháng nước tốt hơn PLA). Vỏ housing là chi
> tiết cao nhất (~108mm) — kiểm giường in đủ cao.

### B. Chi tiết KHÔNG in (mua/cắt/tái dùng)

| Món | Thông số | Nguồn |
|---|---|---|
| **Nắp trụ** = base Matchboxscope | `base/...base_xiao_9.stl` **đã in sẵn**, tái dùng nguyên bản | Đã có |
| Đĩa acrylic đáy (cửa sổ trong) | **Ø42 × 3mm**, acrylic ĐÚC (cast), trong | Cắt laser |
| Màng khuếch tán | Ø~42, mica mờ / giấy can — **1–3 lớp xếp chồng** | Cắt |
| Module LED móc khoá | **37.5×10×16mm**, đầu LED hướng lên, cắm ma sát | Mua sẵn |
| XIAO ESP32-S3 Sense | Cảm biến **OV3660** 3MP ([[camera-sensor]]) | Mua sẵn |
| Bơm màng **RS365 12V** | Tự mồi, bbox ~90×40×35, ngạnh Ø8 | Mua sẵn |
| Ống silicone | **ID≈8 / OD≈11mm** | Mua sẵn |

### C. Điện (BOM tối thiểu chạy được — [[pump-drive-decision]])

- **Module relay 1 kênh có opto** (cách ly quang) — mặc định điều khiển bơm (đấu qua tiếp điểm **NO**).
- **Adapter 12V/2A** (dư cho inrush RS365 vọt 2–3A lúc khởi động).
- **Jack DC cái → terminal vặn vít** (rẽ nguồn không cần hàn).
- **Tụ gốm 0.1µF** hàn ngang 2 cực bơm (BẮT BUỘC — dập nhiễu chổi than để ảnh sạch).
- (Khuyến nghị) **Tụ bulk 470–1000µF** trên rail 12V (bù inrush, chống sụt áp → chống brownout ESP32).
- Cáp USB-C (nạp + nuôi ESP32 5V riêng), dây nối, **chung GND bắt buộc**.

> **Chỉ cần PWM chỉnh lưu lượng** mới đổi sang MOSFET **IRLZ44N** (logic-level) + **diode flyback 1N4007** +
> gate 220Ω + kéo xuống 10k. Demo bật/tắt thì relay là đủ và an toàn hơn.

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
2. Mở `firmware/aqua_scope_cam/aqua_scope_cam.ino` (giữ `camera_pins.h` cùng thư mục).
3. Tools: Board **XIAO_ESP32S3** · **PSRAM: OPI PSRAM** (bắt buộc) · Partition **Huge APP (3MB No OTA/1MB SPIFFS)**.
4. Cắm USB-C → chọn Port → **Upload**. Lỗi upload thì giữ nút **BOOT** khi cắm.

### 6.2 Canh phơi sáng thủ công (qua WiFi — khuyến nghị)
1. Board phát WiFi **`AquaScope`** (mật khẩu `aquascope`) → nối điện thoại/laptop → mở **http://192.168.4.1**.
2. **Bật đèn nền.** Kéo slider **Exposure/Gain**: mục tiêu nền **xám đều**, hạt = **bóng đen rõ**.
   - Firmware đã **TẮT AEC / AEC-DSP / AGC** sẵn; giữ **Gain=0**, **Exposure thấp** (mặc định `t100`, `g0`).
3. Chọn **độ phân giải** cao khi chụp phân tích: **SXGA/UXGA** (thậm chí QXGA của OV3660) — để hạt nhỏ không biến mất.
4. Ưng ý → bấm **LƯU CỨNG vào flash** (cắm điện lần sau tự chạy đúng thông số).

> Serial (115200): `t<exposure>` `g<gain>` `f<framesize>` (12=SXGA,13=UXGA,17=QXGA) `s`=lưu `x`=chụp 1 frame phân tích.

> ⚠️ **Nếu ảnh mờ ở MỌI exposure** → không phải lỗi phơi sáng mà là **giới hạn lấy nét** ([[camera-focus-limit]]).
> Chuyển sang §9 trước khi đi tiếp.

---

## 7. Đấu điện & trạm bơm (tách rời chống rung)

Sơ đồ nguồn (chung GND bắt buộc):

```
   Adapter 12V/2A ──► Jack DC→terminal ──┬──► [+] Bơm RS365 [−] ──► relay NO ──► GND
                                          └──► (khuyến nghị) tụ bulk 470–1000µF ‖ rail 12V
   ESP32-S3  ── USB-C 5V (nguồn riêng) ── GPIO điều khiển ──► IN của relay
   GND adapter ═══════ chung ═══════ GND ESP32     (BẮT BUỘC)
   Tụ gốm 0.1µF ── hàn NGAY 2 cực motor bơm (sát motor nhất có thể)
```

Đấu dây:
1. Bơm qua tiếp điểm **NO** của relay (mặc định TẮT khi chưa cấp tín hiệu).
2. Coil relay ăn **5V**, IN nối 1 GPIO trống của XIAO. Nhiều relay **active-low** → trong `setup()` phải **set GPIO
   về mức TẮT ngay** trước khi cấu hình, tránh bơm tự chạy lúc boot (GPIO thả nổi).
3. Hàn **tụ 0.1µF** ngang 2 cực bơm (chống nhiễu chổi than — nếu không ảnh sẽ nhiễu và ESP32 dễ treo).
4. Đặt bơm **tách rời** khối quang (cách ly rung). Nối ống theo chuỗi ở §8.

Đường ống (chuỗi nối tiếp, bơm **hút** từ đầu ra):

```
   Nguồn mẫu ─(qua prescreen >5mm)→ Khe VÀO khay ─… khay …─ Cổng RA sát đáy → Bơm RS365 → Thải
```

> **Điều khiển tự động (bước sau):** firmware hiện chưa bật/tắt bơm. Khi triển khai máy trạng thái Stop-Flow
> (prototype trong `firmware/.../README.md`), thêm `pinMode(PUMP,OUTPUT); digitalWrite(PUMP,TẮT);` đầu `setup()`
> và điều khiển theo pha FILLING/SETTLING/DRAINING. Trước đó có thể bật/tắt relay bằng tay để thử cơ khí.

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

Theo [[camera-focus-limit]], lens OV3660 của unit thực không nét ở 40mm. Ba hướng (thử theo thứ tự rẻ→tốn):

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
- [ ] XIAO vào base, camera úp xuống (§2)
- [ ] Base ↔ ống: 4 vít M3 (§3)
- [ ] *(từ đáy)* Khay → đĩa acrylic + silicon → vòng ép snap-fit (§4)
- [ ] Luồn ống qua 2 khe dọc → đóng nút bịt khe (§4)
- [ ] Màng khuếch tán → module LED vào vách rời → 2 vít M3 ngang ±Y (§5)
- [ ] Prescreen ở cổng vào
- [ ] Nạp firmware → canh phơi sáng → LƯU CỨNG (§6)
- [ ] Đấu relay + tụ 0.1µF + chung GND + nguồn 12V/2A (§7)
- [ ] Nối ống: nguồn→khay→bơm→thải (§7–§8)
- [ ] Kiểm kín / giữ mực / thả 20 hạt đếm sót / kiểm nét (§8)
```
