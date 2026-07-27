# Thiết kế: Bộ thu thập dataset ESP32-CAM

**Ngày:** 2026-07-19
**Trạng thái:** đã triển khai (`dataset_collector/`)

## 1. Mục tiêu

Có một cách lặp lại được để **chụp ảnh backlit trên ESP32-CAM và kéo về laptop**
làm dataset huấn luyện detector. Kèm chức năng web-cam để canh sáng bằng mắt.

Phần cứng: **ESP32-CAM AI-Thinker (OV2640)** — biến thể `cam_variant=1` trong
`openscad/`, lắp qua cùng interface 4×M3 30×30 với bản XIAO.

## 2. Kiến trúc

Hai thành phần, ranh giới cứng:

| Thành phần | Trách nhiệm | Không làm |
|---|---|---|
| `dataset_collector/firmware/` | phục vụ ảnh qua HTTP (`/`, `/stream`, `/capture`, `/control`) | không đặt tên file, không lưu trữ, không biết "dataset" là gì |
| `dataset_collector/collect_dataset.py` | burst, đặt tên, retry, ghi đĩa | không chỉnh camera |

**Hệ quả có chủ đích:** thay đổi cách thu dataset (số lượng, nhịp, thư mục,
lọc ảnh) không cần nạp lại firmware. Đây là lý do chính chọn hướng
**laptop-kéo** thay vì ESP32-đẩy.

Luồng: `collect_dataset.py --count N` → lặp N lần `GET /capture` → kiểm tra
JPEG hợp lệ → ghi `web/backend/data/dataset/YYYYmmdd-HHMMSS-mmm.jpg`.

## 3. Quyết định & đánh đổi

### 3.1 Laptop kéo, không phải ESP32 đẩy
Firmware giữ được sự đơn giản (là bản stock + 3 sửa nhỏ). Đổi lại: phải biết IP
của board, và không tự chụp khi không có laptop. Chấp nhận được — thu dataset
vốn là hoạt động có người ngồi cạnh.

### 3.2 Thư mục mới `data/dataset/`, KHÔNG dùng `data/images/`
Yêu cầu ban đầu là ghi vào `data/images/`. Đã đổi vì thư mục đó có bất biến:
mỗi file khớp đúng một dòng `Sample` trong DB, tên cứng `{sample_code}.jpg`
(`web/backend/app/routers/ingest.py`). Ảnh thô ở đó sẽ là **file mồ côi** —
web không hiển thị, lại lẫn với `MOCK-*.jpg` của `mock_sender.py`.

`data/dataset/` vẫn nằm trong khu `data` của web (đúng tinh thần yêu cầu) nhưng
không phá mô hình dữ liệu. Có test khóa quyết định này lại
(`test_main_does_not_default_to_the_web_sample_images_dir`).

**Rủi ro đã biết:** `web/backend/data/` bị git-ignore → dataset không được version.
Chấp nhận (không nên commit hàng trăm JPEG), nhưng đã ghi cảnh báo trong README.

### 3.3 Thư mục riêng ở gốc repo, không nằm trong `firmware/`
`firmware/` đang chứa 3 bản web-cam thông thường. Bộ này là **công cụ hoàn chỉnh
gồm cả hai nửa** (board + laptop), để lẫn vào đó sẽ mất ranh giới đó.

### 3.4 Firmware = bản stock Espressif + 3 sửa
Bản `CameraWebServer` của Espressif đã có sẵn mọi endpoint cần thiết. Viết lại
từ đầu là phí. Ba điểm sửa:

1. **Ép mặc định backlit** (`aqua_prefs.cpp`): tắt AEC / AEC-DSP / AGC, gain 0,
   exposure 100, contrast +1. Bản gốc để auto → nền cháy trắng, nuốt mất hạt.
   Thứ tự quan trọng: phải tắt vòng tự động **trước** khi đặt giá trị thủ công.
2. **Mặc định UXGA** thay vì QVGA. OV2640 tối đa UXGA 1600×1200 — kém OV3660
   (QXGA) trên bản XIAO; đây là giới hạn phần cứng cần biết khi đo hạt <2mm.
3. **Lưu cấu hình vào flash** (NVS) + `?var=save` / `?var=reset`. Không có nó thì
   mỗi lần mất điện phải canh sáng lại từ đầu.

Sửa thêm ngoài kế hoạch: **WiFi không treo vô hạn** — bản gốc lặp `while` mãi mãi
khi sai mật khẩu; bản này hết 20s là báo lỗi rõ ràng.

### 3.5 Không gắn nhãn, không manifest
Ảnh lưu phẳng theo timestamp. Gắn nhãn sau bằng công cụ riêng (Roboflow).

## 4. Kiểm thử

`dataset_collector/tests/` — 20 test, dựng **HTTP server thật trên localhost**
làm ESP32-CAM giả thay vì mock `requests`. Lý do: các kiểu hỏng cần bắt đều nằm
ở tầng giao thức/dữ liệu, mock sẽ bỏ lọt:

- body cụt (board sập giữa lúc truyền) — có SOI, thiếu EOI
- **trả HTML kèm HTTP 200** — hỏng âm thầm, nguy hiểm nhất
- timeout, host không tồn tại, HTTP 500
- retry rồi thành công; 1 ảnh hỏng không được làm dừng cả phiên
- trùng tên do 2 ảnh trong cùng mili giây → không bao giờ ghi đè
- JPEG có đệm `\x00` sau EOI vẫn phải được **chấp nhận** (loại nhầm ảnh thật còn
  tệ hơn lọt ảnh hỏng)

**Bug thật tìm được lúc chạy:** console Windows mặc định cp1252 không mã hóa được
tiếng Việt → script crash ngay dòng in đầu tiên. `capsys` của pytest không bắt
được vì không đi qua encoding của console. Đã fix (`_force_utf8_output()`) và
khóa lại bằng test chạy tiến trình con với `PYTHONIOENCODING=cp1252`.

Firmware: compile sạch bằng `arduino-cli` với
`esp32:esp32:esp32cam:PartitionScheme=huge_app` (34% flash, 21% RAM).
**Chưa test trên phần cứng thật** — cần board để xác nhận.

## 5. Việc còn lại

- Nạp lên board thật, xác nhận `/capture` và `save` vào flash hoạt động.
- Đo thực nghiệm `--interval` tối thiểu trước khi board brownout.
- Chưa quyết định: có mount `/dataset` để xem ảnh trên web hay không (1 dòng
  trong `main.py`, làm khi thực sự cần).
