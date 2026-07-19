/*
 * aqua_prefs — lưu/nạp cấu hình camera vào flash (NVS).
 *
 * Vì sao cần: canh sáng backlit (exposure/gain) mất vài phút mỗi lần. Không có
 * lớp này thì mỗi lần mất điện là phải canh lại từ đầu. Có nó thì chỉnh 1 lần,
 * bấm "save", cắm điện là chạy đúng thông số.
 *
 * Ranh giới: file này CHỈ biết đọc/ghi flash và áp giá trị lên sensor. Nó không
 * biết gì về HTTP, WiFi hay dataset.
 */

#ifndef AQUA_PREFS_H
#define AQUA_PREFS_H

#include "esp_camera.h"

// Áp bộ mặc định backlit silhouette lên sensor: TẮT AEC/AEC-DSP/AGC, gain 0,
// exposure thấp. Gọi ngay sau esp_camera_init(), TRƯỚC aquaPrefsLoad().
void aquaPrefsApplyDefaults(sensor_t *s);

// Nạp cấu hình đã lưu (nếu có) và áp lên sensor.
// Trả về true nếu flash có cấu hình, false nếu chưa lưu lần nào (giữ mặc định).
bool aquaPrefsLoad(sensor_t *s);

// Ghi cứng trạng thái sensor hiện tại vào flash.
void aquaPrefsSave(sensor_t *s);

// Xóa cấu hình đã lưu + áp lại mặc định backlit.
void aquaPrefsReset(sensor_t *s);

#endif  // AQUA_PREFS_H
