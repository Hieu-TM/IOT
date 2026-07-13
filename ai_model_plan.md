# Kế hoạch tạo & train model AI (classifier phân loại hạt) — Aqua Scope

> **Phạm vi tài liệu này:** chỉ bàn phần **AI classifier** trong pipeline hybrid.
> Classical CV (ngưỡng hóa → connected components → tâm + diện tích → **đếm & phân bố kích thước**)
> KHÔNG cần AI, không train — giữ nguyên. Model AI ở đây **chỉ nhận crop nhỏ của từng blob
> mà CV đã tìm ra, và trả về nhãn loại hạt**. Đây là việc CV không làm được.
>
> Liên quan: `CLAUDE.md` §"Image processing / inference", memory `image-processing-hybrid`,
> `camera-focus-limit`, `application-context`.

---

## Phase 0 — Tiền đề bắt buộc (ĐỌC TRƯỚC KHI LÀM BẤT CỨ GÌ)

Model AI học từ ảnh. **Ảnh mờ → model rác, không cứu được bằng train.** Trước khi tốn công thu dữ liệu:

1. **Phải giải quyết xong lỗi lấy nét lens** (memory `camera-focus-limit`): unit OV3660 hiện KHÔNG nét ở 3–5cm. Chọn 1 trong 3 hướng (macro clip-on / đổi khoảng cách ~1–2cm / thay module AF) và **xác nhận chụp được ảnh nét ở khoảng cách làm việc** trước khi thu dataset. Nếu bỏ qua bước này, mọi Phase sau đều vô nghĩa.
2. **Classical CV phải chạy được và xuất được crop** từng blob (bounding box quanh mỗi hạt). Chính output crop này là input của model. Nếu CV chưa xong, làm CV trước.
3. **Khóa cứng thông số chụp phân tích**: manual exposure (AEC/AEC-DSP/AGC = OFF, Gain=0, Exposure thấp), độ phân giải cao (SXGA/UXGA khi phân tích), backlit đều không hotspot. Dataset phải chụp **đúng cấu hình sẽ dùng khi chạy thật** — nếu train ở điều kiện A mà deploy ở điều kiện B, độ chính xác sập.

> Nguyên tắc vàng: **dữ liệu train phải sinh ra từ chính cái trạm này, chính cấu hình ánh sáng/exposure này.** Không lấy ảnh nhựa trên Google về train.

---

## Phase 1 — Định nghĩa bài toán (chốt trước khi thu dữ liệu)

### 1.1 Chốt danh sách lớp (class list)
Hiện **chưa chốt** (`image-processing-hybrid`). Đề xuất khởi điểm 4 lớp — điều chỉnh sau khi nhìn dữ liệu thật:

| Nhãn | Đặc điểm silhouette (ảnh nền sáng) | Ghi chú |
|---|---|---|
| `plastic` | Khối đặc, cạnh sắc, mờ đục đều | Mục tiêu chính cần đếm |
| `bubble` | **Tâm sáng + viền tối** (ánh sáng xuyên qua bọt khúc xạ) — đặc trưng phân biệt mạnh nhất | Nhiễu cần loại |
| `organic` | Cạnh lởm chởm/không đều, độ đặc trung bình | Rác hữu cơ |
| `fiber` | Tỉ lệ dài/rộng rất cao (thuôn dài) | CV shape gần như tự tách được |

> **Mẹo quan trọng:** với ảnh silhouette, `fiber` (rất thuôn) và `bubble` (tâm sáng) có thể phân biệt **chỉ bằng đặc trưng hình học**, không cần CNN. Xem Phase 3-Track A.

Thêm 1 lớp kỹ thuật nếu cần: `unknown/noise` (dính chùm, cắt lẹm, bẩn) để model có chỗ "chối".

### 1.2 Chốt đặc tả input của model
- **Định dạng:** crop **grayscale** (ảnh nền là silhouette đen-trắng, màu gần như vô nghĩa — trừ khi sau này thêm Nile-Red).
- **Kích thước:** **32×32** hoặc 48×48 px (chuẩn hóa mọi blob về cùng size). Ở VGA ~14px/mm, hạt 2mm ≈ 28px → 32×32 vừa đẹp. Blob nhỏ hơn thì pad, lớn hơn thì resize.
- **Chuẩn hóa:** giữ tỉ lệ khung (pad để không méo hình — méo làm hỏng đặc trưng hình dạng), canh giữa blob, nền = giá trị nền sáng đồng nhất.

### 1.3 Chốt tiêu chí thành công (đo được)
- Ví dụ: **accuracy ≥ 85%** trên tập test giữ riêng; **`bubble` recall ≥ 90%** (không nhầm bọt thành nhựa làm tăng đếm giả).
- Thời gian suy luận trên XIAO S3 **≤ 30ms/hạt** (để 20–30 hạt/khung vẫn kịp).
- RAM model + tensor arena **≤ ~200KB** (thừa sức với PSRAM 8MB, nhưng giữ nhỏ cho nhanh).

---

## Phase 2 — Chọn hướng tiếp cận & công cụ

**Chiến lược khuyến nghị: đi từ đơn giản lên phức tạp.** Đừng nhảy thẳng vào CNN.

### Track A — Đặc trưng thủ công + classifier nhỏ (LÀM TRƯỚC)
Trích 6–10 đặc trưng hình học/độ sáng từ mỗi blob, rồi đưa vào 1 classifier bé xíu (MLP 2 lớp / logistic regression / decision tree).
- **Đặc trưng gợi ý:** diện tích, chu vi, **circularity** (4πA/P²), **aspect ratio** (dài/rộng), **solidity** (A/A_convexhull), độ đặc trung bình (mean intensity), độ lệch chuẩn intensity, **tỉ lệ pixel sáng ở tâm** (bắt bọt khí), độ sắc cạnh (gradient trung bình ở biên).
- **Ưu:** cực rẻ trên MCU (vài phép nhân), giải thích được, train bằng vài trăm mẫu, dễ debug. Với silhouette, **nhiều khả năng đủ để tách fiber/bubble**, chỉ khó ở plastic-vs-organic.
- Đây là baseline để đo: nếu Track A đã đạt tiêu chí Phase 1.3 → **dừng, không cần CNN.**

### Track B — Tiny CNN trên crop (nếu Track A không đủ)
CNN nhỏ nhận trực tiếp crop 32×32×1. Học được texture/hình dạng tinh vi mà đặc trưng thủ công bỏ sót (plastic vs organic).
- **Ưu:** mạnh hơn, đúng tinh thần "TinyML dùng lệnh vector AI của S3".
- **Nhược:** cần nhiều dữ liệu hơn (vài trăm–nghìn/lớp), nặng hơn, khó debug hơn.

### Công cụ train — vai trò của Roboflow vs Edge Impulse vs thủ công

Hai công cụ **không thay thế nhau, chúng giải quyết hai khâu khác nhau**:

- **Roboflow** = mạnh về **quản lý & gán nhãn dữ liệu ảnh** (upload, vẽ nhãn, auto-label bằng model có sẵn, augmentation, versioning dataset). Xuất được model classification cơ bản (TFLite) nhưng **không chuyên sâu cho MCU** — không có bước tối ưu riêng cho ESP32-S3 (không EON compiler, không ước tính RAM/latency trước khi nạp máy).
- **Edge Impulse** = mạnh về **toàn bộ pipeline nhắm tới thiết bị nhúng**: từ thu thập (có thể lấy trực tiếp qua điện thoại/webcam hoặc upload), trích đặc trưng ảnh (DSP block), train NN ngay trên trình duyệt, **EON Tuner** (tự dò kiến trúc nhỏ nhất đạt độ chính xác mục tiêu), quantize int8 tự động, và **xuất thẳng thư viện Arduino/ESP-IDF cho ESP32-S3** kèm số đo RAM/flash/latency ước tính *trước khi* nạp — rất hợp với ràng buộc Phase 1.3 (≤30ms, ≤200KB).
- **Thủ công (Python/OpenCV/Keras/TFLite-Micro)** = kiểm soát 100%, không phụ thuộc dịch vụ ngoài, nhưng **tự làm hết** mọi bước ở Phase 3–9 (script crop, augment, kiến trúc, quantize, tích hợp TFLM tay).

**Quy trình kết hợp khuyến nghị (tận dụng cả hai, đỡ tốn công nhất):**

1. **Roboflow** — nơi thu & gán nhãn: upload ảnh full-frame (chưa crop) đã chụp theo Phase 3.1–3.2, **vẽ bounding box quanh từng hạt kèm nhãn lớp ngay trên ảnh gốc** (nhanh hơn tự viết script crop, và Roboflow hỗ trợ **auto-label bằng model tạm** để tăng tốc các mẻ sau). Dùng tính năng **"Generate" → augmentation** (xoay/lật/sáng-tối, đúng tập augment "hợp lệ vật lý" ở Phase 5) để nhân dữ liệu ngay trong UI.
2. Roboflow có tính năng **chuyển dataset Object Detection → Classification dataset** (tự động crop theo bounding box đã vẽ, xuất thành thư mục `class_name/*.jpg`) — **thay thế hoàn toàn script `extract_crops.py` thủ công ở Phase 3.3** nếu muốn tiết kiệm thời gian viết code. (Vẫn nên kiểm tra logic crop khớp với threshold/CV thật trên firmware — xem lưu ý train↔deploy ở Phase 10.)
3. Xuất dataset đã gán nhãn/augment từ Roboflow (định dạng thư mục ảnh theo lớp, hoặc zip) → **import vào Edge Impulse** (Edge Impulse có sẵn khối "Upload data" nhận đúng cấu trúc này, và tích hợp trực tiếp với Roboflow Universe để kéo dataset về).
4. Trong Edge Impulse: tạo Impulse (Image block: resize 32×32 grayscale) → Learning block (Classification NN, hoặc EON Tuner để tự tìm kiến trúc nhỏ nhất đạt target accuracy) → train, xem confusion matrix ngay trong UI (thay Phase 7) → Quantize int8 (1 click, thay Phase 8) → Deployment: **Arduino library cho ESP32-S3** (thay Phase 9).

> **Track A (đặc trưng thủ công) thì Roboflow/Edge Impulse gần như không giúp được gì** — cả hai đều xoay quanh ảnh/CNN, không có chỗ nhập đặc trưng số (area, circularity…) để train MLP nhỏ. Track A **bắt buộc làm thủ công** bằng scikit-learn/Python. Roboflow + Edge Impulse chỉ phát huy giá trị ở **Track B (CNN trên ảnh crop)**.

| | Edge Impulse | Roboflow | Thủ công (Python/Keras/TFLM) |
|---|---|---|---|
| Gán nhãn ảnh | Có, cơ bản | **Mạnh nhất** (vẽ box nhanh, auto-label, đa dạng định dạng) | Tự viết/tự xem tay |
| Sinh crop từ ảnh full | Không tự động | **Có** (Object Detection → Classification, auto-crop theo box) | Tự viết `extract_crops.py` |
| Augmentation | Có (cơ bản) | **Có, mạnh, xem trước trực quan** | Tự viết (`imgaug`/Keras `RandomFlip`…) |
| Track A (đặc trưng thủ công) | Không hỗ trợ | Không hỗ trợ | **Chỉ có cách này** |
| Train CNN (Track B) | Có, kéo-thả + EON Tuner (tự tối ưu kiến trúc theo RAM/latency) | Có nhưng ít tối ưu cho MCU | Tự thiết kế, tự thử nghiệm |
| Quantize int8 | 1 click, có ước tính RAM/flash trước khi xuất | Có, ít tùy chỉnh | Tự viết representative dataset |
| Xuất cho ESP32-S3 | **Arduino library sinh sẵn, EON compiler + ESP-NN tối ưu vector S3** | Xuất TFLite chung chung, tự tích hợp TFLM | `xxd` → mảng C, tự đăng ký `MicroMutableOpResolver` |
| Ước tính hiệu năng trước khi nạp máy | **Có** (RAM/flash/latency ngay trong UI) | Không | Phải đo tay sau khi nạp |
| Offline / không phụ thuộc cloud | Không (cloud, có bản trial local) | Không (cloud) | **Có, hoàn toàn local** |
| Dữ liệu riêng tư | Upload lên cloud bên thứ 3 | Upload lên cloud bên thứ 3 | Không rời máy |
| Đường cong học | Thấp (UI kéo-thả) | Thấp (UI kéo-thả) | Cao (cần code Python + TFLM) |
| Tốc độ ra kết quả đầu tiên | **Nhanh nhất** | Nhanh (riêng khâu data) | Chậm nhất |
| Chi phí | Free tier đủ dùng đồ án nhỏ | Free tier giới hạn số ảnh/tháng, workspace public | Miễn phí (chỉ tốn máy tính cá nhân) |

> **Đề xuất cho đồ án:** Roboflow (gán nhãn + crop + augment) → Edge Impulse (train + quantize + xuất ESP32) cho **Track B**; giữ **thủ công/scikit-learn** cho **Track A** (nên thử Track A trước vì rẻ và có thể đã đủ — xem Phase 2 ở trên). Viết sẵn script thủ công (Phase 3.3, 6, 8, 9) như **phương án dự phòng/đối chiếu** — hữu ích khi báo cáo đồ án cần giải thích được "bên trong" model, hoặc khi cần chạy lại offline không phụ thuộc tài khoản cloud.

---

## Phase 3 — Thu thập dữ liệu (khâu khó & quyết định nhất)

**80% thành bại nằm ở đây, không phải ở kiến trúc model.**

### 3.1 Chiến thuật "mẫu đã biết nhãn" (self-labeling)
Thay vì đoán nhãn ảnh, **tự bỏ vật đã biết vào nước rồi chụp** → nhãn có sẵn, khỏi đoán:
1. Chuẩn bị mẫu vật riêng từng loại: vụn nhựa <2mm (cắt từ túi PE/nắp chai PP…), tạo bọt khí (khuấy/ống hút), rác hữu cơ (vụn lá/thức ăn), sợi (chỉ vải/cước cắt ngắn).
2. Chạy trạm theo đúng chu kỳ Stop-Flow, thả **từng loại một** vào tray, chụp nhiều khung.
3. Mọi blob trong mẻ "chỉ có nhựa" → nhãn `plastic`. Tự động hóa gán nhãn.

### 3.2 Kịch bản chụp để dataset đa dạng (chống overfit)
Chụp mỗi lớp ở nhiều điều kiện **trong phạm vi vận hành thật**:
- Nhiều vị trí trong khung (góc, tâm, sát biên).
- Nhiều mức exposure quanh giá trị chuẩn (±1–2 nấc) để model chịu được dao động sáng.
- Hạt to/nhỏ khác nhau, xoay nhiều hướng.
- Vài mẻ có nước hơi bẩn/vẩn để giống thực tế QC nước đầu vào (`application-context`).

### 3.3 Trích crop bằng chính logic CV (khớp train↔deploy)
Viết 1 script Python (OpenCV) **mô phỏng đúng CV on-device** để cắt crop từ ảnh full:

```python
# extract_crops.py — chạy trên PC, cùng logic ngưỡng/label như firmware
import cv2, glob, os, numpy as np

OUT = 32  # kích thước crop chuẩn hóa
def extract(img_path, label, out_dir):
    g = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    # NGƯỠNG: hạt tối trên nền sáng → dùng ngưỡng nghịch (điều chỉnh/Otsu)
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lbl, stats, cent = cv2.connectedComponentsWithStats(bw, 8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 15:  # bỏ nhiễu quá nhỏ (chỉnh theo px/mm)
            continue
        pad = 4
        x0, y0 = max(0, x-pad), max(0, y-pad)
        x1, y1 = min(g.shape[1], x+w+pad), min(g.shape[0], y+h+pad)
        crop = g[y0:y1, x0:x1]
        # pad về vuông rồi resize (GIỮ tỉ lệ, không méo)
        s = max(crop.shape)
        sq = np.full((s, s), int(np.median(g)), np.uint8)  # nền = median
        yo, xo = (s-crop.shape[0])//2, (s-crop.shape[1])//2
        sq[yo:yo+crop.shape[0], xo:xo+crop.shape[1]] = crop
        out = cv2.resize(sq, (OUT, OUT), interpolation=cv2.INTER_AREA)
        os.makedirs(f"{out_dir}/{label}", exist_ok=True)
        cv2.imwrite(f"{out_dir}/{label}/{os.path.basename(img_path)}_{i}.png", out)
```
> Cấu trúc thư mục ra: `dataset/plastic/*.png`, `dataset/bubble/*.png`, … — đúng định dạng Edge Impulse/Keras `image_dataset_from_directory` ăn thẳng.

### 3.4 Số lượng mục tiêu
- **Track A (đặc trưng):** ~150–300 crop/lớp là chạy được.
- **Track B (CNN):** tối thiểu **~300–500 crop thật/lớp** *trước* augmentation; càng nhiều càng tốt.
- **Cân bằng lớp:** số mẫu các lớp xấp xỉ nhau; nếu lệch, oversample hoặc phạt class-weight.
- **Tách tập ngay từ đầu:** ~70% train / 15% val / 15% test. **Test giữ riêng, không đụng tới cho đến khi báo cáo cuối** (nếu không sẽ tự lừa mình).

---

## Phase 4 — Gán nhãn & làm sạch
- Nhờ 3.1, phần lớn nhãn có sẵn theo mẻ. Vẫn phải **duyệt tay loại crop rác**: blob dính chùm 2 hạt, hạt bị cắt lẹm ở mép khung, vệt bẩn cố định trên kính.
- Công cụ: xem nhanh bằng thư mục ảnh, hoặc UI của Edge Impulse.
- Ghi lại **quy ước biên giới** giữa các lớp (bao giờ tính là fiber vs organic?) để nhãn nhất quán — đây cũng chính là dữ liệu truy xuất nguồn gốc cho yêu cầu traceability (`application-context`).

---

## Phase 5 — Tiền xử lý & tăng cường dữ liệu (augmentation)
Augmentation "hợp lệ vật lý" cho ảnh hạt — chỉ biến đổi mà thực tế có thể xảy ra:
- **Xoay 0–360°, lật ngang/dọc** (hạt trôi mọi hướng → hợp lệ, nhân dữ liệu mạnh).
- **Dịch nhẹ, zoom nhẹ ±10%**.
- **Đổi độ sáng/tương phản nhẹ** (mô phỏng dao động backlit/exposure).
- **Thêm nhiễu Gaussian nhẹ**.
- **KHÔNG** dùng: méo phối cảnh mạnh, đổi màu (ảnh xám), cắt ngẫu nhiên làm mất hình dạng — sẽ dạy model sai.
- Chuẩn hóa pixel về `[0,1]` hoặc `[-1,1]` (Track B); với int8 sau này, giữ nhất quán với bước quantize.

---

## Phase 6 — Thiết kế & huấn luyện model

### Track A — classifier đặc trưng (Python/scikit-learn hoặc MLP nhỏ)
```python
# Trích đặc trưng cho từng crop rồi train — cực nhẹ cho MCU
# features: [area, perimeter, circularity, aspect_ratio, solidity,
#            mean_int, std_int, center_bright_ratio, edge_grad]
from sklearn.neural_network import MLPClassifier   # hoặc LogisticRegression / DecisionTree
clf = MLPClassifier(hidden_layer_sizes=(16, 8), max_iter=500)
clf.fit(X_train, y_train)   # X: ma trận đặc trưng đã chuẩn hóa
# Trên MCU: tự cài lại forward-pass (vài phép nhân) HOẶC xuất qua TFLite nếu là MLP.
```
> Track A thường **không cần TFLite Micro** — có thể hardcode forward-pass MLP nhỏ ngay trong firmware C. Nhẹ nhất, nhanh nhất.

### Track B — Tiny CNN (Keras)
```python
import tensorflow as tf
from tensorflow.keras import layers, models

NUM_CLASSES = 4
model = models.Sequential([
    layers.Input((32, 32, 1)),
    layers.Conv2D(8, 3, activation='relu', padding='same'),
    layers.MaxPooling2D(),                       # 16x16
    layers.Conv2D(16, 3, activation='relu', padding='same'),
    layers.MaxPooling2D(),                       # 8x8
    layers.Conv2D(32, 3, activation='relu', padding='same'),
    layers.GlobalAveragePooling2D(),
    layers.Dropout(0.3),
    layers.Dense(NUM_CLASSES, activation='softmax'),
])
model.compile(optimizer='adam',
              loss='sparse_categorical_crossentropy', metrics=['accuracy'])
model.fit(train_ds, validation_data=val_ds, epochs=40,
          callbacks=[tf.keras.callbacks.EarlyStopping(patience=6,
                     restore_best_weights=True)])
```
- Model này chỉ vài chục nghìn tham số → int8 vài chục KB, chạy vài ms trên S3.
- Nếu overfit (val acc << train acc): thêm dropout, tăng augmentation, thu thêm dữ liệu thật (ưu tiên hơn là chỉnh kiến trúc).
- Nếu underfit: tăng filter (8→16→32) từ từ.

---

## Phase 7 — Đánh giá (trên tập TEST giữ riêng)
- **Confusion matrix** — quan trọng hơn accuracy đơn lẻ. Xem cặp nào hay nhầm (dự đoán: plastic↔organic sẽ khó nhất; bubble nên tách sạch nhờ tâm sáng).
- Kiểm `bubble recall` (đừng để bọt bị đếm thành nhựa) theo tiêu chí Phase 1.3.
- **Nhìn tận mắt** các crop bị dự đoán sai → thường lộ vấn đề dữ liệu (crop dính chùm, nhãn sai, mờ nét) hơn là vấn đề model.
- Nếu chưa đạt: quay lại **Phase 3 thu thêm dữ liệu** (đòn bẩy lớn nhất), rồi mới tính đổi kiến trúc.

---

## Phase 8 — Lượng tử hóa int8 (bắt buộc cho ESP32)
ESP32-S3 chạy nhanh nhất với **int8 full-integer quantization**. Cần **representative dataset** (vài trăm ảnh train thật) để hiệu chỉnh thang đo:

```python
def rep_data():
    for img in representative_images[:300]:      # ảnh train thật, đã chuẩn hóa
        yield [img.reshape(1, 32, 32, 1).astype('float32')]

conv = tf.lite.TFLiteConverter.from_keras_model(model)
conv.optimizations = [tf.lite.Optimize.DEFAULT]
conv.representative_dataset = rep_data
conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
conv.inference_input_type = tf.int8
conv.inference_output_type = tf.int8
open('model_int8.tflite', 'wb').write(conv.convert())
```
- **So sánh accuracy trước/sau int8** trên tập test — thường tụt <1–2%. Nếu tụt nhiều → representative dataset chưa đại diện.
- (Edge Impulse tự làm bước này khi chọn "Quantized (int8)".)

---

## Phase 9 — Đưa lên ESP32-S3

**Đường Roboflow → Edge Impulse (khuyến nghị, nhanh nhất):**
1. Dataset đã gán nhãn/crop/augment ở Roboflow (Phase 2 mục "Quy trình kết hợp") → import vào Edge Impulse project.
2. Deployment → chọn **Arduino library** (hoặc ESP-IDF). EON compiler + ESP-NN tối ưu sẵn cho S3.
3. Tải `.zip`, add vào Arduino IDE, include header sinh sẵn.
4. Gọi `run_classifier()` với buffer ảnh crop.

**Đường TFLite-Micro thủ công:**
```bash
xxd -i model_int8.tflite > model_data.cc   # nhúng thành mảng C
```
- Dùng thư viện `tflite-micro` (Arduino) hoặc **ESP-DL/ESP-NN** (ESP-IDF, tối ưu vector S3).
- Cấp `tensor_arena` (ví dụ 100–200KB) **trong PSRAM** (`ps_malloc`), đăng ký `MicroMutableOpResolver` đúng các op đã dùng (Conv2D, MaxPool, FullyConnected, Softmax, Reshape).

---

## Phase 10 — Tích hợp với pipeline CV trên thiết bị
Vòng chạy thật trên XIAO S3 (khớp chu kỳ Stop-Flow trong `CLAUDE.md`):
```
Chụp ảnh SXGA/UXGA (backlit, manual exposure)
  └─ Classical CV: threshold → connectedComponents → mỗi blob: centroid + area
       ├─ [ĐẾM + PHÂN BỐ KÍCH THƯỚC]  ← không cần AI, xuất log truy xuất
       └─ với MỖI blob:
            crop → chuẩn hóa 32×32 grayscale (ĐÚNG như Phase 3.3)
                 → model int8 (Track A hoặc B) → nhãn loại + confidence
  └─ Tổng hợp: {sampleID, timestamp, count, size_dist, phân bố loại}
       → ghi log (yêu cầu traceability QC nước đầu vào)
```
- **Điểm chí mạng:** bước chuẩn hóa crop trên MCU phải **giống hệt** script Phase 3.3 (cùng cách pad, cùng nền, cùng resize). Lệch một chút là accuracy sập dù model tốt.
- Dùng ngưỡng confidence: dưới ngưỡng → gán `unknown` thay vì đoán bừa.

---

## Phase 11 — Kiểm định thực địa & vòng lặp cải tiến
1. Chạy trạm với **mẫu nước trộn nhiều loại** (giống thực tế), so nhãn model với đếm tay.
2. **Thu các ca sai về làm dữ liệu mới** (active learning): crop nào model đoán sai/độ tin thấp → gán nhãn đúng → thêm vào dataset → train lại. Đây là đòn bẩy tăng độ chính xác mạnh nhất sau khi pipeline đã chạy.
3. Sau khi có dữ liệu thật, **rà lại danh sách lớp Phase 1.1**: gộp lớp hay nhầm, tách lớp nếu thấy loại mới. Chốt class list chính thức tại đây.
4. Lặp Phase 3→10 cho tới khi đạt tiêu chí, hoặc chốt lại tiêu chí cho thực tế.

---

## Lộ trình thời gian gợi ý (đồ án)
| Tuần | Việc |
|---|---|
| 0 | Phase 0: sửa lens nét + CV xuất crop chạy được |
| 1 | Phase 1–3: chốt lớp, viết script crop, thu mẻ dữ liệu "mẫu đã biết nhãn" |
| 2 | Phase 4–7 Track A: đặc trưng + classifier nhỏ, đánh giá. Nếu đủ → nhảy Phase 8 |
| 3 | (Nếu cần) Track B: train tiny CNN, so với Track A |
| 4 | Phase 8–10: int8, deploy Edge Impulse, tích hợp on-device |
| 5 | Phase 11: kiểm thực địa, active learning, chốt class list, viết báo cáo |

---

## Rủi ro & lưu ý
- **Lens chưa nét (`camera-focus-limit`)** = rủi ro số 1. Không có ảnh nét thì không có dự án AI. Xử lý ở Phase 0.
- **plastic vs organic từ silhouette là ranh giới khó nhất** — cả hai đều là khối tối đục. Nếu Track A/B đều không tách được, đây chính là chỗ **Nile-Red (mở rộng tương lai)** cấp thêm đặc trưng màu; đừng hứa hẹn tách "nhựa vs không nhựa" bằng hình dạng thuần trong báo cáo.
- **Data leakage:** đừng để crop từ cùng 1 ảnh gốc nằm cả ở train lẫn test → accuracy ảo. Chia theo ảnh gốc/mẻ, không chia theo crop.
- **Train↔deploy mismatch:** cùng exposure, cùng backlit, cùng logic crop. Đây là lỗi hay gặp nhất khiến "trên PC 95%, trên board 60%".
- **Đừng thay CV bằng detection end-to-end** (đã phân tích: FOMO mất size, không đủ px cho hạt <2mm). Model AI chỉ làm phân loại crop.
- **Roboflow/Edge Impulse chỉ giúp Track B (CNN ảnh)**, không giúp Track A (đặc trưng thủ công) — đừng mất công tìm cách nhét feature vector vào 2 tool này.
- **Free tier Roboflow giới hạn số ảnh & mặc định public workspace** — kiểm tra hạn mức trước khi upload nhiều mẻ; nếu dữ liệu/đồ án cần riêng tư, cân nhắc trả phí hoặc giữ máy local (đường thủ công).
