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
    Serial.println("Dừng lại: không có mạng thì laptop không kéo ảnh được.");
    return;
  }

  aquaDeviceInit();  // sau WiFi: MAC chỉ đọc được khi WiFi stack đã chạy

  startCameraServer();

  IPAddress ip = USE_AP ? WiFi.softAPIP() : WiFi.localIP();
  Serial.printf("\nSẵn sàng. Web UI:  http://%s/\n", ip.toString().c_str());
  Serial.printf("Thu dataset:       python collect_dataset.py --host %s\n\n",
                ip.toString().c_str());
}

void loop() {
  // Server chạy ở task riêng của esp_http_server; loop chỉ báo trạng thái sóng
  // để soi khi /capture bị timeout giữa phiên thu dài.
  if (!USE_AP) {
    Serial.printf("[WiFi] status=%d  RSSI=%d dBm\n", WiFi.status(), WiFi.RSSI());
  }
  delay(10000);
}
