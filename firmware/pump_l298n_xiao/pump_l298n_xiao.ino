// pump_l298n_xiao.ino
// Firmware TEST bơm RS365 12V qua MODULE L298N cho board XIAO ESP32-S3 Sense (Seeed Studio).
//
// ĐÂY LÀ PHIÊN BẢN CHUYỂN ĐỔI TỪ pump_pwm_test.ino (dùng MOSFET IRLZ44N trên ESP32 generic)
// sang L298N + XIAO ESP32-S3 Sense. Toàn bộ logic Stop-Flow giữ nguyên, chỉ thay:
//   - PUMP_PIN: GPIO13 → GPIO1 (D0/A0 trên XIAO — xem bảng chân bên dưới)
//   - Comment hướng dẫn đấu nối: MOSFET → L298N
//
// Mục tiêu chống sóng (docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md):
//   1. SOFT-STOP: vuốt duty 100%→0 trong ~350ms trước khi tắt hẳn, thay vì cắt đột
//      ngột. Cắt đột ngột gây BÚA NƯỚC.
//   2. SOFT-START: vuốt 0→duty khi khởi động, tránh cú giật hút lúc bơm vào tải.
//   3. CRUISE DUTY < 100% suốt pha FILL: giảm vận tốc hút trung bình.
//      Pha FLUSH vẫn chạy duty cao để quét sạch hạt.
//
// ═══════════════════════════════════════════════════════════════════════════════
// ĐẤU NỐI: XIAO ESP32-S3 Sense + Module L298N + Bơm RS365 12V
// ═══════════════════════════════════════════════════════════════════════════════
//
//   XIAO ESP32-S3 Sense          Module L298N             Bơm RS365 12V
//   ────────────────────         ─────────────            ──────────────
//   GPIO1 (D0/A0) ──────PWM───► ENA (THÁO jumper!)
//   3.3V           ───────────► IN1  (cố định HIGH)
//   GND            ───────────► IN2  (cố định LOW = chiều quay cố định)
//                                OUT1 ─────────────────► Cực (+) bơm
//                                OUT2 ─────────────────► Cực (−) bơm
//                                +12V ◄─────────────────  Adapter 12V/2A (+)
//                                GND  ◄─────────────────  Adapter 12V/2A (−)
//   GND  ═══════════ CHUNG GND ═══════════ Adapter GND
//
//   Tụ gốm 0.1µF: hàn ngang 2 cực bơm (sát motor, chống nhiễu chổi than)
//   Tụ hóa 470–1000µF: trên rail 12V (gánh dòng khởi động đỉnh ~2A)
//
// ⚠️ THÁO JUMPER ENA: Module L298N mặc định có jumper nhựa nối ENA lên 5V
//    (= bơm chạy full tốc). PHẢI rút jumper ra, rồi nối dây PWM vào trụ
//    phía gần IN1/IN2 (trụ EN). Trụ còn lại (5V) bỏ trống.
//
// ⚠️ CHUNG GND BẮT BUỘC: GND của XIAO, GND của L298N, GND của adapter 12V
//    phải nối chung. Thiếu = tín hiệu PWM không có đường về, L298N không nhận lệnh.
//
// ⚠️ NẾU BƠM CHẠY NGƯỢC NƯỚC: đảo 2 dây OUT1/OUT2, hoặc đổi IN1↔IN2.
//
// ═══════════════════════════════════════════════════════════════════════════════
// BẢNG CHÂN XIAO ESP32-S3 Sense — CHÂN NÀO DÙNG ĐƯỢC CHO BƠM?
// ═══════════════════════════════════════════════════════════════════════════════
//
// Chân header trên board XIAO (cạnh trái + cạnh phải, đánh số D0–D10):
//
//   Pad   │ GPIO │ Camera dùng? │ Ghi chú
//   ──────┼──────┼──────────────┼─────────────────────────────────
//   D0/A0 │  1   │ KHÔNG        │ ✅ DÙNG CHO BƠM (PWM_PIN) ← CHỌN
//   D1/A1 │  2   │ KHÔNG        │ ✅ Dự phòng
//   D2/A2 │  3   │ KHÔNG        │ ✅ Dự phòng
//   D3/A3 │  4   │ KHÔNG        │ ✅ Dự phòng
//   D4/A4 │  5   │ KHÔNG        │ ✅ Dự phòng (cũng là SDA)
//   D5/A5 │  6   │ KHÔNG        │ ✅ Dự phòng (cũng là SCL)
//   D6/TX │ 43   │ KHÔNG        │ ❌ TRÁNH — đang dùng cho Serial TX
//   D7/RX │ 44   │ KHÔNG        │ ❌ TRÁNH — đang dùng cho Serial RX
//   D8    │  7   │ KHÔNG        │ ✅ Dự phòng
//   D9    │  8   │ KHÔNG        │ ✅ Dự phòng
//   D10   │  9   │ KHÔNG        │ ✅ Dự phòng
//
//   (Camera OV3660 chiếm GPIO: 10,11,12,13,14,15,16,17,18,38,39,40,47,48)
//   → Tất cả chân D0–D5, D8–D10 đều AN TOÀN để dùng cho bơm.
//
// Lý do chọn GPIO1 (D0):
//   - Nằm ở góc board, dễ hàn / kẹp dây
//   - Hỗ trợ PWM (mọi GPIO trên ESP32-S3 đều có thể xuất PWM)
//   - Không xung đột camera, không xung đột Serial
//   - Không có chức năng đặc biệt lúc boot (an toàn)
//
// Board: XIAO ESP32-S3 (Sense), Arduino-ESP32 core 3.x (API ledcAttach/ledcWrite).
//        Core 2.x dùng ledcSetup/ledcAttachPin — KHÔNG biên dịch được file này.

#include <Arduino.h>

// ---------- Cấu hình chân & PWM ----------
// GPIO1 = pad D0/A0 trên XIAO ESP32-S3 Sense.
// Đổi sang GPIO khác nếu muốn: xem bảng chân phía trên, chọn D0–D5 hoặc D8–D10.
const int PUMP_PIN  = 1;      // GPIO1 (D0/A0) — nối tới chân ENA của L298N
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

// ⚠️ LƯU Ý VỀ SỤT ÁP L298N:
// L298N sụt áp ~1.8–2.5V qua transistor nội → bơm chỉ nhận ~9.5–10V thay vì 12V.
// Nếu bơm yếu quá so với bản MOSFET cũ:
//   1. Tăng fillDuty lên (ví dụ 65–70% thay vì 55%)
//   2. Hoặc dùng adapter 14–15V thay vì 12V để bù sụt áp
// Giá trị fillDuty mặc định 55% ở đây có thể cần điều chỉnh lại
// vì đặc tính bơm thay đổi khi điện áp thực tế thấp hơn.

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

  if (willRun) {
    uint8_t target = (p == FILLING) ? timing.fillDuty : timing.flushDuty;
    rampDuty(target, timing.rampUpMs);
  }

  // Bat dau dong ho pha SAU khi vuot xong, de toan bo fillMs/flushMs co thuc te o
  // muc cruise/flush. Truoc day timestamp chay tran tren thoi gian vuot, tao ra
  // am lenh: fillMs 5000 voi rampUpMs 250 chi co ~4750ms cruise thuc te.
  phaseStartMs = millis();

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
  Serial.println(F("Con nghe 'uc uc'/xoay phieu o mieng xa -> ha 'd' 5% roi thu lai."));
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
  // AN TOÀN TRƯỚC TIÊN: ghim chân xuống LOW (= L298N không nhận PWM = bơm TẮT)
  // trước mọi việc khác, rồi mới gắn PWM.
  // L298N + đấu nối IN1=HIGH IN2=LOW: khi ENA=LOW → bơm đứng yên.
  // Khi ENA nhận PWM → bơm chạy tỉ lệ với duty cycle.
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);

  ledcAttach(PUMP_PIN, PWM_FREQ, PWM_BITS);
  pumpDuty(0);

  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println(F("══════════════════════════════════════════════════════════════"));
  Serial.println(F("  Aqua Scope - Pump PWM (L298N) test firmware"));
  Serial.println(F("  Board: XIAO ESP32-S3 Sense (Seeed Studio)"));
  Serial.println(F("══════════════════════════════════════════════════════════════"));
  Serial.printf("PUMP_PIN=GPIO%d (D0/A0) | PWM %dHz %d-bit | ACTIVE-HIGH\n",
                PUMP_PIN, PWM_FREQ, PWM_BITS);
  Serial.println(F("Driver: L298N | ENA=PWM, IN1=3.3V, IN2=GND (1 chieu co dinh)"));
  Serial.println(F(""));
  Serial.println(F("Dau noi:"));
  Serial.println(F("  XIAO GPIO1 (D0) --> L298N ENA (DA THAO jumper!)"));
  Serial.println(F("  XIAO 3.3V       --> L298N IN1"));
  Serial.println(F("  XIAO GND        --> L298N IN2 + L298N GND"));
  Serial.println(F("  Adapter 12V     --> L298N +12V"));
  Serial.println(F("  Adapter GND     --> L298N GND (chung GND voi XIAO)"));
  Serial.println(F("  L298N OUT1/OUT2 --> 2 cuc bom RS365"));
  Serial.println(F(""));
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
