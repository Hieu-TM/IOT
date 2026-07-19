# Aqua Scope — Bộ thu thập dataset (ESP32-CAM)

Firmware + script để **chụp ảnh trên ESP32-CAM và kéo về laptop** làm dataset huấn luyện.

Tách riêng khỏi `firmware/` (nơi chứa 3 bản web-cam thông thường) vì đây là một
công cụ hoàn chỉnh gồm cả hai nửa: phần chạy trên board và phần chạy trên máy.

```
dataset_collector/
├── firmware/            ← nạp vào ESP32-CAM AI-Thinker
│   ├── firmware.ino         khởi tạo camera + WiFi + mặc định backlit
│   ├── aqua_prefs.{h,cpp}   lưu/nạp cấu hình camera vào flash
│   ├── app_httpd.cpp        web server (bản Espressif + 2 lệnh save/reset)
│   └── camera_index.h  camera_pins.h  board_config.h  partitions.csv
├── collect_dataset.py   ← chạy trên laptop, kéo ảnh về
└── tests/               ← 20 test cho collect_dataset.py
```

## Phân chia trách nhiệm

| | Firmware | `collect_dataset.py` |
|---|---|---|
| Làm gì | phục vụ ảnh qua HTTP | burst, đặt tên file, retry, lưu trữ |
| Không làm gì | không biết dataset là gì | không chỉnh camera |

Nhờ vậy, **sửa cách thu dataset không cần nạp lại firmware**.

---

## Bước 1 — Nạp firmware

Dùng **[`firmware/aqua_scope_station/`](../firmware/aqua_scope_station/)** — bản
chính thức của dự án. Xem hướng dẫn nạp trong README của nó.

`dataset_collector/firmware/` là bản tiền thân, giữ lại để tham khảo. Bản chính
thức là hậu duệ trực tiếp: cùng `/capture`, nên `collect_dataset.py` chạy được
với cả hai.

## Bước 2 — Canh sáng (một lần)

Mở `http://<IP>/` → chỉnh slider tới khi **nền xám đều, hạt = bóng đen rõ**, không có đốm chói.

Chỉnh xong, **ghi cứng vào flash** để lần sau cắm điện là đúng luôn:

```
http://<IP>/control?var=save&val=1
```

Chỉnh hỏng, muốn về mặc định: `http://<IP>/control?var=reset&val=1`

## Bước 3 — Thu dataset

```bash
# chụp 1 ảnh (kiểm tra trước)
python collect_dataset.py --host 192.168.1.50 --count 1

# burst 200 ảnh, cách nhau 1.5 giây
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

## Khác gì bản `CameraWebServer` gốc của Espressif

1. **Ép mặc định backlit** — tắt AEC / AEC-DSP / AGC, gain 0, exposure 100.
   Bản gốc để auto, và auto-exposure sẽ **kéo nền cháy trắng nuốt mất hạt**,
   bất kể chỉnh đèn nền thế nào.
2. **Mặc định UXGA 1600×1200** thay vì QVGA — hạt <2mm cần độ phân giải.
   (OV2640 tối đa UXGA; OV3660 trên bản XIAO lên được QXGA.)
3. **Lưu cấu hình vào flash** — thêm `?var=save` / `?var=reset`.
4. **Không treo vô hạn khi WiFi hỏng** — bản gốc lặp `while` mãi mãi, bản này
   hết 20s là báo lỗi rõ ràng.

## Trục trặc hay gặp

| Hiện tượng | Nguyên nhân thường gặp |
|---|---|
| Ảnh lỗi liên tục, board reset | **Brownout**: WiFi TX + chụp UXGA cùng lúc. Tăng `--interval`, dùng nguồn 5V ≥ 2A. |
| Nền trắng xóa, không thấy hạt | Cấu hình chưa lưu, board boot lại về auto → mở web chỉnh lại rồi `var=save`. |
| `lỗi mạng: ... timed out` | Router nghẽn. Đổi `USE_AP = true`, nối laptop thẳng vào WiFi `AquaScope` (`http://192.168.4.1`). |
| Serial in `[CẢNH BÁO] Không thấy PSRAM` | Chọn nhầm board, hoặc board lỗi. Ảnh sẽ chỉ có SVGA. |

## Chạy test

```bash
cd dataset_collector
python -m pytest tests/ -q
```

Test dựng một **ESP32-CAM giả bằng HTTP server thật** trên localhost để mô phỏng
đúng các kiểu hỏng ngoài đời (body cụt, trả HTML kèm HTTP 200, timeout,
brownout giữa burst) — mock `requests` sẽ bỏ lọt đúng những ca đó.

## Khác gì `ml.infer --from-board`

Hai công cụ, hai mục đích, cố ý không gộp:

| | `collect_dataset.py` | `ml.infer --from-board` |
|---|---|---|
| Mục đích | thu ảnh thô để **train** | đo mẫu thật để **ghi sổ audit** |
| Đầu ra | file JPEG trong `data/dataset/` | dòng Sample + Particle trong DB |
| Chạy suy luận | không | có |

Gộp lại sẽ buộc công cụ thu dataset phải mang theo cả detector lẫn kết nối DB
— hai thứ nó không cần.

> **`--from-board` đang được thêm vào** (Task 6–9 của plan firmware). Tới khi
> xong, chỉ `collect_dataset.py` ở cột trái là chạy được.
