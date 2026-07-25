/*
 * wifi_config.example.h — MẪU. File này ĐƯỢC commit.
 *
 * CÁCH DÙNG: copy file này thành `wifi_config.h` (cùng thư mục) rồi điền
 * SSID/mật khẩu thật vào đó. `wifi_config.h` đã được .gitignore nên thông tin
 * thật KHÔNG bao giờ lọt vào git.
 *
 *     cp wifi_config.example.h wifi_config.h
 *
 * Vì sao tách ra: trước đây mật khẩu WiFi nằm thẳng trong
 * aqua_scope_station.ino và đã bị commit + đẩy lên GitHub. Sketch vẫn biên
 * dịch được khi thiếu wifi_config.h (xem __has_include trong .ino), chỉ là nó
 * dùng giá trị mặc định vô hại và in cảnh báo lúc build.
 */

#ifndef WIFI_CONFIG_H
#define WIFI_CONFIG_H

// true  = board tự phát AP tên AQUA_AP_SSID, nối laptop vào rồi mở 192.168.4.1
// false = board nối vào router nhà bằng AQUA_STA_SSID/AQUA_STA_PASS
#define AQUA_USE_AP false

#define AQUA_STA_SSID "TenWiFiCuaBan"
#define AQUA_STA_PASS "MatKhauCuaBan"

// Mật khẩu AP phải >= 8 ký tự (yêu cầu của WPA2).
#define AQUA_AP_SSID "AquaScope"
#define AQUA_AP_PASS "aquascope"

#endif  // WIFI_CONFIG_H
