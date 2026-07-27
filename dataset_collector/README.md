# Aqua Scope — Bộ thu thập dataset (ESP32-CAM)

Firmware + script để **chụp ảnh trên ESP32-CAM và kéo về laptop** làm dataset huấn luyện.

Tách riêng khỏi `firmware/` (nơi chứa 3 bản web-cam thông thường) vì đây là một
công cụ hoàn chỉnh gồm cả hai nửa: phần chạy trên board và phần chạy trên máy.

```
dataset_collector/
├── firmware/            ← nạp vào ESP32-CAM AI-Thinker
│   ├── firmware.ino         bản esp32-cam-webserver, đã cắt OTA/mDNS/NTP/portal
│   ├── app_httpd.cpp        web server — GIỮ NGUYÊN, không sửa dòng nào
│   ├── index_ov2640.h       web UI + khối "thu dataset" thêm vào
│   ├── index_ov3660.h       bản UI cho sensor OV3660 (giữ đồng bộ với trên)
│   ├── storage.{h,cpp}      lưu cấu hình camera vào SPIFFS
│   └── myconfig.h  camera_pins.h  css.h  index_other.h  src/
├── collect_dataset.py   ← chạy trên laptop: nhận ảnh (--serve) hoặc kéo ảnh
└── tests/               ← 38 test
```

## Phân chia trách nhiệm

| | Firmware | Trình duyệt | `collect_dataset.py` |
|---|---|---|---|
| Làm gì | phục vụ ảnh qua HTTP | cầu nối: lấy `/capture` rồi đẩy sang PC | ghi file vào dataset |
| Không làm gì | không biết dataset, không biết địa chỉ PC | không lưu gì | không chỉnh camera |

Firmware không mang HTTP client và không cần biết địa chỉ laptop — **toàn bộ việc
nối hai đầu nằm trong đoạn JS của trang web**. Nhờ vậy đổi cách thu dataset không
phải nạp lại firmware.

---

## Bước 1 — Nạp firmware

`dataset_collector/firmware/` là **bản sao của `firmware/esp32-cam-webserver/`**
(bản port easytarget đã sửa cho core 3.x + nút Dark), đã cắt bớt và thêm phần thu
dataset. Chọn bản này vì nó chạy **XCLK 8MHz** thay vì 20MHz — đó là nguyên nhân
của ảnh sọc/ám xanh trên các bản dựng từ ví dụ stock của Espressif.

Arduino IDE, gói board **esp32 by Espressif ≥ 3.0**:

| Mục | Chọn |
|---|---|
| Board | **AI Thinker ESP32-CAM** |
| Partition Scheme | **Huge APP (3MB No OTA/1MB SPIFFS)** |

WiFi sửa trong `myconfig.h`. Nạp: nối **IO0 → GND**, cấp nguồn, Upload, rút IO0, reset.

## Bước 2 — Canh sáng (một lần)

Mở `http://<IP>/` → bấm **Dark** (áp preset silhouette backlit) → chỉnh slider tới
khi **nền xám đều, hạt = bóng đen rõ**, không có đốm chói.

Vẫn còn sọc/ám màu? Hạ **xclk** trong Settings (8 → 6 → 4 MHz). Ảnh chậm hơn chút
nhưng sạch hơn — với Stop-Flow thì không ảnh hưởng gì.

Chỉnh xong bấm **Save** để ghi vào SPIFFS, lần sau cắm điện là đúng luôn.

## Bước 3 — Thu dataset

**Cách 1 — bấm nút ngay trên web (tiện nhất khi ngồi cạnh máy):**

```bash
python collect_dataset.py --serve          # để cửa sổ này chạy
```
Script in ra địa chỉ dạng `192.168.1.20:8765`. Điền vào ô **Dataset PC** trong
Settings của web UI (trình duyệt nhớ giúp, chỉ nhập 1 lần), đặt **Burst** = số ảnh
mỗi lần bấm, rồi bấm nút **💾 Dataset**. Trạng thái hiện ngay cạnh nút.

**Cách 2 — laptop kéo hàng loạt (khi cần số lượng lớn, không cần ngồi canh):**

```bash
python collect_dataset.py --host 192.168.1.50 --count 200 --interval 1.5
```

Ảnh lưu vào **`web/backend/data/dataset/`**, tên `YYYYmmdd-HHMMSS-mmm.jpg`.

| Tham số | Mặc định | |
|---|---|---|
| `--host` | *bắt buộc* | IP lấy từ Serial Monitor |
| `--count` | 1 | số ảnh |
| `--interval` | 1.5 | giây nghỉ giữa 2 ảnh |
| `--out` | `web/backend/data/dataset` | thư mục lưu |
| `--timeout` | 15 | timeout mỗi request |
| `--retries` | 3 | số lần thử lại mỗi ảnh |

Ctrl+C dừng giữa chừng — ảnh đã lưu vẫn còn nguyên.

---

## Vì sao lưu ở `data/dataset/` chứ không phải `data/images/`

`web/backend/data/images/` là kho ảnh **của các Sample trong DB**: mỗi file khớp
đúng một dòng, tên cứng `{sample_code}.jpg`
([ingest.py](../web/backend/app/routers/ingest.py)). Đổ ảnh thô vào đó sẽ tạo
file mồ côi — web không hiển thị được, lại lẫn với ảnh `MOCK-*` của
`mock_sender.py`. `data/dataset/` nằm cùng khu `data` nhưng không đụng vào mô
hình dữ liệu của web.

> **Lưu ý:** toàn bộ `web/backend/data/` bị **git-ignore**. Với dataset thì hợp lý
> (không nên commit hàng trăm JPEG), nhưng nghĩa là **xóa thư mục là mất trắng** —
> git không cứu được. Tự backup nếu dataset đã tốn công thu.

## Khác gì `firmware/esp32-cam-webserver/`

Toàn bộ đường camera (`StartCamera()`, `app_httpd.cpp`, prefs SPIFFS, cả 3 file
giao diện) **giữ nguyên không sửa** — đó là lý do chọn bản này. Chỉ có 2 thay đổi:

**1. Cắt 4 thư viện mạng:** OTA, mDNS, NTP, captive portal + DNSServer. Không cái
nào đụng vào camera, nhưng mỗi cái chạy task nền ăn heap — thứ ESP32-CAM vốn đã
thiếu khi chụp UXGA. Đo được: **41% → 39% flash, 75.9KB → 69.7KB RAM tĩnh.**

Các biến cờ (`otaEnabled`, `haveTime`, `captivePortal`) được giữ lại và đặt cứng
`false` vì `app_httpd.cpp` tham chiếu tới chúng — nhờ vậy file đó không phải sửa
một dòng nào.

**2. Thêm khối thu dataset vào web UI:** nút **💾 Dataset**, ô **Dataset PC**, ô
**Burst**, và dòng trạng thái. Thêm vào **cả** `index_ov2640.h` lẫn
`index_ov3660.h` — giao diện được chọn theo sensor lúc chạy, chỉ thêm một file thì
gặp board sensor khác là mất nút mà compile vẫn sạch.

## Ảnh trắng xóa / hỏng → chạy `diagnose.py` trước

```bash
python diagnose.py --host 192.168.1.50
```

Nó tắt đèn GPIO4 + mọi chế độ tự động, rồi **quét exposure từ 0 đến 1200** và đo
độ sáng từng ảnh. Kết quả trả lời dứt điểm một câu hỏi:

| Kết quả | Nghĩa là |
|---|---|
| Ảnh tối dần khi giảm exposure | Phần cứng bình thường, chỉ là canh sáng. Công cụ in luôn mức exposure nên dùng. |
| **Trắng ở mọi mức exposure** | Cảm biến không phản ứng. Chỉnh thông số vô ích → soi ánh sáng lọt vào, cáp ribbon, module. |

Đừng đoán mò khi ảnh trắng — hai trường hợp trên nhìn giống hệt nhau nhưng cách
sửa ngược nhau hoàn toàn.

**Nghi phạm số 1 khi trắng ở cả stream lẫn capture:** đèn flood **GPIO4** ngay
cạnh ống kính. `app_httpd.cpp` bật nó cho cả hai đường khi `lamp` ≠ 0 hoặc
`autolamp` bật. Trong ống chụp kín, nó bật là trắng xóa. Giữ **Light = 0**.

## Trục trặc khác

| Hiện tượng | Nguyên nhân thường gặp |
|---|---|
| **Ảnh sọc ngang / ám xanh lục** | XCLK quá cao. Hạ `xclk` trong Settings: 8 → 6 → 4 MHz. |
| Ảnh lỗi liên tục, board reset | **Brownout**: WiFi TX + chụp UXGA cùng lúc. Giảm Burst, tăng `--interval`, dùng nguồn 5V ≥ 2A. |
| Nền trắng xóa, không thấy hạt | Chưa bấm **Dark**, hoặc chỉnh xong quên bấm **Save**. |
| Bấm Dataset → `khong ket noi duoc ...` | Chưa chạy `collect_dataset.py --serve`, hoặc nhập sai IP/cổng, hoặc Windows Firewall chặn cổng 8765. |
| Bấm Dataset → `PC tu choi (HTTP 400)` | Ảnh tới nơi bị hỏng (thường do brownout giữa lúc truyền). Ảnh hỏng **không** được ghi vào dataset. |

## Chạy test

```bash
cd dataset_collector
python -m pytest tests/ -q      # 38 test
```

- **Chiều kéo + chiều nhận** đều test bằng **HTTP server thật** trên localhost,
  không mock `requests` — các kiểu hỏng cần bắt đều nằm ở tầng giao thức (body
  cụt, trả HTML kèm HTTP 200, preflight CORS, Content-Length nói dối), mock sẽ bỏ lọt.
- **Giao diện web** được kiểm bằng cách đối chiếu ID: mọi `getElementById` phải có
  phần tử tương ứng trong HTML, và khối JS ở 2 file index phải giống hệt nhau. Gõ
  sai một ID thì firmware vẫn compile sạch, vẫn nạp được, chỉ tới lúc bấm nút mới
  phát hiện im ru — đây là loại lỗi trình biên dịch không bao giờ thấy.

## Khác gì `ml.infer --from-board`

Hai công cụ, hai mục đích, cố ý không gộp:

| | `collect_dataset.py` | `ml.infer --from-board` |
|---|---|---|
| Mục đích | thu ảnh thô để **train** | đo mẫu thật để **ghi sổ audit** |
| Đầu ra | file JPEG trong `data/dataset/` | dòng Sample + Particle trong DB |
| Chạy suy luận | không | có |

Gộp lại sẽ buộc công cụ thu dataset phải mang theo cả detector lẫn kết nối DB
— hai thứ nó không cần.
