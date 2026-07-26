# Gộp workflow local về một tiến trình + suy luận liên tục — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bật một file `start.bat` là có dashboard điều khiển được cả trạm, chụp và suy luận liên tục theo từng chu kỳ bơm cho tới khi bấm Dừng — thay cho 6 bước tay hiện tại và giới hạn cứng `--count 5`.

**Architecture:** Vòng lặp chụp/suy luận chạy như một worker thread trong chính backend FastAPI, kích hoạt theo **cạnh pha bơm SETTLING** đọc từ `/device` của board. Worker dùng lại nguyên package `ml/infer/` (detector, mapper) và **POST ngược vào `/api/ingest` của chính nó** thay vì ghi thẳng DB, để không nhân đôi logic ghi sổ audit. Hai chế độ: XEM (không ghi gì) và ĐO (ghi đầy đủ).

**Tech Stack:** Python 3.11+, FastAPI + SQLModel + Jinja2 (đã có), `threading` (stdlib), `requests`, vanilla JS (không framework, không CDN), Arduino/ESP32 core 3.x cho firmware.

**Spec:** `docs/superpowers/specs/2026-07-26-one-process-local-workflow-design.md` — đọc trước khi bắt đầu.

## Global Constraints

- **Python 3.11+** (`ml/infer/config.py` dùng `tomllib` trong thư viện chuẩn).
- **Không thêm dependency mới nào** ngoài những gì đã có trong `web/requirements.txt`. Worker chỉ dùng `threading` + `requests`.
- **Không thư viện JS ngoài, không CDN, không webfont.** Dashboard phải chạy được trên LAN offline hoàn toàn (quyết định đã có từ Module 5).
- **Toàn bộ chuỗi hiển thị cho người dùng viết bằng tiếng Việt.** Comment trong code: theo file đang sửa (`ml/infer/` phần lớn tiếng Việt, `web/backend/app/` phần lớn tiếng Anh — bám theo file, đừng đổi ngôn ngữ của file có sẵn).
- **Không đổi hành vi công khai của `ml.infer` CLI.** Cờ `--count`, `--interval`, `--from-board`, `--dry-run`, `--check-config` giữ nguyên nghĩa. Toàn bộ `ml/tests/` hiện có phải xanh sau mỗi task.
- **Không thêm route PUT/PATCH/DELETE.** Dữ liệu mẫu vẫn append-only.
- **Chạy test:**
  - `ml/`: từ gốc repo → `python -m pytest ml/tests -q`
  - `web/`: từ `web/backend/` → `python -m pytest -q`
- **Không tự ý gọi `?var=darkmode`.** Runner chỉ được **cảnh báo** khi AEC/AGC còn bật (spec §2.4 — quyết định 2026-07-25).

---

## File Structure

**Tạo mới**

| File | Trách nhiệm |
|---|---|
| `ml/tests/fake_board.py` | ESP32-CAM giả bằng HTTP server thật, dùng chung cho nhiều file test |
| `ml/infer/station.py` | `StationClient` — nói chuyện HTTP với board (`/device`, `/capture`), không biết gì về vòng lặp |
| `ml/tests/test_station_client.py` | Test cho `StationClient` |
| `web/backend/app/settings_store.py` | Đọc/ghi `data/settings.json` (tham số vận hành) + validate |
| `web/backend/tests/test_settings_store.py` | Test cho settings store |
| `web/backend/app/runner.py` | `Runner` — máy trạng thái + worker thread + factory thật |
| `web/backend/tests/test_runner.py` | Test máy trạng thái (gọi `tick()` trực tiếp, không đụng thread) |
| `web/backend/tests/test_runner_thread.py` | Test vòng đời thread start/stop |
| `web/backend/app/routers/control.py` | `/api/runner/*`, `/api/station/*`, `/api/settings` |
| `web/backend/tests/test_control_api.py` | Test hợp đồng API điều khiển |
| `web/backend/app/templates/_control_panel.html` | Panel điều khiển trên dashboard |
| `web/backend/app/static/js/control_panel.js` | Poll trạng thái + nối nút bấm |
| `ml/requirements-infer.txt` | Dependency tối thiểu để CHẠY (không kéo ultralytics/tensorflow) |
| `start.bat` | Launcher một-cú-đúp ở gốc repo |

**Sửa**

| File | Sửa gì |
|---|---|
| `ml/infer/naming.py` | Thêm `station_sample_code()` + `unique_station_sample_code()` (chuyển từ `source.py`) |
| `ml/infer/source.py` | `Esp32CaptureSource` ủy quyền cho `StationClient`; bỏ code HTTP trùng lặp |
| `ml/tests/test_source.py` | Import `FakeBoard` từ `fake_board.py` thay vì tự định nghĩa |
| `web/backend/app/main.py` | Wire router `control`; sửa docstring "không route mutating" |
| `web/backend/app/templates/index.html` | Include panel điều khiển; nạp `control_panel.js` |
| `web/backend/app/static/css/style.css` | CSS cho panel điều khiển |
| `firmware/aqua_scope_station/aqua_scope_station.ino` | mDNS `aqua-scope.local` |
| `firmware/aqua_scope_station/README.md` | Ghi mDNS + workflow mới |
| `web_plan.md` | §2.2 — làm rõ append-only áp dụng cho dữ liệu mẫu |
| `ml/README.md` | Đường chạy chính giờ là dashboard |
| `README.md` (gốc) | Mục "Chạy thử nhanh" |

---

## Task 1: `StationClient` — tách tầng nói chuyện với board

**Files:**
- Create: `ml/tests/fake_board.py`
- Create: `ml/infer/station.py`
- Create: `ml/tests/test_station_client.py`
- Modify: `ml/tests/test_source.py:59-153` (bỏ `_FakeBoard`/`_DEVICE_JSON`/`_jpeg_bytes`, import từ chỗ mới)

**Interfaces:**
- Consumes: không có (task đầu tiên).
- Produces:
  - `ml.tests.fake_board.FakeBoard(capture_responses, device_response=None)` — context manager, thuộc tính `.host` (dạng `"127.0.0.1:<port>"`), `.capture_hits`; `ml.tests.fake_board.DEVICE_JSON` (dict), `ml.tests.fake_board.jpeg_bytes() -> bytes`
  - `ml.infer.station.StationError` (subclass `RuntimeError`)
  - `ml.infer.station.StationClient(host, *, timeout_s=20, retries=3)` với `.base_url: str`, `.read_device() -> dict`, `.capture_once() -> bytes`, `.device_info` (dict, đọc lười và nhớ lại), `.device_id -> str | None`

- [ ] **Step 1: Chuyển board giả ra file dùng chung**

Tạo `ml/tests/fake_board.py`. Nội dung: **cắt nguyên** `_FakeBoard`, `_DEVICE_JSON`, `_jpeg_bytes` từ `ml/tests/test_source.py` (dòng 45–153) sang, đổi tên bỏ dấu gạch dưới đầu (`FakeBoard`, `DEVICE_JSON`, `jpeg_bytes`), giữ nguyên toàn bộ docstring tiếng Việt và mọi nhánh `_respond` (`json`, `jpeg`, `html200`, `503`, `500`, `jpeg_truncated`) — không sửa một dòng logic nào.

Đầu file thêm docstring:

```python
"""ESP32-CAM giả bằng HTTP server THẬT, dùng chung cho test của source + station.

Dùng server thật chứ không mock `requests`: các ca hỏng ngoài đời quan trọng
nhất (body cụt, HTML kèm HTTP 200, server chết giữa burst) chỉ tái hiện được ở
tầng socket. Mock sẽ bỏ lọt đúng những ca đó.
"""
```

Trong `ml/tests/test_source.py`, xoá phần vừa cắt và thay bằng:

```python
from ml.tests.fake_board import DEVICE_JSON, FakeBoard, jpeg_bytes
```

rồi đổi mọi chỗ dùng `_FakeBoard` → `FakeBoard`, `_DEVICE_JSON` → `DEVICE_JSON`, `_jpeg_bytes()` → `jpeg_bytes()`. Chỗ `board._server.shutdown()` trong `test_server_dies_midway_yields_earlier_frames` giữ nguyên (`_server` vẫn là thuộc tính của `FakeBoard`).

- [ ] **Step 2: Chạy test cũ để chứng minh đây là refactor thuần**

Run: `python -m pytest ml/tests -q`
Expected: PASS toàn bộ, đúng số test như trước khi sửa. Nếu đỏ → bạn đã đổi logic khi chuyển, quay lại Step 1.

- [ ] **Step 3: Commit**

```bash
git add ml/tests/fake_board.py ml/tests/test_source.py
git commit -m "refactor(ml): tách board giả ra ml/tests/fake_board.py dùng chung"
```

- [ ] **Step 4: Viết test cho `StationClient` (phải fail)**

Tạo `ml/tests/test_station_client.py`:

```python
"""StationClient — tầng nói chuyện HTTP với board, tách khỏi vòng đếm khung.

Vì sao cần tách: Esp32CaptureSource trộn "cách nói chuyện với board" vào
"vòng lặp chụp N khung", nên không có cách nào lấy MỘT khung theo yêu cầu —
đó chính là lý do runner trên web không dùng lại được nó.
"""

import pytest

from ml.infer.station import StationClient, StationError
from ml.tests.fake_board import DEVICE_JSON, FakeBoard, jpeg_bytes


def test_read_device_returns_board_identity():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host)
        info = client.read_device()

    assert info["device_id"] == "aqua-cam-a1b2c3"
    assert info["pump"]["phase"] == "SETTLING"


def test_capture_once_returns_jpeg_bytes():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        body = StationClient(board.host).capture_once()

    assert body[:2] == b"\xff\xd8"
    assert body.rstrip()[-2:] == b"\xff\xd9"


def test_html_with_http_200_is_rejected():
    # Captive portal của router trả HTML kèm HTTP 200. Đẩy HTML vào detector
    # sẽ ra lỗi khó hiểu ở tận cuối pipeline, nên phải chặn ngay đây.
    with FakeBoard([("html200", None)],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host, retries=2)
        with pytest.raises(StationError):
            client.capture_once()
        assert board.capture_hits == 2   # đã thử lại đủ số lần


def test_truncated_jpeg_is_rejected():
    with FakeBoard([("jpeg_truncated", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host, retries=2)
        with pytest.raises(StationError):
            client.capture_once()
        assert board.capture_hits == 2


def test_capture_retries_then_gives_up_on_503():
    with FakeBoard([("503", None)],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host, retries=3)
        with pytest.raises(StationError):
            client.capture_once()
        assert board.capture_hits == 3


def test_capture_succeeds_after_one_failure():
    with FakeBoard([("503", None), ("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        body = StationClient(board.host, retries=2).capture_once()

    assert body[:2] == b"\xff\xd8"


def test_device_json_not_an_object_raises_without_retrying():
    # JSON hợp lệ nhưng SAI HÌNH DẠNG không phải lỗi thoáng qua — firmware trả
    # sai thì thử lại không giúp gì.
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", [1, 2, 3])) as board:
        with pytest.raises(StationError) as exc:
            StationClient(board.host, retries=3).read_device()
    assert "không phải object" in str(exc.value)


def test_unreachable_board_raises_station_error():
    with pytest.raises(StationError) as exc:
        StationClient("127.0.0.1:1", timeout_s=1, retries=1).read_device()
    assert "/device" in str(exc.value)


def test_device_id_property_reads_lazily_and_caches():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host)
        assert client.device_id == "aqua-cam-a1b2c3"
        assert client.device_id == "aqua-cam-a1b2c3"   # lần 2 lấy từ cache


def test_device_id_is_none_when_firmware_omits_it():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", {"firmware": "x"})) as board:
        assert StationClient(board.host).device_id is None


def test_host_with_scheme_is_accepted():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(f"http://{board.host}")
        assert client.base_url == f"http://{board.host}"
        assert client.read_device()["device_id"] == "aqua-cam-a1b2c3"
```

Test này cần `DEVICE_JSON` có khối `pump`, mà bản chuyển từ `test_source.py` chưa có. Thêm vào `ml/tests/fake_board.py`, trong `DEVICE_JSON`, ngay trước `"captures": 7`:

```python
    "pump": {"pwm_ready": True, "auto": True, "phase": "SETTLING", "duty": 0,
             "cycle_count": 3, "fill_ms": 5000, "settle_ms": 2000,
             "flush_ms": 5000, "cooldown_ms": 3000, "ramp_up_ms": 250,
             "ramp_down_ms": 350, "fill_duty": 55, "flush_duty": 100},
```

- [ ] **Step 5: Chạy test để xác nhận nó fail**

Run: `python -m pytest ml/tests/test_station_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ml.infer.station'`

- [ ] **Step 6: Viết `ml/infer/station.py`**

Toàn bộ logic **chuyển nguyên** từ `Esp32CaptureSource._read_device()` / `_capture_once()` (`ml/infer/source.py:91-149`). Không viết lại, không "cải tiến" — đây là code đã chạy thật với board thật.

```python
"""Tầng nói chuyện HTTP với firmware aqua_scope_station.

Tách khỏi source.py vì có HAI người dùng với nhu cầu khác nhau:
  * Esp32CaptureSource — chụp N khung rồi dừng (CLI `--count`)
  * Runner của backend web — chụp MỘT khung theo yêu cầu, lặp vô hạn

Trước đây hai việc này dính vào nhau trong một class, nên cái thứ hai không
làm được: vòng `for i in range(count)` là thứ duy nhất biết cách gọi /capture.
"""

import time

import requests

# Nghỉ giữa các lần thử lại /capture trong cùng một khung. Brownout WiFi (lý
# do phổ biến nhất khiến /capture hỏng) cần vài trăm ms mới hồi; thử lại liền
# tay trong vài mili-giây nhiều khả năng đụng đúng lúc nguồn còn sụt và hỏng
# cả retries lần liên tiếp.
CAPTURE_RETRY_BACKOFF_S = 0.3


class StationError(RuntimeError):
    """Board không dùng được (không tới được, hoặc trả về thứ không hợp lệ)."""


class StationClient:
    """Client HTTP tới một board aqua_scope_station.

    Không giữ trạng thái vòng lặp nào — mỗi phương thức là một lần gọi độc lập.
    """

    def __init__(self, host, *, timeout_s=20, retries=3):
        self.base_url = host if "://" in host else f"http://{host}"
        self.timeout_s = float(timeout_s)
        self.retries = max(1, int(retries))
        self._device_info = None

    # --- /device ---------------------------------------------------------

    def read_device(self):
        """Đọc /device, thử lại tối đa self.retries lần trước khi bỏ cuộc.

        Cùng một brownout WiFi lúc board mới cấp nguồn có thể làm /device
        timeout HOẶC trả JSON cụt — cùng một nguyên nhân, nên cùng một nhánh
        retry. Ngược lại, JSON hợp lệ nhưng SAI HÌNH DẠNG (không phải object)
        là firmware trả sai: thử lại không giúp gì nên raise ngay.
        """
        url = f"{self.base_url}/device"
        last_exc = None
        for _attempt in range(self.retries):
            try:
                resp = requests.get(url, timeout=self.timeout_s)
                resp.raise_for_status()
                info = resp.json()
            except (StationError, requests.RequestException) as exc:
                # Chỉ nuốt lỗi mạng/board (requests.exceptions.JSONDecodeError
                # là subclass của RequestException từ requests>=2.27). Lỗi lập
                # trình thật (AttributeError, TypeError, ...) phải nổi lên.
                last_exc = exc
                continue
            if not isinstance(info, dict):
                raise StationError(f"{url} trả về JSON không phải object: {info!r}")
            self._device_info = info
            return info
        raise StationError(
            f"không đọc được {url}: {last_exc}. Kiểm tra board đã bật, đúng IP, "
            f"và đã nạp firmware/aqua_scope_station."
        ) from last_exc

    @property
    def device_info(self):
        """Khối /device gần nhất; đọc lười ở lần gọi đầu."""
        if self._device_info is None:
            self.read_device()
        return self._device_info

    @property
    def device_id(self):
        """device_id board tự báo, hoặc None nếu firmware không khai."""
        value = self.device_info.get("device_id")
        return value if isinstance(value, str) and value else None

    # --- /capture --------------------------------------------------------

    def capture_once(self):
        """Một khung JPEG. Thử lại self.retries lần; hỏng hết thì raise."""
        last_error = None
        for attempt in range(self.retries):
            if attempt > 0:
                time.sleep(CAPTURE_RETRY_BACKOFF_S)
            try:
                return self._capture_attempt()
            except (StationError, requests.RequestException) as exc:
                last_error = exc
        raise StationError(f"chụp hỏng sau {self.retries} lần thử: {last_error}")

    def _capture_attempt(self):
        url = f"{self.base_url}/capture"
        resp = requests.get(url, timeout=self.timeout_s)
        if resp.status_code != 200:
            raise StationError(f"HTTP {resp.status_code}: {resp.text[:120]}")
        body = resp.content
        # Kiểm tra magic, KHÔNG tin Content-Type: captive portal của router trả
        # HTML kèm HTTP 200 và đủ loại header.
        if not body.startswith(b"\xff\xd8"):
            raise StationError(
                f"phản hồi không phải JPEG (bắt đầu bằng {body[:8]!r})")
        if not body.rstrip().endswith(b"\xff\xd9"):
            raise StationError("JPEG cụt (thiếu marker kết thúc)")
        return body
```

- [ ] **Step 7: Chạy test để xác nhận đã pass**

Run: `python -m pytest ml/tests/test_station_client.py -q`
Expected: PASS toàn bộ (11 test).

- [ ] **Step 8: Chạy cả bộ ml để chắc không vỡ gì**

Run: `python -m pytest ml/tests -q`
Expected: PASS toàn bộ.

- [ ] **Step 9: Commit**

```bash
git add ml/infer/station.py ml/tests/test_station_client.py ml/tests/fake_board.py
git commit -m "feat(ml): StationClient - tách tầng HTTP board khỏi vòng đếm khung"
```

---

## Task 2: `Esp32CaptureSource` ủy quyền cho `StationClient`

**Files:**
- Modify: `ml/infer/naming.py` (thêm 2 hàm ở cuối)
- Modify: `ml/infer/source.py:1-218` (bỏ code HTTP trùng, ủy quyền)
- Modify: `ml/tests/test_source.py` (thêm 1 test cho đường ủy quyền)

**Interfaces:**
- Consumes: `ml.infer.station.StationClient`, `ml.infer.station.StationError` (Task 1)
- Produces:
  - `ml.infer.naming.station_sample_code(captured_at) -> str` — dạng `S{yyyyMMdd}-{HHmmss}-{mmm}`
  - `ml.infer.naming.unique_station_sample_code(captured_at, used: set) -> str` — thêm mã vào `used` rồi trả về
  - `ml.infer.source.StationError` vẫn re-export được (code cũ `from ml.infer.source import StationError` không được gãy)

- [ ] **Step 1: Viết test cho hai hàm sinh mã (phải fail)**

Thêm vào cuối `ml/tests/test_naming.py`:

```python
from datetime import datetime, timezone

from ml.infer.naming import station_sample_code, unique_station_sample_code


def test_station_sample_code_format():
    dt = datetime(2026, 7, 26, 9, 5, 3, 456000, tzinfo=timezone.utc)
    assert station_sample_code(dt) == "S20260726-090503-456"


def test_unique_station_sample_code_suffixes_on_collision():
    # QUAN TRỌNG: ingest coi sample_code trùng là một bản RETRY và trả
    # already_exists KHÔNG báo lỗi. Hai khung trùng mã thì khung thứ hai biến
    # mất khỏi sổ audit mà không ai biết. Độ phân giải mili-giây của đồng hồ
    # KHÔNG đủ đảm bảo khác nhau, nên phải chống trùng bằng cấu trúc dữ liệu.
    dt = datetime(2026, 7, 26, 9, 5, 3, 456000, tzinfo=timezone.utc)
    used = set()

    a = unique_station_sample_code(dt, used)
    b = unique_station_sample_code(dt, used)
    c = unique_station_sample_code(dt, used)

    assert a == "S20260726-090503-456"
    assert b == "S20260726-090503-456-2"
    assert c == "S20260726-090503-456-3"
    assert used == {a, b, c}


def test_unique_station_sample_code_stays_ingest_safe():
    dt = datetime(2026, 7, 26, 9, 5, 3, 456000, tzinfo=timezone.utc)
    used = set()
    for _ in range(12):
        code = unique_station_sample_code(dt, used)
        assert 1 <= len(code) <= 64
        assert all(ch.isalnum() or ch in "._-" for ch in code)
```

- [ ] **Step 2: Chạy để xác nhận fail**

Run: `python -m pytest ml/tests/test_naming.py -q`
Expected: FAIL — `ImportError: cannot import name 'station_sample_code'`

- [ ] **Step 3: Thêm hai hàm vào `ml/infer/naming.py`**

Chuyển từ `source.py:183-217`, giữ nguyên docstring giải thích vì sao tồn tại:

```python
def station_sample_code(captured_at):
    """`S{yyyyMMdd}-{HHmmss}-{mmm}` từ thời điểm chụp.

    CHỈ định dạng theo giờ chụp — KHÔNG tự đảm bảo duy nhất giữa hai lần gọi
    liên tiếp (xem unique_station_sample_code()). Cùng dạng với mã do server
    sinh (web/backend/app/routers/ingest.py), và khớp sẵn
    ^[A-Za-z0-9._-]{1,64}$ nên hậu tố "-N" nếu có cũng không cần làm sạch thêm.
    """
    return (f"S{captured_at:%Y%m%d}-{captured_at:%H%M%S}-"
            f"{captured_at.microsecond // 1000:03d}")


def unique_station_sample_code(captured_at, used):
    """Mã cho một khung, đảm bảo KHÔNG trùng bất kỳ mã nào trong `used`.

    `used` là một set bị THAY ĐỔI TẠI CHỖ (mã mới được thêm vào).

    QUAN TRỌNG — vì sao không dùng thẳng station_sample_code():
    web/backend/app/routers/ingest.py coi sample_code trùng là một bản RETRY
    và trả về already_exists — KHÔNG báo lỗi. Nếu hai khung liên tiếp sinh
    trùng mã, khung thứ hai bị ingest âm thầm bỏ qua như thể nó là bản gửi lại
    của khung đầu, và dữ liệu mất khỏi sổ audit mà không ai biết. Độ phân giải
    mili-giây của đồng hồ hệ thống KHÔNG đủ đảm bảo khác nhau khi interval_s=0
    hoặc máy chạy đủ nhanh — nên phải chống trùng bằng cấu trúc dữ liệu ở đây,
    không dựa vào may mắn của đồng hồ.
    """
    base = station_sample_code(captured_at)
    code = base
    suffix = 2
    while code in used:
        code = f"{base}-{suffix}"
        suffix += 1
    used.add(code)
    return code
```

- [ ] **Step 4: Chạy để xác nhận pass**

Run: `python -m pytest ml/tests/test_naming.py -q`
Expected: PASS.

- [ ] **Step 5: Viết lại `ml/infer/source.py` để ủy quyền**

Thay toàn bộ `Esp32CaptureSource` (dòng 58–217) bằng:

```python
class Esp32CaptureSource:
    """Chụp N khung từ firmware aqua_scope_station (chế độ CLI --from-board).

    Chỉ còn giữ phần "vòng lặp đếm khung": mọi thứ liên quan tới HTTP nằm ở
    StationClient (ml/infer/station.py), dùng chung với runner của backend web.

    Hỏng NGAY ở /device: nếu không đọc được danh tính board thì mọi mẫu thu
    được sau đó cũng không truy nguyên được — thà dừng còn hơn ghi vào sổ audit
    những dòng không biết đến từ đâu.

    Ngược lại, một khung ảnh hỏng chỉ làm mất khung đó. Brownout khi WiFi TX
    trùng lúc chụp UXGA là chuyện thường ngày trên board này; để nó giết cả
    lượt đo là sai.
    """

    def __init__(self, host, *, count=1, interval_s=2.0, timeout_s=20, retries=3):
        self.client = StationClient(host, timeout_s=timeout_s, retries=retries)
        self.base_url = self.client.base_url
        self.count = int(count)
        self.interval_s = float(interval_s)
        # Mã đã phát ra trong lượt đo này (xem naming.unique_station_sample_code).
        self._used_sample_codes = set()
        # Số khung đã bỏ vì hỏng cả retries lần thử. cli.py đọc thuộc tính này
        # SAU KHI đã tiêu thụ hết source.frames() để cộng vào Summary và quyết
        # định exit code — nếu không, một lượt đo mà board brownout hết mọi
        # khung sẽ báo "0 failed" và RC=0 dù không mẫu nào được ghi vào sổ audit.
        self.skipped = 0
        self.device_info = self.client.read_device()

    @property
    def device_id(self):
        return self.client.device_id

    def frames(self):
        for i in range(self.count):
            if i > 0 and self.interval_s > 0:
                time.sleep(self.interval_s)
            try:
                body = self.client.capture_once()
            except (StationError, requests.RequestException) as exc:
                self.skipped += 1
                print(f"[warn] khung {i + 1}/{self.count} hỏng, bỏ qua: {exc}")
                continue

            captured_at = datetime.now(timezone.utc)
            yield Frame(
                image_bytes=body,
                sample_code=unique_station_sample_code(
                    captured_at, self._used_sample_codes),
                captured_at=captured_at,
                source_name=f"{self.base_url}/capture#{i + 1}",
            )
```

Sửa phần import ở đầu file thành:

```python
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .naming import sample_code_from_filename, unique_station_sample_code
from .station import StationClient, StationError   # StationError re-export: cli.py và
                                                   # test cũ import nó từ đây
```

Xoá hằng `_CAPTURE_RETRY_BACKOFF_S` (đã chuyển sang `station.py`) và hai hàm `_next_sample_code` / `_station_sample_code` (đã chuyển sang `naming.py`). Giữ nguyên `Frame` và `FolderSource`.

- [ ] **Step 6: Thêm test cho đường ủy quyền**

Thêm vào `ml/tests/test_source.py`:

```python
def test_capture_source_exposes_station_client():
    # Ủy quyền chứ không sao chép: sửa retry/validate ở StationClient là cả
    # CLI lẫn runner web cùng được, không phải sửa hai nơi.
    from ml.infer.station import StationClient

    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=1, interval_s=0)
        assert isinstance(src.client, StationClient)
        assert src.device_id == "aqua-cam-a1b2c3"
```

- [ ] **Step 7: Chạy toàn bộ bộ ml**

Run: `python -m pytest ml/tests -q`
Expected: PASS toàn bộ — **đặc biệt** `test_all_frames_503_are_counted_as_skipped`, `test_truncated_jpeg_frame_is_skipped`, `test_sample_code_does_not_collide_when_clock_stands_still` (ba test này bảo vệ đúng hành vi vừa chuyển chỗ).

Nếu `test_sample_code_does_not_collide_when_clock_stands_still` đỏ: nó `monkeypatch.setattr(source_module, "datetime", ...)`, mà `datetime.now()` vẫn được gọi trong `source.py` → vẫn đúng. Nếu đỏ thật thì bạn đã chuyển nhầm chỗ gọi `datetime.now()` sang `naming.py` — nó phải ở lại `source.py`.

- [ ] **Step 8: Commit**

```bash
git add ml/infer/source.py ml/infer/naming.py ml/tests/test_source.py ml/tests/test_naming.py
git commit -m "refactor(ml): Esp32CaptureSource ủy quyền StationClient, mã mẫu về naming.py"
```

---

## Task 3: `settings_store` — tham số vận hành đổi được từ web

**Files:**
- Create: `web/backend/app/settings_store.py`
- Create: `web/backend/tests/test_settings_store.py`

**Interfaces:**
- Consumes: `app.config.DATA_DIR` (đã có)
- Produces:
  - `app.settings_store.DEFAULTS: dict`
  - `app.settings_store.SettingsError(ValueError)`
  - `app.settings_store.load(path=None) -> dict` — luôn trả về đủ mọi khoá
  - `app.settings_store.save(patch: dict, path=None) -> dict` — merge + validate + ghi nguyên tử, trả về bản đầy đủ sau khi ghi

- [ ] **Step 1: Viết test (phải fail)**

Tạo `web/backend/tests/test_settings_store.py`:

```python
"""settings_store — tham số VẬN HÀNH (đổi theo ca), tách khỏi ml/config.toml.

Ranh giới: ml/config.toml giữ thứ lập trình viên sửa (backend suy luận, API
key, weights); file này giữ thứ người vận hành sửa qua web (IP board, lô, chế
độ). Hai file, hai người dùng, không chồng lấn.
"""

import json

import pytest

from app.settings_store import DEFAULTS, SettingsError, load, save


def test_load_returns_defaults_when_file_absent(tmp_path):
    assert load(tmp_path / "settings.json") == DEFAULTS


def test_save_merges_and_persists(tmp_path):
    path = tmp_path / "settings.json"

    out = save({"station_host": "192.168.1.50"}, path)

    assert out["station_host"] == "192.168.1.50"
    assert out["mode"] == DEFAULTS["mode"]        # khoá không đụng tới giữ nguyên
    assert load(path)["station_host"] == "192.168.1.50"


def test_save_twice_keeps_earlier_keys(tmp_path):
    path = tmp_path / "settings.json"
    save({"station_host": "10.0.0.9"}, path)
    save({"mode": "measure"}, path)

    out = load(path)
    assert out["station_host"] == "10.0.0.9"
    assert out["mode"] == "measure"


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    # Người dùng sửa tay hỏng file, hoặc mất điện giữa lúc ghi. Dashboard phải
    # mở được để họ nhập lại — sập ở đây là mất luôn đường sửa.
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")

    assert load(path) == DEFAULTS


def test_unknown_key_is_rejected(tmp_path):
    with pytest.raises(SettingsError) as exc:
        save({"nope": 1}, tmp_path / "settings.json")
    assert "nope" in str(exc.value)


def test_invalid_mode_is_rejected(tmp_path):
    with pytest.raises(SettingsError):
        save({"mode": "turbo"}, tmp_path / "settings.json")


def test_negative_px_per_mm_is_rejected(tmp_path):
    # px_per_mm <= 0 chảy thẳng vào size_mm của mọi hạt — sai lặng lẽ.
    with pytest.raises(SettingsError):
        save({"px_per_mm": -3}, tmp_path / "settings.json")


def test_px_per_mm_can_be_cleared_to_none(tmp_path):
    path = tmp_path / "settings.json"
    save({"px_per_mm": 14.0}, path)
    assert save({"px_per_mm": None}, path)["px_per_mm"] is None


def test_capture_delay_out_of_range_is_rejected(tmp_path):
    with pytest.raises(SettingsError):
        save({"capture_delay_ms": -1}, tmp_path / "settings.json")
    with pytest.raises(SettingsError):
        save({"capture_delay_ms": 60001}, tmp_path / "settings.json")


def test_station_host_rejects_url_with_path(tmp_path):
    # Host là host, không phải URL tuỳ ý: /api/station/control ghép nó thành
    # địa chỉ để gọi, nên nhận cả path/query là mở đường bắn request đi đâu tuỳ.
    with pytest.raises(SettingsError):
        save({"station_host": "evil.example.com/x?y=1"}, tmp_path / "settings.json")


def test_station_host_accepts_ip_hostname_and_port(tmp_path):
    path = tmp_path / "settings.json"
    for host in ("192.168.1.50", "aqua-scope.local", "192.168.1.50:8080"):
        assert save({"station_host": host}, path)["station_host"] == host


def test_station_host_is_trimmed(tmp_path):
    path = tmp_path / "settings.json"
    assert save({"station_host": "  10.0.0.9  "}, path)["station_host"] == "10.0.0.9"


def test_written_file_is_valid_json(tmp_path):
    path = tmp_path / "settings.json"
    save({"batch_lot": "LOT-001"}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["batch_lot"] == "LOT-001"
```

- [ ] **Step 2: Chạy để xác nhận fail**

Run (từ `web/backend/`): `python -m pytest tests/test_settings_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.settings_store'`

- [ ] **Step 3: Viết `web/backend/app/settings_store.py`**

```python
"""Operational settings the OPERATOR changes from the dashboard.

Deliberately separate from ml/config.toml, which holds what a *developer*
configures (inference backend, API keys, weights). Two files, two audiences,
no overlap — see the spec's §4 precedence table:

  * station_host / px_per_mm : this file wins; empty falls back to ml/config.toml
  * mode                     : the start request wins; this only remembers the
                               last choice so the dashboard pre-selects it

Never raises on a corrupt file: the dashboard must still open so the operator
can fix the bad value from the UI.
"""

import json
import os
import re
import tempfile

from . import config

SETTINGS_PATH = config.DATA_DIR / "settings.json"

DEFAULTS = {
    "station_host": "",        # empty -> fall back to ml/config.toml [station].host
    "mode": "preview",         # remembered UI default, not the runtime authority
    "batch_lot": None,
    "capture_delay_ms": 800,   # after the SETTLING edge, before capturing
    "px_per_mm": None,         # None -> ml/config.toml, then the placeholder default
}

ALLOWED_MODES = ("preview", "measure")
MAX_CAPTURE_DELAY_MS = 60_000

# Host only — no scheme, no path, no query. /api/station/control turns this into
# a URL it calls, so accepting a full URL here would turn that endpoint into an
# arbitrary-request tool. Public on purpose: control.py validates the probe host
# with the SAME rule, and one host rule beats two that can drift apart.
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,253}(:\d{1,5})?$")


class SettingsError(ValueError):
    """A rejected settings value, with a message meant for the operator."""


def load(path=None):
    path = SETTINGS_PATH if path is None else path
    data = dict(DEFAULTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in DEFAULTS:
        if key in raw:
            data[key] = raw[key]
    return data


def save(patch, path=None):
    path = SETTINGS_PATH if path is None else path
    unknown = set(patch) - set(DEFAULTS)
    if unknown:
        raise SettingsError(
            f"khoá không hợp lệ: {', '.join(sorted(unknown))}. "
            f"Chỉ nhận: {', '.join(sorted(DEFAULTS))}.")

    data = load(path)
    data.update(patch)
    _validate(data)

    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))
    return data


def _validate(data):
    host = data["station_host"]
    if host is None:
        data["station_host"] = ""
    else:
        if not isinstance(host, str):
            raise SettingsError("station_host phải là chuỗi.")
        host = host.strip()
        if host and not HOST_RE.match(host):
            raise SettingsError(
                f"station_host {host!r} không hợp lệ. Nhập IP hoặc tên máy "
                "(ví dụ 192.168.1.50 hoặc aqua-scope.local), không kèm "
                "http:// hay đường dẫn.")
        data["station_host"] = host

    if data["mode"] not in ALLOWED_MODES:
        raise SettingsError(
            f"mode phải là một trong {ALLOWED_MODES}, nhận được {data['mode']!r}.")

    lot = data["batch_lot"]
    if lot is not None:
        if not isinstance(lot, str):
            raise SettingsError("batch_lot phải là chuỗi hoặc để trống.")
        lot = lot.strip()
        data["batch_lot"] = lot or None

    delay = data["capture_delay_ms"]
    if not isinstance(delay, int) or isinstance(delay, bool):
        raise SettingsError("capture_delay_ms phải là số nguyên (mili-giây).")
    if not 0 <= delay <= MAX_CAPTURE_DELAY_MS:
        raise SettingsError(
            f"capture_delay_ms phải trong khoảng 0–{MAX_CAPTURE_DELAY_MS} ms.")

    px = data["px_per_mm"]
    if px is not None:
        if isinstance(px, bool) or not isinstance(px, (int, float)):
            raise SettingsError("px_per_mm phải là số hoặc để trống.")
        if px <= 0:
            # <= 0 không phải tỉ lệ vật lý hợp lệ và sẽ chảy thẳng vào size_mm
            # của mọi hạt.
            raise SettingsError("px_per_mm phải lớn hơn 0 (hoặc để trống).")
        data["px_per_mm"] = float(px)


def _write_atomic(path, text):
    """Ghi qua file tạm rồi os.replace — mất điện giữa chừng không để lại
    file JSON cụt mà lần mở sau phải đoán."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Chạy để xác nhận pass**

Run (từ `web/backend/`): `python -m pytest tests/test_settings_store.py -q`
Expected: PASS (13 test).

- [ ] **Step 5: Commit**

```bash
git add web/backend/app/settings_store.py web/backend/tests/test_settings_store.py
git commit -m "feat(web): settings_store - tham số vận hành sửa được từ dashboard"
```

---

## Task 4: `Runner` — máy trạng thái (một `tick()`, không thread)

**Files:**
- Create: `web/backend/app/runner.py`
- Create: `web/backend/tests/test_runner.py`

**Interfaces:**
- Consumes: `ml.infer.mapper.build_metadata`, `ml.infer.naming.unique_station_sample_code` (Task 2), `app.settings_store` (Task 3)
- Produces:
  - `app.runner.RunnerBusy(RuntimeError)`, `app.runner.RunnerConfigError(RuntimeError)`
  - `app.runner.RunnerConfig(mode, station_host, capture_delay_s, px_per_mm, batch_lot, api_url, device_id_override=None)` — dataclass
  - `app.runner.Runner(*, station_factory, detector_factory, poster, monotonic=time.monotonic, utcnow=...)`
    - `.arm(cfg) -> None` — dựng station + detector, đặt `running=True`, **không** tạo thread
    - `.tick() -> None` — đúng MỘT vòng poll
    - `.snapshot() -> dict`
    - `.disarm() -> None`
    - `.keep() -> dict` — ghi khung XEM đang giữ vào sổ audit
  - Hằng: `app.runner.POLL_INTERVAL_S = 0.5`, `MAX_CONSECUTIVE_ERRORS = 10`, `SETTLING = "SETTLING"`

**Vì sao tách `tick()` khỏi thread:** máy trạng thái là thứ dễ sai nhất (chụp 4 lần một chu kỳ, hoặc không chụp lần nào) và cũng là thứ khó test nhất nếu trộn với `threading` + `sleep`. Test gọi `tick()` tay với đồng hồ giả → xác định, không flaky. Thread là việc của Task 5.

- [ ] **Step 1: Viết test (phải fail)**

Tạo `web/backend/tests/test_runner.py`:

```python
"""Runner — máy trạng thái chụp theo cạnh pha bơm.

Gọi tick() trực tiếp với đồng hồ giả: máy trạng thái phải xác định, không phụ
thuộc thread timing. Vòng đời thread nằm ở test_runner_thread.py.
"""

from datetime import datetime, timezone

import pytest

from app.runner import (MAX_CONSECUTIVE_ERRORS, Runner, RunnerConfig)


class FakeDetection:
    def __init__(self, label="fragment"):
        self.bbox_xywh = (10, 20, 30, 40)
        self.class_name = label
        self.confidence = 0.9


class FakeResult:
    def __init__(self, n=2):
        self.detections = [FakeDetection() for _ in range(n)]
        self.image_width = 1600
        self.image_height = 1200


class FakeDetector:
    def __init__(self, n=2, raises=False):
        self.n = n
        self.raises = raises
        self.calls = 0

    def run(self, image_bytes):
        self.calls += 1
        if self.raises:
            raise RuntimeError("detector nổ")
        return FakeResult(self.n)


class FakeStation:
    """Board giả ở mức đối tượng: test tự lái pha bơm qua .phase."""

    def __init__(self, phase="FILLING", auto=True, aec=0, agc=0, settle_ms=2000):
        self.phase = phase
        self.auto = auto
        self.aec = aec
        self.agc = agc
        self.settle_ms = settle_ms
        self.device_error = None
        self.capture_error = None
        self.captures = 0
        self.device_id = "aqua-cam-test"

    def read_device(self):
        if self.device_error:
            raise self.device_error
        return {
            "device_id": self.device_id,
            "firmware": "aqua_scope_station/1.0.0",
            "camera": {"aec": self.aec, "agc": self.agc,
                       "width": 1600, "height": 1200},
            "pump": {"auto": self.auto, "phase": self.phase, "pwm_ready": True,
                     "settle_ms": self.settle_ms, "cycle_count": 1},
        }

    def capture_once(self):
        if self.capture_error:
            raise self.capture_error
        self.captures += 1
        return b"\xff\xd8fake-jpeg\xff\xd9"


class FakePoster:
    class Result:
        def __init__(self, status="created"):
            self.status = status
            self.http_status = 201
            self.detail = ""

    def __init__(self, status="created"):
        self.status = status
        self.calls = []

    def __call__(self, api_url, metadata, image_bytes, image_name):
        self.calls.append((api_url, metadata, image_bytes, image_name))
        return self.Result(self.status)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def make_runner(station, detector=None, poster=None, clock=None, mode="measure",
                capture_delay_s=0.8):
    clock = clock or FakeClock()
    poster = poster or FakePoster()
    runner = Runner(
        station_factory=lambda host: station,
        detector_factory=lambda: detector or FakeDetector(),
        poster=poster,
        monotonic=clock,
    )
    cfg = RunnerConfig(
        mode=mode,
        station_host="board.local",
        capture_delay_s=capture_delay_s,
        px_per_mm=14.0,
        batch_lot="LOT-1",
        api_url="http://localhost:8000",
    )
    runner.arm(cfg)
    return runner, clock, poster


def drive_one_cycle(runner, station, clock, settle_ticks=4):
    """Một chu kỳ bơm: FILLING -> SETTLING (nhiều tick) -> FLUSHING."""
    station.phase = "FILLING"
    runner.tick()
    station.phase = "SETTLING"
    for _ in range(settle_ticks):
        runner.tick()
        clock.advance(0.5)
    station.phase = "FLUSHING"
    runner.tick()


def test_one_capture_per_settling_cycle():
    # TEST QUAN TRỌNG NHẤT của plan này. Pha SETTLING kéo dài nhiều lần poll;
    # bắt TRẠNG THÁI thay vì CẠNH sẽ chụp 4 lần cho một chu kỳ bơm và nhồi sổ
    # audit toàn mẫu trùng của cùng một lần lấy nước.
    station = FakeStation()
    runner, clock, poster = make_runner(station)

    drive_one_cycle(runner, station, clock)

    assert station.captures == 1
    assert len(poster.calls) == 1
    assert runner.snapshot()["counters"]["cycles"] == 1


def test_three_cycles_give_three_samples():
    station = FakeStation()
    runner, clock, poster = make_runner(station)

    for _ in range(3):
        drive_one_cycle(runner, station, clock)

    assert station.captures == 3
    assert runner.snapshot()["counters"]["written"] == 3
    # Mã mẫu phải khác nhau, nếu không ingest coi các khung sau là bản retry
    codes = [call[1]["sample_code"] for call in poster.calls]
    assert len(set(codes)) == 3


def test_no_capture_before_the_delay_elapses():
    station = FakeStation()
    runner, clock, poster = make_runner(station, capture_delay_s=0.8)

    station.phase = "FILLING"
    runner.tick()
    station.phase = "SETTLING"
    runner.tick()              # cạnh: mới hẹn giờ, chưa tới lúc chụp

    assert station.captures == 0

    clock.advance(0.9)
    runner.tick()

    assert station.captures == 1


def test_preview_mode_never_posts():
    station = FakeStation()
    runner, clock, poster = make_runner(station, mode="preview")

    drive_one_cycle(runner, station, clock)

    assert station.captures == 1          # vẫn chụp và suy luận
    assert poster.calls == []             # nhưng KHÔNG ghi gì
    assert runner.snapshot()["counters"]["written"] == 0
    assert runner.snapshot()["last"]["written"] is False


def test_preview_frame_is_kept_in_memory_for_the_browser():
    station = FakeStation()
    runner, clock, _ = make_runner(station, mode="preview")

    drive_one_cycle(runner, station, clock)

    assert runner.preview_jpeg() == b"\xff\xd8fake-jpeg\xff\xd9"


def test_keep_writes_the_held_preview_frame():
    station = FakeStation()
    runner, clock, poster = make_runner(station, mode="preview")
    drive_one_cycle(runner, station, clock)

    out = runner.keep()

    assert len(poster.calls) == 1
    assert out["sample_code"] == poster.calls[0][1]["sample_code"]
    assert runner.snapshot()["counters"]["written"] == 1


def test_keep_without_a_preview_frame_raises():
    station = FakeStation()
    runner, _, _ = make_runner(station, mode="preview")

    with pytest.raises(RuntimeError):
        runner.keep()


def test_metadata_carries_lot_calibration_and_board_identity():
    station = FakeStation()
    runner, clock, poster = make_runner(station)

    drive_one_cycle(runner, station, clock)

    meta = poster.calls[0][1]
    assert meta["batch_lot"] == "LOT-1"
    assert meta["px_per_mm"] == 14.0
    assert meta["device_id"] == "aqua-cam-test"   # tên board tự báo, không phải hằng
    assert meta["device"]["firmware"] == "aqua_scope_station/1.0.0"
    assert len(meta["particles"]) == 2


def test_device_errors_stop_the_runner_after_the_limit():
    # Quay vô tận trong im lặng là kiểu hỏng tệ nhất cho một trạm QC.
    station = FakeStation()
    station.device_error = OSError("mạng chết")
    runner, _, _ = make_runner(station)

    for _ in range(MAX_CONSECUTIVE_ERRORS - 1):
        runner.tick()
        assert runner.snapshot()["running"] is True

    runner.tick()

    snap = runner.snapshot()
    assert snap["running"] is False
    assert "mạng chết" in snap["error"]


def test_one_good_read_resets_the_error_streak():
    station = FakeStation()
    runner, _, _ = make_runner(station)

    station.device_error = OSError("chớp mạng")
    for _ in range(MAX_CONSECUTIVE_ERRORS - 1):
        runner.tick()
    station.device_error = None
    runner.tick()

    for _ in range(MAX_CONSECUTIVE_ERRORS - 1):
        station.device_error = OSError("chớp mạng")
        runner.tick()

    assert runner.snapshot()["running"] is True


def test_capture_failure_counts_and_keeps_running():
    station = FakeStation()
    station.capture_error = RuntimeError("JPEG cụt")
    runner, clock, poster = make_runner(station)

    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    assert snap["counters"]["failed"] == 1
    assert snap["running"] is True        # một khung hỏng không giết lượt đo
    assert poster.calls == []


def test_detector_failure_counts_and_keeps_running():
    station = FakeStation()
    runner, clock, poster = make_runner(station, detector=FakeDetector(raises=True))

    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    assert snap["counters"]["failed"] == 1
    assert snap["running"] is True
    assert poster.calls == []


def test_failed_post_counts_as_failed_not_written():
    station = FakeStation()
    poster = FakePoster(status="failed")
    runner, clock, _ = make_runner(station, poster=poster)

    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    assert snap["counters"]["written"] == 0
    assert snap["counters"]["failed"] == 1


def test_already_exists_counts_as_written():
    station = FakeStation()
    poster = FakePoster(status="already_exists")
    runner, clock, _ = make_runner(station, poster=poster)

    drive_one_cycle(runner, station, clock)

    assert runner.snapshot()["counters"]["written"] == 1


def test_warns_when_pump_is_not_in_auto():
    # Bơm không auto -> pha không đổi -> không khung nào được chụp. Đúng, nhưng
    # nếu để im thì trông y hệt "hệ thống treo".
    station = FakeStation(auto=False)
    runner, _, _ = make_runner(station)

    runner.tick()

    assert any("auto" in w for w in runner.snapshot()["warnings"])


def test_warns_when_aec_or_agc_still_on():
    station = FakeStation(aec=1)
    runner, _, _ = make_runner(station)

    runner.tick()

    assert any("AEC" in w for w in runner.snapshot()["warnings"])


def test_warns_when_capture_delay_exceeds_settle_window():
    station = FakeStation(settle_ms=500)
    runner, _, _ = make_runner(station, capture_delay_s=0.8)

    runner.tick()

    assert any("FLUSHING" in w for w in runner.snapshot()["warnings"])


def test_no_warnings_on_a_healthy_board():
    station = FakeStation()
    runner, _, _ = make_runner(station)

    runner.tick()

    assert runner.snapshot()["warnings"] == []


def test_snapshot_is_a_copy_not_live_state():
    # Handler HTTP đọc snapshot trong khi worker đang ghi; trả về tham chiếu
    # sống là mở đường cho dữ liệu đọc dở.
    station = FakeStation()
    runner, clock, _ = make_runner(station)
    drive_one_cycle(runner, station, clock)

    snap = runner.snapshot()
    snap["counters"]["written"] = 999

    assert runner.snapshot()["counters"]["written"] == 1
```

- [ ] **Step 2: Chạy để xác nhận fail**

Run (từ `web/backend/`): `python -m pytest tests/test_runner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.runner'`

- [ ] **Step 3: Viết `web/backend/app/runner.py` (phần máy trạng thái)**

```python
"""The capture/inference worker that drives one measurement per pump cycle.

Why this lives inside the web app instead of staying a CLI: the operator needs
Start/Stop buttons and a live view, and a second process controlled from a
second terminal is exactly the friction this replaces.

Two deliberate shapes here:

  * `tick()` is ONE poll iteration and does no sleeping. The thread (start/stop)
    is a thin wrapper around it. The state machine is the part that is easy to
    get wrong — capture four times per pump cycle, or never — so it is testable
    on its own with a fake clock.
  * results are POSTed back into this app's own /api/ingest rather than written
    to the DB directly. Ingest already owns validation, sample_code generation,
    idempotency and the atomic image+rows write; duplicating that here would
    mean every future fix has to land in two places, and the audit trail is the
    one thing that must not drift.
"""

import copy
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _ensure_repo_on_path():
    """Put the repo root on sys.path so `import ml.infer...` works.

    The backend normally runs with cwd=web/backend, where `ml` is not
    importable. start.bat launches uvicorn from the repo root so both paths
    resolve, but the tests (and anyone starting the server their own way) do
    not — so fix it here rather than making the import order depend on how the
    process was launched.
    """
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_on_path()

from ml.infer.mapper import build_metadata          # noqa: E402
from ml.infer.naming import unique_station_sample_code  # noqa: E402

POLL_INTERVAL_S = 0.5
# ~5s of silence at the default poll interval. Long enough to ride out a WiFi
# hiccup, short enough that a dead board is reported instead of spun on.
MAX_CONSECUTIVE_ERRORS = 10
SETTLING = "SETTLING"


class RunnerBusy(RuntimeError):
    """Start requested while a run is already in progress."""


class RunnerConfigError(RuntimeError):
    """The runner cannot start: missing host, unusable detector config, ..."""


@dataclass
class RunnerConfig:
    mode: str                 # "preview" | "measure"
    station_host: str
    capture_delay_s: float
    px_per_mm: float
    batch_lot: Optional[str]
    api_url: str
    device_id_override: Optional[str] = None


def _utcnow():
    return datetime.now(timezone.utc)


class Runner:
    def __init__(self, *, station_factory, detector_factory, poster,
                 monotonic=time.monotonic, utcnow=_utcnow):
        self._station_factory = station_factory
        self._detector_factory = detector_factory
        self._poster = poster
        self._monotonic = monotonic
        self._utcnow = utcnow

        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = None

        self._station = None
        self._detector = None
        self._cfg = None
        self._reset_state()

    # --- lifecycle (thread-free half) ------------------------------------

    def _reset_state(self):
        self._running = False
        self._device = None
        self._prev_phase = None
        self._pending_capture_at = None
        self._consecutive_errors = 0
        self._error = None
        self._warnings = []
        self._counters = {"cycles": 0, "captured": 0, "written": 0, "failed": 0}
        self._last = None
        self._used_codes = set()
        self._preview_jpeg = None
        self._preview_metadata = None

    def arm(self, cfg):
        """Build the station + detector and mark the runner live.

        Separate from start() so the state machine can be exercised without a
        thread. start() (below) is arm() + a thread that calls tick().
        """
        if self._running:
            raise RunnerBusy("runner đang chạy rồi.")
        if not cfg.station_host:
            raise RunnerConfigError(
                "chưa có địa chỉ board. Nhập IP hoặc bấm Dò trên dashboard.")
        self._reset_state()
        self._cfg = cfg
        self._station = self._station_factory(cfg.station_host)
        self._detector = self._detector_factory()
        self._running = True

    def disarm(self):
        self._running = False

    # --- one poll iteration ----------------------------------------------

    def tick(self):
        try:
            device = self._station.read_device()
        except Exception as exc:       # noqa: BLE001 - any board failure is the same here
            self._consecutive_errors += 1
            self._error = f"không đọc được /device: {exc}"
            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self._running = False
                self._error = (
                    f"đã dừng: {MAX_CONSECUTIVE_ERRORS} lần liên tiếp không đọc "
                    f"được /device ({exc}). Kiểm tra board còn điện và còn trong mạng.")
            return

        self._consecutive_errors = 0
        self._error = None
        self._device = device
        self._warnings = self._compute_warnings(device)

        phase = (device.get("pump") or {}).get("phase")
        # CẠNH, không phải trạng thái: pha SETTLING kéo dài nhiều lần poll, bắt
        # trạng thái sẽ chụp nhiều lần cho cùng một lần lấy nước.
        if phase == SETTLING and self._prev_phase != SETTLING:
            self._counters["cycles"] += 1
            self._pending_capture_at = self._monotonic() + self._cfg.capture_delay_s
        self._prev_phase = phase

        if (self._pending_capture_at is not None
                and self._monotonic() >= self._pending_capture_at):
            self._pending_capture_at = None
            self._capture_and_process(device)

    def _capture_and_process(self, device):
        try:
            jpeg = self._station.capture_once()
        except Exception as exc:       # noqa: BLE001
            self._counters["failed"] += 1
            self._error = f"chụp hỏng: {exc}"
            return
        self._counters["captured"] += 1

        try:
            result = self._detector.run(jpeg)
        except Exception as exc:       # noqa: BLE001
            self._counters["failed"] += 1
            self._error = f"suy luận hỏng: {exc}"
            return

        captured_at = self._utcnow()
        code = unique_station_sample_code(captured_at, self._used_codes)
        metadata = build_metadata(
            detections=result.detections,
            image_width=result.image_width,
            image_height=result.image_height,
            sample_code=code,
            captured_at=captured_at,
            device_id=self._resolve_device_id(device),
            px_per_mm=self._cfg.px_per_mm,
            batch_lot=self._cfg.batch_lot,
            device_info=device,
        )

        if self._cfg.mode == "measure":
            written = self._post(metadata, jpeg, code)
        else:
            # XEM: giữ trong RAM cho trình duyệt xem, không chạm đĩa.
            self._preview_jpeg = jpeg
            self._preview_metadata = metadata
            written = False

        self._last = {
            "sample_code": code,
            "particle_count": len(metadata["particles"]),
            "labels": _label_counts(metadata["particles"]),
            "at": captured_at.isoformat(),
            "written": written,
        }

    def _post(self, metadata, jpeg, code):
        res = self._poster(self._cfg.api_url, metadata, jpeg, f"{code}.jpg")
        if res.status in ("created", "already_exists"):
            self._counters["written"] += 1
            return True
        self._counters["failed"] += 1
        self._error = f"ghi sổ hỏng ({res.http_status}): {res.detail}"
        return False

    def _resolve_device_id(self, device):
        """Tên board tự báo thắng hằng trong config; cờ tay thắng cả hai."""
        if self._cfg.device_id_override:
            return self._cfg.device_id_override
        board_id = device.get("device_id")
        return board_id if isinstance(board_id, str) and board_id else "pc-infer"

    def _compute_warnings(self, device):
        out = []
        pump = device.get("pump") or {}
        cam = device.get("camera") or {}

        if pump.get("auto") is False:
            out.append("Bơm chưa ở chế độ auto — sẽ không có khung nào được chụp.")
        if pump.get("pwm_ready") is False:
            out.append("Bơm báo pwm_ready=false — firmware không gắn được PWM, "
                       "bơm sẽ không chạy.")
        if cam.get("aec") or cam.get("agc"):
            out.append("AEC/AGC đang bật — nền sẽ cháy trắng và nuốt mất hạt. "
                       "Bấm 'Canh sáng buồng tối' trước khi đo.")
        settle_ms = pump.get("settle_ms")
        delay_ms = int(self._cfg.capture_delay_s * 1000)
        if isinstance(settle_ms, int) and delay_ms >= settle_ms:
            out.append(f"Độ trễ chụp ({delay_ms}ms) ≥ thời gian lắng ({settle_ms}ms) "
                       "— khung sẽ rơi sang pha FLUSHING lúc nước đang chảy.")
        return out

    # --- preview ----------------------------------------------------------

    def preview_jpeg(self):
        return self._preview_jpeg

    def keep(self):
        """Ghi khung XEM đang giữ vào sổ audit (nút 'Lưu mẫu này')."""
        if self._preview_metadata is None or self._preview_jpeg is None:
            raise RuntimeError("chưa có khung nào để lưu.")
        metadata = self._preview_metadata
        code = metadata["sample_code"]
        written = self._post(metadata, self._preview_jpeg, code)
        if self._last is not None and self._last["sample_code"] == code:
            self._last["written"] = written
        return {"sample_code": code, "written": written}

    # --- read model -------------------------------------------------------

    def snapshot(self):
        """A deep copy: HTTP handlers read this while the worker writes."""
        return copy.deepcopy({
            "running": self._running,
            "mode": self._cfg.mode if self._cfg else None,
            "station_host": self._cfg.station_host if self._cfg else "",
            "device": self._device,
            "phase": self._prev_phase,
            "counters": self._counters,
            "last": self._last,
            "error": self._error,
            "warnings": self._warnings,
            "has_preview": self._preview_jpeg is not None,
        })


def _label_counts(particles):
    counts = {}
    for p in particles:
        counts[p["label"]] = counts.get(p["label"], 0) + 1
    return counts
```

- [ ] **Step 4: Chạy để xác nhận pass**

Run (từ `web/backend/`): `python -m pytest tests/test_runner.py -q`
Expected: PASS (20 test).

- [ ] **Step 5: Commit**

```bash
git add web/backend/app/runner.py web/backend/tests/test_runner.py
git commit -m "feat(web): Runner - máy trạng thái chụp một khung mỗi chu kỳ bơm"
```

---

## Task 5: Vòng đời thread + factory thật + singleton

**Files:**
- Modify: `web/backend/app/runner.py` (thêm vào cuối, và `start`/`stop` vào class `Runner`)
- Create: `web/backend/tests/test_runner_thread.py`

**Interfaces:**
- Consumes: `Runner.arm()`, `Runner.tick()`, `Runner.disarm()` (Task 4); `ml.infer.station.StationClient` (Task 1); `app.settings_store.load()` (Task 3)
- Produces:
  - `Runner.start(cfg, poll_interval_s=POLL_INTERVAL_S) -> None`
  - `Runner.stop(timeout=5.0) -> None` — idempotent
  - `app.runner.default_station_factory(host) -> StationClient`
  - `app.runner.default_detector_factory() -> detector` (raise `RunnerConfigError` khi config thiếu)
  - `app.runner.build_config_from_settings() -> RunnerConfig` — gộp `settings.json` + `ml/config.toml` theo đúng thứ tự ưu tiên của spec §4
  - `app.runner.RUNNER` — singleton dùng bởi router
  - `app.runner.get_runner() -> Runner` — điểm để test override

- [ ] **Step 1: Viết test vòng đời thread (phải fail)**

Tạo `web/backend/tests/test_runner_thread.py`:

```python
"""Vòng đời thread của Runner. Máy trạng thái đã được test riêng ở
test_runner.py — ở đây chỉ hỏi: thread có chạy, có dừng, và có từ chối chạy
hai lần không.
"""

import time

import pytest

from app.runner import Runner, RunnerBusy, RunnerConfig, RunnerConfigError
from tests.test_runner import FakeDetector, FakePoster, FakeStation


def make_cfg(host="board.local", mode="preview"):
    return RunnerConfig(
        mode=mode,
        station_host=host,
        capture_delay_s=0.0,
        px_per_mm=14.0,
        batch_lot=None,
        api_url="http://localhost:8000",
    )


def make_runner(station):
    return Runner(
        station_factory=lambda host: station,
        detector_factory=FakeDetector,
        poster=FakePoster(),
    )


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_start_runs_ticks_in_background_then_stop_ends_them():
    station = FakeStation(phase="SETTLING")
    runner = make_runner(station)

    runner.start(make_cfg(), poll_interval_s=0.01)
    assert wait_until(lambda: station.captures >= 1), "thread không chạy tick"
    runner.stop()

    assert runner.snapshot()["running"] is False
    settled = station.captures
    time.sleep(0.1)
    assert station.captures == settled, "thread vẫn chạy sau khi stop"


def test_start_twice_raises_busy():
    station = FakeStation()
    runner = make_runner(station)
    runner.start(make_cfg(), poll_interval_s=0.01)
    try:
        with pytest.raises(RunnerBusy):
            runner.start(make_cfg(), poll_interval_s=0.01)
    finally:
        runner.stop()


def test_stop_when_idle_is_a_no_op():
    runner = make_runner(FakeStation())
    runner.stop()      # không được ném
    assert runner.snapshot()["running"] is False


def test_start_without_host_raises_config_error():
    runner = make_runner(FakeStation())
    with pytest.raises(RunnerConfigError):
        runner.start(make_cfg(host=""), poll_interval_s=0.01)


def test_start_again_after_stop_works():
    station = FakeStation(phase="SETTLING")
    runner = make_runner(station)

    runner.start(make_cfg(), poll_interval_s=0.01)
    wait_until(lambda: station.captures >= 1)
    runner.stop()
    first = station.captures

    runner.start(make_cfg(), poll_interval_s=0.01)
    assert wait_until(lambda: station.captures > first)
    runner.stop()


def test_thread_stops_itself_when_the_board_dies():
    station = FakeStation()
    station.device_error = OSError("board rút điện")
    runner = make_runner(station)

    runner.start(make_cfg(), poll_interval_s=0.01)

    assert wait_until(lambda: runner.snapshot()["running"] is False), \
        "runner phải tự dừng khi board chết, không quay vô tận"
    runner.stop()
    assert "board rút điện" in runner.snapshot()["error"]
```

- [ ] **Step 2: Chạy để xác nhận fail**

Run (từ `web/backend/`): `python -m pytest tests/test_runner_thread.py -q`
Expected: FAIL — `ImportError: cannot import name 'RunnerConfigError'` hoặc `AttributeError: 'Runner' object has no attribute 'start'`

- [ ] **Step 3: Thêm `start`/`stop` vào class `Runner`**

Chèn vào `Runner`, ngay sau `disarm()`:

```python
    def start(self, cfg, poll_interval_s=POLL_INTERVAL_S):
        """arm() + một thread nền gọi tick() cho tới khi stop()."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RunnerBusy("runner đang chạy rồi.")
            self.arm(cfg)                       # ném RunnerConfigError nếu thiếu host
            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(self._stop_event, poll_interval_s),
                name="aqua-runner",
                daemon=True,                    # không giữ tiến trình sống khi tắt server
            )
            self._thread.start()

    def stop(self, timeout=5.0):
        """Idempotent: gọi lúc đang idle là no-op."""
        with self._lock:
            thread, event = self._thread, self._stop_event
            self._thread = self._stop_event = None
        if event is not None:
            event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self.disarm()

    def _run_loop(self, stop_event, poll_interval_s):
        while not stop_event.is_set():
            self.tick()
            if not self._running:
                # tick() đã tự dừng (board chết quá lâu) — thoát chứ đừng quay
                # tiếp trên một station không dùng được nữa.
                break
            stop_event.wait(poll_interval_s)
```

Lưu ý: `arm()` được gọi bên trong `self._lock`, và `arm()` **không** tự lấy lock — đừng thêm lock vào `arm()` nếu không muốn deadlock.

- [ ] **Step 4: Thêm factory thật + singleton vào cuối `runner.py`**

```python
# --- real wiring ---------------------------------------------------------


def default_station_factory(host):
    from ml.infer.station import StationClient

    return StationClient(host)


def default_detector_factory():
    """Build the configured detector, lazily.

    Called on Start, never at import: with backend="local" this pulls
    ultralytics + torch in, which would add tens of seconds to every server
    start even for someone who only wanted to read history.
    """
    from ml.infer import config as ml_config
    from ml.infer.cli import build_detector

    cfg = ml_config.load(_repo_root() / "ml" / "config.toml")
    backend = cfg.get("general", "backend")
    problems = cfg.missing_for(backend)
    if problems:
        raise RunnerConfigError(
            f"backend suy luận {backend!r} chưa chạy được: " + " | ".join(problems))
    try:
        return build_detector(cfg, backend, cfg.get("local", "weights"))
    except Exception as exc:       # noqa: BLE001
        raise RunnerConfigError(
            f"không dựng được backend {backend!r}: {exc}") from exc


def default_poster(api_url, metadata, image_bytes, image_name):
    from ml.infer.ingest_client import post

    return post(api_url, metadata, image_bytes, image_name)


def _repo_root():
    return Path(__file__).resolve().parents[3]


def build_config_from_settings(mode=None):
    """Merge data/settings.json with ml/config.toml per the spec's precedence.

    settings.json wins for station_host / px_per_mm; empty falls back to
    ml/config.toml. `mode` passed by the caller (the start request) always
    wins over the remembered UI default.
    """
    from ml.infer import config as ml_config

    from . import settings_store

    s = settings_store.load()
    ml = ml_config.load(_repo_root() / "ml" / "config.toml")

    host = s["station_host"] or (ml.get("station", "host") or "")
    px = s["px_per_mm"]
    if px is None:
        px = ml.get("calibration", "px_per_mm")
    if px is None or float(px) <= 0:
        # Same honesty rule as the CLI: size_mm is a PLACEHOLDER until a real
        # px/mm is measured on the rig.
        from ml.infer.naming import DEFAULT_PX_PER_MM

        px = DEFAULT_PX_PER_MM

    return RunnerConfig(
        mode=mode or s["mode"],
        station_host=host,
        capture_delay_s=s["capture_delay_ms"] / 1000.0,
        px_per_mm=float(px),
        batch_lot=s["batch_lot"],
        api_url=ml.get("ingest", "api_url") or "http://localhost:8000",
    )


RUNNER = Runner(
    station_factory=default_station_factory,
    detector_factory=default_detector_factory,
    poster=default_poster,
)


def get_runner():
    """Seam for tests: FastAPI dependency override swaps in a fake Runner."""
    return RUNNER
```

- [ ] **Step 5: Chạy để xác nhận pass**

Run (từ `web/backend/`): `python -m pytest tests/test_runner_thread.py tests/test_runner.py -q`
Expected: PASS toàn bộ.

- [ ] **Step 6: Commit**

```bash
git add web/backend/app/runner.py web/backend/tests/test_runner_thread.py
git commit -m "feat(web): vòng đời thread + factory thật cho Runner"
```

---

## Task 6: API điều khiển

**Files:**
- Create: `web/backend/app/routers/control.py`
- Create: `web/backend/tests/test_control_api.py`
- Modify: `web/backend/app/main.py:1-42`

**Interfaces:**
- Consumes: `app.runner.get_runner`, `app.runner.RUNNER`, `RunnerBusy`, `RunnerConfigError`, `build_config_from_settings` (Task 5); `app.settings_store` (Task 3); `ml.infer.station.StationClient` (Task 1)
- Produces: router `app.routers.control.router` với prefix `/api`, và `app.routers.control.CONTROL_VARS: frozenset`

- [ ] **Step 1: Viết test (phải fail)**

Tạo `web/backend/tests/test_control_api.py`:

```python
"""Hợp đồng API điều khiển. Không đụng board thật, không đụng thread thật:
Runner giả tiêm qua dependency override.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import control
from app.runner import RunnerBusy, RunnerConfigError


class FakeRunner:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.start_error = None
        self.snap = {"running": False, "mode": None, "station_host": "",
                     "device": None, "phase": None,
                     "counters": {"cycles": 0, "captured": 0, "written": 0, "failed": 0},
                     "last": None, "error": None, "warnings": [], "has_preview": False}
        self._preview = None
        self.kept = 0

    def start(self, cfg, **kw):
        if self.start_error:
            raise self.start_error
        self.started.append(cfg)
        self.snap["running"] = True
        self.snap["mode"] = cfg.mode

    def stop(self):
        self.stopped += 1
        self.snap["running"] = False

    def snapshot(self):
        return dict(self.snap)

    def preview_jpeg(self):
        return self._preview

    def keep(self):
        if self._preview is None:
            raise RuntimeError("chưa có khung nào để lưu.")
        self.kept += 1
        return {"sample_code": "S-PREVIEW-1", "written": True}


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def client(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(control.settings_store, "SETTINGS_PATH",
                        tmp_path / "settings.json")
    app = FastAPI()
    app.include_router(control.router)
    app.dependency_overrides[control.get_runner] = lambda: runner
    return TestClient(app)


def test_status_returns_the_snapshot(client):
    r = client.get("/api/runner/status")
    assert r.status_code == 200
    assert r.json()["running"] is False
    assert r.json()["counters"]["written"] == 0


def test_start_measure_passes_mode_through(client, runner):
    client.post("/api/settings", json={"station_host": "192.168.1.50"})

    r = client.post("/api/runner/start", json={"mode": "measure"})

    assert r.status_code == 200
    assert runner.started[0].mode == "measure"
    assert runner.started[0].station_host == "192.168.1.50"


def test_start_without_host_is_400(client, runner):
    runner.start_error = RunnerConfigError("chưa có địa chỉ board.")
    r = client.post("/api/runner/start", json={"mode": "preview"})
    assert r.status_code == 400
    assert "board" in r.json()["detail"]


def test_start_while_running_is_409(client, runner):
    runner.start_error = RunnerBusy("runner đang chạy rồi.")
    r = client.post("/api/runner/start", json={"mode": "preview"})
    assert r.status_code == 409


def test_start_rejects_unknown_mode(client):
    r = client.post("/api/runner/start", json={"mode": "turbo"})
    assert r.status_code == 422


def test_stop_is_idempotent(client, runner):
    assert client.post("/api/runner/stop").status_code == 200
    assert client.post("/api/runner/stop").status_code == 200
    assert runner.stopped == 2


def test_preview_404_when_no_frame_yet(client):
    assert client.get("/api/runner/preview.jpg").status_code == 404


def test_preview_returns_jpeg_bytes(client, runner):
    runner._preview = b"\xff\xd8fake\xff\xd9"
    r = client.get("/api/runner/preview.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == b"\xff\xd8fake\xff\xd9"


def test_keep_without_frame_is_409(client):
    assert client.post("/api/runner/keep").status_code == 409


def test_keep_writes_the_frame(client, runner):
    runner._preview = b"\xff\xd8fake\xff\xd9"
    r = client.post("/api/runner/keep")
    assert r.status_code == 200
    assert r.json()["sample_code"] == "S-PREVIEW-1"
    assert runner.kept == 1


def test_settings_roundtrip(client):
    client.post("/api/settings", json={"batch_lot": "LOT-9"})
    assert client.get("/api/settings").json()["batch_lot"] == "LOT-9"


def test_settings_rejects_bad_value_with_400(client):
    r = client.post("/api/settings", json={"capture_delay_ms": -5})
    assert r.status_code == 400
    assert "capture_delay_ms" in r.json()["detail"]


def test_control_rejects_var_outside_allowlist(client, monkeypatch):
    # Không allowlist thì đây là proxy mở: ai trong LAN cũng bắn được tham số
    # tuỳ ý vào firmware.
    called = []
    monkeypatch.setattr(control, "_board_get", lambda url, timeout=5: called.append(url))

    r = client.post("/api/station/control", json={"var": "framesize", "val": "13"})

    assert r.status_code == 400
    assert called == [], "không được gửi request nào tới board"


def test_control_forwards_allowed_var(client, monkeypatch):
    client.post("/api/settings", json={"station_host": "192.168.1.50"})
    called = []
    monkeypatch.setattr(control, "_board_get",
                        lambda url, timeout=5: called.append(url) or "OK")

    r = client.post("/api/station/control", json={"var": "darkmode", "val": "1"})

    assert r.status_code == 200
    assert called == ["http://192.168.1.50/control?var=darkmode&val=1"]


def test_control_without_configured_host_is_400(client, monkeypatch):
    monkeypatch.setattr(control, "_board_get", lambda url, timeout=5: "OK")
    r = client.post("/api/station/control", json={"var": "darkmode", "val": "1"})
    assert r.status_code == 400


def test_control_rejects_unsafe_val(client, monkeypatch):
    client.post("/api/settings", json={"station_host": "192.168.1.50"})
    called = []
    monkeypatch.setattr(control, "_board_get", lambda url, timeout=5: called.append(url))

    r = client.post("/api/station/control",
                    json={"var": "device_id", "val": "a&var=reset&val=1"})

    assert r.status_code == 422
    assert called == []


def test_probe_rejects_a_url_shaped_host(client, monkeypatch):
    monkeypatch.setattr(control, "_probe_host", lambda host: {"device_id": "x"})
    r = client.get("/api/station/probe", params={"host": "evil.example.com/x?y=1"})
    assert r.status_code == 400


def test_probe_returns_device_json(client, monkeypatch):
    monkeypatch.setattr(control, "_probe_host",
                        lambda host: {"device_id": "aqua-cam-1", "_host": host})
    r = client.get("/api/station/probe", params={"host": "aqua-scope.local"})
    assert r.status_code == 200
    assert r.json()["device_id"] == "aqua-cam-1"


def test_probe_unreachable_board_is_502(client, monkeypatch):
    def boom(host):
        raise RuntimeError("không tới được")

    monkeypatch.setattr(control, "_probe_host", boom)
    r = client.get("/api/station/probe", params={"host": "10.0.0.7"})
    assert r.status_code == 502
```

- [ ] **Step 2: Chạy để xác nhận fail**

Run (từ `web/backend/`): `python -m pytest tests/test_control_api.py -q`
Expected: FAIL — `ImportError: cannot import name 'control'`

- [ ] **Step 3: Viết `web/backend/app/routers/control.py`**

```python
"""Runner + station control endpoints (spec 2026-07-26 §5).

These are the first POST routes outside /api/ingest. They do NOT mutate stored
samples — append-only still holds for the audit data; what they mutate is
runtime state (a worker thread, an operational settings file) and the board's
own camera/pump settings.

`/api/station/control` deliberately does NOT take a host from the request: it
always targets the configured station. Otherwise it would be a general-purpose
"make the server fetch this URL" tool for anyone on the LAN. The `var`
allowlist exists for the same reason at the parameter level.
"""

import re

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .. import settings_store
from ..runner import (RunnerBusy, RunnerConfigError, build_config_from_settings,
                      get_runner)

router = APIRouter(prefix="/api", tags=["control"])

# Every var the dashboard needs, and nothing else. Adding one here is a
# deliberate act — see the module docstring.
CONTROL_VARS = frozenset({
    "darkmode", "save", "reset", "device_id",
    "pump_auto", "pump_fill_ms", "pump_settle_ms", "pump_flush_ms",
    "pump_cooldown_ms", "pump_fill_duty", "pump_flush_duty",
    "pump_ramp_up_ms", "pump_ramp_down_ms",
})

# Board's own device_id rule (firmware README): [A-Za-z0-9._-], 1–64 chars.
# Also blocks `&`/`?`, which would smuggle a second var into the query string.
_VAL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Same host rule as the settings store — a probe host that settings_store would
# reject must not sneak in through the query string instead.
HOST_RE = settings_store.HOST_RE


class StartBody(BaseModel):
    mode: str = Field(pattern="^(preview|measure)$")


class ControlBody(BaseModel):
    var: str
    val: str


class SettingsBody(BaseModel):
    station_host: str | None = None
    mode: str | None = None
    batch_lot: str | None = None
    capture_delay_ms: int | None = None
    px_per_mm: float | None = None
    # Distinguishing "not sent" from "sent as null" matters for batch_lot and
    # px_per_mm, both of which are legitimately clearable.
    model_config = {"extra": "forbid"}


# --- runner ---------------------------------------------------------------


@router.get("/runner/status")
def runner_status(runner=Depends(get_runner)):
    return runner.snapshot()


@router.post("/runner/start")
def runner_start(body: StartBody, runner=Depends(get_runner)):
    cfg = build_config_from_settings(mode=body.mode)
    try:
        runner.start(cfg)
    except RunnerBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RunnerConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Remember the choice so the dashboard pre-selects it next time.
    settings_store.save({"mode": body.mode})
    return runner.snapshot()


@router.post("/runner/stop")
def runner_stop(runner=Depends(get_runner)):
    runner.stop()
    return runner.snapshot()


@router.get("/runner/preview.jpg")
def runner_preview(runner=Depends(get_runner)):
    jpeg = runner.preview_jpeg()
    if not jpeg:
        raise HTTPException(status_code=404, detail="chưa có khung xem nào.")
    # no-store: the frame changes every pump cycle and must never be cached.
    return Response(content=jpeg, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.post("/runner/keep")
def runner_keep(runner=Depends(get_runner)):
    try:
        return runner.keep()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# --- settings -------------------------------------------------------------


@router.get("/settings")
def settings_get():
    return settings_store.load()


@router.post("/settings")
def settings_post(body: SettingsBody):
    patch = body.model_dump(exclude_unset=True)
    try:
        return settings_store.save(patch)
    except settings_store.SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- station --------------------------------------------------------------


@router.get("/station/probe")
def station_probe(host: str = Query(...)):
    host = host.strip()
    if not HOST_RE.match(host):
        raise HTTPException(
            status_code=400,
            detail=f"host {host!r} không hợp lệ. Nhập IP hoặc tên máy, không "
                   "kèm http:// hay đường dẫn.")
    try:
        return _probe_host(host)
    except Exception as exc:       # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"không tới được board: {exc}")


@router.post("/station/control")
def station_control(body: ControlBody):
    if body.var not in CONTROL_VARS:
        raise HTTPException(
            status_code=400,
            detail=f"tham số {body.var!r} không nằm trong danh sách cho phép.")
    if not _VAL_RE.match(body.val):
        raise HTTPException(
            status_code=422,
            detail="giá trị chỉ được chứa chữ, số và . _ - (1–64 ký tự).")

    host = settings_store.load()["station_host"]
    if not host:
        raise HTTPException(
            status_code=400,
            detail="chưa có địa chỉ board. Nhập IP hoặc bấm Dò trước.")

    url = f"http://{host}/control?var={body.var}&val={body.val}"
    try:
        text = _board_get(url)
    except Exception as exc:       # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"board không nhận lệnh: {exc}")
    return JSONResponse({"ok": True, "var": body.var, "val": body.val,
                         "board_response": text})


# --- seams (monkeypatched in tests; the only places that touch the network) --


def _board_get(url, timeout=5):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text[:200]


def _probe_host(host):
    from ml.infer.station import StationClient

    return StationClient(host, timeout_s=5, retries=1).read_device()
```

- [ ] **Step 4: Chạy để xác nhận pass**

Run (từ `web/backend/`): `python -m pytest tests/test_control_api.py -q`
Expected: PASS (19 test).

- [ ] **Step 5: Wire router vào app + sửa docstring nói sai**

Trong `web/backend/app/main.py`, đổi khối docstring (dòng 10–11) từ:

```
Append-only is enforced at the routing layer: none of the wired routers expose
a PUT/PATCH/DELETE path (§2.2).
```

thành:

```
Append-only applies to the SAMPLE DATA: no route anywhere exposes PUT/PATCH/
DELETE, so a stored sample can never be edited or removed. The control router
does add POST routes (start/stop the capture worker, write operational
settings, forward a command to the board) — those mutate runtime state and the
board's own config, never a stored row (spec 2026-07-26 §5.1).
```

Sửa import (dòng 21) và phần wiring (dòng 34–37):

```python
from .routers import control, ingest, pages, samples
...
app.include_router(ingest.router)
app.include_router(samples.router)
app.include_router(control.router)
# Server-rendered dashboard pages (/, /history, /samples/{id}, /stream).
app.include_router(pages.router)
```

Thêm vào `lifespan`, ngay trước `yield` là không cần gì; nhưng **sau** `yield` phải dừng worker để `uvicorn --reload` không để lại thread mồ côi:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create data/aqua_scope.db + data/images/ and both tables before serving.
    create_db_and_tables()
    yield
    # Stop the capture worker on shutdown; with --reload the process is
    # replaced repeatedly and an orphaned thread would keep polling the board.
    from .runner import RUNNER

    RUNNER.stop()
```

- [ ] **Step 6: Chạy toàn bộ bộ test web**

Run (từ `web/backend/`): `python -m pytest -q`
Expected: PASS toàn bộ (test cũ + mới).

- [ ] **Step 7: Commit**

```bash
git add web/backend/app/routers/control.py web/backend/tests/test_control_api.py web/backend/app/main.py
git commit -m "feat(web): API điều khiển runner + trạm, wire vào app"
```

---

## Task 7: Panel điều khiển trên dashboard

**Files:**
- Create: `web/backend/app/templates/_control_panel.html`
- Create: `web/backend/app/static/js/control_panel.js`
- Modify: `web/backend/app/templates/index.html:3-6` và `:115-117`
- Modify: `web/backend/app/static/css/style.css` (thêm vào cuối)
- Modify: `web/backend/tests/test_module5_pages.py` (thêm 2 test)

**Interfaces:**
- Consumes: mọi endpoint của Task 6.
- Produces: không có API mới cho task sau.

**Lệch có chủ đích so với spec §6:** spec viết "thẻ *Mẫu mới nhất* được cập nhật
tại chỗ từ payload status". Ở đây thay bằng **thẻ live riêng trong panel**
(`#cp-live`) thay vì viết JS đổi nội dung thẻ "Mẫu mới nhất" do server render.
Lý do: thẻ của server có overlay bbox + `<script type="application/json">` riêng,
cập nhật nó bằng JS nghĩa là dựng lại cùng một khối markup ở hai nơi (Jinja và
JS) — đúng kiểu trùng lặp sẽ lệch nhau ở lần sửa sau. Thẻ live phục vụ đúng
nhu cầu "thấy khung vừa chụp ngay"; bảng và thẻ của server vẫn cập nhật khi tải
lại trang, như spec đã nói.

- [ ] **Step 1: Viết test cho panel (phải fail)**

Thêm vào cuối `web/backend/tests/test_module5_pages.py`:

```python
def test_control_panel_present_on_dashboard(client):
    html = client.get("/").text
    assert 'id="control-panel"' in html
    assert 'id="btn-start"' in html
    assert "/static/js/control_panel.js" in html


def test_control_panel_present_even_with_no_samples():
    # Trạm chưa có mẫu nào chính là lúc cần nút Bắt đầu nhất — panel phải nằm
    # NGOÀI nhánh empty của template.
    c = _make_client(seed=False)
    html = c.get("/").text
    assert 'id="control-panel"' in html
    assert "Chưa có mẫu nào" in html
```

(`_make_client(seed=...)` là helper đã có sẵn ở đầu file, dòng 47 — trả về
`TestClient`. Test đầu dùng fixture `client` cũng đã có sẵn.)

- [ ] **Step 2: Chạy để xác nhận fail**

Run (từ `web/backend/`): `python -m pytest tests/test_module5_pages.py -q`
Expected: FAIL — `assert 'id="control-panel"' in html`

- [ ] **Step 3: Viết `_control_panel.html`**

```html
{# Panel điều khiển trạm — nằm NGOÀI nhánh {% if empty %} của index.html:
   lúc chưa có mẫu nào chính là lúc cần nút Bắt đầu nhất. #}
<section class="card" id="control-panel" style="margin-bottom:20px">
  <div class="card-head">
    <h2 class="card-title">Điều khiển trạm</h2>
    <span class="chip" id="runner-state">— đang tải</span>
    <div class="spacer"></div>
    <span class="hint-caption" id="runner-counters"></span>
  </div>

  <div class="cp-grid">
    <div class="cp-field">
      <label class="cp-label" for="cp-host">Địa chỉ board</label>
      <div class="cp-row">
        <input class="cp-input mono" id="cp-host" type="text"
               placeholder="aqua-scope.local" autocomplete="off">
        <button class="btn" id="btn-probe" type="button">Dò</button>
      </div>
      <span class="hint-caption" id="cp-board-info">chưa kết nối</span>
    </div>

    <div class="cp-field">
      <label class="cp-label" for="cp-lot">Mã lô</label>
      <input class="cp-input mono" id="cp-lot" type="text" placeholder="LOT-001"
             autocomplete="off">
      <span class="hint-caption">ghi kèm mọi mẫu của lượt đo này</span>
    </div>

    <div class="cp-field">
      <span class="cp-label">Chế độ</span>
      <div class="cp-row" role="radiogroup" aria-label="Chế độ chạy">
        <button class="btn cp-mode active" id="btn-mode-preview" type="button"
                role="radio" aria-checked="true">Xem</button>
        <button class="btn cp-mode" id="btn-mode-measure" type="button"
                role="radio" aria-checked="false">Đo</button>
      </div>
      <span class="hint-caption" id="cp-mode-hint">
        Xem: suy luận liên tục, <strong>không ghi</strong> vào sổ audit.
      </span>
    </div>

    <div class="cp-field">
      <span class="cp-label">Chạy</span>
      <div class="cp-row">
        <button class="btn btn-primary" id="btn-start" type="button">Bắt đầu</button>
        <button class="btn" id="btn-stop" type="button" disabled>Dừng</button>
      </div>
      <span class="hint-caption" id="cp-phase">pha bơm: —</span>
    </div>

    <div class="cp-field cp-wide">
      <span class="cp-label">Lệnh trạm</span>
      <div class="cp-row cp-wrap">
        <button class="btn" id="btn-darkmode" type="button">Canh sáng buồng tối</button>
        <button class="btn" id="btn-save" type="button">Lưu vào flash</button>
        <button class="btn" id="btn-pump-on" type="button">Bơm auto BẬT</button>
        <button class="btn" id="btn-pump-off" type="button">Bơm auto TẮT</button>
      </div>
    </div>
  </div>

  <div id="cp-warnings" class="cp-warnings" hidden></div>

  <div class="cp-live" id="cp-live" hidden>
    <div class="cp-live-img">
      <img id="cp-preview" alt="Khung vừa chụp" src="">
    </div>
    <div class="cp-live-meta">
      <div class="meta-list">
        <div class="meta-row"><span class="meta-k">Mã mẫu</span><span class="meta-v mono" id="cp-last-code">—</span></div>
        <div class="meta-row"><span class="meta-k">Số hạt</span><span class="meta-v" id="cp-last-count">—</span></div>
        <div class="meta-row"><span class="meta-k">Ghi sổ</span><span class="meta-v" id="cp-last-written">—</span></div>
      </div>
      <button class="btn" id="btn-keep" type="button" hidden>Lưu mẫu này vào sổ</button>
    </div>
  </div>
</section>
```

- [ ] **Step 4: Viết `control_panel.js`**

```javascript
/* Panel điều khiển trạm — poll /api/runner/status mỗi giây, nối nút bấm.
 *
 * Không framework, không CDN: dashboard phải chạy được trên LAN offline
 * (cùng quyết định với "SVG server-rendered thay Chart.js" của Module 5).
 */
(function () {
  var panel = document.getElementById('control-panel');
  if (!panel) return;

  var POLL_MS = 1000;
  var mode = 'preview';
  var running = false;

  function $(id) { return document.getElementById(id); }

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
        return data;
      });
    });
  }

  function flash(message, isError) {
    var box = $('cp-warnings');
    box.hidden = false;
    box.className = 'cp-warnings' + (isError ? ' error' : '');
    box.textContent = message;
  }

  function saveSettings(patch) {
    return post('/api/settings', patch).catch(function (e) {
      flash('Không lưu được cấu hình: ' + e.message, true);
    });
  }

  /* --- render ------------------------------------------------------- */

  function render(s) {
    running = s.running;
    $('runner-state').textContent = s.running
      ? (s.mode === 'measure' ? 'đang ĐO' : 'đang XEM')
      : 'đã dừng';
    $('runner-state').className = 'chip' + (s.running ? ' chip-live' : '');

    var c = s.counters || {};
    $('runner-counters').textContent =
      'chu kỳ ' + (c.cycles || 0) + ' · chụp ' + (c.captured || 0) +
      ' · ghi ' + (c.written || 0) + ' · hỏng ' + (c.failed || 0);

    $('btn-start').disabled = s.running;
    $('btn-stop').disabled = !s.running;
    $('cp-phase').textContent = 'pha bơm: ' + (s.phase || '—');

    var dev = s.device;
    $('cp-board-info').textContent = dev
      ? (dev.device_id || '?') + ' · ' + (dev.firmware || '?') +
        ' · RSSI ' + ((dev.wifi && dev.wifi.rssi) || '?') + ' dBm' +
        (dev.prefs_saved ? ' · đã lưu cấu hình' : ' · CHƯA lưu cấu hình')
      : 'chưa kết nối';

    var msgs = (s.warnings || []).slice();
    if (s.error) msgs.unshift(s.error);
    var box = $('cp-warnings');
    if (msgs.length) {
      box.hidden = false;
      box.className = 'cp-warnings' + (s.error ? ' error' : '');
      box.textContent = msgs.join('  •  ');
    } else {
      box.hidden = true;
    }

    var last = s.last;
    $('cp-live').hidden = !last;
    if (last) {
      $('cp-last-code').textContent = last.sample_code;
      $('cp-last-count').textContent = last.particle_count + ' hạt';
      $('cp-last-written').textContent = last.written
        ? 'đã ghi vào sổ audit'
        : 'KHÔNG ghi (chế độ Xem)';
      $('btn-keep').hidden = last.written || !s.has_preview;
      if (s.has_preview) {
        // cache-bust: khung đổi mỗi chu kỳ, cùng một URL
        $('cp-preview').src = '/api/runner/preview.jpg?t=' + encodeURIComponent(last.at);
      }
    }
  }

  function poll() {
    fetch('/api/runner/status')
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () { /* server vừa restart — lần poll sau sẽ bắt lại */ });
  }

  /* --- mode toggle -------------------------------------------------- */

  function setMode(next) {
    mode = next;
    var isMeasure = next === 'measure';
    $('btn-mode-measure').classList.toggle('active', isMeasure);
    $('btn-mode-preview').classList.toggle('active', !isMeasure);
    $('btn-mode-measure').setAttribute('aria-checked', String(isMeasure));
    $('btn-mode-preview').setAttribute('aria-checked', String(!isMeasure));
    $('cp-mode-hint').innerHTML = isMeasure
      ? 'Đo: mỗi chu kỳ bơm ghi <strong>một mẫu vĩnh viễn</strong> vào sổ audit.'
      : 'Xem: suy luận liên tục, <strong>không ghi</strong> vào sổ audit.';
    saveSettings({ mode: next });
  }

  /* --- wiring ------------------------------------------------------- */

  $('btn-mode-preview').addEventListener('click', function () { setMode('preview'); });
  $('btn-mode-measure').addEventListener('click', function () { setMode('measure'); });

  $('btn-start').addEventListener('click', function () {
    saveSettings({
      station_host: $('cp-host').value.trim(),
      batch_lot: $('cp-lot').value.trim() || null
    }).then(function () {
      return post('/api/runner/start', { mode: mode });
    }).then(render).catch(function (e) {
      flash('Không bắt đầu được: ' + e.message, true);
    });
  });

  $('btn-stop').addEventListener('click', function () {
    post('/api/runner/stop').then(render).catch(function (e) {
      flash('Không dừng được: ' + e.message, true);
    });
  });

  $('btn-probe').addEventListener('click', function () {
    var host = $('cp-host').value.trim() || 'aqua-scope.local';
    $('cp-host').value = host;
    $('cp-board-info').textContent = 'đang dò ' + host + '...';
    fetch('/api/station/probe?host=' + encodeURIComponent(host))
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
          return d;
        });
      })
      .then(function (dev) {
        saveSettings({ station_host: host });
        $('cp-board-info').textContent =
          'tìm thấy ' + (dev.device_id || '?') + ' · ' + (dev.firmware || '?');
      })
      .catch(function (e) {
        $('cp-board-info').textContent = 'không thấy board: ' + e.message;
      });
  });

  function control(varName, val, label) {
    post('/api/station/control', { var: varName, val: val })
      .then(function () { flash(label + ': board đã nhận.', false); })
      .catch(function (e) { flash(label + ' hỏng: ' + e.message, true); });
  }

  $('btn-darkmode').addEventListener('click', function () {
    control('darkmode', '1', 'Canh sáng buồng tối');
  });
  $('btn-save').addEventListener('click', function () {
    control('save', '1', 'Lưu vào flash');
  });
  $('btn-pump-on').addEventListener('click', function () {
    control('pump_auto', '1', 'Bơm auto BẬT');
  });
  $('btn-pump-off').addEventListener('click', function () {
    control('pump_auto', '0', 'Bơm auto TẮT');
  });

  $('btn-keep').addEventListener('click', function () {
    post('/api/runner/keep')
      .then(function (d) { flash('Đã lưu ' + d.sample_code + ' vào sổ audit.', false); })
      .catch(function (e) { flash('Không lưu được: ' + e.message, true); });
  });

  /* --- boot --------------------------------------------------------- */

  fetch('/api/settings')
    .then(function (r) { return r.json(); })
    .then(function (s) {
      $('cp-host').value = s.station_host || '';
      $('cp-lot').value = s.batch_lot || '';
      setMode(s.mode || 'preview');
    })
    .catch(function () {});

  poll();
  setInterval(poll, POLL_MS);
})();
```

- [ ] **Step 5: Nối panel vào `index.html`**

Sửa đầu block content (dòng 3–4) thành:

```jinja
{% block content %}
{% include "_control_panel.html" %}
{% if empty %}
```

và block scripts (dòng 115–117) thành:

```jinja
{% block scripts %}
<script src="/static/js/bbox_overlay.js"></script>
<script src="/static/js/control_panel.js"></script>
{% endblock %}
```

- [ ] **Step 6: Thêm CSS vào cuối `web/backend/app/static/css/style.css`**

```css
/* --- Control panel (spec 2026-07-26) ---------------------------------- */
.cp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 16px;
  padding: 18px;
}
.cp-field { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.cp-wide { grid-column: 1 / -1; }
.cp-label {
  font-size: 11.5px; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: var(--text-dim);
}
.cp-row { display: flex; gap: 8px; align-items: center; }
.cp-wrap { flex-wrap: wrap; }
.cp-input {
  flex: 1; min-width: 0; padding: 8px 10px; font-size: 13px;
  color: var(--text); background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 8px;
}
.cp-input:focus { outline: 2px solid var(--teal); outline-offset: 1px; }
.cp-mode.active { background: var(--teal); color: #fff; border-color: var(--teal); }

.chip-live { background: var(--teal); color: #fff; }

.cp-warnings {
  margin: 0 18px 16px; padding: 10px 12px; border-radius: 8px;
  font-size: 12.5px; line-height: 1.5;
  background: var(--amber-soft, rgba(217, 152, 26, .13));
  border: 1px solid var(--amber, #d9981a); color: var(--text);
}
.cp-warnings.error {
  background: var(--danger-soft, rgba(200, 60, 60, .13));
  border-color: var(--danger, #c83c3c);
}

.cp-live {
  display: flex; gap: 18px; flex-wrap: wrap;
  padding: 0 18px 18px; align-items: flex-start;
}
.cp-live-img { flex: 1; min-width: 240px; }
.cp-live-img img {
  width: 100%; height: auto; display: block; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface-1);
}
.cp-live-meta { flex: 1; min-width: 210px; display: flex; flex-direction: column; gap: 12px; }

@media (max-width: 900px) {
  .cp-grid { grid-template-columns: 1fr; }
}
```

Nếu các biến `--amber-soft` / `--danger` / `--danger-soft` chưa tồn tại trong `:root` của file, giá trị dự phòng trong `var(..., fallback)` ở trên đã lo — không cần thêm biến mới.

- [ ] **Step 7: Chạy test**

Run (từ `web/backend/`): `python -m pytest -q`
Expected: PASS toàn bộ, gồm 2 test mới.

- [ ] **Step 8: Kiểm bằng mắt**

```bash
cd web/backend && python -m uvicorn app.main:app --port 8000
```

Mở `http://localhost:8000`. Kỳ vọng: panel hiện ở đầu trang, chip trạng thái báo "đã dừng", nút Dừng bị mờ, không có lỗi nào trong console trình duyệt. Bấm **Bắt đầu** khi chưa có board → dải cảnh báo đỏ "Không bắt đầu được: chưa có địa chỉ board...". Thu nhỏ cửa sổ xuống ≤900px → lưới gập một cột, thân trang không cuộn ngang.

- [ ] **Step 9: Commit**

```bash
git add web/backend/app/templates/_control_panel.html web/backend/app/templates/index.html web/backend/app/static/js/control_panel.js web/backend/app/static/css/style.css web/backend/tests/test_module5_pages.py
git commit -m "feat(web): panel điều khiển trạm trên dashboard"
```

---

## Task 8: Firmware — mDNS `aqua-scope.local`

**Files:**
- Modify: `firmware/aqua_scope_station/aqua_scope_station.ino:34-43` (include), `:176-179` (sự kiện GOT_IP), `:198-200` (log sau khi nối)
- Modify: `firmware/aqua_scope_station/README.md`

**Interfaces:**
- Consumes: không có (độc lập với phần Python).
- Produces: board trả lời tại `aqua-scope.local` — thứ mà nút **Dò** ở Task 7 thử đầu tiên.

Không có test tự động cho firmware (nạp qua Arduino IDE, kiểm bằng board thật) — nghiệm thu bằng checklist ở Step 4.

- [ ] **Step 1: Thêm include + hàm bật mDNS**

Trong `aqua_scope_station.ino`, thêm sau `#include <WiFi.h>` (dòng 35):

```cpp
#include <ESPmDNS.h>
```

Thêm hằng + hàm ngay trước `static bool connectWiFi()` (dòng 154):

```cpp
// Tên mDNS cố định: dashboard web thử "aqua-scope.local" trước khi bắt người
// dùng đi tìm IP. Cố ý KHÔNG gắn device_id vào tên — cái web cần là một tên
// đoán được, không phải một tên duy nhất.
static const char *MDNS_HOSTNAME = "aqua-scope";

static void startMdns() {
  // MDNS.end() trước: hàm này còn được gọi lại ở sự kiện GOT_IP sau mỗi lần
  // nối lại WiFi. Không đóng phiên cũ thì begin() lần hai thất bại và board
  // biến mất khỏi .local sau lần rớt mạng đầu tiên — đúng thứ đang muốn bỏ.
  MDNS.end();
  if (MDNS.begin(MDNS_HOSTNAME)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("[mdns] http://%s.local\n", MDNS_HOSTNAME);
  } else {
    Serial.println("[mdns] không bật được — dùng IP thay thế.");
  }
}
```

- [ ] **Step 2: Gọi ở cả hai chỗ (nối lần đầu và nối lại)**

Trong handler `ARDUINO_EVENT_WIFI_STA_GOT_IP` (dòng 176–179), thêm `startMdns();`:

```cpp
  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
    Serial.printf("[WiFi] đã nối lại | IP: %s\n",
                  WiFi.localIP().toString().c_str());
    startMdns();
  }, ARDUINO_EVENT_WIFI_STA_GOT_IP);
```

Và ngay trước `return true;` cuối `connectWiFi()` (sau dòng log "WiFi OK", dòng 198–200):

```cpp
  Serial.printf("WiFi OK | IP: %s | RSSI: %d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  startMdns();
  return true;
```

Gọi cả hai chỗ là cố ý: sự kiện GOT_IP không đảm bảo đã kích hoạt xong trước khi `connectWiFi()` trả về ở lần nối đầu, và `startMdns()` tự an toàn khi gọi lại (đã `MDNS.end()` ở đầu).

Nhánh `USE_AP` (dòng 155–164) **không** gọi mDNS: ở chế độ AP người dùng nối thẳng vào board và IP là hằng số đã in ra Serial.

- [ ] **Step 3: Nạp và kiểm trên board thật**

Arduino IDE → Board **AI Thinker ESP32-CAM**, Partition **Huge APP** → Upload → Serial Monitor 115200.

Kỳ vọng: sau dòng `WiFi OK | IP: ...` có dòng `[mdns] http://aqua-scope.local`.

- [ ] **Step 4: Nghiệm thu**

```bash
curl http://aqua-scope.local/device
```

Kỳ vọng: JSON `/device` như khi gọi bằng IP.

Rồi tắt router 30 giây, bật lại, đợi board tự nối lại (Serial in `[WiFi] đã nối lại` + `[mdns] http://aqua-scope.local`), gọi lại `curl` trên → vẫn trả JSON. Đây là mục quan trọng: mất mDNS sau lần rớt mạng đầu tiên là lỗi hay gặp nhất của cách làm này.

- [ ] **Step 5: Cập nhật README firmware**

Trong `firmware/aqua_scope_station/README.md`:

Thêm vào bảng Endpoint, ngay dưới dòng `GET /device`:

```markdown
| mDNS `aqua-scope.local` | Board tự xưng tên trong LAN — khỏi mở Serial Monitor lấy IP |
```

Thêm mục mới trước "Checklist nghiệm thu trên board thật":

```markdown
## mDNS — khỏi đi tìm IP

Board tự xưng `aqua-scope.local` sau khi nối WiFi (và tự xưng lại sau mỗi lần
nối lại). Dashboard web thử tên này trước khi bắt bạn gõ IP.

```
curl http://aqua-scope.local/device
```

**Không phải mạng nào cũng cho.** Một số router chặn multicast, mạng khách bật
AP isolation, vài máy Windows cũ thiếu bộ phân giải .local. Ô nhập IP tay trên
dashboard là đường dự phòng chính thức — không phải tính năng thừa. Chế độ
`USE_AP` không bật mDNS (nối thẳng vào board thì IP đã cố định và in ra Serial).
```

Thêm 2 mục vào checklist nghiệm thu:

```markdown
- [ ] 14. Serial in `[mdns] http://aqua-scope.local` sau dòng `WiFi OK`
- [ ] 15. Tắt router 30 giây rồi bật lại → sau khi board tự nối lại,
      `curl http://aqua-scope.local/device` **vẫn** trả JSON (mDNS được bật lại,
      không chết theo lần rớt mạng)
```

- [ ] **Step 6: Commit**

```bash
git add firmware/aqua_scope_station/aqua_scope_station.ino firmware/aqua_scope_station/README.md
git commit -m "feat(firmware): mDNS aqua-scope.local, bật lại sau mỗi lần nối lại WiFi"
```

---

## Task 9: `start.bat` + dependency tối thiểu + tài liệu

**Files:**
- Create: `start.bat` (gốc repo)
- Create: `ml/requirements-infer.txt`
- Modify: `README.md` (gốc)
- Modify: `ml/README.md` (mục "Chạy nhanh")
- Modify: `web_plan.md` (§2.2)

**Interfaces:**
- Consumes: mọi task trước.
- Produces: không có (task cuối).

- [ ] **Step 1: Tạo `ml/requirements-infer.txt`**

```
# Dependency TỐI THIỂU để CHẠY suy luận (backend "roboflow" hoặc runner web).
#
# Vì sao tách khỏi requirements.txt: file kia kéo cả ultralytics + tensorflow
# (~2GB) — cần cho TRAIN và EXPORT TFLite, hoàn toàn không cần cho đường chạy
# thật hiện tại. start.bat cài file này, nên lần khởi động đầu tính bằng giây
# chứ không phải chục phút.
#
# Muốn chạy backend "local" (weights .pt tự train) thì cài thêm:
#     pip install -r ml/requirements.txt
requests
pillow
numpy
```

- [ ] **Step 2: Tạo `start.bat`**

```bat
@echo off
REM Aqua Scope - khởi động toàn bộ hệ thống bằng một cú đúp.
REM
REM Chạy uvicorn TỪ GỐC REPO với --app-dir web/backend: `python -m` đưa thư mục
REM hiện tại (gốc repo) vào sys.path để `import ml.infer...` chạy được, còn
REM --app-dir đưa web/backend vào để `app.main` chạy được. Đổi cách khởi động
REM thì kiểm lại cả hai import đó.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay python. Cai Python 3.11+ va tich "Add to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Tao moi truong ao .venv ...
  python -m venv .venv || (echo [LOI] Tao .venv that bai. & pause & exit /b 1)
)

set PY=.venv\Scripts\python.exe

if not exist ".venv\.deps-installed" (
  echo [2/3] Cai thu vien lan dau, doi mot chut ...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r web\requirements.txt || (echo [LOI] Cai web deps that bai. & pause & exit /b 1)
  "%PY%" -m pip install -r ml\requirements-infer.txt || (echo [LOI] Cai ml deps that bai. & pause & exit /b 1)
  echo ok > ".venv\.deps-installed"
)

echo [3/3] Khoi dong Aqua Scope tai http://localhost:8000
start "" http://localhost:8000
"%PY%" -m uvicorn --app-dir web/backend app.main:app --host 0.0.0.0 --port 8000

endlocal
```

Ghi chú cho người triển khai: file `.venv\.deps-installed` là dấu "đã cài rồi" để lần chạy sau bỏ qua bước pip. Cài thêm thư viện mới thì xoá file đó đi.

- [ ] **Step 3: Kiểm `start.bat` chạy thật**

Xoá `.venv` nếu đang có (hoặc đổi tên tạm), bấm đúp `start.bat`.
Expected: tạo `.venv`, cài thư viện, mở trình duyệt tới `http://localhost:8000`, dashboard hiện panel điều khiển. Ctrl+C trong cửa sổ để dừng.

Chạy lại `start.bat` lần hai → bỏ qua bước cài, mở gần như tức thì.

- [ ] **Step 4: Thêm `.venv/` vào `.gitignore` gốc**

`.gitignore` ở gốc repo **chưa** có mục nào cho venv (đã kiểm 2026-07-26 —
`web/.gitignore` có `.venv/` nhưng nó chỉ áp cho `web/`). Thêm vào cuối
`.gitignore` gốc:

```
# Môi trường ảo + dấu "đã cài deps" do start.bat tạo
.venv/
```

- [ ] **Step 5: Cập nhật `README.md` gốc**

Thêm mục ngay sau phần mô tả tổng quan (đặt trước mọi hướng dẫn chạy tay đang có):

```markdown
## Chạy hệ thống (đường ngắn nhất)

Bấm đúp **`start.bat`** ở thư mục gốc. Nó tự tạo môi trường ảo, cài thư viện ở
lần đầu, khởi động backend và mở `http://localhost:8000`.

Trên dashboard:

1. Bấm **Dò** — tìm board qua `aqua-scope.local`. Không thấy thì gõ IP tay
   (Serial Monitor 115200 in ra IP lúc board khởi động).
2. Bấm **Canh sáng buồng tối** rồi **Lưu vào flash** (chỉ cần làm một lần cho
   mỗi rig — cấu hình được nhớ qua các lần mất điện).
3. Bấm **Bơm auto BẬT**.
4. Chọn **Xem** hoặc **Đo**, rồi bấm **Bắt đầu**.

Mỗi chu kỳ bơm sinh một khung ở pha lắng (SETTLING); hệ thống chạy tới khi bấm
**Dừng** — không còn giới hạn số ảnh.

| Chế độ | Ghi vào sổ audit? | Dùng khi |
|---|---|---|
| **Xem** | Không | canh sáng, chỉnh rig, thử nghiệm |
| **Đo** | Có, mỗi chu kỳ một mẫu | đo thật, cần truy xuất nguồn gốc |

> **Cảnh báo triển khai:** backend lắng nghe trên `0.0.0.0:8000` để mở được từ
> điện thoại trong cùng LAN, và **không có xác thực**. Đây là rig demo trong
> mạng nội bộ — đừng chuyển tiếp cổng này ra Internet.
>
> Chế độ **Đo** chạy dài sẽ tích ảnh trong `web/backend/data/images/`
> (~300KB/mẫu, chu kỳ 15s ≈ 70MB/giờ). Chưa có dọn rác tự động — tự theo dõi
> dung lượng đĩa nếu chạy nhiều giờ liền.
```

- [ ] **Step 6: Cập nhật `ml/README.md`**

Thay mục "### Đo mẫu thật từ board (đường chạy chính)" bằng:

```markdown
### Đo mẫu thật từ board — dùng dashboard

Đường chạy chính giờ là **`start.bat`** ở gốc repo (xem `README.md`): nó khởi
động backend web và bạn điều khiển bằng nút trên `http://localhost:8000` —
chụp + suy luận liên tục theo từng chu kỳ bơm, không giới hạn số khung.

CLI dưới đây vẫn dùng được và **không đổi hành vi**, hợp cho chạy lô cố định
hoặc chạy trong script:

```bash
python -m ml.infer --check-config
python -m ml.infer --from-board 192.168.1.50 --count 5 --interval 2
```

Cả hai đường dùng chung `ml/infer/` (`StationClient` → detector → mapper →
ingest) và cùng ghi vào một sổ audit.
```

- [ ] **Step 7: Cập nhật `web_plan.md`**

Hai dòng khẳng định điều giờ đã không còn đúng nguyên văn (đã xác định vị trí
chính xác 2026-07-26):

- dòng 45: *"mọi bản ghi bất biến (append-only), không có API sửa/xoá"*
- dòng 119: *"**Không có route PUT/PATCH/DELETE ở bất kỳ đâu** — đây là cách
  enforce yêu cầu append-only ở tầng kiến trúc, không chỉ là quy ước UI."*

Cả hai vẫn **đúng** về bản chất (không có route sửa/xoá bản ghi nào), nên giữ
nguyên văn hai dòng đó và chèn ghi chú ngay **dưới dòng 119**:

```markdown
> **Cập nhật 2026-07-26** (spec `2026-07-26-one-process-local-workflow-design.md`
> §5.1): append-only vẫn đúng cho **dữ liệu mẫu** — không route nào ở bất kỳ
> đâu có PUT/PATCH/DELETE, nên một mẫu đã ghi thì không sửa và không xoá được.
> Nhưng hệ đã có thêm các route POST **điều khiển** (`/api/runner/start|stop`,
> `/api/settings`, `/api/station/control`). Chúng đổi trạng thái lúc chạy
> (worker thread, file cấu hình vận hành) và cấu hình của board, **không** đụng
> tới bản ghi đã lưu.
```

- [ ] **Step 8: Chạy toàn bộ test lần cuối**

```bash
python -m pytest ml/tests -q
```

```bash
cd web/backend && python -m pytest -q
```

Expected: PASS cả hai bộ.

- [ ] **Step 9: Commit**

```bash
git add start.bat ml/requirements-infer.txt README.md ml/README.md web_plan.md .gitignore
git commit -m "feat: start.bat một cú đúp + tài liệu workflow mới"
```

---

## Nghiệm thu cuối trên rig thật

Chạy sau khi cả 9 task xong. Không tự động hoá được — cần board + bơm + nước.

- [ ] Bấm đúp `start.bat` → dashboard mở, **không gõ lệnh nào**.
- [ ] Nút **Dò** tìm thấy board qua `aqua-scope.local`, thẻ board hiện đúng
      `device_id` và firmware.
- [ ] Chưa bật bơm auto → dải cảnh báo hiện "Bơm chưa ở chế độ auto".
- [ ] AEC/AGC còn bật → dải cảnh báo hiện "AEC/AGC đang bật". Bấm **Canh sáng
      buồng tối** → cảnh báo biến mất ở lần poll sau.
- [ ] Bật bơm auto + **Bắt đầu** ở chế độ **Xem** → ảnh live đổi theo từng chu
      kỳ bơm; `web/backend/data/images/` **không** có file mới; số "chu kỳ" tăng
      đúng bằng số lần bơm chạy.
- [ ] Bấm **Lưu mẫu này vào sổ** → đúng một mẫu xuất hiện trong lịch sử.
- [ ] Chuyển **Đo** + **Bắt đầu** → mỗi chu kỳ bơm đúng **một** mẫu mới, chạy
      **quá 5 mẫu** và tiếp tục tới khi bấm Dừng. Đây là vấn đề gốc user nêu.
- [ ] Không có hai mẫu nào trùng `sample_code` trong lịch sử.
- [ ] Rút điện board giữa lượt đo → trong ~5s dashboard báo đỏ, runner tự dừng,
      web **không** sập, các mẫu đã ghi vẫn còn.
- [ ] Cắm lại board, bấm **Bắt đầu** → chạy tiếp bình thường.
- [ ] Mở dashboard từ điện thoại cùng LAN (`http://<ip-máy>:8000`) → panel dùng
      được, không cuộn ngang.
