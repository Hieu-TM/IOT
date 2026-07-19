# Thiết kế: Firmware chính thức `aqua_scope_station` + đường chạy liền mạch board → model → web

Ngày: 2026-07-19
Trạng thái: đã duyệt (brainstorming), chờ lập plan

## 1. Vấn đề

Các mảnh của dự án đều đã chạy được, nhưng **chưa nối thành một hệ**:

- `dataset_collector/firmware/` — bản ESP32-CAM tốt nhất hiện có (backlit defaults,
  prefs flash, `/capture`), nhưng được đóng khung là **công cụ thu dataset**, không phải
  firmware của trạm đo.
- `firmware/Esp32 cam/`, `firmware/aqua_scope_cam/`, `firmware/esp32-cam-webserver/`,
  `firmware/pump_stopflow_test/` — thử nghiệm hoặc tiền đề, không rõ bản nào là bản nạp.
- `ml/infer` — chạy được, nhưng chỉ đọc **thư mục ảnh** trên đĩa.
- `web/backend` — nhận `/api/ingest` và hiển thị dashboard, đã hoạt động.

Hệ quả: để đo một mẫu, phải chạy `collect_dataset.py` tải ảnh về thư mục, rồi mới chạy
`ml.infer` trỏ vào thư mục đó. Hai bước rời, và không có gì trong sổ audit cho biết ảnh
đến từ board nào ở thiết lập camera nào.

## 2. Quyết định kiến trúc

**PC là nhạc trưởng.** Firmware là nguồn ảnh + (sau này) cơ cấu chấp hành; PC điều phối
chu trình đo, chạy suy luận, ghi sổ audit.

Lý do chọn hướng này thay vì để ESP32 tự POST ảnh lên backend: backend hiện nhận ảnh
**kèm danh sách particles** đã suy luận. Nếu board POST ảnh trần, mọi Sample sẽ có
`particle_count = 0` và phải viết lại cả backend lẫn `ml/infer` thành kiến trúc
pull/worker. Đổi lại, hệ cần có PC bật thì mới đo được — chấp nhận được vì đây là
demo/lab rig, và chu trình vốn là **lấy mẫu theo lô/định kỳ**, không phải giám sát 24/7.

Ràng buộc phần cứng hiện tại thu hẹp phạm vi firmware đáng kể:

- **Đèn nền cắm điện trực tiếp, luôn sáng** → firmware không điều khiển đèn.
- **Chưa cần điều khiển bơm** → không gộp state machine của `pump_stopflow_test`.

Còn lại đúng: camera + WiFi + phục vụ ảnh + báo cáo trạng thái.

## 3. Phần A — Firmware `firmware/aqua_scope_station/`

Bản chính thức duy nhất của dự án. Kế thừa nguyên phần đã chạy tốt của
`dataset_collector/firmware`: mặc định backlit (tắt AEC / AEC-DSP / AGC, gain 0,
exposure thấp), mặc định UXGA, `aqua_prefs` lưu/nạp cấu hình vào NVS, web UI canh sáng,
`/capture`, `/stream`, `/control?var=save|reset`.

### A0. Tắt đèn flash khi chụp (phát hiện lúc lập plan)

`capture_handler` của bản Espressif bật **đèn flash trắng GPIO4 trong 150ms trước mỗi
lần chụp** (`LED_GPIO_NUM 4` được định nghĩa cho AI-Thinker, `camera_pins.h:180`).

Với rig backlit silhouette, đó là ánh sáng chiếu **từ trên xuống** mặt nước: làm nhạt
tương phản bóng hạt và tạo phản xạ trên mặt nước — đúng thứ toàn bộ thiết kế quang học
đang cố tránh. Bản chính thức phải bỏ hẳn, đồng thời bỏ luôn 150ms trễ mỗi khung.

### A1. `GET /device` → JSON

Endpoint mới. **Tên là `/device`, không phải `/status`**: `/status` đã bị chiếm bởi
handler trả JSON cấu hình camera mà web UI dùng để nạp slider (`app_httpd.cpp:431`) —
đổi nó sẽ làm hỏng trang canh sáng.

Trả về:

```json
{
  "device_id": "aqua-cam-a1b2c3",
  "firmware": "aqua_scope_station/1.0.0",
  "uptime_s": 4512,
  "wifi": { "ssid": "...", "rssi": -58, "ip": "192.168.1.50" },
  "psram": true,
  "sensor": "OV2640",
  "camera": {
    "framesize": "UXGA", "width": 1600, "height": 1200, "quality": 10,
    "aec": 0, "aec2": 0, "agc": 0, "gain": 0, "exposure": 100
  },
  "captures": 137,
  "prefs_saved": true
}
```

Vì sao cần: yêu cầu truy xuất nguồn gốc của dự án đòi hỏi biết một mẫu được chụp
**bởi board nào, ở thiết lập camera nào**. `prefs_saved: false` là cảnh báo trực tiếp
cho lỗi hay gặp nhất trong README hiện tại ("nền trắng xóa, không thấy hạt" — do board
boot lại về auto vì chưa `var=save`). PC gọi endpoint này một lần trước khi chạy và
nhét nguyên khối vào metadata của mẫu.

### A2. `device_id` ổn định

Sinh từ MAC: `aqua-cam-` + 3 byte cuối dạng hex thường (ví dụ `aqua-cam-a1b2c3`).
Ghi đè được bằng `GET /control?var=device_id&val=<chuỗi>`, lưu cùng chỗ với prefs
camera trong NVS.

Vì sao: hiện `ingest.device_id` trong `ml/config.toml` là hằng `"pc-infer"` — mọi mẫu
đều mang chung một tên. Với sổ audit thì cột đó phải chỉ ra **thiết bị đo thật**.

Ràng buộc: `device_id` phải khớp `^[A-Za-z0-9._-]{1,64}$` để đi lọt qua ingest contract
của web (`web/backend/app/models.py`).

### A3. Độ bền khi chạy dài

| Vấn đề ở bản hiện tại | Xử lý |
|---|---|
| Rớt WiFi giữa chừng là đứng luôn | Nối lại qua WiFi event handler, **không dùng vòng `while` chặn**. Vẫn phục vụ HTTP ngay khi có lại IP. |
| `esp_camera_fb_get()` trả `NULL` → phản hồi cụt, client không biết vì sao | Trả **HTTP 503** kèm body lý do rõ ràng. Không bao giờ trả 200 với thân rỗng. |
| Board treo phải rút điện | Bật task watchdog cho vòng lặp chính. |

### A4. Cố tình KHÔNG có trong phạm vi này

- Điều khiển đèn nền (đèn cắm thẳng).
- Điều khiển bơm / state machine Stop-Flow (`pump_stopflow_test` vẫn đứng riêng).
- Suy luận on-device.

Không viết sẵn code cho những thứ này. Chỗ để dành duy nhất được chấp nhận: `/device`
có cấu trúc mở rộng được, và README ghi rõ bơm sẽ vào ở đâu khi tới lúc.

## 4. Phần B — `ml/infer` đọc thẳng từ board

### B1. `Esp32CaptureSource`

Thêm vào `ml/infer/source.py`, **cùng interface `.frames()`** với `FolderSource`
(docstring của file đã dự trù sẵn lớp này). Nhờ vậy `cli.py`, `mapper.py`,
`ingest_client.py` không phải sửa gì ngoài chỗ chọn source.

Hành vi:

- `GET http://<host>/device` một lần lúc khởi tạo → giữ lại để nhét vào metadata.
  Nếu không gọi được → báo lỗi rõ ràng và dừng, **không** âm thầm chạy tiếp.
- Lặp `--count` lần: `GET /capture`, nghỉ `--interval` giây giữa hai lần.
- Mỗi lần chụp lỗi (timeout / 503 / body không phải JPEG) → thử lại `retries` lần,
  hết thì bỏ qua khung đó và ghi log, **không** làm hỏng cả lượt chạy.
- `captured_at` lấy theo giờ PC lúc nhận được ảnh (timezone-aware UTC).
- `sample_code` sinh dạng `S{yyyyMMdd}-{HHmmss}-{mmm}` từ thời điểm chụp — cùng dạng với
  mã do server sinh, và khớp sẵn `^[A-Za-z0-9._-]{1,64}$` nên không cần làm sạch thêm.
  Phần mili-giây là thứ giữ cho hai khung chụp liền nhau không trùng mã.

### B2. CLI

```bash
python -m ml.infer --from-board 192.168.1.50 --count 5 --interval 2
```

- `--from-board <host>` loại trừ lẫn nhau với đối số `input` (thư mục ảnh). Đưa cả hai
  → lỗi rõ ràng, không đoán.
- Bỏ `--from-board` mà `[station].host` đã khai trong config → dùng giá trị đó.
- `--dry-run`, `--check-config` hoạt động y hệt. `--dry-run` vẫn chụp thật nhưng **không
  POST** — DB là sổ audit, mỗi lần chạy thật là một bản ghi vĩnh viễn.
- `--device-id` không đưa → dùng `device_id` **board tự báo** (không phải hằng trong
  config). Đưa tay → giá trị tay thắng, theo đúng thứ tự ưu tiên hiện có của config.

### B3. Config

Thêm mục vào `ml/config.toml`:

```toml
[station]
host = ""          # IP hoặc hostname của board, lấy từ Serial Monitor
timeout_s = 20     # timeout mỗi request (UXGA qua WiFi có thể lâu)
retries = 3        # số lần thử lại mỗi khung ảnh
interval_s = 2.0   # nghỉ giữa hai lần chụp
```

`config.missing_for("station")` kiểm tra mục này, và `--check-config` phải báo cáo nó
**cùng lúc** với backend suy luận — hai thứ trực giao: đọc từ board vẫn chạy được cả
`local` lẫn `roboflow`.

## 5. Ranh giới với `dataset_collector`

`collect_dataset.py` chạy nguyên vẹn với firmware mới (cùng `/capture`). **Không gộp.**

| | `collect_dataset.py` | `ml.infer --from-board` |
|---|---|---|
| Mục đích | thu ảnh thô để **train** | đo mẫu thật để **ghi sổ audit** |
| Đầu ra | file JPEG trong `data/dataset/` | dòng Sample + Particle trong DB |
| Chạy suy luận | không | có |

Gộp lại sẽ buộc công cụ thu dataset phải mang theo cả detector và kết nối DB — hai thứ
nó không cần.

## 6. Các firmware cũ

Giữ nguyên, không xóa. Thêm một dòng ở đầu README mỗi thư mục:

> Tham khảo/thử nghiệm — bản chính thức để nạp là `firmware/aqua_scope_station/`.

`dataset_collector/firmware/` là trường hợp riêng: nó bị **thay thế** bởi bản mới
(bản mới là hậu duệ trực tiếp). README của `dataset_collector` phải nói rõ dùng
`firmware/aqua_scope_station/` và giữ `collect_dataset.py` như cũ.

## 7. Kiểm chứng

**Phần Python** — test theo đúng kiểu `dataset_collector/tests` đang làm: dựng HTTP
server thật trên localhost giả lập board, để bắt các ca hỏng ngoài đời mà mock
`requests` sẽ bỏ lọt:

- `/device` không gọi được → lỗi rõ ràng, dừng
- `/device` trả JSON thiếu khóa → không sập, báo thiếu
- `/capture` timeout → thử lại đủ số lần rồi bỏ qua khung
- `/capture` trả HTML kèm HTTP 200 → nhận ra không phải JPEG
- `/capture` trả 503 → bỏ qua khung, chạy tiếp
- body JPEG cụt giữa chừng → không đẩy rác vào detector
- brownout giữa burst (server chết giữa lượt) → các khung đã lấy vẫn được xử lý
- `--dry-run` → không có request POST nào chạm tới ingest

**Phần firmware** — không test tự động được. Nghiệm thu bằng checklist chạy trên board
thật, ghi vào README, và **không tuyên bố "chạy được" trước khi chạy đủ checklist**:

1. Nạp, mở Serial 115200 → thấy IP.
2. `GET /device` → JSON hợp lệ, `device_id` khớp MAC, `psram: true`.
3. Web UI canh sáng → nền xám đều, hạt là bóng đen.
4. `var=save` → rút điện → cắm lại → `/device` báo `prefs_saved: true` và đúng thông số.
5. Tắt router 30 giây rồi bật lại → board tự nối lại, `/device` phản hồi, không cần reset.
6. `python -m ml.infer --from-board <ip> --count 3 --dry-run` → 3 khung, không ghi DB.
7. Bỏ `--dry-run` → 3 mẫu hiện trên dashboard, cột device_id đúng tên board.

## 8. Ngoài phạm vi

- Điều khiển bơm và hợp nhất state machine Stop-Flow.
- Điều khiển đèn nền qua GPIO.
- Suy luận on-device trên ESP32-CAM.
- Hiệu chuẩn `px_per_mm` thật trên rig (đến khi có, `size_mm` vẫn là placeholder và
  CLI vẫn phải cảnh báo mỗi lần chạy).
- Dọn/xóa các thư mục firmware cũ.
