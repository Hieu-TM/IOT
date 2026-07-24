// pump_pwm_test.ino
// Firmware TEST bơm RS365 12V qua MOSFET + PWM (thay module relay ON/OFF).
// Mục tiêu chống sóng (docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md):
//   1. SOFT-STOP: vuốt duty 100%→0 trong ~350ms trước khi tắt hẳn, thay vì cắt đột
//      ngột. Cắt đột ngột gây BÚA NƯỚC (xung áp suất do khối nước trong ống có quán
//      tính, không dừng kịp theo motor) — tự nó kích một đợt sóng mới đúng lúc bắt
//      đầu pha SETTLING.
//   2. SOFT-START: vuốt 0→duty khi khởi động, tránh cú giật hút lúc bơm vào tải.
//   3. CRUISE DUTY < 100% suốt pha FILL: giảm vận tốc hút trung bình xuống dưới
//      ngưỡng gây "ực nước" (xoáy hút khí) tại miệng cổng xả. Giá trị đúng KHÔNG
//      tính được bằng lý thuyết — phải dò thực nghiệm bằng lệnh 'd'.
//      Pha FLUSH vẫn chạy duty cao để quét sạch hạt.
//
// ⚠️⚠️ KHÁC BIỆT SỐNG CÒN SO VỚI BẢN RELAY (pump_stopflow_test.ino):
//   Module relay opto trong bản cũ là ACTIVE-LOW  (GPIO LOW  = bơm CHẠY).
//   MOSFET N-channel IRLZ44N ở đây là  ACTIVE-HIGH (GPIO HIGH = bơm CHẠY).
//   Nạp nhầm bản này với đấu nối relay (hoặc ngược lại) = bơm chạy full tốc ngay
//   lúc boot. Kiểm kỹ phần cứng trước khi nạp.
//
// Đấu nối (MOSFET N-channel low-side):
//   ESP32 GPIO13 --[220Ω]--> Gate IRLZ44N
//   Gate --[10kΩ]--> GND        (kéo xuống: MOSFET TẮT khi ESP32 reset/boot,
//                                lúc đó GPIO ở trạng thái trôi nổi)
//   Source IRLZ44N -> GND chung (ESP32 GND + GND nguồn 12V)
//   Drain  IRLZ44N -> Bơm (−)
//   Bơm (+)        -> 12V+ (adapter 12V/2A)
//   Diode 1N4007/UF4007 song song 2 cực bơm, CATỐT (vạch) về phía 12V+
//     → dập xung cảm ứng ngược khi ngắt dòng cuộn dây motor
//   Tụ gốm 0.1µF hàn ngang 2 cực bơm, càng sát motor càng tốt (chống nhiễu chổi than)
//   Tụ hóa 470–1000µF trên rail 12V (gánh dòng khởi động đỉnh ~2A)
//
// ⚠️ IRLZ44N (logic-level) — KHÔNG dùng IRF540N: IRF540N là standard-level, cần
//    ~10V ở cổng mới mở bão hòa; với 3.3V của ESP32 nó chỉ mở dở, điện trở dẫn cao
//    hơn nhiều so datasheet → nóng bất thường, có thể hỏng.
//
// Board: ESP32 bất kỳ, Arduino-ESP32 core 3.x (API ledcAttach/ledcWrite).
//        Core 2.x dùng ledcSetup/ledcAttachPin — KHÔNG biên dịch được file này.

#include <Arduino.h>

// ---------- Cấu hình chân & PWM ----------
const int PUMP_PIN  = 13;
const int PWM_FREQ  = 20000;  // 20kHz: ngoài ngưỡng nghe + dòng cuộn cảm liên tục
const int PWM_BITS  = 10;     // độ phân giải 10 bit → duty 0..1023
const int PWM_MAX   = (1 << PWM_BITS) - 1;

// ---------- Tham số chu trình ----------
struct Timing {
  uint32_t fillMs     = 5000;
  uint32_t settleMs   = 2000;
  uint32_t flushMs    = 5000;
  uint32_t cooldownMs = 3000;
  uint32_t rampUpMs   = 250;   // vuốt lên khi khởi động
  uint32_t rampDownMs = 350;   // vuốt xuống trước khi tắt (chống búa nước)
  uint8_t  fillDuty   = 55;    // % — GIÁ TRỊ KHỞI ĐIỂM, phải dò thực nghiệm bằng 'd'
  uint8_t  flushDuty  = 100;   // % — flush cần mạnh để quét sạch hạt
} timing;

enum Phase { FILLING, SETTLING, FLUSHING, COOLDOWN };

const char* phaseName(Phase p) {
  switch (p) {
    case FILLING:  return "FILLING (bom chay cruise - fill)";
    case SETTLING: return "SETTLING (bom tat - lang nuoc - CHUP ANH)";
    case FLUSHING: return "FLUSHING (bom chay manh - xa hat)";
    case COOLDOWN: return "COOLDOWN (bom tat - nghi)";
  }
  return "?";
}

Phase    phase        = FILLING;
uint32_t phaseStartMs = 0;
bool     autoRunning  = true;
uint32_t cycleCount   = 0;
uint8_t  curDuty      = 0;     // % duty hiện tại

void pumpDuty(uint8_t pct) {
  if (pct > 100) pct = 100;
  curDuty = pct;
  ledcWrite(PUMP_PIN, (uint32_t)pct * PWM_MAX / 100);
}

// Vuốt duty tuyến tính từ mức hiện tại tới đích trong ms mili-giây.
// CHẶN (blocking) — chấp nhận được vì đây là firmware test 1 việc, và mọi pha
// đều phải đợi ramp xong mới có ý nghĩa. Bước 10ms đủ mượt so quán tính motor.
void rampDuty(uint8_t target, uint32_t ms) {
  const uint32_t stepMs = 10;
  if (ms < stepMs) { pumpDuty(target); return; }
  uint32_t steps = ms / stepMs;
  int      from  = curDuty;
  for (uint32_t i = 1; i <= steps; i++) {
    pumpDuty((uint8_t)(from + (int)(target - from) * (int)i / (int)steps));
    delay(stepMs);
  }
  pumpDuty(target);
}

void enterPhase(Phase p) {
  // Ra khỏi pha đang chạy: nếu sắp dừng bơm thì vuốt xuống TRƯỚC (chống búa nước)
  bool willRun = (p == FILLING || p == FLUSHING);
  if (!willRun && curDuty > 0) rampDuty(0, timing.rampDownMs);

  phase = p;
  phaseStartMs = millis();

  if (willRun) {
    uint8_t target = (p == FILLING) ? timing.fillDuty : timing.flushDuty;
    rampDuty(target, timing.rampUpMs);
  }

  Serial.printf("[%lu ms] -> %s | duty=%u%%\n", phaseStartMs, phaseName(p), curDuty);
  if (p == SETTLING) {
    Serial.println("          (day la luc thuc te se: bat den nen + chup 1 anh)");
  }
}

void printStatus() {
  Serial.println(F("--- Trang thai ---"));
  Serial.printf("Auto:      %s\n", autoRunning ? "dang chay" : "TAM DUNG (dieu khien tay)");
  Serial.printf("Pha:       %s (da %lu ms)\n", phaseName(phase), millis() - phaseStartMs);
  Serial.printf("Duty:      %u%%\n", curDuty);
  Serial.printf("Chu ky:    %lu\n", cycleCount);
  Serial.printf("Timing(ms): fill=%lu settle=%lu flush=%lu cooldown=%lu\n",
                timing.fillMs, timing.settleMs, timing.flushMs, timing.cooldownMs);
  Serial.printf("Ramp(ms):   up=%lu down=%lu\n", timing.rampUpMs, timing.rampDownMs);
  Serial.printf("Duty(%%):    fill=%u flush=%u\n", timing.fillDuty, timing.flushDuty);
  Serial.println(F("------------------"));
}

void printHelp() {
  Serial.println(F("Lenh Serial:"));
  Serial.println(F("  p         - in trang thai"));
  Serial.println(F("  0         - TAM DUNG auto, vuot bom ve 0"));
  Serial.println(F("  1         - TAM DUNG auto, vuot bom len fillDuty"));
  Serial.println(F("  a         - chay lai auto tu dau pha FILLING"));
  Serial.println(F("  f<ms>     - thoi gian fill,     vd f3000"));
  Serial.println(F("  s<ms>     - thoi gian settle,   vd s1500"));
  Serial.println(F("  x<ms>     - thoi gian flush,    vd x8000"));
  Serial.println(F("  c<ms>     - thoi gian cooldown, vd c5000"));
  Serial.println(F("  u<ms>     - ramp UP,            vd u250"));
  Serial.println(F("  w<ms>     - ramp DOWN,          vd w350"));
  Serial.println(F("  d<0-100>  - CRUISE duty pha FILL  (do thuc nghiem!), vd d45"));
  Serial.println(F("  X<0-100>  - duty pha FLUSH,        vd X100"));
  Serial.println(F("  r         - khoi phuc mac dinh"));
  Serial.println(F("  ?         - in lai menu"));
  Serial.println(F(""));
  Serial.println(F("CACH DO CRUISE DUTY: chay 'a', nhin mat nuoc luc FILLING."));
  Serial.println(F("Con nghe 'uc uc'/xoay phieu o mieng xa -> ha 'd' 5%% roi thu lai."));
  Serial.println(F("Lay muc THAP NHAT ma van day nuoc len du muc trong fillMs."));
}

void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  char cmd = line[0];
  long val = line.length() > 1 ? line.substring(1).toInt() : -1;

  switch (cmd) {
    case 'p': printStatus(); break;
    case '?': printHelp();   break;
    case '0':
      autoRunning = false;
      rampDuty(0, timing.rampDownMs);
      Serial.println("Manual: bom TAT (da vuot xuong), auto tam dung.");
      break;
    case '1':
      autoRunning = false;
      rampDuty(timing.fillDuty, timing.rampUpMs);
      Serial.printf("Manual: bom BAT duty=%u%%, auto tam dung.\n", curDuty);
      break;
    case 'a':
      autoRunning = true;
      enterPhase(FILLING);
      Serial.println("Da chay lai auto Stop-Flow.");
      break;
    case 'f': if (val > 0) { timing.fillMs     = val; Serial.printf("fillMs=%ld\n", val); }     break;
    case 's': if (val > 0) { timing.settleMs   = val; Serial.printf("settleMs=%ld\n", val); }   break;
    case 'x': if (val > 0) { timing.flushMs    = val; Serial.printf("flushMs=%ld\n", val); }    break;
    case 'c': if (val > 0) { timing.cooldownMs = val; Serial.printf("cooldownMs=%ld\n", val); } break;
    case 'u': if (val >= 0) { timing.rampUpMs   = val; Serial.printf("rampUpMs=%ld\n", val); }   break;
    case 'w': if (val >= 0) { timing.rampDownMs = val; Serial.printf("rampDownMs=%ld\n", val); } break;
    case 'd':
      if (val >= 0 && val <= 100) {
        timing.fillDuty = (uint8_t)val;
        Serial.printf("fillDuty=%ld%%\n", val);
        if (phase == FILLING && curDuty > 0) rampDuty(timing.fillDuty, 200);
      } else Serial.println("Duty phai trong 0..100");
      break;
    case 'X':
      if (val >= 0 && val <= 100) {
        timing.flushDuty = (uint8_t)val;
        Serial.printf("flushDuty=%ld%%\n", val);
      } else Serial.println("Duty phai trong 0..100");
      break;
    case 'r':
      timing = Timing();
      Serial.println("Da khoi phuc mac dinh.");
      break;
    default:
      Serial.println("Lenh khong hop le. Go '?' de xem menu.");
  }
}

void setup() {
  // AN TOÀN TRƯỚC TIÊN: ghim chân xuống LOW (= MOSFET TẮT) trước mọi việc khác,
  // rồi mới gắn PWM. Ngược chiều với bản relay active-low — xem cảnh báo đầu file.
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);

  ledcAttach(PUMP_PIN, PWM_FREQ, PWM_BITS);
  pumpDuty(0);

  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println(F("=== Aqua Scope - Pump PWM (MOSFET IRLZ44N) test firmware ==="));
  Serial.printf("PUMP_PIN=GPIO%d | PWM %dHz %d-bit | ACTIVE-HIGH (HIGH = bom CHAY)\n",
                PUMP_PIN, PWM_FREQ, PWM_BITS);
  Serial.println(F("!! Firmware nay dung cho MOSFET. KHONG nap khi dang dau RELAY active-low !!"));
  printHelp();

  enterPhase(FILLING);
}

void loop() {
  handleSerial();
  if (!autoRunning) return;

  uint32_t elapsed = millis() - phaseStartMs;
  switch (phase) {
    case FILLING:  if (elapsed >= timing.fillMs)     enterPhase(SETTLING); break;
    case SETTLING: if (elapsed >= timing.settleMs)   enterPhase(FLUSHING); break;
    case FLUSHING: if (elapsed >= timing.flushMs)    enterPhase(COOLDOWN); break;
    case COOLDOWN:
      if (elapsed >= timing.cooldownMs) { cycleCount++; enterPhase(FILLING); }
      break;
  }
}
