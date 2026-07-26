/*
 * ============================================================================
 *  Aqua Scope — Firmware thu thập dataset + điều khiển bơm (ESP32-CAM AI-Thinker, OV2640)
 * ============================================================================
 *  Nhiệm vụ: làm "nguồn ảnh câm" cho laptop kéo về.
 *    - GET /         web UI gốc của Espressif (canh sáng bằng slider)
 *    - GET /stream   MJPEG xem trực tiếp (chỉ dùng lúc canh sáng)
 *    - GET /capture  trả 1 ảnh JPEG  <-- script collect_dataset.py gọi cái này
 *    - GET /control?var=save&val=1   ghi cứng cấu hình vào flash
 *    - GET /control?var=reset&val=1  xóa cấu hình + về mặc định
 *
 *  Firmware KHÔNG biết gì về dataset: không đặt tên file, không lưu trữ, không
 *  đếm. Toàn bộ việc đó nằm ở collect_dataset.py trên laptop — sửa cách thu
 *  dataset thì không phải nạp lại firmware.
 *
 *  Khác bản CameraWebServer gốc đúng 3 điểm:
 *    1) Mặc định UXGA 1600x1200 thay vì QVGA — hạt <2mm cần độ phân giải.
 *    2) Lưu cấu hình vào flash (aqua_prefs.*) — chỉnh 1 lần, dùng mãi.
 *    3) Có điều khiển bơm L298N (aqua_pump.*) + /device để truy xuất nguồn gốc.
 *
 *  Phơi sáng mặc định để AUTO như bản gốc (ảnh sáng, ngắm được ngay). Cấu hình
 *  backlit thật — tắt AEC/AEC-DSP/AGC + exposure thấp — là bước người vận hành
 *  chủ động chỉnh qua web UI/serial rồi ?var=save TRƯỚC khi chụp khung phân
 *  tích, không còn bị ép cứng lúc boot.
 *
 *  Cấu hình board trong Arduino IDE:
 *    - Board:     "AI Thinker ESP32-CAM"
 *    - Partition: "Huge APP (3MB No OTA/1MB SPIFFS)"
 *    (Board này KHÔNG có menu PSRAM — core esp32 luôn bật sẵn cho variant này.)
 *  Nạp code: nối IO0 -> GND rồi cấp nguồn để vào bootloader, nạp xong rút ra.
 * ============================================================================
 */

#include <Arduino.h>
#include <WiFi.h>

#include "esp_camera.h"
#include "esp_task_wdt.h"

#include "aqua_device.h"
#include "aqua_prefs.h"
#include "aqua_pump.h"
#include "board_config.h"

// ---------------------------------------------------------------------------
// 1) WIFI
//    Mặc định STA (nối router nhà) — laptop vẫn có internet trong lúc thu.
//    Nếu router nghẽn / rớt giữa chừng: đổi AQUA_USE_AP thành true, board tự
//    phát WiFi "AquaScope", nối laptop vào rồi dùng http://192.168.4.1
//
//    SSID/mật khẩu KHÔNG nằm trong file này nữa. Chúng nằm ở wifi_config.h —
//    file đã .gitignore — vì bản cũ để mật khẩu WiFi thật ngay đây và nó đã bị
//    commit rồi đẩy lên GitHub. Copy wifi_config.example.h thành wifi_config.h
//    rồi điền vào đó.
// ---------------------------------------------------------------------------
#if __has_include("wifi_config.h")
#include "wifi_config.h"
#define AQUA_HAS_WIFI_CONFIG 1
#else
// Thiếu wifi_config.h thì vẫn phải BIÊN DỊCH ĐƯỢC (nếu không, người vừa clone
// repo về sẽ gặp lỗi compile khó hiểu thay vì một lời nhắc rõ ràng). Dùng giá
// trị vô hại và chuyển sang chế độ AP: board tự phát WiFi riêng, chạy được
// ngay mà không cần biết mật khẩu router nào.
//
// Lời nhắc được in ra Serial lúc chạy chứ KHÔNG dùng #warning: Arduino IDE mặc
// định để "Compiler warnings: None", tức truyền -w cho gcc và dập luôn cả
// #warning. Đã đo: chỉ khi build với --warnings all thì dòng đó mới hiện, nên
// một cảnh báo lúc biên dịch ở đây thực tế là vô hình.
#define AQUA_HAS_WIFI_CONFIG 0
#define AQUA_USE_AP true
#define AQUA_STA_SSID ""
#define AQUA_STA_PASS ""
#define AQUA_AP_SSID "AquaScope"
#define AQUA_AP_PASS "aquascope"
#endif

#define USE_AP AQUA_USE_AP

const char *STA_SSID = AQUA_STA_SSID;
const char *STA_PASS = AQUA_STA_PASS;

const char *AP_SSID = AQUA_AP_SSID;
const char *AP_PASS = AQUA_AP_PASS;  // >= 8 ký tự

void startCameraServer();
void setupLedFlash();

// Tần số XCLK cấp cho OV2640.
//
// Bản gốc Espressif dùng 20MHz, nhưng 20MHz gây artifact ảnh (sọc, vỡ khối,
// ngả màu) trên nhiều module OV2640 — lỗi này KHÔNG phụ thuộc độ phân giải:
//   https://github.com/espressif/esp32-camera/issues/150
// dataset_collector/firmware/firmware.ino:155 đã gặp đúng chuyện này và hạ
// xuống 8MHz; đó là firmware chạy sạch trên chính board này, nên lấy luôn 8MHz
// làm giá trị chuẩn ở đây.
//
// Đánh đổi: 8MHz → tốc độ khung thấp hơn 20MHz. Với trạm Stop-Flow thì KHÔNG
// quan trọng — mỗi chu trình chỉ chụp 1 khung lúc nước đã lặng, chất lượng ảnh
// mới là thứ đáng đổi. Đừng nâng lại lên 20MHz chỉ để stream mượt hơn.
static const int CAM_XCLK_HZ = 8000000;

static bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = CAM_XCLK_HZ;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_UXGA;
  config.jpeg_quality = 10;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.fb_count = 1;

  if (psramFound()) {
    // fb_count=2 cho stream mượt hơn; CAMERA_GRAB_LATEST để /capture luôn lấy
    // khung mới nhất chứ không phải khung cũ còn tồn trong hàng đợi — quan
    // trọng khi chụp dataset: ảnh phải khớp với thứ đang đặt dưới camera.
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    // Không có PSRAM thì không đủ RAM cho UXGA. Không im lặng chạy tiếp ở độ
    // phân giải thấp mà không báo — ảnh dataset sẽ vô dụng cho hạt <2mm.
    Serial.println("[CẢNH BÁO] Không thấy PSRAM! Hạ xuống SVGA.");
    Serial.println("           Board AI-Thinker thật luôn có IC PSRAM — nếu thấy dòng");
    Serial.println("           này thì nhiều khả năng chọn nhầm board hoặc hàng lỗi.");
    config.frame_size = FRAMESIZE_SVGA;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[LỖI] Camera init thất bại, mã 0x%x\n", err);
    return false;
  }
  return true;
}

static bool connectWiFi() {
  if (USE_AP) {
    WiFi.mode(WIFI_AP);
    if (!WiFi.softAP(AP_SSID, AP_PASS)) {
      Serial.println("[LỖI] Không bật được Access Point.");
      return false;
    }
    Serial.printf("AP đang phát: SSID=%s  IP=%s\n", AP_SSID,
                  WiFi.softAPIP().toString().c_str());
    return true;
  }

  WiFi.mode(WIFI_STA);

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

  WiFi.begin(STA_SSID, STA_PASS);
  WiFi.setSleep(false);  // sleep làm /capture trễ và hay timeout khi kéo liên tục

  Serial.printf("Đang nối WiFi \"%s\"", STA_SSID);
  // Có giới hạn thời gian: không treo vô hạn trong vòng while như bản gốc.
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[LỖI] Hết 20s vẫn không nối được WiFi.");
    Serial.println("      Kiểm tra SSID/mật khẩu, hoặc đặt USE_AP = true.");
    return false;
  }
  Serial.printf("WiFi OK | IP: %s | RSSI: %d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  return true;
}

void setup() {
  // VIỆC ĐẦU TIÊN, trước cả Serial: ghim chân bơm xuống LOW.
  // Chân ENA thả nổi có thể được L298N đọc là HIGH → bơm chạy hết tốc. Mọi thứ
  // bên dưới (camera init, WiFi connect tới 20s, và cả nhánh restart khi camera
  // lỗi) đều đủ lâu để làm tràn khay nếu chân còn thả nổi. Phần gắn PWM nằm ở
  // aquaPumpInit() cuối setup() — xem aqua_pump.h, mục "khởi tạo hai giai đoạn".
  aquaPumpPreInit();

  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println("\n=== Aqua Scope — firmware thu thập dataset + điều khiển bơm ===");

#if !AQUA_HAS_WIFI_CONFIG
  Serial.println("[CẢNH BÁO] Không tìm thấy wifi_config.h — đang chạy chế độ AP mặc định.");
  Serial.println("           Muốn nối vào router nhà: copy wifi_config.example.h thành");
  Serial.println("           wifi_config.h (cùng thư mục) rồi điền SSID/mật khẩu vào đó.");
  Serial.println("           wifi_config.h đã được .gitignore nên sẽ không lọt vào git.");
#endif

  if (!initCamera()) {
    // KHÔNG `return` như bản cũ. Return ở đây làm setup() kết thúc, loop() chạy
    // rỗng, và board NẰM CHẾT CÂM tới khi có người tới rút điện — đúng cái mà
    // chính file này đã bác bỏ ở nhánh WiFi bên dưới ("không chấp nhận được với
    // trạm chạy dài"). Camera init hỏng phần lớn là lỗi TẠM THỜI: sụt áp lúc
    // boot khi WiFi TX và camera khởi động trùng nhau (cùng nguyên nhân với
    // /capture trả 503). Khởi động lại thì lần sau gần như luôn qua được.
    //
    // Nếu camera hỏng thật thì đây thành vòng lặp reset — vẫn tốt hơn chết câm:
    // Serial in rõ lý do mỗi vòng nên soi ra ngay, còn chết câm thì không có
    // dấu hiệu nào để lần.
    Serial.println("[LỖI] Camera không khởi tạo được.");
    Serial.println("      Khởi động lại sau 5 giây để thử lại (thường do sụt áp lúc boot).");
    Serial.println("      Nếu dòng này lặp mãi: kiểm tra cáp camera và nguồn 5V ≥ 2A.");
    Serial.flush();
    delay(5000);
    ESP.restart();
  }

  sensor_t *s = esp_camera_sensor_get();
  // %lu + ép kiểu: getFreePsram() trả uint32_t (long unsigned trên ESP32), %d
  // là sai kiểu. printf lấy tham số theo đúng kiểu mà chuỗi định dạng khai báo,
  // nên đây là hành vi không xác định chứ không chỉ là cảnh báo của trình dịch.
  Serial.printf("Sensor PID: 0x%x | PSRAM: %s (%lu bytes free) | XCLK: %d Hz\n",
                s->id.PID, psramFound() ? "co" : "KHONG",
                (unsigned long)ESP.getFreePsram(), CAM_XCLK_HZ);

  // Trần framesize mà bộ nhớ hiện có kham nổi - PHẢI khớp với nhánh đã chọn
  // trong initCamera() (UXGA/PSRAM hay SVGA/DRAM). Không truyền cái này vào
  // sẽ khiến applyDefaults/Load set thẳng UXGA, xóa mất fallback DRAM vừa
  // dựng và làm buffer không đủ chỗ (ảnh ra bị cụt).
  framesize_t maxFramesize = psramFound() ? FRAMESIZE_UXGA : FRAMESIZE_SVGA;

  // Mặc định backlit trước, rồi mới đè cấu hình đã lưu (nếu có) lên trên.
  aquaPrefsApplyDefaults(s, maxFramesize);
  if (aquaPrefsLoad(s, maxFramesize)) {
    Serial.println("Đã nạp cấu hình lưu trong flash.");
  } else {
    Serial.println("Flash chưa có cấu hình — dùng mặc định auto exposure.");
  }

  // In trạng thái phơi sáng CUỐI CÙNG (sau khi cấu hình lưu đã đè lên mặc
  // định) — đúng thứ web UI sẽ hiển thị. Có dòng này thì "ảnh tối" phân biệt
  // được ngay là do cấu hình đã lưu hay do mặc định, không phải mở UI ra đoán.
  Serial.printf("Phoi sang: AEC=%s AEC-DSP=%s AGC=%s (aec_value=%u agc_gain=%u)\n",
                s->status.aec ? "auto" : "TAT", s->status.aec2 ? "auto" : "TAT",
                s->status.agc ? "auto" : "TAT", s->status.aec_value,
                s->status.agc_gain);

#if defined(LED_GPIO_NUM)
  setupLedFlash();
#endif

  if (!connectWiFi()) {
    // KHÔNG return: WiFi event handler ở trên vẫn tiếp tục thử nối lại. Dừng
    // setup() ở đây sẽ khiến board đứng im tới khi có người rút điện — không
    // chấp nhận được với trạm chạy dài.
    Serial.println("[CẢNH BÁO] Chưa nối được WiFi. Vẫn chạy tiếp và thử lại nền.");
    Serial.println("           Server sẽ phục vụ được ngay khi có IP.");
  }

  aquaDeviceInit();  // sau WiFi: MAC chỉ đọc được khi WiFi stack đã chạy

  // --- Khởi động bơm ---
  // TRƯỚC startCameraServer(): /control?var=pump_* phải có bơm sẵn sàng ngay
  // từ request đầu tiên, chứ không phải mở cổng ra rồi mới gắn PWM.
  // SAU esp_camera_init(): xem ghi chú kênh LEDC ở đầu aqua_pump.cpp — camera
  // giành LEDC qua ESP-IDF mà Arduino không thấy, nên thứ tự này có ý nghĩa.
  aquaPumpInit();
  if (aquaPumpPrefsLoad()) {
    Serial.println("Đã nạp cấu hình bơm từ flash.");
  } else {
    Serial.println("Flash chưa có cấu hình bơm — dùng mặc định.");
  }
  aquaPumpPrintHelp();
  Serial.println();

  startCameraServer();

  IPAddress ip = USE_AP ? WiFi.softAPIP() : WiFi.localIP();
  Serial.printf("\nSẵn sàng. Web UI:  http://%s/\n", ip.toString().c_str());
  Serial.printf("Thu dataset:       python collect_dataset.py --host %s\n",
                ip.toString().c_str());

  // Watchdog 30s cho task loop: nếu loop treo, board tự reset thay vì đứng câm.
  // 30s rộng rãi so với nhịp báo cáo 10s bên dưới.
  //
  // QUAN TRỌNG: core esp32 3.x đã tự init sẵn TWDT lúc boot (sdkconfig mặc định
  // CONFIG_ESP_TASK_WDT_TIMEOUT_S=5, CONFIG_ESP_TASK_WDT_PANIC=1). Gọi
  // esp_task_wdt_init() lần nữa ở đây trả về ESP_ERR_INVALID_STATE — timeout
  // 30000 KHÔNG được áp dụng, watchdog vẫn ở 5s. Nếu bỏ qua mã lỗi và cứ
  // esp_task_wdt_add(NULL), loop() dưới kia (nghỉ 10s/lát trong bản cũ là một
  // cục delay(10000)) sẽ luôn bị panic ở giây thứ 5 -> board reset -> setup()
  // chạy lại -> panic lần nữa: boot loop vô tận, không bao giờ phục vụ ảnh.
  // idle_core_mask: 1 bit mỗi core, bit bật = idle task của core đó cũng bị
  // watchdog giám sát. Bản cũ để 0, và đó là một tác dụng phụ ngoài ý muốn:
  // core esp32 3.x lúc boot đã ĐĂNG KÝ SẴN idle task của cả hai core vào TWDT,
  // nên esp_task_wdt_reconfigure() với mask 0 sẽ GỠ chúng ra. Kết quả ngược
  // hẳn với điều comment phía trên tuyên bố: một task nào đó quay vòng bận
  // (busy-loop) làm chết đói idle task sẽ không còn bị bắt nữa - đúng kiểu
  // treo mà watchdog sinh ra để cứu. Giữ nguyên giám sát idle của cả 2 core,
  // chỉ nới timeout 5s -> 30s. Nới thì luôn an toàn hơn mặc định của core.
  const uint32_t ALL_CORES_IDLE_MASK = (1 << portNUM_PROCESSORS) - 1;
  esp_task_wdt_config_t wdtConfig = {
    .timeout_ms = 30000,
    .idle_core_mask = ALL_CORES_IDLE_MASK,
    .trigger_panic = true,
  };
  esp_err_t wdtErr = esp_task_wdt_init(&wdtConfig);
  if (wdtErr == ESP_ERR_INVALID_STATE) {
    // TWDT của core đã chạy sẵn — áp lại timeout 30s lên chính nó thay vì
    // init chồng lần hai.
    wdtErr = esp_task_wdt_reconfigure(&wdtConfig);
  }
  if (wdtErr == ESP_OK) {
    esp_task_wdt_add(NULL);
  } else {
    // Không đăng ký loop vào watchdog nếu chưa chắc timeout đã đúng 30s —
    // đăng ký nhầm vào watchdog 5s trong khi loop nghỉ theo lát 1s (xem dưới)
    // vẫn an toàn, nhưng nếu esp_task_wdt_reconfigure() cũng lỗi thì ta không
    // biết timeout thực tế là bao nhiêu. Thà chạy không watchdog còn hơn tự
    // dựng lại vòng lặp reset vô tận.
    Serial.printf("[CẢNH BÁO] Không cấu hình được watchdog (mã 0x%x) — loop() sẽ KHÔNG được giám sát watchdog.\n",
                  wdtErr);
  }
}

void loop() {
  esp_task_wdt_reset();  // báo watchdog rằng loop còn sống

  // Xử lý lệnh Serial (pump + status)
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      // Thử lệnh pump trước; nếu không phải lệnh pump thì báo lỗi.
      if (!aquaPumpHandleSerial(line)) {
        Serial.println("Lenh khong hop le. Go '?' de xem menu bom.");
      }
    }
  }

  // Tick state machine bơm mỗi vòng loop.
  // Nếu autoRunning=false thì tick không làm gì (nhẹ).
  aquaPumpTick();

  // Server chạy ở task riêng của esp_http_server; loop chỉ báo trạng thái để
  // soi khi /capture bị timeout giữa phiên đo dài.
  // In trạng thái WiFi mỗi ~10s. Đếm thời gian bằng static var thay vì
  // delay(10000) một cục — loop cần chạy nhanh cho pump tick.
  static uint32_t lastStatusPrint = 0;
  uint32_t now = millis();
  if (now - lastStatusPrint >= 10000) {
    lastStatusPrint = now;
    if (!USE_AP) {
      if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WiFi] OK | IP=%s | RSSI=%d dBm | chup=%lu\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI(),
                      (unsigned long)aquaDeviceCaptureCount());
      } else {
        Serial.printf("[WiFi] mat ket noi (status=%d) — dang thu noi lai\n",
                      WiFi.status());
      }
    }
  }

  // Nghỉ ngắn mỗi vòng để nhường CPU cho các task FreeRTOS khác (httpd, WiFi),
  // nhưng đủ ngắn để pump tick phản hồi kịp thời (50ms « thời gian pha ngắn
  // nhất mặc định 2000ms SETTLING). Watchdog 30s/5s không bị chạm.
  delay(50);
}
