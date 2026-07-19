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
//
// Lưu ý về lý do: server hiện KHÔNG validate device_id (chỉ sample_code có
// field_validator, và chỉ sample_code mới thành tên file trong ingest.py).
// Đây là phòng thủ chủ động ở nguồn, không phải vá một lỗ hổng đang mở: giữ
// device_id trong tập ký tự an toàn để nó dùng được ở mọi chỗ sau này (tên
// file, path URL, tên cột) mà không phải rà lại.
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
    // strncpy KHÔNG tự thêm null khi nguồn dài đúng bằng sức chứa. Hiện tại
    // g_deviceId là static zero-init nên byte cuối vẫn là 0, nhưng dựa vào
    // bất biến ngầm đó thì hỏng ngay khi có ai gọi lại hàm này sau một lần
    // ghi khác. Tự bảo đảm, đừng dựa vào may mắn.
    g_deviceId[sizeof(g_deviceId) - 1] = '\0';
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
