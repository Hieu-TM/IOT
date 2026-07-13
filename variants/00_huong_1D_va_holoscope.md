# Biến thể: Hướng cảm biến 1D + Holography

> Thư mục `variants/` chứa các hướng thiết kế *thay thế* (không thay thế baseline Aqua Scope
> camera-silhouette hiện tại trong `openscad/` + `README.md`). File này là ghi chú nghiên cứu,
> **chưa phải quyết định chốt**.

## Nguồn tham khảo

1. **Bài 1D (ĐỌC ĐƯỢC):** Cerioli et al., *"Efficient Detection of Microplastics on Edge Devices
   With Tailored Compiler for TinyML Applications"*, IEEE Access, vol.13, 2025.
   File: `../Efficient_Detection_of_Microplastics_on_Edge_Devices_With_Tailored_Compiler_for_TinyML_Applications.pdf`
   Code: https://github.com/alecerio/microplastic

2. **ESPressoscope / holoscope (ĐÃ CÓ NGUỒN ĐÚNG — cập nhật 2026-07-12):** file
   `../ESpressoscope.pdf` giờ LÀ bài đúng: Ethan Li, V. Saggiomo, W. Ouyang, M. Prakash,
   B. Diederich, *"ESPressoscope: A small and powerful approach for in situ microscopy"*,
   PLOS ONE 19(10) e0306654, 2024. (Ghi chú "đặt sai tên" trước đây ĐÃ LỖI THỜI.)
   - "Holoscope" = cấu hình **HoloESP** trong bài này.
   - **HoloESP thực chất:** kính hiển vi **holography nội tuyến KHÔNG THẤU KÍNH (lensless
     inline / Gabor)**. LƯU Ý: nó **vẫn dùng cảm biến ảnh** ESP32-CAM, chỉ **tháo lens**, nhỏ
     giọt mẫu lên lamella áp thẳng mặt sensor. "Không dùng camera" là nói chưa chuẩn — đúng hơn:
     **sensor trần, bỏ thấu kính.**
   - Chiếu sáng: LED băng hẹp **450nm ±20nm**, cách mẫu **~80mm**, lọc không gian bằng **đầu phun
     máy in 3D (pinhole 0.1mm)** → nguồn điểm, sóng cầu bán-kết-hợp → hologram.
   - Tái dựng: **backpropagation số** (refocus bằng phần mềm) chạy bằng **PyScript trên trình
     duyệt của một PC**, **KHÔNG chạy on-device ESP32**. → điểm yếu cho câu chuyện "TinyML on-edge".
   - Lợi ích: chụp "2.5D", **lấy nét lại bằng phần mềm sau khi chụp** → giải đúng blocker
     `camera-focus-limit`.

## Bài 1D thực chất làm gì

- **Cảm biến:** optofluidic light-scattering — chùm sáng hẹp qua dòng chảy, **photodiode** đọc
  tín hiệu theo thời gian. KHÔNG camera, KHÔNG lens, KHÔNG ảnh 2D.
- **Dữ liệu:** mỗi hạt đi qua = 1 xung Gaussian, **41 mẫu/tín hiệu**.
- **Bài toán:** phân loại nhị phân — có hạt (1) / không (0).
- **Model:** MLP 1 lớp 8 neuron, hoặc GRU hidden 8. PTQ int8. Accuracy ~0.985–0.991.
- **Đóng góp CHÍNH:** compiler **NeuralCasting** (ONNX → C thuần, không cần inference engine).
  Latency trên ESP32-PICO-D4 (M5StickC): MLP ~63.5µs, GRU ~255µs. RAM/Flash cực nhỏ.
- **⚠️ Quan trọng:** dataset là **SYNTHETIC** (mô phỏng theo Sasso 2024, ref [35]). Bài KHÔNG
  dựng phần cứng cảm biến. Muốn theo hướng này phải **tự dựng sensor quang 1D thật**.

## Vì sao hướng 1D hấp dẫn cho project này

- **Né đúng blocker hiện tại:** memory `camera-focus-limit` — lens OV3660 không nét ở 3–5cm.
  Photodiode 1D không cần lấy nét → xoá vấn đề.
- Nhẹ RAM/Flash, hợp ESP32-S3, chạy liên tục tốc độ cao.

## Vì sao phải cân nhắc (đánh đổi)

- Mất **ảnh từng hạt** và **phân bố size chi tiết** (chỉ suy size thô từ biên độ/độ rộng xung).
- Mà "phân bố size + truy xuất nguồn gốc" là functional requirement của use case nhà máy thực
  phẩm (memory `application-context`).

## ~~Ý tưởng kết hợp 1D + Holography (dual-modality)~~ — ĐÃ BỎ (2026-07-12)

> Người dùng quyết định **KHÔNG kết hợp** với holography (vì holo không khớp kiến trúc dòng chảy hở
> + tái dựng nặng). Biến thể **tách riêng, thuần 1D, phục vụ duy nhất module NeuralCasting.** Phần
> dưới đây giữ lại làm lịch sử, không còn là hướng đang theo.

Không phải "trộn quang học" mà là **cảm biến kép**, mỗi kênh làm việc nó giỏi:

- **Kênh A — Quang 1D (photodiode):** cổng đếm nhanh + trigger. Đếm hạt + size thô, MLP 8-neuron.
- **Kênh B — Holography (sensor trần, không lens):** khi kênh A báo xung đáng ngờ → trigger chụp
  1 hologram → tái dựng → hình thái + phân loại loại hạt. Giải quyết lấy nét bằng phần mềm.
- Khớp chu trình **Stop-Flow**: 1D chạy khi bơm ON, holography chụp khi bơm OFF.

### Rủi ro cần ghi nhớ
1. Cả hai kênh đều là phần cứng CHƯA có sẵn (1D chỉ mô phỏng; holoscope chưa có nguồn).
2. NeuralCasting chỉ compile được model nhỏ (MLP/GRU). Tái dựng hologram KHÔNG phải NN nhỏ →
   không dùng NeuralCasting, nặng hơn nhiều bậc, có thể phải offload.
3. Phải trả lời được: biến thể này HƠN gì so với camera baseline? → Điểm bán được: né blocker lấy
   nét + đếm liên tục tốc độ cao (không phải "nhiều cảm biến cho oai").

## QUYẾT ĐỊNH (2026-07-12)

Người dùng chốt: **đi hướng A — CHỈ 1D (photodiode scatter), KHÔNG holography.**
Deliverable yêu cầu: **đếm + phân bố size + phân loại.**
→ Kế hoạch chi tiết + cách hoà giải deliverable với giới hạn 1D: xem
[`01_bien_the_1D_ke_hoach.md`](01_bien_the_1D_ke_hoach.md).

Holography (HoloESP) **tạm gác** — giữ mô tả ở trên làm tham khảo nếu sau này cần kênh ảnh.

## TODO (đã xử lý)
- [x] Bổ sung đúng bài ESPressoscope/holoscope — đã có, xem mục Nguồn #2.
- [x] Làm rõ "holoscope không dùng camera" — lensless nhưng VẪN dùng image sensor, bỏ lens.
- [x] Xác định deliverable — đếm + phân bố size + phân loại (holo gác lại).
