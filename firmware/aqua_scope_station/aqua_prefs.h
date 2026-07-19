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
//
// max_framesize: trần framesize mà bộ nhớ hiện có kham nổi (initCamera() đã
// tự hạ xuống FRAMESIZE_SVGA + CAMERA_FB_IN_DRAM khi không thấy PSRAM - xem
// aqua_scope_station.ino). Mặc định FRAMESIZE_UXGA (đúng bằng DEF_FRAMESIZE,
// tức "không hạ gì cả") để không phá caller cũ nào gọi thiếu tham số này.
// KHÔNG được bỏ tham số này rồi set_framesize(s, UXGA) vô điều kiện như
// trước - làm vậy sẽ dỡ bỏ đúng cái fallback initCamera() vừa dựng, buffer
// DRAM không đủ cho UXGA và ảnh ra bị cụt.
void aquaPrefsApplyDefaults(sensor_t *s, framesize_t max_framesize = FRAMESIZE_UXGA);

// Nạp cấu hình đã lưu (nếu có) và áp lên sensor.
// Trả về true nếu flash có cấu hình, false nếu chưa lưu lần nào (giữ mặc định).
//
// max_framesize: cùng ý nghĩa như aquaPrefsApplyDefaults(). Bắt buộc truyền
// lại giá trị đã tính ở initCamera(): NVS có thể còn giữ framesize=UXGA từ
// một lần lưu trước đó (lúc PSRAM còn hoạt động, hoặc từ bản firmware cũ) -
// nếu không kiểm ở đây, một giá trị vượt quá bộ nhớ hiện có sẽ được nạp lại
// mù quáng mỗi lần khởi động.
bool aquaPrefsLoad(sensor_t *s, framesize_t max_framesize = FRAMESIZE_UXGA);

// Ghi cứng trạng thái sensor hiện tại vào flash.
void aquaPrefsSave(sensor_t *s);

// Xóa cấu hình đã lưu + áp lại mặc định backlit.
void aquaPrefsReset(sensor_t *s);

// Flash đã có cấu hình lưu hay chưa (không áp gì lên sensor).
bool aquaPrefsIsSaved();

#endif  // AQUA_PREFS_H
