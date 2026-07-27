/*
 * aqua_pump — điều khiển bơm RS365 12V qua L298N, chu trình Stop-Flow.
 *
 * Phần cứng:
 *   GPIO13 (PWM 20kHz/10-bit qua LEDC) → ENA của L298N
 *   IN1 cố định 3.3V, IN2 cố định GND  → một chiều, không đảo
 *   Nguồn 12V/2A adapter riêng cho L298N+bơm, GND chung với ESP32-CAM.
 *
 * GPIO13 trên AI-Thinker: không trùng chân camera. Chỉ trùng HS2_DATA3
 * (SD card 4-bit) — firmware này không dùng khe SD nên không sao.
 *
 * State machine: FILLING → SETTLING → FLUSHING → COOLDOWN → lặp.
 *   - FILLING/FLUSHING: bơm chạy (duty%), ramp lên/xuống chống búa nước.
 *   - SETTLING: bơm tắt, nước đứng yên — đây là lúc chụp ảnh.
 *   - COOLDOWN: bơm tắt, nghỉ giữa 2 chu kỳ.
 *
 * KHỞI TẠO HAI GIAI ĐOẠN — đọc kỹ trước khi đổi thứ tự gọi:
 *   1) aquaPumpPreInit()  — ép GPIO13 xuống LOW. Phải là việc ĐẦU TIÊN của
 *      setup(), trước cả Serial.begin(). Lý do ở phần An toàn bên dưới.
 *   2) aquaPumpInit()     — gắn LEDC, bật PWM. Gọi SAU esp_camera_init().
 *
 * An toàn:
 *   - Chân ép LOW ngay đầu setup(): ENA thả nổi có thể được L298N đọc là
 *     HIGH → bơm chạy hết tốc. Giữa lúc cấp điện và lúc gắn PWM có camera
 *     init + WiFi connect (timeout tới 20 giây), và setup() còn có nhánh
 *     thoát sớm khi camera lỗi. Ép LOW muộn là để hở đúng cửa sổ đó.
 *   - autoRunning mặc định TẮT — phải bật tay qua HTTP hoặc Serial.
 *
 * ĐỒNG THỜI (quan trọng): state machine chỉ được chạy trong task loop().
 * Handler HTTP chạy ở task httpd riêng nên KHÔNG được gọi thẳng hàm nào có
 * ramp/đổi pha — dùng aquaPumpRequestAuto(), aquaPumpTick() sẽ thực thi.
 * Xem phần "Điều khiển" bên dưới để biết hàm nào gọi được từ đâu.
 *
 * Ranh giới: file này CHỈ biết điều khiển bơm. Không biết gì về camera,
 * WiFi hay HTTP. Tích hợp HTTP nằm ở app_httpd.cpp, serial ở .ino.
 */

#ifndef AQUA_PUMP_H
#define AQUA_PUMP_H

#include <stdint.h>
#include <Arduino.h>  // String dùng trong aquaPumpHandleSerial()

// ---------- Pha của chu trình Stop-Flow ----------
enum PumpPhase {
  PUMP_PHASE_FILLING,
  PUMP_PHASE_SETTLING,
  PUMP_PHASE_FLUSHING,
  PUMP_PHASE_COOLDOWN,
};

// Tên pha, dùng cho Serial debug và /device JSON.
const char *pumpPhaseName(PumpPhase p);

// ---------- Cấu hình thời gian (ms) và duty (%) ----------
struct PumpTiming {
  uint32_t fillMs     = 5000;
  uint32_t settleMs   = 2000;
  uint32_t flushMs    = 5000;
  uint32_t cooldownMs = 3000;
  uint32_t rampUpMs   = 250;   // vuốt lên khi khởi động
  uint32_t rampDownMs = 350;   // vuốt xuống trước khi tắt (chống búa nước)
  uint8_t  fillDuty   = 55;    // % — giá trị khởi điểm, dò thực nghiệm bằng 'd'
  uint8_t  flushDuty  = 100;   // % — flush cần mạnh để quét sạch hạt
};

// ---------- API chính ----------

// GIAI ĐOẠN 1: ép GPIO13 xuống LOW (bơm tắt) và không làm gì khác.
// Gọi ở DÒNG ĐẦU TIÊN của setup(), trước cả Serial.begin() — hàm này cố ý
// không in gì để không phụ thuộc Serial. An toàn khi gọi nhiều lần.
void aquaPumpPreInit();

// GIAI ĐOẠN 2: gắn LEDC vào GPIO13 → duty 0. autoRunning bắt đầu = false.
// Gọi SAU esp_camera_init() (xem ghi chú kênh LEDC trong aqua_pump.cpp).
// Trả về false nếu gắn PWM thất bại — khi đó bơm KHÔNG điều khiển được và
// mọi lệnh duty sẽ bị bỏ qua thay vì im lặng không có tác dụng.
bool aquaPumpInit();

// PWM đã gắn thành công chưa. false = bơm không điều khiển được.
bool aquaPumpPwmReady();

// Gọi mỗi vòng loop(). Xử lý yêu cầu auto đang chờ (từ HTTP), rồi chạy
// state machine nếu autoRunning. Khi chuyển pha có ramp thì blocking tối đa
// ~350ms. CHỈ được gọi từ task loop().
void aquaPumpTick();

// ---------- Điều khiển ----------
//
// Gọi được từ TASK NÀO là một phần của hợp đồng, không phải chi tiết nội bộ:
//   - aquaPumpRequestAuto()  : gọi từ BẤT KỲ task nào (kể cả httpd).
//   - các hàm còn lại        : CHỈ từ task loop() (Serial), vì chúng ramp
//                              (blocking) và sửa thẳng state machine.

// An toàn đa task: chỉ ghi lại yêu cầu, aquaPumpTick() sẽ thực thi ở task
// loop(). Đây là hàm mà đường HTTP phải dùng.
void aquaPumpRequestAuto(bool on);

// Bật/tắt chu trình auto NGAY LẬP TỨC (có ramp). Chỉ gọi từ task loop().
void aquaPumpSetAuto(bool on);
bool aquaPumpIsAuto();

// Điều khiển tay (tắt auto trước). Vuốt duty lên/xuống. Chỉ từ task loop().
void aquaPumpManualOn();   // ramp lên fillDuty
void aquaPumpManualOff();  // ramp xuống 0

// ---------- Đọc trạng thái ----------
PumpPhase    aquaPumpPhase();
uint8_t      aquaPumpDuty();       // % duty hiện tại
uint32_t     aquaPumpCycleCount();

// ---------- Cấu hình (đọc/ghi) ----------

// Con trỏ tới struct timing sống — ghi trực tiếp rồi hiệu lực ngay.
// Lưu vĩnh viễn bằng aquaPrefsSave().
PumpTiming  *aquaPumpTiming();

// Khôi phục timing về giá trị mặc định (chỉ trong RAM, chưa lưu flash).
void aquaPumpResetTiming();

// ---------- Serial ----------

// Xử lý 1 dòng Serial cho pump. Trả true nếu đã nhận lệnh pump
// (dù hợp lệ hay không), false nếu ký tự đầu không phải lệnh pump.
// Gọi từ loop() của .ino, phía trước hoặc phía sau handleSerial camera.
bool aquaPumpHandleSerial(const String &line);

// In trạng thái bơm ra Serial.
void aquaPumpPrintStatus();

// In menu lệnh bơm ra Serial.
void aquaPumpPrintHelp();

#endif  // AQUA_PUMP_H
