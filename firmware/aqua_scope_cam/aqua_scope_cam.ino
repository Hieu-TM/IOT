/*
 * ============================================================================
 *  Aqua Scope — Firmware camera cho XIAO ESP32-S3 Sense (OV3660, 3MP)
 * ============================================================================
 *  Mục tiêu: chụp ảnh BACKLIT SILHOUETTE (nền sáng đều, hạt = bóng đen) để
 *  đếm & đo kích thước hạt rác 1-5mm. KHÔNG phải firmware kính hiển vi.
 *
 *  Điểm khác biệt so với firmware Matchboxscope:
 *   - Ép PHƠI SÁNG THỦ CÔNG: TẮT AEC / AEC-DSP / AGC, đặt Gain=0 + Exposure thấp
 *     -> nền không bị "cháy trắng" (đây là lỗi kinh điển khi để auto).
 *   - LƯU CỨNG cấu hình vào flash (NVS/Preferences): cắm điện là chạy đúng thông
 *     số đã chỉnh, không cần chỉnh lại.
 *   - Một selector ĐỘ PHÂN GIẢI duy nhất (QVGA..QXGA), đổi tự do khi test qua web
 *     hoặc serial; dùng chung cho cả stream lẫn chụp. OV3660 là cảm biến 3MP nên
 *     có thể lên tới QXGA 2048x1536 (OV2640 chỉ UXGA).
 *   - Chỉnh qua Web UI (slider trực quan) HOẶC lệnh Serial.
 *   - Có sẵn hook runVision() để nhúng computer vision on-device về sau.
 *
 *  Cấu hình board trong Arduino IDE:
 *   - Board:  "XIAO_ESP32S3"  (gói: esp32 by Espressif >= 3.0)
 *   - PSRAM:  "OPI PSRAM"  (BẮT BUỘC bật, nếu không camera không init được)
 *   - Partition: "Huge APP (3MB No OTA/1MB SPIFFS)" cho thoải mái
 * ============================================================================
 */

#include "esp_camera.h"
#include "camera_pins.h"
#include <WiFi.h>
#include <Preferences.h>
#include "esp_http_server.h"

// ----------------------------------------------------------------------------
// 1) WIFI — mặc định chạy Access Point (không cần router). Nối wifi "AquaScope"
//    rồi mở http://192.168.4.1  . Muốn nối vào router nhà thì đặt USE_STA = true.
// ----------------------------------------------------------------------------
#define USE_STA         false
const char* STA_SSID  = "TEN_WIFI_NHA";
const char* STA_PASS  = "MAT_KHAU_WIFI";
const char* AP_SSID   = "AquaScope";
const char* AP_PASS   = "aquascope";   // >= 8 ký tự

// ----------------------------------------------------------------------------
// 2) CẤU HÌNH — được nạp từ flash lúc boot; chỉnh runtime rồi 'save' để ghi cứng
// ----------------------------------------------------------------------------
struct CamConfig {
  int  exposure;       // AEC value thủ công 0..1200 (thấp = tối). Điểm chỉnh CHÍNH.
  int  gain;           // AGC gain thủ công 0..30. Backlit nên để 0.
  int  brightness;     // -2..2
  int  contrast;       // -2..2   (tăng nhẹ giúp tách bóng hạt khỏi nền)
  int  jpegQuality;    // 4(đẹp)..30(xấu). ~12 là hợp lý.
  int  grayscale;      // 1 = ép ảnh xám (tốt cho silhouette + CV), 0 = màu
  int  hmirror;        // 0/1
  int  vflip;          // 0/1
  int  framesize;      // độ phân giải dùng chung (giá trị enum framesize_t, xem HTML select)
};

// Giá trị mặc định "an toàn" cho backlit silhouette (nền sáng, phơi sáng thấp).
// Giữ const để nút "Khôi phục mặc định" luôn có bản gốc mà quay về.
const CamConfig DEFAULT_CFG = {
  .exposure   = 100,
  .gain       = 0,
  .brightness = 0,
  .contrast   = 1,
  .jpegQuality= 12,
  .grayscale  = 1,
  .hmirror    = 0,
  .vflip      = 1,                       // OV3660 mặc định ảnh lật ngược -> vflip=1 cho đúng chiều
  .framesize  = (int)FRAMESIZE_VGA,      // mặc định VGA; đổi tự do khi test (tới QXGA)
};

// Cấu hình đang chạy (khởi tạo từ mặc định, sẽ bị loadConfig() ghi đè nếu flash có dữ liệu)
CamConfig cfg = DEFAULT_CFG;

Preferences prefs;
httpd_handle_t httpServer   = NULL;   // port 80: điều khiển + chụp
httpd_handle_t streamServer = NULL;   // port 81: chỉ stream (tách riêng để không chặn điều khiển)

// CHẾ ĐỘ NGẮM/LẤY NÉT: khi true, tạm bật AEC/AGC/AWB + ảnh màu để nhìn rõ mà căn
// khung & lấy nét (đặt mẫu đúng ~4cm). KHÔNG lưu vào flash — chỉ là trạng thái
// runtime; boot lại luôn về chế độ backlit thủ công. Đây KHÔNG phải cấu hình chụp.
bool aimingMode = false;

// ----------------------------------------------------------------------------
// 3) LƯU / NẠP cấu hình từ flash (namespace "aquascope")
// ----------------------------------------------------------------------------
void loadConfig() {
  prefs.begin("aquascope", true);            // read-only
  if (prefs.isKey("exposure")) {
    cfg.exposure     = prefs.getInt("exposure",   cfg.exposure);
    cfg.gain         = prefs.getInt("gain",       cfg.gain);
    cfg.brightness   = prefs.getInt("bright",     cfg.brightness);
    cfg.contrast     = prefs.getInt("contrast",   cfg.contrast);
    cfg.jpegQuality  = prefs.getInt("jpegq",      cfg.jpegQuality);
    cfg.grayscale    = prefs.getInt("gray",       cfg.grayscale);
    cfg.hmirror      = prefs.getInt("hmirror",    cfg.hmirror);
    cfg.vflip        = prefs.getInt("vflip",      cfg.vflip);
    cfg.framesize    = prefs.getInt("fsize",      cfg.framesize);
    Serial.println("[cfg] Da nap cau hinh tu flash.");
  } else {
    Serial.println("[cfg] Chua co cau hinh trong flash -> dung mac dinh.");
  }
  prefs.end();
}

void saveConfig() {
  prefs.begin("aquascope", false);           // read-write
  prefs.putInt("exposure", cfg.exposure);
  prefs.putInt("gain",     cfg.gain);
  prefs.putInt("bright",   cfg.brightness);
  prefs.putInt("contrast", cfg.contrast);
  prefs.putInt("jpegq",    cfg.jpegQuality);
  prefs.putInt("gray",     cfg.grayscale);
  prefs.putInt("hmirror",  cfg.hmirror);
  prefs.putInt("vflip",    cfg.vflip);
  prefs.putInt("fsize",    cfg.framesize);
  prefs.end();
  Serial.println("[cfg] DA GHI CUNG cau hinh vao flash.");
}

// Khôi phục về mặc định: nạp lại DEFAULT_CFG, áp lên sensor, và XÓA cấu hình đã
// lưu trong flash -> lần sau reboot cũng chạy mặc định. Dùng khi lỡ chỉnh nhầm.
void resetConfig() {
  cfg = DEFAULT_CFG;
  applyConfig();
  sensor_t* s = esp_camera_sensor_get();
  if (s) s->set_framesize(s, (framesize_t)cfg.framesize);
  prefs.begin("aquascope", false);
  prefs.clear();
  prefs.end();
  Serial.println("[cfg] DA KHOI PHUC mac dinh + xoa cau hinh da luu trong flash.");
}

// ----------------------------------------------------------------------------
// 4) ÁP cấu hình lên sensor. Đây là TRÁI TIM của firmware này:
//    ép phơi sáng thủ công để nền backlit không cháy trắng.
// ----------------------------------------------------------------------------
void applyConfig() {
  sensor_t* s = esp_camera_sensor_get();
  if (!s) return;

  if (aimingMode) {
    // ====== CHẾ ĐỘ NGẮM/LẤY NÉT (tạm thời) ======
    // Bật auto everything + ảnh màu để nhìn rõ mà căn khung và lấy nét (đặt mẫu
    // đúng ~4cm cho sắc nét). Đây KHÔNG phải chế độ chụp phân tích.
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_wb_mode(s, 0);
    s->set_exposure_ctrl(s, 1);          // BẬT AEC
    s->set_aec2(s, 1);                    // BẬT AEC DSP
    s->set_gain_ctrl(s, 1);              // BẬT AGC
    s->set_gainceiling(s, GAINCEILING_16X);
    s->set_special_effect(s, 0);         // màu, dễ nhìn để căn
  } else {
    // ====== CHẾ ĐỘ CHỤP BACKLIT SILHOUETTE (mặc định) ======
    // --- Cân bằng trắng: TẮT để nền không "tự sửa màu" trôi giá trị ---
    s->set_whitebal(s, 0);
    s->set_awb_gain(s, 0);
    s->set_wb_mode(s, 0);

    // --- PHƠI SÁNG THỦ CÔNG (quan trọng nhất) ---
    s->set_exposure_ctrl(s, 0);          // TẮT AEC (auto exposure)
    s->set_aec2(s, 0);                   // TẮT AEC DSP
    s->set_gain_ctrl(s, 0);              // TẮT AGC (auto gain)
    s->set_agc_gain(s, cfg.gain);        // gain thủ công
    s->set_aec_value(s, cfg.exposure);   // exposure thủ công
    s->set_gainceiling(s, GAINCEILING_2X); // trần gain thấp

    // --- Ép ảnh xám cho silhouette / CV (special_effect 2 = grayscale) ---
    s->set_special_effect(s, cfg.grayscale ? 2 : 0);
  }

  // --- Chỉnh nét/độ tương phản để tách bóng hạt (dùng chung cho cả 2 chế độ) ---
  s->set_brightness(s, cfg.brightness);
  s->set_contrast(s, cfg.contrast);
  s->set_bpc(s, 1);
  s->set_wpc(s, 1);
  s->set_raw_gma(s, 1);
  s->set_lenc(s, 1);                     // bù sáng viền ống kính -> nền đều hơn
  s->set_dcw(s, 1);
  s->set_colorbar(s, 0);

  s->set_hmirror(s, cfg.hmirror);
  s->set_vflip(s, cfg.vflip);

  // Sàn an toàn JPEG: ở độ phân giải cao (>= SXGA) mà quality quá "đẹp" (số quá
  // nhỏ) thì encoder ESP32 dễ tràn buffer -> khung xám/hỏng. Ép tối thiểu 10.
  int q = cfg.jpegQuality;
  if (cfg.framesize >= (int)FRAMESIZE_SXGA && q < 10) q = 10;
  s->set_quality(s, q);
}

// ----------------------------------------------------------------------------
// 5) KHỞI TẠO camera. Init ở framesize LỚN NHẤT (QXGA) để buffer đủ chỗ cho mọi
//    lựa chọn độ phân giải, rồi set về framesize đã lưu trong cấu hình.
// ----------------------------------------------------------------------------
bool initCamera() {
  camera_config_t c;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer   = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;   c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM;   c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.frame_size   = FRAMESIZE_QXGA;         // OV3660 3MP: cấp phát buffer cho size lớn nhất (QXGA)
  c.pixel_format = PIXFORMAT_JPEG;
  c.grab_mode    = CAMERA_GRAB_LATEST;
  c.fb_location  = CAMERA_FB_IN_PSRAM;
  c.jpeg_quality = cfg.jpegQuality;
  c.fb_count     = 2;

  if (!psramFound()) {
    Serial.println("[cam] LOI: khong thay PSRAM! Bat 'OPI PSRAM' trong Tools.");
  }

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[cam] esp_camera_init that bai: 0x%x\n", err);
    return false;
  }

  applyConfig();
  sensor_t* s = esp_camera_sensor_get();
  s->set_framesize(s, (framesize_t)cfg.framesize);
  return true;
}

// ----------------------------------------------------------------------------
// 6) HOOK COMPUTER VISION — để trống, nhúng CV on-device về sau tại đây.
//    fb là 1 frame JPEG. Muốn CV on-device: giải nén sang grayscale rồi
//    threshold -> connected components (xem README firmware).
// ----------------------------------------------------------------------------
void runVision(camera_fb_t* fb) {
  // TODO (giai đoạn CV): fmt2rgb888()/jpg2gray -> nguong -> dem blob -> gui ket qua.
  // Hien tai chi log kich thuoc frame de xac nhan pipeline chup hoat dong.
  Serial.printf("[cv] frame %ux%u, %u bytes (chua co CV)\n",
                fb->width, fb->height, (unsigned)fb->len);
}

// ============================================================================
//  WEB SERVER
// ============================================================================
static const char* STREAM_CONTENT_TYPE =
  "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
static const char* STREAM_BOUNDARY = "\r\n--123456789000000000000987654321\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// --- Stream MJPEG (chế độ preview) ---
static esp_err_t stream_handler(httpd_req_t* req) {
  camera_fb_t* fb = NULL;
  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  char part[64];
  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) { res = ESP_FAIL; break; }
    size_t hlen = snprintf(part, 64, STREAM_PART, (unsigned)fb->len);
    res  = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, part, hlen);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    if (res != ESP_OK) break;
  }
  return res;
}

// --- Chụp 1 ảnh ở độ phân giải hiện tại rồi trả JPEG; cũng gọi runVision ---
static esp_err_t capture_handler(httpd_req_t* req) {
  camera_fb_t* fb = esp_camera_fb_get();
  esp_err_t res = ESP_OK;
  if (!fb) {
    httpd_resp_send_500(req);
    res = ESP_FAIL;
  } else {
    runVision(fb);                             // hook CV on-device (hien chi log)
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=aqua.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    res = httpd_resp_send(req, (const char*)fb->buf, fb->len);
    esp_camera_fb_return(fb);
  }
  return res;
}

// --- /control?var=exposure&val=100  -> chỉnh runtime (chưa ghi cứng) ---
static esp_err_t control_handler(httpd_req_t* req) {
  char buf[128];
  if (httpd_req_get_url_query_str(req, buf, sizeof(buf)) != ESP_OK) {
    httpd_resp_send_404(req); return ESP_FAIL;
  }
  char var[32] = {0}, val[32] = {0};
  httpd_query_key_value(buf, "var", var, sizeof(var));
  httpd_query_key_value(buf, "val", val, sizeof(val));
  int v = atoi(val);

  if      (!strcmp(var, "exposure"))   cfg.exposure   = v;
  else if (!strcmp(var, "gain"))       cfg.gain       = v;
  else if (!strcmp(var, "brightness")) cfg.brightness = v;
  else if (!strcmp(var, "contrast"))   cfg.contrast   = v;
  else if (!strcmp(var, "jpegq"))      cfg.jpegQuality= v;
  else if (!strcmp(var, "grayscale"))  cfg.grayscale  = v;
  else if (!strcmp(var, "hmirror"))    cfg.hmirror    = v;
  else if (!strcmp(var, "vflip"))      cfg.vflip      = v;
  else if (!strcmp(var, "framesize"))  { cfg.framesize = v;
             esp_camera_sensor_get()->set_framesize(esp_camera_sensor_get(), (framesize_t)v); }
  else if (!strcmp(var, "aim"))        { aimingMode = (v != 0); }   // bật/tắt chế độ ngắm
  else if (!strcmp(var, "save"))       { saveConfig(); }
  else if (!strcmp(var, "reset"))      { resetConfig(); }

  applyConfig();
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_send(req, "OK", 2);
  return ESP_OK;
}

// --- /status -> JSON cấu hình hiện tại ---
static esp_err_t status_handler(httpd_req_t* req) {
  char json[320];
  snprintf(json, sizeof(json),
    "{\"exposure\":%d,\"gain\":%d,\"brightness\":%d,\"contrast\":%d,"
    "\"jpegq\":%d,\"grayscale\":%d,\"hmirror\":%d,\"vflip\":%d,"
    "\"framesize\":%d,\"aim\":%d}",
    cfg.exposure, cfg.gain, cfg.brightness, cfg.contrast, cfg.jpegQuality,
    cfg.grayscale, cfg.hmirror, cfg.vflip, cfg.framesize, aimingMode ? 1 : 0);
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_send(req, json, strlen(json));
  return ESP_OK;
}

// --- Trang web điều khiển ---
static const char INDEX_HTML[] PROGMEM = R"HTML(
<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aqua Scope Cam</title><style>
body{font-family:sans-serif;background:#111;color:#eee;margin:0;padding:12px}
h2{margin:.2em 0}img{width:100%;max-width:640px;border:1px solid #444;background:#000}
.row{display:flex;align-items:center;gap:8px;margin:6px 0;max-width:640px}
.row label{width:110px}.row input[type=range]{flex:1}.row span{width:52px;text-align:right}
button{padding:8px 14px;margin:4px 2px;background:#0a7;color:#fff;border:0;border-radius:6px}
button.save{background:#c50}button.reset{background:#666}button.aim{background:#26c}small{color:#999}
#hint{color:#fc6;font-weight:bold;display:none;margin:4px 0}
</style></head><body>
<h2>Aqua Scope — Camera</h2>
<small>Backlit silhouette. Chỉnh Exposure/Gain tới khi nền xám đều, hạt = bóng đen rõ. Xong bấm LƯU CỨNG.<br>
Chưa thấy gì / ảnh tối mờ? Bấm <b>NGẮM/LẤY NÉT</b> để bật auto tạm thời, đặt mẫu đúng ~4cm cho nét, rồi tắt lại.</small>
<div id="hint">⚠ ĐANG Ở CHẾ ĐỘ NGẮM (auto) — chỉ để căn khung/lấy nét, KHÔNG dùng để chụp phân tích. Tắt trước khi đo.</div>
<div><img id="s"></div>
<div class="row"><label>Độ phân giải</label>
  <select id="framesize" style="flex:1;padding:6px">
    <option value="5">QVGA 320x240</option>
    <option value="8">VGA 640x480</option>
    <option value="9">SVGA 800x600</option>
    <option value="10">XGA 1024x768</option>
    <option value="12">SXGA 1280x1024</option>
    <option value="13">UXGA 1600x1200</option>
    <option value="17">QXGA 2048x1536</option>
  </select></div>
<div class="row"><label>Exposure</label><input id="exposure" type="range" min="0" max="1200"><span id="exposure_v"></span></div>
<div class="row"><label>Gain</label><input id="gain" type="range" min="0" max="30"><span id="gain_v"></span></div>
<div class="row"><label>Brightness</label><input id="brightness" type="range" min="-2" max="2"><span id="brightness_v"></span></div>
<div class="row"><label>Contrast</label><input id="contrast" type="range" min="-2" max="2"><span id="contrast_v"></span></div>
<div class="row"><label>JPEG q</label><input id="jpegq" type="range" min="4" max="30"><span id="jpegq_v"></span></div>
<div class="row"><label>Grayscale</label><input id="grayscale" type="range" min="0" max="1"><span id="grayscale_v"></span></div>
<div>
  <button class="aim" id="aimBtn" onclick="toggleAim()">NGẮM/LẤY NÉT (auto)</button>
  <button onclick="cap()">Chụp 1 ảnh (độ phân giải hiện tại)</button>
  <button class="save" onclick="ctl('save',1)">LƯU CỨNG vào flash</button>
  <button class="reset" onclick="reset()">Khôi phục mặc định</button>
</div>
<div><img id="cap" style="margin-top:8px"></div>
<script>
const ids=['exposure','gain','brightness','contrast','jpegq','grayscale'];
const fs=document.getElementById('framesize');
let aim=0;
function ctl(v,val){fetch('/control?var='+v+'&val='+val);}
// cập nhật nhãn nút + banner cảnh báo theo trạng thái ngắm
function setAimUI(){document.getElementById('aimBtn').innerText=
  aim?'ĐANG NGẮM — bấm để về chế độ CHỤP':'NGẮM/LẤY NÉT (auto)';
  document.getElementById('hint').style.display=aim?'block':'none';}
function toggleAim(){aim=aim?0:1;ctl('aim',aim);setAimUI();}
// stream chạy ở port 81 (server riêng); dựng URL theo host hiện tại
function streamUrl(){return location.protocol+'//'+location.hostname+':81/stream?t='+Date.now();}
// đọc cấu hình hiện tại từ thiết bị, đổ vào slider/select + nạp lại stream
function loadStatus(){fetch('/status').then(r=>r.json()).then(c=>{
  ids.forEach(id=>{const e=document.getElementById(id);e.value=c[id];
    document.getElementById(id+'_v').innerText=c[id];});
  fs.value=c.framesize;
  aim=c.aim||0;setAimUI();
  document.getElementById('s').src=streamUrl();});}
// khôi phục mặc định (có xác nhận) rồi làm mới lại giao diện
function reset(){if(confirm('Khôi phục cấu hình mặc định? Cấu hình đã lưu sẽ bị xóa.'))
  fetch('/control?var=reset&val=1').then(()=>loadStatus());}
// đổi độ phân giải: gọi control rồi nạp lại stream cho khớp kích thước
fs.onchange=()=>{fetch('/control?var=framesize&val='+fs.value).then(()=>{
  document.getElementById('s').src=streamUrl();});};
function cap(){document.getElementById('cap').src='/capture?t='+Date.now();}
ids.forEach(id=>{const e=document.getElementById(id);e.oninput=()=>{
  document.getElementById(id+'_v').innerText=e.value;ctl(id,e.value);};});
loadStatus();
</script></body></html>
)HTML";

static esp_err_t index_handler(httpd_req_t* req) {
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, INDEX_HTML, strlen(INDEX_HTML));
}

void startServer() {
  // --- Server điều khiển (port 80): index, capture, control, status ---
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;
  config.ctrl_port   = 32768;
  config.max_uri_handlers = 8;

  httpd_uri_t idx = { "/",        HTTP_GET, index_handler,   NULL };
  httpd_uri_t cap = { "/capture", HTTP_GET, capture_handler, NULL };
  httpd_uri_t ctl = { "/control", HTTP_GET, control_handler, NULL };
  httpd_uri_t st  = { "/status",  HTTP_GET, status_handler,  NULL };

  if (httpd_start(&httpServer, &config) == ESP_OK) {
    httpd_register_uri_handler(httpServer, &idx);
    httpd_register_uri_handler(httpServer, &cap);
    httpd_register_uri_handler(httpServer, &ctl);
    httpd_register_uri_handler(httpServer, &st);
    Serial.println("[web] HTTP control server (port 80) da chay.");
  }

  // --- Server stream (port 81): chạy riêng để vòng lặp stream KHÔNG chặn điều khiển ---
  httpd_config_t sconfig = HTTPD_DEFAULT_CONFIG();
  sconfig.server_port = 81;
  sconfig.ctrl_port   = 32769;           // phải khác ctrl_port của server trên
  httpd_uri_t strm = { "/stream", HTTP_GET, stream_handler, NULL };

  if (httpd_start(&streamServer, &sconfig) == ESP_OK) {
    httpd_register_uri_handler(streamServer, &strm);
    Serial.println("[web] HTTP stream server (port 81) da chay.");
  }
}

// ============================================================================
//  ĐIỀU KHIỂN QUA SERIAL: t=exposure g=gain b=bright c=contrast q=jpegq y=gray
//                         f=framesize(5..17)  a=aiming(0/1)  s=save  r=reset
//                         p=print  x=capture
// ============================================================================
void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;
  char cmd = line.charAt(0);
  int  val = line.substring(1).toInt();
  switch (cmd) {
    case 't': cfg.exposure   = val; applyConfig(); Serial.printf("exposure=%d\n", val); break;
    case 'g': cfg.gain       = val; applyConfig(); Serial.printf("gain=%d\n", val); break;
    case 'b': cfg.brightness = val; applyConfig(); Serial.printf("bright=%d\n", val); break;
    case 'c': cfg.contrast   = val; applyConfig(); Serial.printf("contrast=%d\n", val); break;
    case 'q': cfg.jpegQuality = val; applyConfig(); Serial.printf("jpegq=%d\n", val); break;
    case 'y': cfg.grayscale  = val; applyConfig(); Serial.printf("gray=%d\n", val); break;
    case 'f': cfg.framesize  = val;
              esp_camera_sensor_get()->set_framesize(esp_camera_sensor_get(), (framesize_t)val);
              Serial.printf("framesize=%d\n", val); break;
    case 'a': aimingMode = (val != 0); applyConfig();
              Serial.printf("aiming=%d (%s)\n", aimingMode,
                aimingMode ? "AUTO - de ngam/lay net" : "MANUAL - backlit chup"); break;
    case 's': saveConfig(); break;
    case 'r': resetConfig(); break;
    case 'p': Serial.printf("exp=%d gain=%d bright=%d contrast=%d jpegq=%d gray=%d fsize=%d\n",
                cfg.exposure, cfg.gain, cfg.brightness, cfg.contrast, cfg.jpegQuality, cfg.grayscale, cfg.framesize); break;
    case 'x': {  // chụp 1 frame ở độ phân giải hiện tại -> chạy runVision (không gửi ảnh qua UART)
      camera_fb_t* fb = esp_camera_fb_get();
      if (fb) { runVision(fb); esp_camera_fb_return(fb); }
      break;
    }
    default: Serial.println("Lenh: t g b c q y f (val), a=aiming, s=save, r=reset, p=print, x=capture"); break;
  }
}

// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== Aqua Scope Cam firmware ===");

  loadConfig();
  if (!initCamera()) {
    Serial.println("[cam] KHOI TAO THAT BAI. Kiem tra PSRAM & cap cam. Treo tai day.");
    while (true) delay(1000);
  }

  if (USE_STA) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(STA_SSID, STA_PASS);
    Serial.print("[wifi] Noi wifi");
    for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) { delay(500); Serial.print("."); }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED)
      Serial.printf("[wifi] IP: http://%s\n", WiFi.localIP().toString().c_str());
    else Serial.println("[wifi] Noi that bai.");
  } else {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("[wifi] AP '%s' | mo: http://%s\n", AP_SSID, WiFi.softAPIP().toString().c_str());
  }

  startServer();
  Serial.println("San sang. Lenh serial: t<exp> g<gain> ... s=save r=reset p=print x=capture");
}

void loop() {
  handleSerial();
  delay(5);
}
