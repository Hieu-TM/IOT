// pump_stopflow_test.ino
// Firmware TEST độc lập — chỉ điều khiển bơm RS365 12V theo chu trình Stop-Flow,
// KHÔNG đụng tới camera. Dùng để kiểm tra relay/bơm trước khi ráp vào khay thật.
//
// Board: ESP32-CAM (AI-Thinker) hoặc bất kỳ board ESP32 nào, CẤP NGUỒN RIÊNG
// (ESP32 ăn 5V qua USB/FTDI của riêng nó — KHÔNG rút 5V từ nguồn 12V của bơm).
// GPIO13 rảnh trên AI-Thinker (không trùng chân camera; chỉ trùng SD card 4-bit
// HS2_DATA3 — không dùng khe SD trong bài test này thì không sao).
//
// Đấu nối (module relay 1 kênh, opto-cách ly, ACTIVE-LOW — theo BOM đã chốt):
//   Relay IN   -> GPIO13
//   Relay VCC  -> 5V (chân 5V của ESP32-CAM)
//   Relay GND  -> GND chung với ESP32 VÀ GND của nguồn 12V bơm
//   Relay COM  -> 12V+ (từ adapter 12V/2A)
//   Relay NO   -> Bơm (+)
//   Bơm (-)    -> 12V GND
//   Tụ gốm 0.1µF hàn ngang 2 cực bơm, càng sát motor càng tốt (chống nhiễu chổi
//   than lên ảnh/ESP32 — bắt buộc theo quyết định đã lưu).
//
// AN TOÀN: relay active-low nghĩa là GPIO=LOW -> đóng relay -> BƠM CHẠY.
// Vì vậy việc đầu tiên trong setup() là kéo chân lên mức TẮT (HIGH) trước khi
// làm bất cứ việc gì khác, để bơm không tự chạy lúc boot/nạp code.

#include <Arduino.h>

// ---------- Cấu hình chân ----------
const int PUMP_PIN = 13;
const int PUMP_ON_LEVEL = LOW;    // active-low: LOW = relay đóng = bơm chạy
const int PUMP_OFF_LEVEL = HIGH;

// ---------- Thời gian mặc định các pha (ms) — chỉnh nhanh qua Serial, xem lệnh bên dưới ----------
struct Timing {
  uint32_t fillMs = 5000;    // bơm chạy, hút nước vào khay tới vòi tràn
  uint32_t settleMs = 2000;  // bơm tắt, nước đứng yên (mô phỏng chỗ chụp ảnh)
  uint32_t flushMs = 5000;   // bơm chạy mạnh, xả hạt ra ngoài qua đường ra
  uint32_t cooldownMs = 3000; // bơm tắt, nghỉ giữa 2 chu kỳ
} timing;

enum Phase { FILLING, SETTLING, FLUSHING, COOLDOWN };
const char* phaseName(Phase p) {
  switch (p) {
    case FILLING:  return "FILLING (bom bat - fill)";
    case SETTLING: return "SETTLING (bom tat - lang nuoc)";
    case FLUSHING: return "FLUSHING (bom bat manh - xa hat)";
    case COOLDOWN: return "COOLDOWN (bom tat - nghi)";
  }
  return "?";
}

Phase phase = FILLING;
uint32_t phaseStartMs = 0;
bool autoRunning = true;   // false = tạm dừng chu trình để test tay qua '0'/'1'
uint32_t cycleCount = 0;

void pumpWrite(bool on) {
  digitalWrite(PUMP_PIN, on ? PUMP_ON_LEVEL : PUMP_OFF_LEVEL);
}

void enterPhase(Phase p) {
  phase = p;
  phaseStartMs = millis();
  bool pumpOn = (p == FILLING || p == FLUSHING);
  pumpWrite(pumpOn);
  Serial.printf("[%lu ms] -> %s | bom=%s\n", phaseStartMs, phaseName(p), pumpOn ? "ON" : "OFF");
  if (p == SETTLING) {
    Serial.println("          (day la luc thuc te se: bat den nen + chup 1 anh)");
  }
}

void printStatus() {
  Serial.println(F("--- Trang thai ---"));
  Serial.printf("Auto:     %s\n", autoRunning ? "dang chay" : "TAM DUNG (dieu khien tay)");
  Serial.printf("Pha hien tai: %s (da %lu ms)\n", phaseName(phase), millis() - phaseStartMs);
  Serial.printf("So chu ky da xong: %lu\n", cycleCount);
  Serial.printf("Timing (ms): fill=%lu settle=%lu flush=%lu cooldown=%lu\n",
                timing.fillMs, timing.settleMs, timing.flushMs, timing.cooldownMs);
  Serial.println(F("------------------"));
}

void printHelp() {
  Serial.println(F("Lenh Serial:"));
  Serial.println(F("  p        - in trang thai hien tai"));
  Serial.println(F("  0        - TAM DUNG auto, tat bom (test tay)"));
  Serial.println(F("  1        - TAM DUNG auto, bat bom (test tay)"));
  Serial.println(F("  a        - chay lai auto Stop-Flow tu dau pha FILLING"));
  Serial.println(F("  f<so_ms> - dat thoi gian fill,    vd: f3000"));
  Serial.println(F("  s<so_ms> - dat thoi gian settle,  vd: s1500"));
  Serial.println(F("  x<so_ms> - dat thoi gian flush,   vd: x8000"));
  Serial.println(F("  c<so_ms> - dat thoi gian cooldown, vd: c5000"));
  Serial.println(F("  r        - khoi phuc timing mac dinh"));
  Serial.println(F("  ?        - in lai menu nay"));
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
    case '?': printHelp(); break;
    case '0':
      autoRunning = false;
      pumpWrite(false);
      Serial.println("Manual: bom TAT, auto da tam dung.");
      break;
    case '1':
      autoRunning = false;
      pumpWrite(true);
      Serial.println("Manual: bom BAT, auto da tam dung.");
      break;
    case 'a':
      autoRunning = true;
      enterPhase(FILLING);
      Serial.println("Da chay lai auto Stop-Flow.");
      break;
    case 'f': if (val > 0) { timing.fillMs = val; Serial.printf("fillMs=%ld\n", val); } break;
    case 's': if (val > 0) { timing.settleMs = val; Serial.printf("settleMs=%ld\n", val); } break;
    case 'x': if (val > 0) { timing.flushMs = val; Serial.printf("flushMs=%ld\n", val); } break;
    case 'c': if (val > 0) { timing.cooldownMs = val; Serial.printf("cooldownMs=%ld\n", val); } break;
    case 'r':
      timing = Timing();
      Serial.println("Da khoi phuc timing mac dinh.");
      break;
    default:
      Serial.println("Lenh khong hop le. Go '?' de xem menu.");
  }
}

void setup() {
  // Kéo chân về mức TẮT trước tiên (an toàn boot) — active-low nên OFF = HIGH.
  pinMode(PUMP_PIN, OUTPUT);
  pumpWrite(false);

  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println(F("=== Aqua Scope - Pump Stop-Flow test firmware ==="));
  Serial.printf("PUMP_PIN = GPIO%d, active-%s\n", PUMP_PIN, PUMP_ON_LEVEL == LOW ? "LOW" : "HIGH");
  printHelp();

  enterPhase(FILLING);
}

void loop() {
  handleSerial();
  if (!autoRunning) return;

  uint32_t elapsed = millis() - phaseStartMs;
  switch (phase) {
    case FILLING:
      if (elapsed >= timing.fillMs) enterPhase(SETTLING);
      break;
    case SETTLING:
      if (elapsed >= timing.settleMs) enterPhase(FLUSHING);
      break;
    case FLUSHING:
      if (elapsed >= timing.flushMs) enterPhase(COOLDOWN);
      break;
    case COOLDOWN:
      if (elapsed >= timing.cooldownMs) {
        cycleCount++;
        enterPhase(FILLING);
      }
      break;
  }
}
