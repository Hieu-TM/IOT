# 🌊 Aqua Scope — Trạm Quan Trắc & Đếm Hạt/Rác Thải Vĩ Mô (Runtime Edition)

**Aqua Scope** là hệ thống trạm quan trắc tự động chụp ảnh bóng đổ (backlit silhouette) và phát hiện, đếm, đo kích thước hạt rác thải vĩ mô (1mm–5mm) trong dòng chảy nước. 

Nhánh **`release/runtime-only`** chứa bộ mã nguồn và tệp tin tinh gọn nhất dành riêng cho việc **vận hành và chạy ứng dụng thực tế** (bao gồm Web Backend, Dashboard, Pipeline AI Inference, Firmware ESP32-CAM và kịch bản khởi động 1-click).

---

## 🏗️ Cấu Trúc Thành Phần Runtime

* **`start.bat`**: Kịch bản tự động khởi động hệ thống trên Windows chỉ với 1 cú click.
* **`scripts/start-server.ps1`**: PowerShell script chạy FastAPI Backend & ML Pipeline.
* **`web/`**: 
  * `web/backend/`: Server FastAPI quản lý API, kết nối DB SQLite và chạy ML runner background process.
  * `web/backend/app/static/` & `templates/`: Giao diện Web UI Dashboard truy xuất nguồn gốc.
  * `web/mock_sender.py`: Script giả lập camera gửi dữ liệu đo khi chưa kết nối phần cứng thật.
  * `web/requirements.txt`: Các thư viện Python cần thiết cho Web Backend.
* **`ml/`**: 
  * `ml/infer/`: Module suy luận AI (hỗ trợ YOLO Local hoặc Roboflow Cloud API).
  * `ml/config.toml`: Tệp cấu hình tham số suy luận ML.
  * `ml/requirements-infer.txt`: Các thư viện cho nhánh suy luận ML.
* **`firmware/`**:
  * `firmware/aqua_scope_station/`: Mã nguồn Arduino C++ cho board ESP32-CAM (điều khiển camera + bơm màng RS365 theo chu trình Stop-Flow).

---

## 📋 Yêu Cầu Môi Trường

1. **Hệ điều hành**: Windows 10/11 (khuyên dùng) hoặc Linux/macOS.
2. **Python**: Phải cài đặt **Python 3.11+** và tick chọn **"Add Python to PATH"** lúc cài đặt.
3. **Trình duyệt**: Chrome, Edge, Brave hoặc Firefox mới nhất.
4. **Phần cứng (Tùy chọn)**: 
   * Trạm ESP32-CAM (AI-Thinker) + Bơm màng RS365 12V.
   * *(Nếu không có phần cứng, có thể dùng `web/mock_sender.py` để chạy thử nghiệm giao diện).*

---

## 🚀 Hướng Dẫn Khởi Động Nhanh (1-Click)

### Bước 1: Khởi chạy Server
Tại thư mục gốc của dự án, bấm đúp vào tệp **`start.bat`**.

Quá trình tự động thực hiện:
1. Kiểm tra môi trường Python.
2. Tự động tạo môi trường ảo `.venv` (nếu chưa có).
3. Tự động cài đặt các thư viện phụ thuộc (`web/requirements.txt` và `ml/requirements-infer.txt`).
4. Mở cửa sổ PowerShell mới tên **"Aqua Scope Server"** chạy FastAPI backend tại địa chỉ: **`http://localhost:8000`**.

> **Lưu ý:** Cửa sổ `start.bat` ban đầu sẽ tự đóng sau khi bật cửa sổ server. Để dừng hệ thống, bạn hãy đóng cửa sổ PowerShell **"Aqua Scope Server"** hoặc bấm `Ctrl + C` tại cửa sổ đó.

---

## ⚙️ Cấu Hình Mô Hình AI (ML Inference)

Hệ thống hỗ trợ 2 chế độ nhận diện hạt trong `ml/config.toml`:

### Chế độ 1: Roboflow Cloud API (Mặc định khuyên dùng thử)
1. Mở tệp `ml/config.toml`, đảm bảo `backend = "roboflow"`.
2. Tạo tệp `ml/config.local.toml` (nếu cần điền API key riêng) với nội dung:
   ```toml
   [roboflow]
   api_key = "YOUR_ROBOFLOW_API_KEY"
   workspace = "microplastics-m7mf5"
   workflow_id = "detect-count-size"
   ```

### Chế độ 2: Local YOLO (`ultralytics`)
1. Cài đặt thêm ultralytics: `pip install ultralytics`
2. Đặt weights của mô hình vào đường dẫn: `ml/models/best.pt`.
3. Sửa tệp `ml/config.toml`:
   ```toml
   backend = "local"
   ```

---

## 🔌 Cấu Hình & Nạp Firmware ESP32-CAM

Nếu bạn có trạm phần cứng thật:

1. Mở thư mục `firmware/aqua_scope_station/` bằng **Arduino IDE**.
2. Sao chép tệp `wifi_config.example.h` thành `wifi_config.h`:
   ```cpp
   #ifndef WIFI_CONFIG_H
   #define WIFI_CONFIG_H

   const char* WIFI_SSID = "TEN_WIFI_CUANBAN";
   const char* WIFI_PASS = "MATKHAU_WIFI";

   #endif
   ```
3. Cài đặt các thư viện cần thiết trong Arduino IDE (`Esp32-cam`, `ArduinoJson`).
4. Chọn Board **AI Thinker ESP32-CAM**, chọn đúng cổng COM và tiến hành **Upload**.

---

## 🖥️ Hướng Dẫn Sử Dụng Giao Diện Web Dashboard

Mở trình duyệt truy cập: `http://localhost:8000`

### 1. Dò tìm và kết nối Trạm (Board Discovery)
* Tại bảng **Điều khiển Trạm**, bấm nút **Dò**.
* Hệ thống sẽ tự tìm IP của board qua tên miền mDNS `aqua-scope.local`.
* Trường hợp không dò được tự động, gõ trực tiếp địa chỉ IP (in ra từ Serial Monitor của ESP32) vào ô cấu hình.

### 2. Canh sáng buồng tối (Darkmode Calibration)
* Đèn nền trắng và camera nằm trong buồng tối chắn sáng.
* Bấm nút **Canh sáng buồng tối** để khóa các thông số cảm biến (tắt AEC/AGC, đặt Exposure cố định).
* Bấm **Lưu vào flash** để ESP32 ghi nhớ thông số phơi sáng này qua các lần khởi động lại.

### 3. Bật Bơm Tự Động & Chu Kỳ Stop-Flow
* Chuyển công tắc **Bơm auto** sang trạng thái **BẬT**.
* Bơm màng RS365 sẽ chạy theo chu kỳ 5 pha tự động:
  1. `FILLING`: Bơm hút nước chứa hạt vào khay.
  2. `SETTLING`: Bơm ngắt 1–2 giây để mặt nước phẳng lặng.
  3. `CAPTURING`: Bật đèn nền, chụp ảnh độ phân giải cao (SXGA/UXGA).
  4. `INFERRING`: Gửi ảnh sang ML Pipeline để đếm & đo kích thước hạt bóng đổ.
  5. `FLUSHING`: Bơm chạy xả mạnh để đẩy hạt ra khỏi khay và nạp mẫu mới.

### 4. Chế độ Xem (Preview) vs Chế độ Đo (Measure)
* **Chế độ Xem (Preview)**: Bật khi muốn chỉnh sửa phần cứng, kiểm tra hình ảnh camera mượt mà, dữ liệu chụp **không** ghi vào cơ sở dữ liệu audit.
* **Chế độ Đo (Measure)**: Bật khi bắt đầu ca quan trắc chính thức. Mỗi mẫu đo sẽ được cấp **Sample ID**, lưu vết lịch sử số lượng hạt, phân bố kích thước và hình ảnh vào cơ sở dữ liệu để phục vụ truy xuất nguồn gốc (Traceability).

---

## 🧪 Giả Lập Phần Cứng (Hardware Mock Simulator)

Nếu muốn trải nghiệm giao diện và thử nghiệm hệ thống mà **chưa có board ESP32-CAM thật**:

1. Đảm bảo Web Server đang chạy (`start.bat`).
2. Mở một cửa sổ Terminal/Command Prompt mới.
3. Chạy lệnh:
   ```bash
   python web/mock_sender.py --target http://localhost:8000 --interval 10
   ```
4. Script sẽ giả lập một camera gửi ảnh mẫu định kỳ mỗi 10 giây lên server. Bạn có thể mở Dashboard tại `http://localhost:8000` để xem kết quả nhận diện và lưu vết lịch sử.
