# Aqua Scope Station Firmware — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng firmware chính thức `firmware/aqua_scope_station/` cho ESP32-CAM và nối nó thẳng vào `ml.infer` → `/api/ingest`, để đo một mẫu chỉ còn một lệnh thay vì hai bước rời.

**Architecture:** PC là nhạc trưởng. Firmware là nguồn ảnh backlit + endpoint `/device` báo danh tính và thiết lập camera. `ml/infer` mọc thêm `Esp32CaptureSource` dùng chung interface `.frames()` với `FolderSource`, nên `cli.py`/`mapper.py`/`ingest_client.py` gần như không đổi.

**Tech Stack:** Arduino ESP32 core ≥ 3.0 (esp_camera, esp_http_server, Preferences, esp_task_wdt) · Python 3.11+ · pytest · requests

## Global Constraints

- Board đích: **AI Thinker ESP32-CAM (OV2640)**, Partition Scheme **Huge APP (3MB No OTA/1MB SPIFFS)**.
- Tài liệu và comment trong repo này viết **tiếng Việt** (theo CLAUDE.md).
- `device_id` giữ trong tập ký tự `^[A-Za-z0-9._-]{1,64}$` — cùng tập với `SAMPLE_CODE_PATTERN` (`web/backend/app/models.py`). Đây là phòng thủ ở nguồn: server **không** validate `device_id` và **không** dùng nó làm tên file (tên file dựng từ `sample_code`, xem `routers/ingest.py`).
- `captured_at` phải **timezone-aware**; ingest từ chối datetime không có offset.
- Mặc định backlit là bất khả xâm phạm: **AEC / AEC-DSP / AGC tắt**, gain 0, exposure thấp. Đừng để bất kỳ đường code nào bật lại chúng.
- **Không** thêm điều khiển đèn nền, điều khiển bơm, hay suy luận on-device — ngoài phạm vi (spec §8).
- `--dry-run` phải **không** phát sinh request POST nào tới ingest. DB là sổ audit.
- Endpoint mới tên **`/device`**, KHÔNG phải `/status`. `/status` đã bị chiếm bởi handler trả JSON cấu hình camera mà web UI dùng để nạp slider (`app_httpd.cpp:431`) — đổi nó sẽ làm hỏng trang canh sáng.

---

## File Structure

**Tạo mới — `firmware/aqua_scope_station/`** (sao từ `dataset_collector/firmware/`, rồi sửa):

| File | Trách nhiệm |
|---|---|
| `aqua_scope_station.ino` | WiFi (nối + tự nối lại), khởi tạo camera, watchdog, in thông tin khởi động |
| `aqua_device.h` / `.cpp` | **Mới.** Danh tính thiết bị: `device_id` từ MAC, ghi đè/lưu NVS, đếm số lần chụp |
| `app_httpd.cpp` | Web server. Sửa: tắt flash LED khi chụp, thêm `/device`, `/capture` lỗi trả 503 |
| `aqua_prefs.h` / `.cpp` | Không đổi — lưu/nạp cấu hình camera vào NVS |
| `camera_index.h`, `camera_pins.h`, `board_config.h`, `partitions.csv` | Không đổi |
| `README.md` | **Mới.** Hướng dẫn nạp + checklist nghiệm thu phần cứng |

**Sửa — `ml/`:**

| File | Thay đổi |
|---|---|
| `ml/infer/source.py` | Thêm `Esp32CaptureSource` |
| `ml/infer/cli.py` | Thêm `--from-board` / `--count` / `--interval`, chọn source |
| `ml/infer/config.py` | Thêm mục `[station]` vào `DEFAULTS` + `missing_for` |
| `ml/config.toml` | Tài liệu hóa `[station]` |
| `ml/tests/test_source.py` | Test `Esp32CaptureSource` bằng HTTP server thật |
| `ml/tests/test_cli.py` | Test đấu dây `--from-board` |
| `ml/tests/test_config.py` | Test `missing_for` với station |

**Sửa — tài liệu:** `dataset_collector/README.md`, README của 4 thư mục firmware cũ, `ml/README.md`.

---

## Task 1: Dựng firmware/aqua_scope_station/ và tắt đèn flash khi chụp

Đây là task quan trọng nhất về mặt vật lý. `capture_handler` của bản Espressif bật **đèn flash trắng GPIO4 trong 150ms trước mỗi lần chụp** (`LED_GPIO_NUM 4` được định nghĩa cho AI-Thinker trong `camera_pins.h:180`). Với rig backlit silhouette, đó là ánh sáng chiếu từ trên xuống mặt nước: làm nhạt tương phản bóng hạt và tạo phản xạ trên mặt nước — đúng thứ toàn bộ thiết kế quang học đang cố tránh.

**Files:**
- Create: `firmware/aqua_scope_station/` (sao toàn bộ từ `dataset_collector/firmware/`)
- Modify: `firmware/aqua_scope_station/app_httpd.cpp` (vùng `capture_handler`, khoảng dòng 158–175)
- Rename: `firmware.ino` → `aqua_scope_station.ino`

**Interfaces:**
- Consumes: không có (task đầu)
- Produces: thư mục firmware biên dịch được, là nền cho Task 2–4

- [ ] **Step 1: Sao thư mục và đổi tên sketch**

```bash
cd "C:/University/Semester 4/IOT102/project"
mkdir -p firmware/aqua_scope_station
cp dataset_collector/firmware/* firmware/aqua_scope_station/
mv firmware/aqua_scope_station/firmware.ino firmware/aqua_scope_station/aqua_scope_station.ino
ls firmware/aqua_scope_station/
```

Kỳ vọng thấy: `aqua_scope_station.ino  app_httpd.cpp  aqua_prefs.cpp  aqua_prefs.h  board_config.h  camera_index.h  camera_pins.h  partitions.csv`

(Arduino IDE yêu cầu tên file `.ino` trùng tên thư mục — đó là lý do phải đổi tên.)

- [ ] **Step 2: Tắt đèn flash trong `capture_handler`**

Trong `firmware/aqua_scope_station/app_httpd.cpp`, tìm khối này ở đầu `capture_handler`:

```cpp
#if defined(LED_GPIO_NUM)
  enable_led(true);
  vTaskDelay(150 / portTICK_PERIOD_MS);  // The LED needs to be turned on ~150ms before the call to esp_camera_fb_get()
  fb = esp_camera_fb_get();              // or it won't be visible in the frame. A better way to do this is needed.
  enable_led(false);
#else
  fb = esp_camera_fb_get();
#endif
```

Thay bằng:

```cpp
  // KHÔNG bật đèn flash GPIO4. Bản gốc Espressif bật nó 150ms trước mỗi lần
  // chụp — hợp lý cho camera thường, nhưng SAI cho rig này: Aqua Scope chiếu
  // sáng bằng đèn nền TỪ DƯỚI (backlit silhouette). Thêm ánh sáng từ trên
  // xuống sẽ làm nhạt bóng đen của hạt và tạo phản xạ trên mặt nước.
  // Bỏ luôn được 150ms trễ mỗi khung.
  fb = esp_camera_fb_get();
```

- [ ] **Step 3: Kiểm tra không còn đường nào bật đèn flash lúc chụp**

```bash
grep -n "enable_led" firmware/aqua_scope_station/app_httpd.cpp
```

Kỳ vọng: chỉ còn các dòng thuộc định nghĩa hàm `enable_led` và nhánh `led_intensity` của `/control`. **Không** còn dòng nào trong `capture_handler` hay `stream_handler`. Nếu `stream_handler` cũng gọi `enable_led`, xóa y hệt với cùng lý do.

- [ ] **Step 4: Biên dịch**

Trước hết định vị arduino-cli (không có trên PATH ở máy này):

```bash
find /c/Users/hieut /c/Program\ Files -maxdepth 6 -name "arduino-cli.exe" 2>/dev/null | head -3
```

Nếu tìm thấy, biên dịch:

```bash
"<đường-dẫn>/arduino-cli.exe" compile --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app "firmware/aqua_scope_station"
```

Kỳ vọng: `Sketch uses ... bytes` và không có lỗi.

Nếu **không** tìm thấy arduino-cli: mở thư mục bằng Arduino IDE, chọn board *AI Thinker ESP32-CAM* + Partition *Huge APP*, bấm **Verify**. Ghi lại kết quả. **Không đánh dấu task xong khi chưa biên dịch được** — ghi rõ trạng thái "chưa verify được, thiếu toolchain" thay vì cho qua.

- [ ] **Step 5: Commit**

```bash
git add firmware/aqua_scope_station
git commit -m "feat(firmware): dựng aqua_scope_station, tắt đèn flash khi chụp

Đèn flash GPIO4 chiếu từ trên xuống làm hỏng ảnh backlit silhouette."
```

---

## Task 2: Danh tính thiết bị (`aqua_device`)

**Files:**
- Create: `firmware/aqua_scope_station/aqua_device.h`
- Create: `firmware/aqua_scope_station/aqua_device.cpp`

**Interfaces:**
- Consumes: không có
- Produces: `const char *aquaDeviceId()`, `bool aquaDeviceSetId(const char *)`, `void aquaDeviceInit()`, `uint32_t aquaDeviceCaptureCount()`, `void aquaDeviceCountCapture()` — Task 3 và 4 gọi các hàm này.

- [ ] **Step 1: Viết `aqua_device.h`**

```cpp
/*
 * aqua_device — danh tính thiết bị cho sổ audit.
 *
 * Vì sao cần: mỗi mẫu trong DB phải chỉ ra ĐÚNG board nào đã chụp nó. Trước
 * đây device_id là hằng "pc-infer" trong config trên máy tính, nên mọi mẫu
 * mang chung một tên — vô nghĩa khi có nhiều board hoặc khi truy ngược lỗi.
 *
 * Mặc định sinh từ MAC nên hai board khác nhau không bao giờ trùng tên, mà
 * cũng không cần cấu hình tay lúc nạp.
 */

#ifndef AQUA_DEVICE_H
#define AQUA_DEVICE_H

#include <stdint.h>

// Nạp device_id đã lưu trong NVS; chưa có thì sinh từ MAC ("aqua-cam-a1b2c3").
// Gọi trong setup(), SAU khi WiFi đã khởi tạo (MAC cần WiFi stack).
void aquaDeviceInit();

// Trả về device_id hiện tại. Không bao giờ NULL sau aquaDeviceInit().
const char *aquaDeviceId();

// Đặt device_id mới và ghi vào NVS.
// Trả về false (không đổi gì) nếu id rỗng, dài quá 64, hoặc chứa ký tự ngoài
// [A-Za-z0-9._-] — ingest của web dùng chuỗi này nguyên văn làm tên file.
bool aquaDeviceSetId(const char *id);

// Đếm số lần chụp từ lúc khởi động (chỉ trong RAM, reset là về 0).
void aquaDeviceCountCapture();
uint32_t aquaDeviceCaptureCount();

#endif  // AQUA_DEVICE_H
```

- [ ] **Step 2: Viết `aqua_device.cpp`**

```cpp
#include "aqua_device.h"

#include <Preferences.h>
#include <WiFi.h>
#include <string.h>

#include <Arduino.h>

static Preferences devPrefs;
static const char *NVS_NS = "aquadev";

static char g_deviceId[65] = {0};
static uint32_t g_captures = 0;

// Cùng tập ký tự với SAMPLE_CODE_PATTERN của web (models.py). Giữ khớp.
static bool idCharOk(char c) {
  return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
         (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-';
}

static bool idValid(const char *id) {
  if (id == nullptr) return false;
  size_t n = strlen(id);
  if (n == 0 || n > 64) return false;
  for (size_t i = 0; i < n; i++) {
    if (!idCharOk(id[i])) return false;
  }
  return true;
}

static void makeDefaultId(char *out, size_t cap) {
  uint8_t mac[6] = {0};
  WiFi.macAddress(mac);
  snprintf(out, cap, "aqua-cam-%02x%02x%02x", mac[3], mac[4], mac[5]);
}

void aquaDeviceInit() {
  devPrefs.begin(NVS_NS, true);  // read-only
  String saved = devPrefs.getString("device_id", "");
  devPrefs.end();

  if (saved.length() > 0 && idValid(saved.c_str())) {
    strncpy(g_deviceId, saved.c_str(), sizeof(g_deviceId) - 1);
  } else {
    makeDefaultId(g_deviceId, sizeof(g_deviceId));
  }
  g_captures = 0;
  Serial.printf("device_id = %s\n", g_deviceId);
}

const char *aquaDeviceId() {
  if (g_deviceId[0] == '\0') {
    makeDefaultId(g_deviceId, sizeof(g_deviceId));
  }
  return g_deviceId;
}

bool aquaDeviceSetId(const char *id) {
  if (!idValid(id)) return false;

  strncpy(g_deviceId, id, sizeof(g_deviceId) - 1);
  g_deviceId[sizeof(g_deviceId) - 1] = '\0';

  devPrefs.begin(NVS_NS, false);  // read-write
  devPrefs.putString("device_id", g_deviceId);
  devPrefs.end();
  return true;
}

void aquaDeviceCountCapture() { g_captures++; }

uint32_t aquaDeviceCaptureCount() { return g_captures; }
```

- [ ] **Step 3: Gọi `aquaDeviceInit()` trong sketch**

Trong `firmware/aqua_scope_station/aqua_scope_station.ino`, thêm include cạnh các include khác:

```cpp
#include "aqua_device.h"
```

Trong `setup()`, chèn **ngay sau** `if (!connectWiFi()) { ... }` và **trước** `startCameraServer();`:

```cpp
  aquaDeviceInit();  // sau WiFi: MAC chỉ đọc được khi WiFi stack đã chạy
```

- [ ] **Step 4: Biên dịch**

Chạy lại lệnh compile của Task 1 Step 4.
Kỳ vọng: biên dịch sạch, không cảnh báo về `aqua_device`.

- [ ] **Step 5: Commit**

```bash
git add firmware/aqua_scope_station/aqua_device.h firmware/aqua_scope_station/aqua_device.cpp firmware/aqua_scope_station/aqua_scope_station.ino
git commit -m "feat(firmware): device_id ổn định sinh từ MAC, lưu NVS"
```

---

## Task 3: Endpoint `GET /device` + lệnh `var=device_id`

**Files:**
- Modify: `firmware/aqua_scope_station/app_httpd.cpp`

**Interfaces:**
- Consumes: `aquaDeviceId()`, `aquaDeviceSetId()`, `aquaDeviceCaptureCount()` (Task 2)
- Produces: `GET /device` trả JSON với các khóa `device_id`, `firmware`, `uptime_s`, `wifi{ssid,rssi,ip}`, `psram`, `sensor`, `camera{framesize,width,height,quality,aec,aec2,agc,gain,exposure}`, `captures`, `prefs_saved` — Task 7 (`Esp32CaptureSource`) đọc đúng các tên này.

- [ ] **Step 1: Thêm hàm cho `aqua_prefs` biết đã lưu hay chưa**

`/device` phải báo `prefs_saved`, vì "board boot lại về auto do chưa `var=save`" là lỗi hay gặp nhất trong README hiện tại.

Thêm vào cuối `firmware/aqua_scope_station/aqua_prefs.h`, trước `#endif`:

```cpp
// Flash đã có cấu hình lưu hay chưa (không áp gì lên sensor).
bool aquaPrefsIsSaved();
```

Thêm vào cuối `firmware/aqua_scope_station/aqua_prefs.cpp`:

```cpp
bool aquaPrefsIsSaved() {
  prefs.begin(NVS_NS, true);  // read-only
  bool saved = prefs.getBool("saved", false);
  prefs.end();
  return saved;
}
```

- [ ] **Step 2: Viết `device_handler` trong `app_httpd.cpp`**

Thêm include ở đầu file, cạnh `#include "aqua_prefs.h"`:

```cpp
#include "aqua_device.h"
#include <WiFi.h>
```

Thêm hằng phiên bản ngay dưới phần include:

```cpp
#define AQUA_FIRMWARE_VERSION "aqua_scope_station/1.0.0"
```

Thêm handler này **ngay trước** `static esp_err_t status_handler(httpd_req_t *req) {`:

```cpp
// GET /device — danh tính + thiết lập hiện hành, phục vụ truy xuất nguồn gốc.
// KHÁC với /status: /status trả cấu hình camera cho slider của web UI (định
// dạng do bản gốc Espressif quy định, không được đổi). /device là khối audit
// mà ml.infer nhét vào metadata của mẫu.
static esp_err_t device_handler(httpd_req_t *req) {
  static char json[640];
  sensor_t *s = esp_camera_sensor_get();

  const char *sensorName = "unknown";
  if (s != nullptr) {
    if (s->id.PID == OV2640_PID) sensorName = "OV2640";
    else if (s->id.PID == OV3660_PID) sensorName = "OV3660";
    else if (s->id.PID == OV5640_PID) sensorName = "OV5640";
  }

  framesize_t fs = (s != nullptr) ? (framesize_t)s->status.framesize : FRAMESIZE_UXGA;
  uint16_t w = resolution[fs].width;
  uint16_t h = resolution[fs].height;

  snprintf(json, sizeof(json),
           "{\"device_id\":\"%s\","
           "\"firmware\":\"%s\","
           "\"uptime_s\":%lu,"
           "\"wifi\":{\"ssid\":\"%s\",\"rssi\":%d,\"ip\":\"%s\"},"
           "\"psram\":%s,"
           "\"sensor\":\"%s\","
           "\"camera\":{\"framesize\":%d,\"width\":%u,\"height\":%u,"
           "\"quality\":%d,\"aec\":%d,\"aec2\":%d,\"agc\":%d,"
           "\"gain\":%d,\"exposure\":%d},"
           "\"captures\":%lu,"
           "\"prefs_saved\":%s}",
           aquaDeviceId(),
           AQUA_FIRMWARE_VERSION,
           (unsigned long)(millis() / 1000UL),
           WiFi.SSID().c_str(), WiFi.RSSI(), WiFi.localIP().toString().c_str(),
           psramFound() ? "true" : "false",
           sensorName,
           (int)fs, w, h,
           s ? s->status.quality : 0,
           s ? s->status.aec : 0,
           s ? s->status.aec2 : 0,
           s ? s->status.agc : 0,
           s ? s->status.agc_gain : 0,
           s ? s->status.aec_value : 0,
           (unsigned long)aquaDeviceCaptureCount(),
           aquaPrefsIsSaved() ? "true" : "false");

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
}
```

- [ ] **Step 3: Đăng ký `/device`**

Trong `startCameraServer()`, thêm cạnh các khai báo `httpd_uri_t` khác (ví dụ ngay sau khối `status_uri`):

```cpp
  httpd_uri_t device_uri = {
    .uri = "/device",
    .method = HTTP_GET,
    .handler = device_handler,
    .user_ctx = NULL
#ifdef CONFIG_HTTPD_WS_SUPPORT
    ,
    .is_websocket = true,
    .handle_ws_control_frames = false,
    .supported_subprotocol = NULL
#endif
  };
```

Và trong khối `if (httpd_start(&camera_httpd, &config) == ESP_OK) {`, thêm sau dòng đăng ký `status_uri`:

```cpp
    httpd_register_uri_handler(camera_httpd, &device_uri);
```

- [ ] **Step 4: Thêm `var=device_id` vào `cmd_handler`**

`cmd_handler` hiện chuyển `val` sang `int` bằng `atoi` — không dùng được cho chuỗi. Nên nhánh này phải đọc **chuỗi `value` thô**.

Trong `cmd_handler`, tìm nhánh `save`:

```cpp
  else if (!strcmp(variable, "save")) {
```

Chèn **ngay trước** nó:

```cpp
  // Chuỗi, không phải số: dùng `value` thô chứ không dùng `val` (đã qua atoi).
  else if (!strcmp(variable, "device_id")) {
    if (!aquaDeviceSetId(value)) {
      httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST,
                          "device_id phải khớp [A-Za-z0-9._-], dài 1..64");
      return ESP_FAIL;
    }
  }
```

- [ ] **Step 5: Đếm mỗi lần chụp**

Trong `capture_handler`, ngay sau khối kiểm tra `if (!fb) { ... }`, thêm:

```cpp
  aquaDeviceCountCapture();
```

- [ ] **Step 6: Biên dịch**

Chạy lệnh compile của Task 1 Step 4.
Kỳ vọng: sạch. Nếu báo `resolution` chưa khai báo, thêm `#include "sensor.h"` — mảng `resolution[]` do thư viện camera cung cấp.

- [ ] **Step 7: Commit**

```bash
git add firmware/aqua_scope_station
git commit -m "feat(firmware): GET /device báo danh tính + thiết lập camera cho sổ audit"
```

---

## Task 4: Độ bền — tự nối lại WiFi, watchdog, chụp lỗi trả 503

**Files:**
- Modify: `firmware/aqua_scope_station/aqua_scope_station.ino`
- Modify: `firmware/aqua_scope_station/app_httpd.cpp` (`capture_handler`)

**Interfaces:**
- Consumes: không có gì mới
- Produces: `/capture` trả **503** kèm thân là chuỗi lý do khi chụp lỗi — Task 7 dựa vào đúng hành vi này để bỏ qua khung mà không hỏng cả lượt.

- [ ] **Step 1: `/capture` trả 503 thay vì 500**

Trong `app_httpd.cpp`, tìm trong `capture_handler`:

```cpp
  if (!fb) {
    log_e("Camera capture failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
```

Thay bằng:

```cpp
  if (!fb) {
    // 503 chứ không 500: đây là hỏng TẠM THỜI (thường do brownout khi WiFi TX
    // và chụp UXGA trùng nhau). Client nên thử lại khung này, không nên coi là
    // board hỏng. Kèm thân lý do để log phía PC nói được điều gì đã xảy ra.
    log_e("Camera capture failed");
    httpd_resp_set_status(req, "503 Service Unavailable");
    httpd_resp_set_type(req, "text/plain");
    httpd_resp_sendstr(req, "camera capture failed (esp_camera_fb_get tra NULL)");
    return ESP_FAIL;
  }
```

- [ ] **Step 2: WiFi tự nối lại, không chặn**

Trong `aqua_scope_station.ino`, thêm vào `connectWiFi()` **ngay trước** `WiFi.begin(STA_SSID, STA_PASS);`:

```cpp
  // Tự nối lại khi router chớp nguồn hoặc sóng rớt. Đặt TRƯỚC begin() để
  // không bỏ lỡ sự kiện disconnect đầu tiên.
  WiFi.setAutoReconnect(true);
  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
    Serial.println("[WiFi] mất kết nối — đang nối lại...");
    WiFi.reconnect();
  }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);

  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
    Serial.printf("[WiFi] đã nối lại | IP: %s\n",
                  WiFi.localIP().toString().c_str());
  }, ARDUINO_EVENT_WIFI_STA_GOT_IP);
```

- [ ] **Step 3: Không dừng setup() khi WiFi hỏng lúc khởi động**

Bản hiện tại `return` khỏi `setup()` khi hết 20s không nối được — board thành cục gạch cho tới khi có người rút điện. Với trạm chạy dài, phải để nó tiếp tục thử.

Trong `setup()`, thay:

```cpp
  if (!connectWiFi()) {
    Serial.println("Dừng lại: không có mạng thì laptop không kéo ảnh được.");
    return;
  }
```

bằng:

```cpp
  if (!connectWiFi()) {
    // KHÔNG return: WiFi event handler ở trên vẫn tiếp tục thử nối lại. Dừng
    // setup() ở đây sẽ khiến board đứng im tới khi có người rút điện — không
    // chấp nhận được với trạm chạy dài.
    Serial.println("[CẢNH BÁO] Chưa nối được WiFi. Vẫn chạy tiếp và thử lại nền.");
    Serial.println("           Server sẽ phục vụ được ngay khi có IP.");
  }
```

- [ ] **Step 4: Bật watchdog cho loop**

Thêm include ở đầu `aqua_scope_station.ino`:

```cpp
#include "esp_task_wdt.h"
```

Thêm ở **cuối** `setup()`:

```cpp
  // Watchdog 30s cho task loop: nếu loop treo, board tự reset thay vì đứng câm.
  // 30s rộng rãi so với nhịp báo cáo 10s bên dưới.
  esp_task_wdt_config_t wdtConfig = {
    .timeout_ms = 30000,
    .idle_core_mask = 0,
    .trigger_panic = true,
  };
  esp_task_wdt_init(&wdtConfig);
  esp_task_wdt_add(NULL);
```

Thay `loop()` bằng:

```cpp
void loop() {
  esp_task_wdt_reset();  // báo watchdog rằng loop còn sống

  // Server chạy ở task riêng của esp_http_server; loop chỉ báo trạng thái để
  // soi khi /capture bị timeout giữa phiên đo dài.
  if (!USE_AP) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("[WiFi] OK | IP=%s | RSSI=%d dBm | chụp=%lu\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI(),
                    (unsigned long)aquaDeviceCaptureCount());
    } else {
      Serial.printf("[WiFi] mất kết nối (status=%d) — đang thử nối lại\n",
                    WiFi.status());
    }
  }
  delay(10000);
}
```

- [ ] **Step 5: Biên dịch**

Chạy lệnh compile của Task 1 Step 4.
Kỳ vọng: sạch. Nếu `esp_task_wdt_config_t` báo lỗi, core esp32 đang là 2.x — plan này yêu cầu **≥ 3.0** (xem Global Constraints); nâng core lên chứ đừng lùi API.

- [ ] **Step 6: Commit**

```bash
git add firmware/aqua_scope_station
git commit -m "feat(firmware): tự nối lại WiFi, watchdog, /capture lỗi trả 503"
```

---

## Task 5: README firmware + đánh dấu các bản cũ

**Files:**
- Create: `firmware/aqua_scope_station/README.md`
- Modify: `firmware/Esp32 cam/`, `firmware/aqua_scope_cam/README.md`, `firmware/esp32-cam-webserver/README.md`, `firmware/pump_stopflow_test/README.md`
- Modify: `dataset_collector/README.md`

**Interfaces:**
- Consumes: hành vi của `/device`, `/capture` từ Task 1–4
- Produces: không có mã

- [ ] **Step 1: Viết `firmware/aqua_scope_station/README.md`**

```markdown
# Aqua Scope — Firmware chính thức (ESP32-CAM AI-Thinker)

**Đây là bản duy nhất cần nạp.** Các thư mục firmware khác trong repo là thử
nghiệm hoặc tiền đề, giữ lại để tham khảo.

Vai trò: cung cấp ảnh backlit chất lượng đúng, ổn định, kèm đủ thông tin để
truy xuất nguồn gốc. Firmware **không** đếm hạt, không lưu trữ, không suy luận
— việc đó do `ml.infer` trên máy tính làm.

## Endpoint

| Endpoint | Dùng để |
|---|---|
| `GET /` | Web UI canh sáng (slider) |
| `GET /stream` | MJPEG xem trực tiếp — chỉ dùng lúc canh sáng |
| `GET /capture` | Một ảnh JPEG. Chụp lỗi → **503** kèm lý do |
| `GET /device` | JSON danh tính + thiết lập camera (khối audit) |
| `GET /status` | JSON cấu hình cho slider (bản gốc Espressif) |
| `GET /control?var=save&val=1` | Ghi cứng cấu hình vào flash |
| `GET /control?var=reset&val=1` | Xóa cấu hình, về mặc định backlit |
| `GET /control?var=device_id&val=<tên>` | Đổi device_id (khớp `[A-Za-z0-9._-]`, 1–64 ký tự) |

## Nạp firmware

Arduino IDE, cần gói board **esp32 by Espressif ≥ 3.0**:

| Mục | Chọn |
|---|---|
| Board | **AI Thinker ESP32-CAM** |
| Partition Scheme | **Huge APP (3MB No OTA/1MB SPIFFS)** |

Sửa WiFi ở đầu `aqua_scope_station.ino`, nối **IO0 → GND**, cấp nguồn, Upload,
rút IO0, reset. Mở Serial Monitor 115200 để lấy IP và `device_id`.

## Khác gì bản CameraWebServer gốc

1. **Mặc định backlit** — tắt AEC / AEC-DSP / AGC, gain 0, exposure 100. Bản
   gốc để auto, và auto-exposure sẽ kéo nền cháy trắng nuốt mất hạt.
2. **Không bật đèn flash khi chụp.** Bản gốc bật GPIO4 150ms trước mỗi lần
   chụp. Rig này chiếu sáng **từ dưới** — thêm đèn từ trên làm nhạt bóng hạt
   và tạo phản xạ trên mặt nước.
3. **Mặc định UXGA 1600×1200** — hạt <2mm cần độ phân giải.
4. **Lưu cấu hình vào flash** — `?var=save` / `?var=reset`.
5. **`/device`** — device_id sinh từ MAC + thiết lập camera đang áp dụng.
6. **Chạy dài không chết** — tự nối lại WiFi, watchdog, chụp lỗi trả 503 rõ
   ràng thay vì treo.

## Checklist nghiệm thu trên board thật

Chưa chạy đủ 7 mục này thì **chưa được nói firmware "chạy được"**.

- [ ] 1. Nạp xong, Serial 115200 in ra IP và `device_id = aqua-cam-xxxxxx`
- [ ] 2. `curl http://<ip>/device` → JSON hợp lệ, `psram: true`
- [ ] 3. Mở `http://<ip>/` chỉnh slider → nền xám đều, hạt là bóng đen rõ
- [ ] 4. `?var=save` → rút điện → cắm lại → `/device` báo `prefs_saved: true`
      và đúng thông số vừa chỉnh
- [ ] 5. Tắt router 30 giây rồi bật lại → board tự nối lại, `/device` phản hồi,
      **không** cần bấm reset
- [ ] 6. `python -m ml.infer --from-board <ip> --count 3 --dry-run` → 3 khung,
      không có dòng nào ghi vào DB
- [ ] 7. Bỏ `--dry-run` → 3 mẫu hiện trên dashboard, cột device_id đúng tên board

## Chưa có (cố ý)

Điều khiển đèn nền (đèn cắm thẳng, luôn sáng), điều khiển bơm, suy luận
on-device. State machine bơm nằm riêng ở `firmware/pump_stopflow_test/`; khi
gộp vào đây thì chỗ đặt là `loop()`, và relay dùng **GPIO13** (active-LOW —
phải kéo HIGH ở dòng đầu `setup()` để bơm không tự chạy lúc boot).
```

- [ ] **Step 2: Đánh dấu các firmware cũ**

Thêm dòng này vào **đầu** README của mỗi thư mục `firmware/aqua_scope_cam/`, `firmware/esp32-cam-webserver/`, `firmware/pump_stopflow_test/`:

```markdown
> **Tham khảo/thử nghiệm — không nạp bản này.** Firmware chính thức của dự án
> là [`firmware/aqua_scope_station/`](../aqua_scope_station/).
```

`firmware/pump_stopflow_test/` là ngoại lệ một phần — nó vẫn là công cụ test bơm hợp lệ. Dùng câu này cho nó thay vào:

```markdown
> **Công cụ test bơm độc lập** — không phải firmware của trạm. Firmware chính
> thức là [`firmware/aqua_scope_station/`](../aqua_scope_station/).
```

Với `firmware/Esp32 cam/` (không có README), tạo `firmware/Esp32 cam/README.md` chứa đúng dòng cảnh báo đầu tiên.

- [ ] **Step 3: Sửa `dataset_collector/README.md`**

`dataset_collector/firmware/` bị thay thế bởi bản mới. Thay toàn bộ mục "## Bước 1 — Nạp firmware" bằng:

```markdown
## Bước 1 — Nạp firmware

Dùng **[`firmware/aqua_scope_station/`](../firmware/aqua_scope_station/)** — bản
chính thức của dự án. Xem hướng dẫn nạp trong README của nó.

`dataset_collector/firmware/` là bản tiền thân, giữ lại để tham khảo. Bản chính
thức là hậu duệ trực tiếp: cùng `/capture`, nên `collect_dataset.py` chạy được
với cả hai.
```

Thêm vào cuối README, mục mới:

```markdown
## Khác gì `ml.infer --from-board`

Hai công cụ, hai mục đích, cố ý không gộp:

| | `collect_dataset.py` | `ml.infer --from-board` |
|---|---|---|
| Mục đích | thu ảnh thô để **train** | đo mẫu thật để **ghi sổ audit** |
| Đầu ra | file JPEG trong `data/dataset/` | dòng Sample + Particle trong DB |
| Chạy suy luận | không | có |

Gộp lại sẽ buộc công cụ thu dataset phải mang theo cả detector lẫn kết nối DB
— hai thứ nó không cần.
```

- [ ] **Step 4: Commit**

```bash
git add firmware dataset_collector/README.md
git commit -m "docs(firmware): README bản chính thức + đánh dấu các bản cũ"
```

---

## Task 6: Cấu hình `[station]` trong ml/

**Files:**
- Modify: `ml/infer/config.py`
- Modify: `ml/config.toml`
- Test: `ml/tests/test_config.py`

**Interfaces:**
- Consumes: không có
- Produces: khóa cấu hình `station.host`, `station.timeout_s`, `station.retries`, `station.interval_s`; `Config.missing_for("station")` trả về danh sách vấn đề — Task 8 gọi tới.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `ml/tests/test_config.py`:

```python
def test_station_defaults_present():
    cfg = config.load(config_path="ml/config.toml", env={})
    assert cfg.get("station", "timeout_s") == 20
    assert cfg.get("station", "retries") == 3
    assert cfg.get("station", "interval_s") == 2.0


def test_missing_for_station_flags_empty_host():
    cfg = config.Config({"station": {"host": ""}})
    problems = cfg.missing_for("station")
    assert len(problems) == 1
    assert "station.host" in problems[0]


def test_missing_for_station_ok_when_host_set():
    cfg = config.Config({"station": {"host": "192.168.1.50"}})
    assert cfg.missing_for("station") == []
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest ml/tests/test_config.py -k station -v`
Kỳ vọng: FAIL — `assert None == 20` và `missing_for` trả về thông báo "not one of: local, roboflow".

- [ ] **Step 3: Thêm `station` vào `DEFAULTS`**

Trong `ml/infer/config.py`, thêm vào dict `DEFAULTS` ngay sau mục `"ingest"`:

```python
    "station": {                          # ESP32-CAM đọc ảnh trực tiếp
        "host": "",                       # IP/hostname board, lấy từ Serial Monitor
        "timeout_s": 20,                  # UXGA qua WiFi có thể lâu
        "retries": 3,                     # số lần thử lại mỗi khung
        "interval_s": 2.0,                # nghỉ giữa hai lần chụp
    },
```

- [ ] **Step 4: Thêm nhánh station vào `missing_for`**

`missing_for` hiện nhận tên *backend*. Chế độ station trực giao với backend (đọc từ board vẫn chạy được cả `local` lẫn `roboflow`), nên xử lý nó như một khóa kiểm tra riêng chứ không phải backend thứ ba.

Trong `ml/infer/config.py`, trong `missing_for`, chèn **ngay trước** `if backend == "roboflow":`:

```python
        if backend == "station":
            # Trực giao với backend suy luận: chỉ kiểm tra nguồn ảnh có địa chỉ
            # hay chưa. CLI gọi riêng missing_for("station") cùng với
            # missing_for(<backend thật>) khi chạy --from-board.
            if not self.get("station", "host"):
                problems.append(
                    "station.host chưa đặt - IP của board, lấy từ Serial Monitor "
                    "(hoặc dùng cờ --from-board <ip>).")
            return problems
```

- [ ] **Step 5: Chạy test để xác nhận đạt**

Run: `python -m pytest ml/tests/test_config.py -v`
Kỳ vọng: PASS toàn bộ (cả test cũ).

- [ ] **Step 6: Tài liệu hóa trong `ml/config.toml`**

Thêm sau mục `[ingest]`:

```toml
[station]
# Doc anh THANG tu board ESP32-CAM (che do --from-board), thay vi doc thu muc.
# Truc giao voi general.backend: van chay duoc ca "local" lan "roboflow".
host = ""          # IP hoac hostname board, lay tu Serial Monitor
timeout_s = 20     # timeout moi request (UXGA qua WiFi co the lau)
retries = 3        # so lan thu lai moi khung anh truoc khi bo qua
interval_s = 2.0   # nghi giua hai lan chup (giay)
```

- [ ] **Step 7: Commit**

```bash
git add ml/infer/config.py ml/config.toml ml/tests/test_config.py
git commit -m "feat(ml): thêm cấu hình [station] cho chế độ đọc từ board"
```

---

## Task 7: `Esp32CaptureSource`

**Files:**
- Modify: `ml/infer/source.py`
- Test: `ml/tests/test_source.py`

**Interfaces:**
- Consumes: `Frame` (đã có trong `source.py`), khóa JSON của `/device` (Task 3)
- Produces:
  - `Esp32CaptureSource(host, *, count=1, interval_s=2.0, timeout_s=20, retries=3)`
  - `.device_info` → `dict` (nội dung `/device`), có sau khi khởi tạo
  - `.frames()` → generator các `Frame`, cùng hợp đồng với `FolderSource`
  - `class StationError(RuntimeError)`

  Task 8 (`cli.py`) dùng đúng các tên này.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `ml/tests/test_source.py` (giữ nguyên phần `FolderSource` đã có):

```python
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ml.infer.source import Esp32CaptureSource, StationError

_DEVICE_JSON = {
    "device_id": "aqua-cam-a1b2c3",
    "firmware": "aqua_scope_station/1.0.0",
    "uptime_s": 42,
    "wifi": {"ssid": "test", "rssi": -55, "ip": "127.0.0.1"},
    "psram": True,
    "sensor": "OV2640",
    "camera": {"framesize": 13, "width": 1600, "height": 1200, "quality": 10,
               "aec": 0, "aec2": 0, "agc": 0, "gain": 0, "exposure": 100},
    "captures": 7,
    "prefs_saved": True,
}


def _jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


class _FakeBoard:
    """ESP32-CAM giả bằng HTTP server THẬT.

    Dùng server thật chứ không mock `requests`: các ca hỏng ngoài đời quan
    trọng nhất (body cụt, HTML kèm HTTP 200, server chết giữa burst) chỉ tái
    hiện được ở tầng socket. Mock sẽ bỏ lọt đúng những ca đó.
    """

    def __init__(self, capture_responses, device_response=None):
        self._captures = list(capture_responses)
        self._device = device_response
        self.capture_hits = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/device":
                    kind, payload = outer._device
                    outer._respond(self, kind, payload)
                elif self.path == "/capture":
                    idx = min(outer.capture_hits, len(outer._captures) - 1)
                    outer.capture_hits += 1
                    kind, payload = outer._captures[idx]
                    outer._respond(self, kind, payload)
                else:
                    self.send_response(404)
                    self.end_headers()

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.host = f"127.0.0.1:{self._server.server_port}"

    @staticmethod
    def _respond(handler, kind, payload):
        if kind == "json":
            body = json.dumps(payload).encode()
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
        elif kind == "jpeg":
            handler.send_response(200)
            handler.send_header("Content-Type", "image/jpeg")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
        elif kind == "html200":
            body = b"<html>captive portal</html>"
            handler.send_response(200)
            handler.send_header("Content-Type", "text/html")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
        elif kind == "503":
            body = b"camera capture failed"
            handler.send_response(503)
            handler.send_header("Content-Type", "text/plain")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


def test_reads_device_info_then_yields_frames():
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=2, interval_s=0)
        assert src.device_info["device_id"] == "aqua-cam-a1b2c3"

        frames = list(src.frames())

    assert len(frames) == 2
    for f in frames:
        assert f.image_bytes[:2] == b"\xff\xd8"       # JPEG magic
        assert f.captured_at.tzinfo is not None        # ingest đòi có offset
        assert f.sample_code.startswith("S")
    # sample_code phải khác nhau, nếu không ingest coi khung sau là trùng
    assert frames[0].sample_code != frames[1].sample_code


def test_unreachable_board_raises_immediately():
    # Cổng đóng: phải hỏng NGAY ở /device, không âm thầm chụp tiếp.
    with pytest.raises(StationError) as exc:
        Esp32CaptureSource("127.0.0.1:1", count=1, timeout_s=1, retries=1)
    assert "/device" in str(exc.value)


def test_device_json_missing_keys_does_not_crash():
    with _FakeBoard([("jpeg", _jpeg_bytes())],
                    device_response=("json", {"device_id": "x"})) as board:
        src = Esp32CaptureSource(board.host, count=1, interval_s=0)
        assert src.device_info["device_id"] == "x"
        assert list(src.frames())


def test_html_with_http_200_is_rejected_not_treated_as_image():
    with _FakeBoard([("html200", None)],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=1, interval_s=0, retries=2)
        assert list(src.frames()) == []      # bỏ qua khung, không đẩy rác đi
        assert board.capture_hits == 2       # đã thử lại đủ số lần


def test_503_frame_is_skipped_and_run_continues():
    with _FakeBoard([("503", None), ("jpeg", _jpeg_bytes())],
                    device_response=("json", _DEVICE_JSON)) as board:
        src = Esp32CaptureSource(board.host, count=2, interval_s=0, retries=1)
        frames = list(src.frames())
    # khung 1 hỏng và bị bỏ; khung 2 vẫn tới nơi — một lỗi không giết cả lượt
    assert len(frames) == 1


def test_server_dies_midway_yields_earlier_frames():
    """Brownout giữa burst: khung đã lấy được phải giữ nguyên, và vòng lặp
    phải KẾT THÚC bình thường thay vì ném ngoại lệ ra ngoài."""
    board = _FakeBoard([("jpeg", _jpeg_bytes())],
                       device_response=("json", _DEVICE_JSON))
    with board:
        src = Esp32CaptureSource(board.host, count=3, interval_s=0, retries=1)
        frames = []
        for i, frame in enumerate(src.frames()):
            frames.append(frame)
            if i == 0:
                board._server.shutdown()   # board chết ngay sau khung đầu

    # Đúng 1 khung: khung đầu tới nơi, hai khung sau hỏng vì board đã chết.
    # (Nếu chỉ khẳng định >= 1 thì test không bao giờ fail được — khung đầu
    # luôn được append trước khi shutdown.)
    assert len(frames) == 1
    assert frames[0].image_bytes[:2] == b"\xff\xd8"
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest ml/tests/test_source.py -v`
Kỳ vọng: FAIL — `ImportError: cannot import name 'Esp32CaptureSource'`

- [ ] **Step 3: Cài `Esp32CaptureSource`**

Thay đoạn docstring đầu `ml/infer/source.py` và thêm lớp mới. Docstring mới:

```python
"""Image sources for the inference CLI.

FolderSource reads image files from disk; Esp32CaptureSource pulls them
straight off the board over HTTP. Both expose the same .frames() interface, so
cli.py / mapper.py / ingest_client.py never learn which one they got.
"""
```

Thêm các import cần thiết ở đầu file:

```python
import time

import requests
```

Thêm vào cuối file:

```python
class StationError(RuntimeError):
    """Board không dùng được (không tới được, hoặc /device không hợp lệ)."""


class Esp32CaptureSource:
    """Chụp ảnh trực tiếp từ firmware aqua_scope_station qua HTTP.

    Hỏng NGAY ở /device: nếu không đọc được danh tính board thì mọi mẫu thu
    được sau đó cũng không truy nguyên được — thà dừng còn hơn ghi vào sổ audit
    những dòng không biết đến từ đâu.

    Ngược lại, một khung ảnh hỏng chỉ làm mất khung đó. Brownout khi WiFi TX
    trùng lúc chụp UXGA là chuyện thường ngày trên board này; để nó giết cả
    lượt đo là sai.
    """

    def __init__(self, host, *, count=1, interval_s=2.0, timeout_s=20, retries=3):
        self.base_url = host if "://" in host else f"http://{host}"
        self.count = int(count)
        self.interval_s = float(interval_s)
        self.timeout_s = float(timeout_s)
        self.retries = max(1, int(retries))
        self.device_info = self._read_device()

    def _read_device(self):
        url = f"{self.base_url}/device"
        try:
            resp = requests.get(url, timeout=self.timeout_s)
            resp.raise_for_status()
            info = resp.json()
        except Exception as exc:
            raise StationError(
                f"không đọc được {url}: {exc}. Kiểm tra board đã bật, đúng IP, "
                f"và đã nạp firmware/aqua_scope_station."
            ) from exc
        if not isinstance(info, dict):
            raise StationError(f"{url} trả về JSON không phải object: {info!r}")
        return info

    @property
    def device_id(self):
        """device_id board tự báo, hoặc None nếu firmware không khai."""
        value = self.device_info.get("device_id")
        return value if isinstance(value, str) and value else None

    def _capture_once(self):
        """Trả về bytes JPEG, hoặc raise nếu khung này hỏng."""
        url = f"{self.base_url}/capture"
        resp = requests.get(url, timeout=self.timeout_s)
        if resp.status_code != 200:
            raise StationError(
                f"HTTP {resp.status_code}: {resp.text[:120]}")
        body = resp.content
        # Kiểm tra magic, KHÔNG tin Content-Type: một captive portal của router
        # trả HTML kèm HTTP 200 và đủ loại header. Đẩy HTML vào detector sẽ ra
        # lỗi khó hiểu ở tận cuối pipeline.
        if not body.startswith(b"\xff\xd8"):
            raise StationError(
                f"phản hồi không phải JPEG (bắt đầu bằng {body[:8]!r})")
        if not body.rstrip().endswith(b"\xff\xd9"):
            raise StationError("JPEG cụt (thiếu marker kết thúc)")
        return body

    def frames(self):
        for i in range(self.count):
            if i > 0 and self.interval_s > 0:
                time.sleep(self.interval_s)

            body = None
            last_error = None
            for attempt in range(self.retries):
                try:
                    body = self._capture_once()
                    break
                except Exception as exc:
                    last_error = exc

            if body is None:
                print(f"[warn] khung {i + 1}/{self.count} hỏng, bỏ qua: {last_error}")
                continue

            captured_at = datetime.now(timezone.utc)
            yield Frame(
                image_bytes=body,
                sample_code=_station_sample_code(captured_at),
                captured_at=captured_at,
                source_name=f"{self.base_url}/capture#{i + 1}",
            )


def _station_sample_code(captured_at):
    """`S{yyyyMMdd}-{HHmmss}-{mmm}` — đủ mịn để hai khung liền nhau không trùng.

    Cùng dạng với mã do server sinh (web/backend/app/routers/ingest.py), và
    khớp sẵn ^[A-Za-z0-9._-]{1,64}$ nên không cần làm sạch thêm.
    """
    return (f"S{captured_at:%Y%m%d}-{captured_at:%H%M%S}-"
            f"{captured_at.microsecond // 1000:03d}")
```

- [ ] **Step 4: Chạy test để xác nhận đạt**

Run: `python -m pytest ml/tests/test_source.py -v`
Kỳ vọng: PASS toàn bộ, gồm cả 2 test `FolderSource` cũ.

- [ ] **Step 5: Commit**

```bash
git add ml/infer/source.py ml/tests/test_source.py
git commit -m "feat(ml): Esp32CaptureSource đọc ảnh thẳng từ board qua HTTP"
```

---

## Task 8: Đấu dây `--from-board` vào CLI

**Files:**
- Modify: `ml/infer/cli.py`
- Test: `ml/tests/test_cli.py`

**Interfaces:**
- Consumes: `Esp32CaptureSource`, `StationError` (Task 7); `missing_for("station")` (Task 6)
- Produces: cờ CLI `--from-board`, `--count`, `--interval`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `ml/tests/test_cli.py`:

```python
def test_from_board_and_folder_together_is_rejected(tmp_path, capsys):
    rc = cli.main([str(tmp_path), "--from-board", "192.168.1.50"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "--from-board" in out


def test_no_input_and_no_station_host_reports_both_options(capsys):
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 2
    assert "--from-board" in out
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest ml/tests/test_cli.py -k from_board -v`
Kỳ vọng: FAIL — argparse báo `unrecognized arguments: --from-board` (SystemExit 2 kèm output ở stderr, không phải stdout).

- [ ] **Step 3: Thêm cờ vào parser**

Trong `ml/infer/cli.py`, thêm vào `build_arg_parser()` sau dòng `p.add_argument("--batch-lot", ...)`:

```python
    p.add_argument("--from-board", default=None, metavar="HOST",
                   help="Chụp thẳng từ ESP32-CAM (IP/hostname) thay vì đọc "
                        "thư mục ảnh. Mặc định lấy từ [station].host.")
    p.add_argument("--count", type=int, default=None,
                   help="Số khung chụp ở chế độ --from-board (mặc định 1)")
    p.add_argument("--interval", type=float, default=None,
                   help="Giây nghỉ giữa hai lần chụp (mặc định [station].interval_s)")
```

- [ ] **Step 4: Chọn source trong `main()`**

Thêm import ở đầu file:

```python
from .source import Esp32CaptureSource, FolderSource, StationError
```

(xóa dòng `from .source import FolderSource` cũ)

Thay đoạn:

```python
    if not args.input:
        print("[error] missing input (image file or folder). See --help.")
        return 2
```

bằng:

```python
    station_host = (args.from_board if args.from_board is not None
                    else cfg.get("station", "host"))

    if args.input and args.from_board:
        print("[error] chọn MỘT trong hai: thư mục ảnh, hoặc --from-board <ip>. "
              "Đưa cả hai thì không rõ định lấy ảnh từ đâu.")
        return 2
    if not args.input and not station_host:
        print("[error] chưa có nguồn ảnh. Đưa thư mục ảnh, hoặc dùng "
              "--from-board <ip> (hoặc đặt [station].host trong ml/config.toml).")
        return 2
```

Sau đó thay dòng `source = FolderSource(args.input)` bằng:

```python
    if args.input:
        source = FolderSource(args.input)
    else:
        station = cfg.section("station")
        try:
            source = Esp32CaptureSource(
                station_host,
                count=args.count if args.count is not None else 1,
                interval_s=(args.interval if args.interval is not None
                            else station.get("interval_s")),
                timeout_s=station.get("timeout_s"),
                retries=station.get("retries"),
            )
        except StationError as exc:
            print(f"[error] {exc}")
            return 2
        print(f"[station] {source.device_id or '(không rõ device_id)'} @ "
              f"{station_host} | firmware={source.device_info.get('firmware')}")
        if source.device_info.get("prefs_saved") is False:
            print("[warn] board CHƯA lưu cấu hình camera vào flash. Sau khi mất "
                  "điện nó sẽ về mặc định — canh sáng lại rồi gọi "
                  f"http://{station_host}/control?var=save&val=1")
        # device_id của board thắng hằng trong config, nhưng cờ tay vẫn thắng cả hai.
        if args.device_id is None and source.device_id:
            device_id = source.device_id
```

- [ ] **Step 5: Cho `--check-config` báo cáo cả station**

`missing_for("station")` (Task 6) phải thực sự được dùng, nếu không nó là code chết.
Station trực giao với backend, nên `--check-config` báo cáo **cả hai**.

Trong `main()`, thay khối `if args.check_config:` bằng:

```python
    if args.check_config:
        problems = cfg.missing_for(backend)
        print(f"backend = {backend}")
        # Nguồn ảnh trực giao với backend suy luận: chỉ soi khi người dùng thực
        # sự định chụp từ board, chứ không bắt ai chạy thư mục ảnh phải khai host.
        if args.from_board or cfg.get("station", "host"):
            host = args.from_board or cfg.get("station", "host")
            print(f"station = {host or '(chưa đặt)'}")
            problems = problems + cfg.missing_for("station")
        if problems:
            print("Config NOT ready:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("Config OK - ready to run.")
        return 0
```

Lưu ý thứ tự: khối này nằm **trước** phần phân giải `station_host` ở Step 4, nên nó đọc
`args.from_board` trực tiếp.

- [ ] **Step 6: Chạy test để xác nhận đạt**

Run: `python -m pytest ml/tests/test_cli.py -v`
Kỳ vọng: PASS toàn bộ.

- [ ] **Step 7: Chạy toàn bộ test của ml/**

Run: `python -m pytest ml/tests/ -q`
Kỳ vọng: tất cả PASS. Nếu test cũ hỏng vì thứ tự tham số `main()` đổi, sửa test cũ — nhưng phải nêu rõ vì sao trong commit message.

- [ ] **Step 8: Commit**

```bash
git add ml/infer/cli.py ml/tests/test_cli.py
git commit -m "feat(ml): --from-board chụp thẳng từ board rồi ghi vào sổ audit"
```

---

## Task 9: Ghi khối `/device` vào metadata của mẫu

**Files:**
- Modify: `ml/infer/mapper.py`
- Modify: `ml/infer/cli.py`
- Test: `ml/tests/test_mapper.py`

**Interfaces:**
- Consumes: `source.device_info` (Task 7)
- Produces: `build_metadata(..., device_info=None)` — khóa `device` xuất hiện trong metadata khi có

Vì sao khối này tới được sổ audit: `IngestPayload` bỏ qua khóa lạ (mặc định pydantic là `extra='ignore'`), nhưng `ingest.py` lưu **nguyên văn chuỗi metadata** vào cột `raw_metadata_json`. Nên khối `device` đi thẳng vào bản ghi audit mà không cần sửa gì bên web.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `ml/tests/test_mapper.py`:

```python
def test_device_info_lands_in_metadata():
    md = build_metadata(
        detections=[],
        image_width=1600,
        image_height=1200,
        sample_code="S20260719-120000-001",
        captured_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        device_id="aqua-cam-a1b2c3",
        px_per_mm=14.0,
        device_info={"firmware": "aqua_scope_station/1.0.0",
                     "camera": {"exposure": 100, "gain": 0}},
    )
    assert md["device"]["firmware"] == "aqua_scope_station/1.0.0"
    assert md["device"]["camera"]["exposure"] == 100


def test_no_device_info_means_no_device_key():
    md = build_metadata(
        detections=[],
        image_width=640,
        image_height=480,
        sample_code="x",
        captured_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        device_id="pc-infer",
        px_per_mm=14.0,
    )
    assert "device" not in md
```

Nếu `test_mapper.py` chưa import `datetime`/`timezone`, thêm `from datetime import datetime, timezone` ở đầu file.

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest ml/tests/test_mapper.py -k device -v`
Kỳ vọng: FAIL — `TypeError: build_metadata() got an unexpected keyword argument 'device_info'`

- [ ] **Step 3: Cài trong `mapper.py`**

Đổi chữ ký:

```python
def build_metadata(*, detections, image_width, image_height, sample_code,
                   captured_at, device_id, px_per_mm, batch_lot=None,
                   device_info=None):
```

Thay `return {...}` ở cuối bằng:

```python
    metadata = {
        "device_id": device_id,
        "sample_code": sample_code,
        "batch_lot": batch_lot,
        "captured_at": captured_at.isoformat(),
        "px_per_mm": px,
        "image_width": image_width,
        "image_height": image_height,
        "particles": particles,
    }
    if device_info:
        # IngestPayload bỏ qua khóa lạ, nhưng ingest.py lưu nguyên văn chuỗi
        # metadata vào raw_metadata_json — nên khối này vẫn tới được sổ audit
        # mà không phải sửa gì bên web.
        metadata["device"] = device_info
    return metadata
```

Cập nhật docstring của module, thêm dòng:

```
  * device       — khối /device của board (firmware, thiết lập camera lúc chụp),
    chỉ có khi chụp từ board. Đi vào raw_metadata_json để truy xuất nguồn gốc.
```

- [ ] **Step 4: Chạy test để xác nhận đạt**

Run: `python -m pytest ml/tests/test_mapper.py -v`
Kỳ vọng: PASS toàn bộ.

- [ ] **Step 5: Truyền `device_info` từ CLI**

Trong `ml/infer/cli.py`, ngay trước vòng lặp `for frame in source.frames():`, thêm:

```python
    device_info = getattr(source, "device_info", None)
```

Trong lời gọi `build_metadata(...)` bên trong vòng lặp, thêm tham số cuối:

```python
                device_info=device_info,
```

- [ ] **Step 6: Chạy toàn bộ test**

Run: `python -m pytest ml/tests/ -q`
Kỳ vọng: tất cả PASS.

- [ ] **Step 7: Commit**

```bash
git add ml/infer/mapper.py ml/infer/cli.py ml/tests/test_mapper.py
git commit -m "feat(ml): ghi khối /device vào metadata mẫu cho truy xuất nguồn gốc"
```

---

## Task 10: Tài liệu hóa đường chạy liền mạch

**Files:**
- Modify: `ml/README.md`

**Interfaces:**
- Consumes: hành vi CLI từ Task 8
- Produces: không có mã

- [ ] **Step 1: Sửa mục "Chạy nhanh" trong `ml/README.md`**

Thay mục `## Chạy nhanh` hiện có bằng:

````markdown
## Chạy nhanh

### Đo mẫu thật từ board (đường chạy chính)

```bash
# 1. Bật backend web (terminal riêng)
cd web/backend && python -m uvicorn app.main:app --port 8000

# 2. Kiểm tra cấu hình — không gọi API, không in API key
python -m ml.infer --check-config

# 3. Chụp từ board → suy luận → ghi sổ audit, một lệnh
python -m ml.infer --from-board 192.168.1.50 --count 5 --interval 2
```

Board phải chạy [`firmware/aqua_scope_station/`](../firmware/aqua_scope_station/).
IP lấy từ Serial Monitor 115200. Đặt `[station].host` trong `ml/config.local.toml`
thì khỏi gõ `--from-board` mỗi lần.

`device_id` ghi vào sổ audit là **tên board tự báo** (ví dụ `aqua-cam-a1b2c3`),
không phải hằng `ingest.device_id` — trừ khi bạn ép bằng `--device-id`.

### Chạy lại trên ảnh đã có

```bash
python -m ml.infer <thư-mục-ảnh>            # ghi vào DB
python -m ml.infer <thư-mục-ảnh> --dry-run  # chỉ đếm thử, KHÔNG ghi
```

Dashboard: `http://localhost:8000`

**Dùng `--dry-run` khi thử nghiệm.** DB là sổ audit truy xuất nguồn gốc — mỗi
lần chạy thật là một bản ghi vĩnh viễn, không nên tạo rác trong đó. `--dry-run`
vẫn chụp thật từ board nhưng không gửi gì đi.
````

Giữ nguyên hai đoạn cảnh báo `size_mm là placeholder` và `nhãn là hình thái` ngay sau đó — chúng vẫn đúng.

- [ ] **Step 2: Commit**

```bash
git add ml/README.md
git commit -m "docs(ml): hướng dẫn đường chạy board → model → sổ audit"
```

---

## Nghiệm thu cuối

Sau Task 10, chạy và **dán output thật** vào báo cáo, không tóm tắt:

```bash
python -m pytest ml/tests/ -q
python -m pytest dataset_collector/tests/ -q
```

Kỳ vọng: cả hai đều pass, không có test nào bị bỏ qua ngoài các test đã skip từ trước.

Phần firmware **chưa được coi là xong** cho tới khi chạy đủ 7 mục checklist trong `firmware/aqua_scope_station/README.md` trên board thật. Nếu chưa có board, báo cáo phải nói rõ: *"biên dịch sạch, chưa xác nhận trên phần cứng"* — không được viết "firmware chạy được".
