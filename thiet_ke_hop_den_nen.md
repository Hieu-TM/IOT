# Thiết kế Hộp đèn nền (Light Box) — Aqua Scope

Tài liệu này chốt thiết kế **hộp đèn nền backlit** của trạm Aqua Scope và ghi lại các
quyết định + câu hỏi còn treo. Nguồn ràng buộc gốc: `CLAUDE.md`, `README.md`.

## Sơ đồ

### Tổng quan bộ mô hình
![Sơ đồ tổng quan](so_do/aqua_scope_tong_quan.svg)

Ngăn xếp từ trên xuống: **Nắp trên + Camera** (XIAO ESP32-S3 Sense, tái dùng base
Matchboxscope, camera hướng xuống) → **Ống ảnh** đen mờ, cố định ~40mm tới mặt nước →
**Khay Macro-Flow** (đáy trong, weir giữ mực, lưới thô >5mm) → **Hộp đèn nền** (LED xuôi,
màng khuếch tán) → **Van xả đáy**. **Trạm bơm tách rời**, hút phía sạch để cách rung.

### Chi tiết hộp đèn nền
![Sơ đồ chi tiết hộp đèn nền](so_do/hop_den_nen_chi_tiet.svg)

## Nguyên lý chiếu sáng

**Backlit silhouette** (KHÔNG UV, KHÔNG darkfield xiên): một **module LED trắng khuếch
tán đặt DƯỚI khay, chiếu thẳng lên**; hạt rác hiện thành **bóng đen trên nền sáng đều**.

- **"LED xuôi"**: module xoay để **đầu LED hướng thẳng lên** khay/camera (khác hướng "ngược"
  của ý tưởng trước). Lý do đổi: kết quả test trước với nhựa hơi đục/có chữ, khuếch tán bằng
  lớp giấy, cho kết quả tạm chấp nhận; môi trường thực nghiệm (nước cấp cho nhà máy) sạch và
  ổn định hơn nên nguồn xuôi là đủ.
- Ánh sáng **phải được khuếch tán** thành nền xám đều — không hotspot, camera không được thấy
  bóng LED trần.
- **Phơi sáng thủ công bắt buộc**: firmware **TẮT AEC, AEC-DSP, AGC**, đặt **Gain=0** và
  **phơi sáng thấp** (serial `t<exposure>`, `g<gain>`). Nếu để AEC/AGC bật, cảm biến ghi đè và
  nền cháy trắng.
- **Chụp phân tích ở độ phân giải cao (SXGA/UXGA)** kẻo hạt nhỏ biến mất.

## Nguồn sáng: dùng đúng module LED trong ảnh

- Coi **cả module móc khoá làm "1 bóng"** (1 đơn vị sáng), KHÔNG dùng dải 3 LED.
- Kích thước module: **37.5 × 10 × 16 mm**, thân trong có LED ở đầu + **3 pin cúc**.
- Đặt **dựng đứng, đầu LED hướng lên** (LED nằm ở đầu mũi) → nửa pin nằm phía dưới.
- **Cắm-tháo được, giữ bằng ma sát, không keo** để dễ thay bóng/pin.

## Kết cấu cơ khí (theo phác thảo của người dùng)

- **Vách đỡ ("nắp") nằm GIỮA thân ống** (không phải nắp đáy), là tấm ngang giữ module.
- **Ốc M3 bắt NGANG, xuyên qua thành ống vào mép vách** ở 2 bên → tháo ốc là gỡ được
  vách + module.
- **Module xỏ qua lỗ giữa vách**, đầu LED hướng lên buồng trộn; nửa pin nằm dưới vách.
- **Ống chạy thẳng suốt**; **phần thân kéo dài xuống dưới** bọc kín nửa pin và **chính đáy
  ống làm chân đế** để mô hình đứng vững.
- Phía trên module: **buồng trộn ~8mm** rồi **màng khuếch tán xếp lớp** (thêm/bớt lớp để chỉnh
  độ tán), trên cùng là **kính đáy khay** đặt trên gờ đỡ.

## Bảng thông số (dự kiến — chờ chốt để dựng OpenSCAD)

| Bộ phận | Giá trị | Ghi chú |
|---|---|---|
| Thân trụ (ống) | OD ~50mm · ID ~46mm · vách ~2mm | Khớp footprint base Matchboxscope |
| Vùng nước được chụp | ~40mm | Lấp đầy khung hình |
| Khoảng cách camera–nước | ~40mm | Cố định bởi ống ảnh (đã đo trên phần cứng) |
| Gờ đỡ kính đáy khay | shelf 1.5–2mm | Đặt kính lên |
| Màng khuếch tán | 0–4mm, xếp lớp, có nẹp giữ | Giấy can / mica mờ |
| Buồng trộn (mũi LED → màng) | ~8mm | Khử hotspot nguồn điểm |
| Module LED | 37.5 × 10 × 16mm, dựng đứng | Đầu LED lên |
| Lỗ giữa vách đỡ | tiết diện module +0.4mm | Fit ma sát (chờ chốt dung sai) |
| Ốc bắt vách | M3, xuyên ngang thành ống | Tháo được |

## Câu hỏi còn treo — ✅ ĐÃ CHỐT 2026-07-07 (khi build OpenSCAD)

1. ~~**Chiều lắp module**~~ → cắm module vào vách RỜI **trước**, rồi đưa cả cụm vào ống từ đáy
   và bắt ốc — chiều lắp không còn là ràng buộc; lỗ vách không cần gờ chặn (giữ ma sát +0.4).
2. ~~**Vách đỡ liền hay rời**~~ → **MIẾNG RỜI** (G5): thành ống chỉ có 2 lỗ M3 ngang tại **±Y**
   (tránh 2 khe dọc ±X của ngạnh ống nước); tháo 2 ốc là gỡ cả vách + module.
3. ~~**Dung sai lỗ**~~ → **+0.4mm** mặc định (`fit_clr` trong `openscad/constants.scad` — chỉnh theo máy in).

> Đã hiện thực trong `openscad/components/light_box_001.scad` (vỏ dưới + vách + cột đỡ màng +
> nút bịt khe) — vỏ là **1 ống liền suốt** (G2), vành đáy làm chân đế, hở giữa để thay pin.

## Ràng buộc "3 KHÔNG" liên quan

- Không sửa lens (giữ lens gốc, nét ở 3–5cm).
- Không dùng chip vi lỏng kín → khay hở, mực nước cố định bằng weir; kính đáy đặt cố định
  trên gờ (KHÔNG dùng kính thả nổi — kính chìm).
- Không can thiệp thủ công → bơm/đèn/chụp/đếm/xả tự động (chu trình Stop-Flow).

## Bước tiếp theo

Sau khi chốt 3 câu hỏi trên → dựng file OpenSCAD tham số cho hộp đèn nền (thân ống, gờ kính,
khe màng khuếch tán, vách đỡ có lỗ module + lỗ ren M3, thân kéo dài làm chân đế) qua skill
`/openscad`.
