#include "aqua_prefs.h"
#include "aqua_pump.h"

#include <Preferences.h>

static Preferences prefs;
static const char *NVS_NS      = "aquacam";
static const char *NVS_NS_PUMP = "aquapump";

// Trần framesize gần nhất mà setup() truyền vào qua applyDefaults/Load - nhớ
// lại để aquaPrefsReset() (gọi từ /control?var=reset, KHÔNG biết gì về
// PSRAM/DRAM) không phải đoán lại giá trị mặc định FRAMESIZE_UXGA của tham số
// max_framesize, việc đó sẽ tái diễn đúng lỗi "dỡ fallback DRAM" mà applyDefaults
// vừa được sửa để tránh.
static framesize_t g_maxFramesize = FRAMESIZE_UXGA;

// --- Mặc định lúc boot -------------------------------------------------------
// Phơi sáng để AUTO (AEC/AEC-DSP/AGC nguyên trạng như esp_camera_init() đặt),
// giống bản CameraWebServer gốc và giống firmware aqua_scope_cam — ảnh sáng,
// ngắm/chỉnh được ngay khi cấp điện.
//
// Cấu hình backlit thật (tắt AEC/AGC + exposure thấp) KHÔNG còn là mặc định:
// nó là việc người vận hành chủ động bật qua web UI/serial rồi `?var=save`
// trước khi chụp khung phân tích — xem CLAUDE.md, mục "Lighting".
//
// DEF_AEC_VALUE / DEF_AGC_GAIN vì thế không còn được áp lúc boot, chỉ còn là
// giá trị dự phòng cho aquaPrefsLoad() khi NVS thiếu key (đường phòng thủ).
static const int DEF_AEC_VALUE = 100;
static const int DEF_AGC_GAIN = 0;

// Trạng thái auto-exposure NGUYÊN BẢN của sensor, chụp lại ở lần gọi
// aquaPrefsApplyDefaults() đầu tiên (trong setup(), ngay sau esp_camera_init(),
// lúc chưa ai kịp sửa gì).
//
// Vì sao phải chụp lại chứ không hard-code 1: giá trị auto mặc định là do bảng
// register của driver quyết định và khác nhau giữa OV2640/OV3660 (nhất là
// aec2/AEC-DSP). Chụp lại thì "mặc định" luôn đúng bằng trạng thái lúc cấp
// điện của bản gốc, không cần biết bảng register đó ghi gì.
//
// Vì sao phải phục hồi: applyDefaults() KHÔNG chỉ chạy lúc boot mà còn từ
// aquaPrefsReset() (/control?var=reset). Lúc đó sensor đang ở manual — do người
// dùng vừa chỉnh, hoặc do aquaPrefsLoad() đã áp cấu hình dark đã lưu. "Không
// set gì" ở đường đó = giữ nguyên manual, nên reset sẽ không trả về auto được
// và phải rút điện mới thoát khỏi ảnh tối. Đó chính là lỗi của bản trước.
static bool g_autoCaptured = false;
static int  g_autoAec  = 1;
static int  g_autoAec2 = 1;
static int  g_autoAgc  = 1;
static const int DEF_CONTRAST = 1;     // tách bóng hạt khỏi nền
static const int DEF_BRIGHTNESS = 0;
static const int DEF_QUALITY = 10;
static const int DEF_FRAMESIZE = (int)FRAMESIZE_UXGA;  // OV2640 tối đa 1600x1200
static const int DEF_HMIRROR = 0;
static const int DEF_VFLIP = 0;

// Chặn giá trị framesize rác/quá khả năng bộ nhớ TRƯỚC khi chạm tới sensor.
// Dùng chung cho cả applyDefaults (hằng số DEF_FRAMESIZE, luôn hợp lệ nhưng
// có thể vượt trần bộ nhớ) lẫn aquaPrefsLoad (giá trị đọc từ NVS - có thể là
// rác thật sự, xem app_httpd.cpp::cmd_handler). raw ngoài [0, FRAMESIZE_INVALID)
// thì coi là rác, lùi về max_framesize; trong khoảng hợp lệ nhưng > max thì hạ
// xuống đúng trần bộ nhớ.
static framesize_t clampFramesize(int raw, framesize_t max_framesize) {
  if (raw < 0 || raw >= (int)FRAMESIZE_INVALID) return max_framesize;
  if (raw > (int)max_framesize) return max_framesize;
  return (framesize_t)raw;
}

void aquaPrefsApplyDefaults(sensor_t *s, framesize_t max_framesize) {
  if (s == nullptr) return;
  g_maxFramesize = max_framesize;

  // Phơi sáng: trả về ĐÚNG trạng thái auto lúc cấp điện (xem g_auto* ở trên).
  // Bản cũ ép cả 3 vòng tự động về 0 rồi đặt exposure thủ công thấp, nên mỗi lần
  // boot và mỗi `?var=reset` đều ra ảnh tối, khó ngắm.
  if (!g_autoCaptured) {
    // Lần đầu (boot, ngay sau esp_camera_init): sensor còn nguyên bản — chỉ ghi
    // nhớ, KHÔNG set lại, để không đụng gì vào đường boot của bản gốc.
    g_autoAec  = s->status.aec;
    g_autoAec2 = s->status.aec2;
    g_autoAgc  = s->status.agc;
    g_autoCaptured = true;
  } else {
    // Các lần sau (từ /control?var=reset): sensor có thể đang ở manual, phải
    // ghi trả lại một cách tường minh.
    s->set_exposure_ctrl(s, g_autoAec);
    s->set_aec2(s, g_autoAec2);
    s->set_gain_ctrl(s, g_autoAgc);
  }

  s->set_contrast(s, DEF_CONTRAST);
  s->set_quality(s, DEF_QUALITY);

  // Hiệu chỉnh riêng cho OV3660 — KHÔNG bỏ nhánh này.
  // Board của dự án dùng OV3660 (không phải OV2640 như tên file board ghi). Raw
  // của nó ra ảnh LẬT NGƯỢC và quá bão hoà, nhìn ngả xanh. Cả 3 firmware chạy
  // tốt trong repo đều có đúng nhánh này (CameraWebServer.ino, aqua_scope_cam,
  // dataset_collector); bản station thiếu nó nên ảnh mặc định bị xanh + ngược.
  // Giá trị lấy y theo CameraWebServer gốc của Espressif.
  bool isOv3660 = (s->id.PID == OV3660_PID);
  if (isOv3660) {
    s->set_brightness(s, 1);
    s->set_saturation(s, -2);
  } else {
    s->set_brightness(s, DEF_BRIGHTNESS);
  }

  // Tôn trọng trần bộ nhớ do initCamera() tính (SVGA/DRAM khi không có PSRAM)
  // - KHÔNG set thẳng DEF_FRAMESIZE (UXGA) như trước, việc đó xóa mất fallback.
  s->set_framesize(s, clampFramesize(DEF_FRAMESIZE, max_framesize));
  s->set_hmirror(s, DEF_HMIRROR);
  // vflip PHẢI set sau cùng và phải theo nhánh sensor: OV3660 cần 1 để ảnh đúng
  // chiều. Đặt DEF_VFLIP (0) vô điều kiện ở đây sẽ xoá đúng cái vừa sửa ở trên.
  s->set_vflip(s, isOv3660 ? 1 : DEF_VFLIP);
}

bool aquaPrefsLoad(sensor_t *s, framesize_t max_framesize) {
  if (s == nullptr) return false;
  g_maxFramesize = max_framesize;

  prefs.begin(NVS_NS, true);  // read-only
  bool saved = prefs.getBool("saved", false);
  if (!saved) {
    prefs.end();
    return false;
  }

  // Tắt tự động trước, y hệt lý do ở applyDefaults.
  s->set_exposure_ctrl(s, prefs.getInt("aec", 0));
  s->set_aec2(s, prefs.getInt("aec2", 0));
  s->set_gain_ctrl(s, prefs.getInt("agc", 0));

  s->set_aec_value(s, prefs.getInt("aec_value", DEF_AEC_VALUE));
  s->set_agc_gain(s, prefs.getInt("agc_gain", DEF_AGC_GAIN));
  s->set_contrast(s, prefs.getInt("contrast", DEF_CONTRAST));
  s->set_brightness(s, prefs.getInt("brightness", DEF_BRIGHTNESS));
  s->set_quality(s, prefs.getInt("quality", DEF_QUALITY));
  // Giá trị NVS có thể là rác (từ /control?var=framesize không validate ở
  // cm_handler cũ, hoặc một bản firmware cũ ghi lúc còn PSRAM) - không tin
  // thẳng như trước, phải qua cùng bộ lọc clampFramesize() với applyDefaults.
  s->set_framesize(s, clampFramesize(prefs.getInt("framesize", DEF_FRAMESIZE), max_framesize));
  s->set_hmirror(s, prefs.getInt("hmirror", DEF_HMIRROR));
  s->set_vflip(s, prefs.getInt("vflip", DEF_VFLIP));

  prefs.end();
  return true;
}

void aquaPrefsSave(sensor_t *s) {
  if (s == nullptr) return;

  prefs.begin(NVS_NS, false);  // read-write
  prefs.putInt("aec", s->status.aec);
  prefs.putInt("aec2", s->status.aec2);
  prefs.putInt("agc", s->status.agc);
  prefs.putInt("aec_value", s->status.aec_value);
  prefs.putInt("agc_gain", s->status.agc_gain);
  prefs.putInt("contrast", s->status.contrast);
  prefs.putInt("brightness", s->status.brightness);
  prefs.putInt("quality", s->status.quality);
  prefs.putInt("framesize", s->status.framesize);
  prefs.putInt("hmirror", s->status.hmirror);
  prefs.putInt("vflip", s->status.vflip);
  prefs.putBool("saved", true);
  prefs.end();

  // --- Lưu cấu hình bơm (namespace riêng, tránh va chạm key) ---
  PumpTiming *pt = aquaPumpTiming();
  prefs.begin(NVS_NS_PUMP, false);
  prefs.putULong("fillMs",     pt->fillMs);
  prefs.putULong("settleMs",   pt->settleMs);
  prefs.putULong("flushMs",    pt->flushMs);
  prefs.putULong("cooldownMs", pt->cooldownMs);
  prefs.putULong("rampUpMs",   pt->rampUpMs);
  prefs.putULong("rampDownMs", pt->rampDownMs);
  prefs.putUChar("fillDuty",   pt->fillDuty);
  prefs.putUChar("flushDuty",  pt->flushDuty);
  prefs.putBool("saved", true);
  prefs.end();
}

void aquaPrefsReset(sensor_t *s) {
  prefs.begin(NVS_NS, false);
  prefs.clear();
  prefs.end();

  // Xóa cấu hình bơm
  prefs.begin(NVS_NS_PUMP, false);
  prefs.clear();
  prefs.end();

  // Dùng g_maxFramesize (trần bộ nhớ thật, do setup() truyền vào lúc boot),
  // KHÔNG gọi aquaPrefsApplyDefaults(s) thiếu tham số - tham số mặc định của
  // nó là FRAMESIZE_UXGA, mù bộ nhớ thật, sẽ tái diễn đúng lỗi đã sửa ở trên.
  aquaPrefsApplyDefaults(s, g_maxFramesize);

  // Reset timing bơm về mặc định
  aquaPumpResetTiming();
}

framesize_t aquaPrefsMaxFramesize() { return g_maxFramesize; }

bool aquaPrefsIsSaved() {
  prefs.begin(NVS_NS, true);  // read-only
  bool saved = prefs.getBool("saved", false);
  prefs.end();
  return saved;
}

bool aquaPumpPrefsLoad() {
  prefs.begin(NVS_NS_PUMP, true);  // read-only
  bool saved = prefs.getBool("saved", false);
  if (!saved) {
    prefs.end();
    return false;
  }

  PumpTiming *pt = aquaPumpTiming();
  pt->fillMs     = prefs.getULong("fillMs",     pt->fillMs);
  pt->settleMs   = prefs.getULong("settleMs",   pt->settleMs);
  pt->flushMs    = prefs.getULong("flushMs",    pt->flushMs);
  pt->cooldownMs = prefs.getULong("cooldownMs", pt->cooldownMs);
  pt->rampUpMs   = prefs.getULong("rampUpMs",   pt->rampUpMs);
  pt->rampDownMs = prefs.getULong("rampDownMs", pt->rampDownMs);
  pt->fillDuty   = prefs.getUChar("fillDuty",   pt->fillDuty);
  pt->flushDuty  = prefs.getUChar("flushDuty",  pt->flushDuty);
  prefs.end();
  return true;
}
