/*
 * ============================================================================
 *  Aqua Scope — Firmware thu thập dataset (ESP32-CAM AI-Thinker, OV2640)
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
 *    1) Ép mặc định BACKLIT (tắt AEC/AEC-DSP/AGC) — bản gốc để auto, nền sẽ
 *       cháy trắng và nuốt mất hạt.
 *    2) Mặc định UXGA 1600x1200 thay vì QVGA — hạt <2mm cần độ phân giải.
 *    3) Lưu cấu hình vào flash (aqua_prefs.*) — chỉnh 1 lần, dùng mãi.
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
#include "board_config.h"

// ---------------------------------------------------------------------------
// 1) WIFI
//    Mặc định STA (nối router nhà) — laptop vẫn có internet trong lúc thu.
//    Nếu router nghẽn / rớt giữa chừng: đổi USE_AP thành true, board tự phát
//    WiFi "AquaScope", nối laptop vào rồi dùng http://192.168.4.1
// ---------------------------------------------------------------------------
#define USE_AP false

const char *STA_SSID = "Nha Tro 1998";
const char *STA_PASS = "0913603127";

const char *AP_SSID = "AquaScope";
const char *AP_PASS = "aquascope";  // >= 8 ký tự

void startCameraServer();
void setupLedFlash();

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
  config.xclk_freq_hz = 20000000;
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
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println("\n=== Aqua Scope — firmware thu thập dataset ===");

  if (!initCamera()) {
    Serial.println("Dừng lại: không có camera thì không làm được gì.");
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("Sensor PID: 0x%x | PSRAM: %d bytes\n", s->id.PID, ESP.getFreePsram());

  // Mặc định backlit trước, rồi mới đè cấu hình đã lưu (nếu có) lên trên.
  aquaPrefsApplyDefaults(s);
  if (aquaPrefsLoad(s)) {
    Serial.println("Đã nạp cấu hình lưu trong flash.");
  } else {
    Serial.println("Flash chưa có cấu hình — dùng mặc định backlit.");
  }

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

  startCameraServer();

  IPAddress ip = USE_AP ? WiFi.softAPIP() : WiFi.localIP();
  Serial.printf("\nSẵn sàng. Web UI:  http://%s/\n", ip.toString().c_str());
  Serial.printf("Thu dataset:       python collect_dataset.py --host %s\n\n",
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
  esp_task_wdt_config_t wdtConfig = {
    .timeout_ms = 30000,
    .idle_core_mask = 0,
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
  // Nghỉ 10s nhưng chia thành 10 lát 1s, mỗi lát reset watchdog một lần —
  // KHÔNG delay(10000) một cục. Watchdog thực tế có thể là 30s (cấu hình ở
  // setup()) hoặc 5s (nếu cấu hình thất bại và ta không đăng ký loop vào
  // watchdog — xem cảnh báo ở setup()); dù là giá trị nào, đợi rời rạc kiểu
  // này cũng không bao giờ để quá 1s trôi qua giữa hai lần reset, nên không
  // phụ thuộc vào con số timeout cụ thể. Sau này có ai nâng nhịp báo cáo lên
  // 60s cũng không vô tình dựng lại boot loop như bản delay(10000) cũ.
  for (int i = 0; i < 10; i++) {
    esp_task_wdt_reset();
    delay(1000);
  }
}
