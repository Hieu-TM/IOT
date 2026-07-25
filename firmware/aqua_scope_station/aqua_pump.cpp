/*
 * aqua_pump.cpp — implem cho aqua_pump.h.
 *
 * Port gần nguyên văn state machine + ramp từ pump_l298n_xiao.ino (bản test
 * L298N chạy trên XIAO ESP32-S3, nay đã gộp vào đây và xoá đi), đóng gói
 * thành module riêng thay vì nằm thẳng trong .ino.
 *
 * ---------------------------------------------------------------------------
 * KÊNH LEDC — vì sao aquaPumpInit() phải gọi SAU esp_camera_init()
 * ---------------------------------------------------------------------------
 * Driver esp32-camera tạo XCLK 20MHz bằng LEDC, nhưng nó cấu hình TRỰC TIẾP
 * qua ESP-IDF (ledc_timer_config/ledc_channel_config) nên KHÔNG đăng ký vào
 * Peripheral Manager của Arduino. Hệ quả: ledcAttach() tin rằng mọi kênh đều
 * rảnh và luôn cấp phát kênh 0 — đúng số kênh camera đang dùng.
 *
 * Trên ESP32 classic việc này KHÔNG xung đột, nhưng lý do rất hẹp: Arduino
 * đánh số kênh 0..7 = nhóm HIGH-speed, 8..15 = nhóm LOW-speed; esp32-camera
 * đặt XCLK ở nhóm LOW-speed. Hai nhóm là hai khối timer tách rời về phần
 * cứng, nên "kênh 0" của Arduino và "kênh 0" của camera là hai thứ khác nhau.
 *
 * Đây là sự TRÙNG HỢP có lợi, không phải bảo đảm của API. Vì vậy kết quả gắn
 * LEDC luôn được kiểm tra (g_pwmReady) thay vì tin là xong: nếu một phiên bản
 * core sau này đổi cách cấp phát, ta thấy lỗi ngay trên Serial chứ không phải
 * ngồi đoán vì sao bơm không chạy.
 */

#include "aqua_pump.h"

#include <Arduino.h>
#include "esp32-hal-ledc.h"

// ---------- Cấu hình chân & PWM ----------
static const int PUMP_PIN  = 13;
static const int PWM_FREQ  = 20000;  // 20kHz: ngoài ngưỡng nghe
static const int PWM_BITS  = 10;     // 10 bit → duty 0..1023
static const int PWM_MAX   = (1 << PWM_BITS) - 1;

// ---------- Trạng thái ----------
static PumpTiming g_timing;
static PumpPhase  g_phase       = PUMP_PHASE_FILLING;
static uint32_t   g_phaseStart  = 0;
static bool       g_autoRunning = false;  // TẮT mặc định — an toàn khi lắp/kiểm tra
static uint32_t   g_cycleCount  = 0;
static uint8_t    g_curDuty     = 0;      // % duty hiện tại
static bool       g_pwmReady    = false;  // ledcAttach đã thành công chưa

// Yêu cầu bật/tắt auto đến từ task khác (handler HTTP). aquaPumpTick() ở task
// loop() là nơi DUY NHẤT thực thi — xem ghi chú đồng thời trong aqua_pump.h.
// volatile: hai task đọc/ghi, cấm trình biên dịch giữ trong thanh ghi.
static volatile bool g_autoRequestPending = false;
static volatile bool g_autoRequestValue   = false;

// ---------- Helpers ----------

const char *pumpPhaseName(PumpPhase p) {
  switch (p) {
    case PUMP_PHASE_FILLING:  return "FILLING";
    case PUMP_PHASE_SETTLING: return "SETTLING";
    case PUMP_PHASE_FLUSHING: return "FLUSHING";
    case PUMP_PHASE_COOLDOWN: return "COOLDOWN";
  }
  return "?";
}

static void pumpDuty(uint8_t pct) {
  if (pct > 100) pct = 100;
  // Chưa gắn được PWM thì ledcWrite() là lệnh rỗng. Không cập nhật g_curDuty
  // trong trường hợp đó: /device báo duty=55 trong khi bơm đứng im là kiểu
  // hỏng khó truy nhất. Giữ duty=0 để trạng thái báo ra đúng sự thật.
  if (!g_pwmReady) return;
  g_curDuty = pct;
  ledcWrite(PUMP_PIN, (uint32_t)pct * PWM_MAX / 100);
}

// Vuốt duty tuyến tính từ mức hiện tại tới đích trong ms mili-giây.
// BLOCKING — tối đa ~350ms. Chấp nhận được vì:
//   - Watchdog 30s/5s, quá dư so với 350ms.
//   - /stream và /capture chạy ở task httpd riêng, không bị ảnh hưởng.
//   - Chỉ trễ dòng in trạng thái WiFi mỗi ~10s một chút.
static void rampDuty(uint8_t target, uint32_t ms) {
  const uint32_t stepMs = 10;
  if (ms < stepMs) { pumpDuty(target); return; }
  uint32_t steps = ms / stepMs;
  int      from  = g_curDuty;
  for (uint32_t i = 1; i <= steps; i++) {
    pumpDuty((uint8_t)(from + (int)(target - from) * (int)i / (int)steps));
    delay(stepMs);
  }
  pumpDuty(target);
}

static void enterPhase(PumpPhase p) {
  // Ra khỏi pha đang chạy: nếu sắp dừng bơm thì vuốt xuống TRƯỚC (chống búa nước)
  bool willRun = (p == PUMP_PHASE_FILLING || p == PUMP_PHASE_FLUSHING);
  if (!willRun && g_curDuty > 0) rampDuty(0, g_timing.rampDownMs);

  g_phase = p;

  if (willRun) {
    uint8_t target = (p == PUMP_PHASE_FILLING) ? g_timing.fillDuty : g_timing.flushDuty;
    rampDuty(target, g_timing.rampUpMs);
  }

  // Bắt đầu đồng hồ pha SAU khi vuốt xong, để toàn bộ fillMs/flushMs có thực tế
  // ở mức cruise/flush.
  g_phaseStart = millis();

  Serial.printf("[pump %lu ms] -> %s | duty=%u%%\n", g_phaseStart, pumpPhaseName(p), g_curDuty);
}

// ---------- API chính ----------

void aquaPumpPreInit() {
  // AN TOÀN TRƯỚC TIÊN — việc đầu tiên của cả setup().
  // ENA thả nổi có thể được L298N đọc là HIGH → bơm chạy hết tốc. Từ lúc cấp
  // điện tới lúc aquaPumpInit() chạy có camera init + WiFi connect (tới 20s),
  // và setup() còn thoát sớm nếu camera lỗi — cửa sổ đó phải được bịt ở đây.
  // Cố ý KHÔNG in gì: hàm này chạy trước Serial.begin().
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
}

bool aquaPumpInit() {
  aquaPumpPreInit();  // idempotent — chắc chắn chân đang LOW trước khi gắn PWM

  g_pwmReady = ledcAttach(PUMP_PIN, PWM_FREQ, PWM_BITS);

  g_autoRunning = false;
  g_curDuty     = 0;
  g_cycleCount  = 0;
  g_phase       = PUMP_PHASE_FILLING;
  g_phaseStart  = millis();
  g_autoRequestPending = false;

  if (!g_pwmReady) {
    // Không tự ý chạy tiếp như chưa có chuyện gì: bơm sẽ không bao giờ nhúc
    // nhích và không ai biết vì sao.
    Serial.printf("[pump][LOI] ledcAttach(GPIO%d) THAT BAI — bom KHONG dieu khien duoc.\n",
                  PUMP_PIN);
    Serial.println("[pump][LOI] Kiem tra xung dot kenh LEDC (xem ghi chu dau aqua_pump.cpp).");
    return false;
  }

  pumpDuty(0);
  Serial.printf("[pump] init OK | GPIO%d | PWM %dHz %d-bit | auto=OFF (an toan)\n",
                PUMP_PIN, PWM_FREQ, PWM_BITS);
  return true;
}

bool aquaPumpPwmReady() { return g_pwmReady; }

void aquaPumpTick() {
  // Thực thi yêu cầu auto do task khác (HTTP) gửi sang. Làm ở đây để mọi thay
  // đổi pha và mọi lần ramp đều xảy ra trong đúng một task — xem aqua_pump.h.
  if (g_autoRequestPending) {
    g_autoRequestPending = false;
    aquaPumpSetAuto(g_autoRequestValue);
  }

  if (!g_autoRunning) return;

  uint32_t elapsed = millis() - g_phaseStart;
  switch (g_phase) {
    case PUMP_PHASE_FILLING:
      if (elapsed >= g_timing.fillMs) enterPhase(PUMP_PHASE_SETTLING);
      break;
    case PUMP_PHASE_SETTLING:
      if (elapsed >= g_timing.settleMs) enterPhase(PUMP_PHASE_FLUSHING);
      break;
    case PUMP_PHASE_FLUSHING:
      if (elapsed >= g_timing.flushMs) enterPhase(PUMP_PHASE_COOLDOWN);
      break;
    case PUMP_PHASE_COOLDOWN:
      if (elapsed >= g_timing.cooldownMs) {
        g_cycleCount++;
        enterPhase(PUMP_PHASE_FILLING);
      }
      break;
  }
}

// ---------- Điều khiển ----------

void aquaPumpRequestAuto(bool on) {
  // Gọi được từ task httpd. Chỉ ghi cờ — KHÔNG ramp, KHÔNG đổi pha ở đây:
  // hai việc đó chạy song song với aquaPumpTick() sẽ làm hỏng g_curDuty/
  // g_phase/g_phaseStart, và ramp blocking 350ms sẽ chặn task httpd.
  g_autoRequestValue   = on;
  g_autoRequestPending = true;
}

void aquaPumpSetAuto(bool on) {
  if (on && !g_pwmReady) {
    // Không đếm chu kỳ và in pha như thể đang chạy trong khi bơm đứng im —
    // đó chính là kiểu "báo cáo sai sự thật" mà g_pwmReady sinh ra để chặn.
    Serial.println("[pump][LOI] Khong bat duoc auto: PWM chua gan thanh cong.");
    return;
  }
  g_autoRunning = on;
  if (on) {
    enterPhase(PUMP_PHASE_FILLING);
    Serial.println("[pump] auto ON — bat dau Stop-Flow.");
  } else {
    rampDuty(0, g_timing.rampDownMs);
    Serial.println("[pump] auto OFF — bom da vuot xuong 0.");
  }
}

bool aquaPumpIsAuto() { return g_autoRunning; }

void aquaPumpManualOn() {
  g_autoRunning = false;
  rampDuty(g_timing.fillDuty, g_timing.rampUpMs);
  Serial.printf("[pump] manual ON duty=%u%%, auto tam dung.\n", g_curDuty);
}

void aquaPumpManualOff() {
  g_autoRunning = false;
  rampDuty(0, g_timing.rampDownMs);
  Serial.println("[pump] manual OFF (da vuot xuong), auto tam dung.");
}

// ---------- Đọc trạng thái ----------

PumpPhase    aquaPumpPhase()      { return g_phase; }
uint8_t      aquaPumpDuty()       { return g_curDuty; }
uint32_t     aquaPumpCycleCount() { return g_cycleCount; }

// ---------- Cấu hình ----------

PumpTiming *aquaPumpTiming() { return &g_timing; }

void aquaPumpResetTiming() {
  g_timing = PumpTiming();
  Serial.println("[pump] timing da khoi phuc mac dinh.");
}

// ---------- Serial ----------

void aquaPumpPrintStatus() {
  Serial.println(F("--- Pump status ---"));
  Serial.printf("PWM:       %s\n", g_pwmReady ? "san sang" : "*** THAT BAI - bom khong dieu khien duoc ***");
  Serial.printf("Auto:      %s\n", g_autoRunning ? "dang chay" : "TAM DUNG");
  Serial.printf("Phase:     %s (da %lu ms)\n", pumpPhaseName(g_phase), millis() - g_phaseStart);
  Serial.printf("Duty:      %u%%\n", g_curDuty);
  Serial.printf("Cycles:    %lu\n", (unsigned long)g_cycleCount);
  Serial.printf("Timing(ms): fill=%lu settle=%lu flush=%lu cooldown=%lu\n",
                (unsigned long)g_timing.fillMs, (unsigned long)g_timing.settleMs,
                (unsigned long)g_timing.flushMs, (unsigned long)g_timing.cooldownMs);
  Serial.printf("Ramp(ms):   up=%lu down=%lu\n",
                (unsigned long)g_timing.rampUpMs, (unsigned long)g_timing.rampDownMs);
  Serial.printf("Duty(%%):    fill=%u flush=%u\n", g_timing.fillDuty, g_timing.flushDuty);
  Serial.println(F("-------------------"));
}

void aquaPumpPrintHelp() {
  Serial.println(F("Pump commands:"));
  Serial.println(F("  p        - pump status"));
  Serial.println(F("  0        - manual OFF (ramp down)"));
  Serial.println(F("  1        - manual ON  (ramp to fillDuty)"));
  Serial.println(F("  a        - start auto Stop-Flow"));
  Serial.println(F("  f<ms>    - fill time,     e.g. f3000"));
  Serial.println(F("  s<ms>    - settle time,   e.g. s1500"));
  Serial.println(F("  x<ms>    - flush time,    e.g. x8000"));
  Serial.println(F("  c<ms>    - cooldown time, e.g. c5000"));
  Serial.println(F("  u<ms>    - ramp UP,       e.g. u250"));
  Serial.println(F("  w<ms>    - ramp DOWN,     e.g. w350"));
  Serial.println(F("  d<0-100> - CRUISE duty pha FILL,  e.g. d45"));
  Serial.println(F("  X<0-100> - duty pha FLUSH,        e.g. X100"));
  Serial.println(F("  r        - reset timing to defaults"));
  Serial.println(F("  ?        - this help menu"));
}

bool aquaPumpHandleSerial(const String &line) {
  if (line.length() == 0) return false;

  char cmd = line[0];
  long val = line.length() > 1 ? line.substring(1).toInt() : -1;

  // Bộ lệnh 1 ký tự, port nguyên văn từ pump_pwm_test.ino
  switch (cmd) {
    case 'p': aquaPumpPrintStatus(); return true;
    case '?': aquaPumpPrintHelp();   return true;
    case '0': aquaPumpManualOff();   return true;
    case '1': aquaPumpManualOn();    return true;
    case 'a': aquaPumpSetAuto(true); return true;
    case 'f': if (val > 0) { g_timing.fillMs     = val; Serial.printf("fillMs=%ld\n", val); }     return true;
    case 's': if (val > 0) { g_timing.settleMs   = val; Serial.printf("settleMs=%ld\n", val); }   return true;
    case 'x': if (val > 0) { g_timing.flushMs    = val; Serial.printf("flushMs=%ld\n", val); }    return true;
    case 'c': if (val > 0) { g_timing.cooldownMs = val; Serial.printf("cooldownMs=%ld\n", val); } return true;
    case 'u': if (val >= 0) { g_timing.rampUpMs   = val; Serial.printf("rampUpMs=%ld\n", val); }   return true;
    case 'w': if (val >= 0) { g_timing.rampDownMs = val; Serial.printf("rampDownMs=%ld\n", val); } return true;
    case 'd':
      if (val >= 0 && val <= 100) {
        g_timing.fillDuty = (uint8_t)val;
        Serial.printf("fillDuty=%ld%%\n", val);
        if (g_phase == PUMP_PHASE_FILLING && g_curDuty > 0) rampDuty(g_timing.fillDuty, 200);
      } else {
        Serial.println("Duty phai trong 0..100");
      }
      return true;
    case 'X':
      if (val >= 0 && val <= 100) {
        g_timing.flushDuty = (uint8_t)val;
        Serial.printf("flushDuty=%ld%%\n", val);
      } else {
        Serial.println("Duty phai trong 0..100");
      }
      return true;
    case 'r':
      aquaPumpResetTiming();
      return true;
    default:
      return false;  // không phải lệnh pump — trả về cho caller xử lý
  }
}
