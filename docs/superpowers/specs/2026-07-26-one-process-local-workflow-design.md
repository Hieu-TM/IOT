# Thiết kế: Gộp workflow local về một tiến trình + chạy suy luận liên tục

**Ngày:** 2026-07-26
**Trạng thái:** Đã duyệt bởi user, chờ viết plan triển khai.
**Nhánh:** `feature/simple-local-workflow`
**Liên quan:** `docs/superpowers/specs/2026-07-14-web-system-design.md` (hệ web gốc),
`docs/superpowers/specs/2026-07-15-branch1-pc-inference-design.md` (pipeline `ml/infer`),
`docs/superpowers/specs/2026-07-19-aqua-scope-station-firmware-design.md` (firmware trạm),
`docs/superpowers/specs/2026-07-25-station-camera-default-auto-exposure-design.md`
(quyết định KHÔNG ép darkmode mặc định — doc này tôn trọng, xem §2.4).

## Bối cảnh

Để chạy được một lượt đo hiện phải làm 6 bước tay, trên 3 mặt phẳng điều khiển
khác nhau (Serial Monitor, curl, 2 cửa sổ terminal):

| # | Bước | Ở đâu |
|---|---|---|
| 1 | Nạp firmware, mở Serial Monitor 115200 lấy IP | Arduino IDE |
| 2 | `curl "http://<ip>/control?var=darkmode&val=1"` rồi `?var=save` | terminal |
| 3 | `curl "http://<ip>/control?var=pump_auto&val=1"` | terminal |
| 4 | `cd web/backend && python -m uvicorn app.main:app --port 8000` | terminal A |
| 5 | `python -m ml.infer --from-board <ip> --count 5 --interval 2` | terminal B |
| 6 | Mở `http://localhost:8000` | trình duyệt |

Hai vấn đề user nêu:

1. **Rườm rà.** Không có "một nút bật", và mọi tham số (IP board, số khung, chu
   kỳ) đều nằm rải rác giữa cờ CLI và `ml/config.local.toml`.
2. **Không suy luận liên tục.** `Esp32CaptureSource.frames()`
   (`ml/infer/source.py:151`) chạy `for i in range(self.count)` rồi trả về —
   `--count 5` nghĩa là đúng 5 khung rồi CLI thoát. Muốn đo tiếp phải gõ lại
   lệnh. Nguyên nhân gốc: class này trộn *cách nói chuyện với board* (đọc
   `/device`, GET `/capture`, retry) vào *vòng lặp đếm N khung*, nên không có
   cách nào lấy "một khung theo yêu cầu".

## Mục tiêu

Sau khi sửa: bật `start.bat` → trình duyệt mở `http://localhost:8000` → gõ/dò IP
board một lần → bấm **Bắt đầu** → hệ thống tự chụp + suy luận theo từng chu kỳ
bơm, **không giới hạn số khung**, cho tới khi bấm **Dừng**. Không mở terminal
thứ hai, không sửa file config để đổi tham số vận hành.

## Quyết định đã chốt với user

| Câu hỏi | Chốt |
|---|---|
| Điều khiển ở đâu | **Nút trên dashboard.** Vòng lặp chạy như worker thread trong backend web |
| Cái gì kích hoạt một lần chụp | **Cạnh pha bơm SETTLING** đọc từ `/device`, không phải interval cố định |
| Chạy liên tục có làm ngập sổ audit không | **Hai chế độ XEM / ĐO.** XEM = infer live, không ghi gì. ĐO = ghi đủ vào sổ audit |
| Tìm IP board thế nào | **mDNS (`aqua-scope.local`) + ô nhập tay trên web**, lưu lại cho lần sau |

---

## 1. Kiến trúc

Một tiến trình duy nhất:

```
start.bat
  └── python -m uvicorn --app-dir web/backend app.main:app   (cwd = gốc repo)
        ├── FastAPI
        │     ├── dashboard + /api/ingest + /api/samples      (đã có)
        │     └── /api/runner/* + /api/station/* + /api/settings   (MỚI)
        └── Runner thread (MỚI)
              poll /device 0.5s → thấy cạnh vào SETTLING → chờ capture_delay
              → GET /capture → detector → (ĐO) POST /api/ingest của chính mình
```

### 1.1 Vì sao runner POST ngược vào `/api/ingest` thay vì ghi thẳng DB

Ingest hiện có (`web/backend/app/routers/ingest.py`) đã cầm 4 thứ khó: validate
payload, sinh `sample_code` khi thiếu, idempotency theo `sample_code`, và ghi
**nguyên tử** (row sample + rows particle + file ảnh cùng sống hoặc cùng chết).
Ghi thẳng DB từ runner nghĩa là chép lại cả 4 thứ đó, và mọi sửa đổi sau này
phải sửa hai nơi — đúng kiểu bug âm thầm mà sổ audit không được phép có.

Chi phí: một vòng HTTP qua loopback cho mỗi mẫu (~vài ms so với ~1–3s tải ảnh
UXGA qua WiFi). Không đáng kể.

Hệ quả tốt kèm theo: `ml.infer` CLI **không đổi hành vi** — nó vẫn là một client
HTTP như trước, chạy độc lập được cho việc chạy lại thư mục ảnh.

### 1.2 Runner dùng lại `ml/infer/`, không chép code

Runner import: `Detector` / `RoboflowWorkflowDetector` (qua
`ml.infer.cli.build_detector`), `ml.infer.mapper.build_metadata`,
`ml.infer.ingest_client.post`, `ml.infer.config`. Backend suy luận
(`local` / `roboflow`) vẫn do `ml/config.toml` + `config.local.toml` quyết định —
**không** nhân bản thành một hệ config thứ hai cho web.

**Import path.** Backend web hiện chạy với cwd = `web/backend`, nên `import ml`
sẽ hỏng. Xử lý hai lớp:
- `start.bat` chạy `python -m uvicorn --app-dir web/backend app.main:app` từ gốc
  repo → `-m` đưa cwd (gốc repo) vào `sys.path`, `--app-dir` đưa `web/backend`
  vào. Cả hai import đều chạy.
- Phòng thủ: `runner.py` có `_ensure_repo_on_path()` chèn gốc repo vào
  `sys.path` nếu chưa có (suy từ `config.BACKEND_DIR`), để người khởi động
  bằng cách khác vẫn chạy được. Có comment giải thích vì sao tồn tại.

**Nạp detector lười.** Detector chỉ được dựng ở lần bấm **Bắt đầu** đầu tiên,
không phải lúc khởi động web. Nếu không, backend `local` sẽ kéo ultralytics +
torch vào mỗi lần mở dashboard chỉ để xem lịch sử — chậm hàng chục giây và tốn
RAM vô cớ. Dựng lỗi → trả lỗi kèm danh sách `cfg.missing_for(backend)` như CLI
đang làm, không crash thread.

---

## 2. Runner — máy trạng thái

### 2.1 Trạng thái

```python
mode:    "preview" | "measure"      # XEM / ĐO
running: bool
station_host: str
device:  dict | None                # snapshot /device gần nhất
counters: {cycles, captured, written, failed}
last:    {sample_code, particle_count, labels{}, at, written: bool} | None
error:   str | None                 # lý do dừng bất thường
warnings: list[str]
```

Trạng thái chỉ nằm trong RAM: restart server = về idle. Chỉ **cấu hình** (IP,
chế độ mặc định, lot, capture_delay) mới ghi ra file (§4).

### 2.2 Vòng lặp

Mỗi `POLL_INTERVAL_S = 0.5`:

1. `GET /device` (timeout 5s).
   - Lỗi → `consecutive_errors += 1`, ghi vào `error`, **vẫn chạy tiếp**.
     Tới `MAX_CONSECUTIVE_ERRORS = 10` (~5s im lặng) thì dừng hẳn và báo lý do.
     Quay vô tận trong im lặng là kiểu hỏng tệ nhất cho một trạm QC.
   - OK → reset bộ đếm lỗi, cập nhật `device`.
2. `phase = device["pump"]["phase"]`.
3. **Cạnh vào SETTLING**: `prev_phase != "SETTLING" and phase == "SETTLING"`
   → hẹn chụp sau `capture_delay_ms`. `prev_phase = phase` mỗi vòng.
   - Chỉ bắt **cạnh**, không bắt trạng thái: pha SETTLING kéo dài 2s mà poll
     0.5s → nếu bắt trạng thái sẽ chụp 4 lần cho một chu kỳ bơm.
   - `pump.cycle_count` trong `/device` dùng làm **đối chứng** cho bộ đếm
     `cycles` (phát hiện chu kỳ bị bỏ lỡ khi mạng lag), không dùng làm trigger.
4. Chụp: `StationClient.capture_once()` với retry sẵn có.
5. `detector.run(bytes)` → `build_metadata(...)`.
6. `mode == "measure"` → `post(api_url, metadata, bytes, f"{code}.jpg")`.
   `mode == "preview"` → giữ ảnh + kết quả trong RAM, **không ghi gì ra đĩa**.
7. Cập nhật `last` + counters.

Một khung hỏng (brownout, JPEG cụt, detector ném lỗi) → `failed += 1`, bỏ khung,
chạy tiếp. Giống hệt hành vi CLI hiện tại — một khung hỏng không được giết cả
lượt đo.

### 2.3 Bơm không ở chế độ auto thì sao

Nếu `pump.auto == false`, pha không bao giờ đổi → **không có khung nào được
chụp**. Đây là hành vi đúng (không có chu kỳ Stop-Flow thì không có mẫu hợp lệ),
nhưng nếu để im thì trông y hệt "hệ thống treo". Dashboard phải hiện cảnh báo
rõ: *"Bơm chưa ở chế độ auto — sẽ không có khung nào được chụp"*, kèm nút bật
bơm auto ngay cạnh.

### 2.4 `capture_delay_ms` và phơi sáng — hai cảnh báo, không tự ý sửa

**Thời điểm chụp.** Chụp ngay lúc vào SETTLING là chụp lúc nước vừa mới dừng.
Mặc định `capture_delay_ms = 800`, tức chụp ở khoảng giữa cửa sổ settle mặc
định 2000ms. Runner đọc `pump.settle_ms` từ `/device`; nếu
`capture_delay_ms >= settle_ms` thì **cảnh báo** (khung sẽ rơi sang pha
FLUSHING) chứ không tự sửa thông số bơm của người dùng.

Thời gian *truyền* ảnh UXGA (~1–3s) tràn sang pha FLUSHING là **không sao**:
cảm biến đã lấy khung xong ở thời điểm request tới, rung của bơm sau đó không
ảnh hưởng tới ảnh đã chụp.

**Phơi sáng.** Runner **KHÔNG tự gọi `?var=darkmode`**. Ngày 2026-07-25 đã chốt
bỏ ép darkmode mặc định vì nó làm ảnh tối, khó ngắm
(`2026-07-25-station-camera-default-auto-exposure-design.md`) — tự ý ép lại ở
tầng web là lách đúng quyết định đó qua cửa sau. Thay vào đó: lúc bấm **Bắt
đầu**, runner đọc `camera.aec` / `camera.agc` từ `/device`; nếu còn bật thì
hiện cảnh báo vàng *"AEC/AGC đang bật — nền sẽ cháy trắng và nuốt mất hạt. Bấm
'Canh sáng buồng tối' trước khi đo."* Cảnh báo, không chặn: người vận hành vẫn
được quyền chạy nếu họ biết mình đang làm gì.

### 2.5 An toàn luồng

Một worker duy nhất. `threading.Lock` bao start/stop → bấm **Bắt đầu** hai lần
không tạo hai vòng lặp (lần hai trả 409). Đọc trạng thái từ request handler lấy
một bản copy dưới lock. Dừng bằng `threading.Event`; thread thoát trong vòng
một chu kỳ poll hoặc một timeout capture.

---

## 3. `ml/infer/` — tách `StationClient`

Đây là sửa gốc rễ của vấn đề "chỉ infer được 5 ảnh".

**Mới: `ml/infer/station.py`**

```python
class StationClient:
    def __init__(self, host, *, timeout_s=20, retries=3): ...
    def read_device(self) -> dict          # chuyển nguyên _read_device()
    def capture_once(self) -> bytes        # chuyển nguyên _capture_once() + vòng retry
    @property device_id
```

Toàn bộ logic đã kiểm chứng được **chuyển nguyên**, không viết lại: validate
magic JPEG `\xff\xd8` / `\xff\xd9` (chống captive portal trả HTML kèm HTTP 200),
`_CAPTURE_RETRY_BACKOFF_S = 0.3` cho brownout WiFi, phân biệt lỗi mạng (thử
lại) với JSON sai hình dạng (raise ngay).

**Sửa: `ml/infer/source.py`** — `Esp32CaptureSource` giữ nguyên API công khai
(`frames()`, `.skipped`, `.device_info`, `.device_id`) nhưng bên trong ủy quyền
cho `StationClient`. `_next_sample_code()` / `_station_sample_code()` ở lại
`source.py` vì runner cũng cần → chuyển sang `naming.py`, nơi đã có
`sample_code_from_filename()`.

**Không đổi:** `cli.py`, `detector*.py`, `mapper.py`, `ingest_client.py`. Cờ
`--count` / `--interval` giữ nguyên nghĩa. **Không thêm `--loop` cho CLI** —
dashboard là đường chạy chính rồi; CLI để lại cho việc chạy lại thư mục ảnh.

---

## 4. Cấu hình vận hành

`web/backend/data/settings.json` (thư mục `data/` đã gitignore):

```json
{
  "station_host": "aqua-scope.local",
  "mode": "preview",
  "batch_lot": null,
  "capture_delay_ms": 800,
  "px_per_mm": null
}
```

Ranh giới rõ ràng, không chồng lấn với `ml/config.toml`:

| File | Giữ gì | Ai sửa |
|---|---|---|
| `ml/config.toml` + `.local.toml` | backend suy luận, API key, weights, hiệu chuẩn mặc định | lập trình viên, sửa bằng tay |
| `data/settings.json` | tham số **vận hành** đổi theo ca: IP board, lot, chế độ, delay | người vận hành, sửa qua web |

Thứ tự ưu tiên, để không có hai nguồn sự thật:

- `station_host`, `px_per_mm`: giá trị trong `settings.json` **thắng**; để trống
  thì rơi về `[station].host` / `[calibration].px_per_mm` của `ml/config.toml`.
  Cấu hình cũ vì vậy vẫn chạy nguyên.
- `mode`: body của `POST /api/runner/start` **thắng**. `settings.json` chỉ lưu
  lựa chọn gần nhất để lần mở dashboard sau tick sẵn đúng ô đó — nó là mặc
  định của giao diện, không phải nguồn quyết định lúc chạy.

---

## 5. Hợp đồng API mới

| Route | Việc |
|---|---|
| `GET /api/runner/status` | trạng thái đầy đủ (§2.1). Dashboard poll mỗi 1s |
| `POST /api/runner/start` | `{"mode": "preview"\|"measure"}` → 200 / 400 (thiếu host hoặc config detector) / 409 (đang chạy) |
| `POST /api/runner/stop` | 200, idempotent |
| `GET /api/runner/preview.jpg` | khung mới nhất ở chế độ XEM, từ RAM. 404 khi chưa có |
| `POST /api/runner/keep` | ghi khung XEM đang hiện vào sổ audit (nút "Lưu mẫu này") |
| `GET /api/settings` / `POST /api/settings` | đọc/ghi `settings.json` |
| `GET /api/station/probe?host=` | thử `/device` một host, trả JSON hoặc lỗi (nút "Dò") |
| `POST /api/station/control` | `{"var","val"}` → proxy tới `/control` của board |

**`/api/station/control` phải có allowlist `var`.** Nếu không, đây là một proxy
mở cho phép người bất kỳ trong LAN bắn tham số tùy ý vào firmware. Allowlist:
`darkmode`, `save`, `reset`, `pump_auto`, `pump_fill_ms`, `pump_settle_ms`,
`pump_flush_ms`, `pump_cooldown_ms`, `pump_fill_duty`, `pump_flush_duty`,
`pump_ramp_up_ms`, `pump_ramp_down_ms`, `device_id`. `var` ngoài danh sách →
400. Host đích **luôn** là `station_host` đã cấu hình, không nhận host từ
request body (chống biến endpoint này thành công cụ quét mạng nội bộ).

### 5.1 Backend web không còn thuần read-only

`web_plan.md` §2.2 và docstring `main.py` hiện khẳng định không route nào
mutating. Sau thay đổi này vẫn **không có PUT/PATCH/DELETE**, và **dữ liệu mẫu
vẫn append-only** — nhưng có thêm POST điều khiển. Phải sửa cả hai chỗ tài liệu
cho khớp, diễn đạt lại thành: *"append-only áp dụng cho dữ liệu mẫu; các route
POST điều khiển runner/trạm không đụng tới bản ghi đã có"*. Không để tài liệu
nói dối.

---

## 6. Dashboard

Panel điều khiển đặt ở đầu trang chủ, **ngoài** nhánh `{% if empty %}` — trạm
chưa có mẫu nào chính là lúc cần nút Bắt đầu nhất (test
`test_empty_dashboard_renders_empty_state` phải vẫn xanh).

| Thành phần | Gọi |
|---|---|
| Ô IP + nút **Dò** | `GET /api/station/probe` (thử `aqua-scope.local` trước) |
| Thẻ trạng thái board | device_id, firmware, RSSI, pha bơm, `prefs_saved` |
| Chọn **XEM / ĐO** | ghi vào `settings.json` |
| **Bắt đầu / Dừng** | `POST /api/runner/start|stop` |
| **Canh sáng buồng tối** + **Lưu vào flash** | `control` `darkmode` / `save` |
| **Bơm auto** on/off | `control` `pump_auto` |
| Thẻ live | ảnh + số hạt + chip nhãn của khung mới nhất, cập nhật từ poll |
| Dải cảnh báo | bơm chưa auto / AEC-AGC còn bật / mất kết nối board |

Poll `GET /api/runner/status` mỗi 1s bằng `fetch`, cập nhật DOM tại chỗ. Không
WebSocket, không thư viện JS ngoài — cùng tinh thần với quyết định "SVG server-
rendered thay Chart.js" của Module 5, dashboard chạy offline hoàn toàn trong LAN.

Ở chế độ ĐO, thẻ "Mẫu mới nhất" được cập nhật tại chỗ từ payload status. Các
bảng thống kê/lịch sử vẫn cập nhật khi tải lại trang — không cố render lại toàn
trang bằng JS.

**UI phải nói rõ chế độ XEM không ghi gì.** Nhãn thường trực trên panel, không
phải chú thích mờ: người vận hành thấy một khung đẹp ở chế độ XEM sẽ tưởng nó
đã vào sổ audit. Nút **Lưu mẫu này** đứng ngay đó cho trường hợp muốn giữ lại.

---

## 7. Firmware — chỉ thêm mDNS

`firmware/aqua_scope_station/aqua_scope_station.ino`, sau khi WiFi connect:

```cpp
#include <ESPmDNS.h>
...
if (MDNS.begin("aqua-scope")) {
  MDNS.addService("http", "tcp", 80);
  Serial.println("[mdns] http://aqua-scope.local");
}
```

Nạp lại một lần → hết cần Serial Monitor để lấy IP. Phải gọi **lại** sau mỗi lần
tự nối lại WiFi (firmware đã có nhánh reconnect) — nếu không, mất mDNS sau lần
rớt mạng đầu tiên và người dùng lại phải mở Serial Monitor, đúng thứ đang muốn
bỏ. Không đụng gì khác trong firmware.

Hạn chế phải ghi vào README: mDNS phụ thuộc mạng (một số router chặn multicast,
mạng khách/AP isolation). Ô nhập IP tay là đường dự phòng chính thức, không phải
tính năng thừa.

---

## 8. `start.bat`

Đặt ở gốc repo, bấm đúp chạy được:

1. Tìm `python` (báo lỗi rõ nếu chưa cài).
2. Tạo `.venv` ở gốc repo nếu chưa có; cài `web/requirements.txt` +
   `ml/requirements.txt` ở lần đầu (đánh dấu bằng file stamp để lần sau không
   cài lại).
3. `python -m uvicorn --app-dir web/backend app.main:app --host 0.0.0.0 --port 8000`
   từ gốc repo.
4. Mở trình duyệt tới `http://localhost:8000`.

`--host 0.0.0.0` để mở dashboard từ điện thoại trong cùng LAN. Đây là **rig
demo trong LAN, không có xác thực** — ghi rõ dòng cảnh báo này trong README,
đừng để ai vô tình cắm nó ra Internet.

`ml/requirements.txt` hiện kéo cả `ultralytics` + `tensorflow` (~2GB) dù đường
chạy thật đang là backend `roboflow` (không cần cái nào). Tách một
`ml/requirements-infer.txt` tối thiểu (`requests`, `pillow`, `numpy`) cho
`start.bat` dùng; `requirements.txt` đầy đủ để dành cho việc train/export.

---

## 9. Kiểm thử

Test mới:

**`ml/tests/test_station_client.py`** (mock `requests`)
- `capture_once()` thử lại đúng `retries` lần rồi raise.
- Body không bắt đầu `\xff\xd8` → `StationError` (giả lập captive portal).
- JPEG thiếu marker kết thúc → `StationError`.
- `/device` trả JSON không phải object → raise ngay, **không** retry.

**`web/backend/tests/test_runner.py`** (StationClient giả + detector giả)
- Một chu kỳ SETTLING kéo qua nhiều lần poll → **đúng 1** khung được chụp.
  Đây là test quan trọng nhất: sai chỗ này thì sổ audit đầy mẫu trùng.
- Chế độ XEM → `ingest_client.post` **không được gọi lần nào**.
- Chế độ ĐO → gọi đúng một lần mỗi chu kỳ, đúng `sample_code`.
- `/device` hỏng liên tiếp `MAX_CONSECUTIVE_ERRORS` lần → thread dừng, `error`
  có nội dung, `running == False`.
- Detector ném lỗi một khung → `failed == 1`, vòng lặp vẫn sống.
- `pump.auto == false` → không chụp, có cảnh báo trong `warnings`.

**`web/backend/tests/test_control_api.py`**
- `start` khi chưa có `station_host` → 400.
- `start` hai lần → lần hai 409.
- `stop` lúc đang idle → 200 (idempotent).
- `POST /api/station/control` với `var` ngoài allowlist → 400, và **không** có
  request nào đi tới board.
- `GET /api/runner/preview.jpg` khi chưa chạy → 404.

Test cũ (`test_ingest`, `test_module1_smoke`, `test_module3_read_api`,
`test_module5_pages`, toàn bộ `ml/tests/`) phải xanh y nguyên — đặc biệt
`test_module5_pages` vì panel mới chèn vào `index.html`.

Nghiệm thu tay trên rig thật (không tự động hóa được):
- [ ] Bấm đúp `start.bat` → dashboard mở, không phải gõ lệnh nào.
- [ ] Nút **Dò** tìm thấy board qua `aqua-scope.local`.
- [ ] Bật bơm auto + **Bắt đầu** (XEM) → ảnh live đổi theo từng chu kỳ bơm,
      `web/backend/data/` **không** có file mới.
- [ ] Chuyển **ĐO** → mỗi chu kỳ bơm sinh đúng 1 mẫu mới, chạy quá 5 mẫu
      (đây là vấn đề gốc user nêu — phải chạy tới khi bấm Dừng).
- [ ] Rút điện board giữa chừng → dashboard báo đỏ, runner tự dừng sau ~5s,
      web **không** sập.
- [ ] Cắm lại board, bấm **Bắt đầu** → chạy tiếp bình thường.

---

## 10. Ngoài phạm vi (cố ý)

- Xác thực/đăng nhập cho dashboard — rig demo trong LAN.
- Suy luận on-device trên ESP32-CAM — vẫn là hướng riêng (`ml/deploy_options.md`).
- Runner tự chạy lại sau khi restart server — trạng thái cố ý không bền vững.
- Điều khiển nhiều board cùng lúc — một trạm, một runner.
- Dọn rác tự động cho ảnh cũ ở chế độ ĐO — chạy dài sẽ đầy đĩa; ghi cảnh báo
  vào README, xử lý sau nếu thực sự cần.
