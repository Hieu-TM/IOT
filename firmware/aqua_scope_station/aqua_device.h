/*
 * aqua_device — danh tính thiết bị cho sổ audit.
 *
 * Vì sao cần: mỗi mẫu trong DB phải chỉ ra ĐÚNG board nào đã chụp nó. Trước
 * đây device_id là hằng "pc-infer" trong config trên máy tính, nên mọi mẫu
 * mang chung một tên — vô nghĩa khi có nhiều board hoặc khi truy ngược lỗi.
 *
 * Mặc định sinh từ MAC nên hai board khác nhau không bao giờ trùng tên, mà
 * cũng không cần cấu hình tay lúc nạp.
 */

#ifndef AQUA_DEVICE_H
#define AQUA_DEVICE_H

#include <stdint.h>

// Nạp device_id đã lưu trong NVS; chưa có thì sinh từ MAC ("aqua-cam-a1b2c3").
// Gọi trong setup(), SAU khi WiFi đã khởi tạo (MAC cần WiFi stack).
void aquaDeviceInit();

// Trả về device_id hiện tại. Không bao giờ NULL sau aquaDeviceInit().
const char *aquaDeviceId();

// Đặt device_id mới và ghi vào NVS.
// Trả về false (không đổi gì) nếu id rỗng, dài quá 64, hoặc chứa ký tự ngoài
// [A-Za-z0-9._-] — ingest của web dùng chuỗi này nguyên văn làm tên file.
bool aquaDeviceSetId(const char *id);

// Đếm số lần chụp từ lúc khởi động (chỉ trong RAM, reset là về 0).
void aquaDeviceCountCapture();
uint32_t aquaDeviceCaptureCount();

#endif  // AQUA_DEVICE_H
