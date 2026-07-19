#include "aqua_prefs.h"

#include <Preferences.h>

static Preferences prefs;
static const char *NVS_NS = "aquacam";

// Trần framesize gần nhất mà setup() truyền vào qua applyDefaults/Load - nhớ
// lại để aquaPrefsReset() (gọi từ /control?var=reset, KHÔNG biết gì về
// PSRAM/DRAM) không phải đoán lại giá trị mặc định FRAMESIZE_UXGA của tham số
// max_framesize, việc đó sẽ tái diễn đúng lỗi "dỡ fallback DRAM" mà applyDefaults
// vừa được sửa để tránh.
static framesize_t g_maxFramesize = FRAMESIZE_UXGA;

// --- Mặc định backlit silhouette --------------------------------------------
// Nền sáng đều, hạt = bóng đen. Bản stock của Espressif để AUTO exposure, và đó
// chính là lỗi kinh điển: AEC/AGC sẽ kéo nền cháy trắng và nuốt mất hạt, bất kể
// đèn nền chỉnh thế nào (CLAUDE.md, mục "Lighting").
static const int DEF_AEC_VALUE = 100;  // exposure thủ công, thấp = tối
static const int DEF_AGC_GAIN = 0;     // backlit thì để 0
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

  // Thứ tự có ý nghĩa: phải TẮT các vòng điều khiển tự động TRƯỚC, nếu không
  // sensor sẽ ghi đè giá trị thủ công mình vừa đặt ngay ở khung hình kế tiếp.
  s->set_exposure_ctrl(s, 0);  // AEC off
  s->set_aec2(s, 0);           // AEC-DSP off
  s->set_gain_ctrl(s, 0);      // AGC off

  s->set_aec_value(s, DEF_AEC_VALUE);
  s->set_agc_gain(s, DEF_AGC_GAIN);
  s->set_contrast(s, DEF_CONTRAST);
  s->set_brightness(s, DEF_BRIGHTNESS);
  s->set_quality(s, DEF_QUALITY);
  // Tôn trọng trần bộ nhớ do initCamera() tính (SVGA/DRAM khi không có PSRAM)
  // - KHÔNG set thẳng DEF_FRAMESIZE (UXGA) như trước, việc đó xóa mất fallback.
  s->set_framesize(s, clampFramesize(DEF_FRAMESIZE, max_framesize));
  s->set_hmirror(s, DEF_HMIRROR);
  s->set_vflip(s, DEF_VFLIP);
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
}

void aquaPrefsReset(sensor_t *s) {
  prefs.begin(NVS_NS, false);
  prefs.clear();
  prefs.end();
  // Dùng g_maxFramesize (trần bộ nhớ thật, do setup() truyền vào lúc boot),
  // KHÔNG gọi aquaPrefsApplyDefaults(s) thiếu tham số - tham số mặc định của
  // nó là FRAMESIZE_UXGA, mù bộ nhớ thật, sẽ tái diễn đúng lỗi đã sửa ở trên.
  aquaPrefsApplyDefaults(s, g_maxFramesize);
}

bool aquaPrefsIsSaved() {
  prefs.begin(NVS_NS, true);  // read-only
  bool saved = prefs.getBool("saved", false);
  prefs.end();
  return saved;
}
