# Báo Cáo Nghiên Cứu Chuyên Sâu: Phương Pháp Quang Học Tạo Dữ Liệu 1D Cho Trình Biên Dịch NeuralCasting Trong Hệ Thống Quan Trắc Vi Nhựa Tại Biên

## Nền Tảng Công Nghệ Và Thách Thức Trong Quan Trắc Vi Nhựa Tại Biên

Sự gia tăng theo cấp số nhân của rác thải nhựa đã biến ô nhiễm vi nhựa (microplastics) thành một trong những mối đe dọa sinh thái và sức khỏe cộng đồng nghiêm trọng nhất trên phạm vi toàn cầu1. Các hạt vi nhựa, được định nghĩa là các mảnh nhựa có kích thước dao động từ 1 nanomet đến 5 milimet, đang xâm nhập vào mọi hệ sinh thái từ các đại dương bao la, nguồn nước ngầm sâu thẳm cho đến chuỗi thức ăn của con người3. Trong suốt nhiều thập kỷ qua, các phương pháp phân tích phòng thí nghiệm truyền thống như quang phổ hồng ngoại biến đổi Fourier (FTIR), quang phổ Raman, và phân tích nhiệt đã được thiết lập như những tiêu chuẩn vàng trong việc nhận diện và phân loại thành phần hóa học của vi nhựa2. Tuy nhiên, các kỹ thuật phân tích quang phổ này đòi hỏi hệ thống thiết bị cồng kềnh, quy trình thu thập và tiền xử lý mẫu cực kỳ phức tạp, cùng với sự can thiệp liên tục của các chuyên gia vận hành7. Sự phụ thuộc vào môi trường phòng thí nghiệm đã tạo ra một điểm nghẽn lớn, ngăn cản khả năng triển khai các mạng lưới quan trắc tự động, liên tục và thời gian thực tại các hiện trường xa xôi5.

Để giải quyết sự thiếu hụt về khả năng giám sát tại chỗ (in-situ), sự phát triển của các hệ thống quang học di động kết hợp với Trí tuệ Nhân tạo tại biên (Edge AI / TinyML) trên các vi điều khiển (MCU) giá rẻ đang trở thành một hướng đi mang tính cách mạng9. Các thiết bị vi điều khiển như dòng ESP32 mang lại lợi thế vượt trội về chi phí, khả năng tiêu thụ năng lượng thấp và kích thước nhỏ gọn. Mặc dù vậy, việc áp dụng trực tiếp các kỹ thuật thị giác máy tính (Computer Vision) xử lý hình ảnh quang học 2D trên các thiết bị này vấp phải những rào cản vật lý và tính toán vô cùng khắt khe9. Khối lượng dữ liệu khổng lồ từ ma trận điểm ảnh 2D thường xuyên gây ra hiện tượng tràn bộ nhớ (Memory Overflow) trên MCU. Thêm vào đó, khi quan trắc trong môi trường vi lưu (microfluidics) hoặc dòng chảy tự nhiên, vận tốc di chuyển cao của các hạt vi nhựa gây ra hiện tượng nhòe chuyển động (motion blur) nghiêm trọng, làm suy giảm thảm hại độ chính xác của các mô hình học sâu truyền thống9.

Nhằm vượt qua những rào cản nội tại của phương pháp xử lý ảnh 2D, một kiến trúc đo lường hoàn toàn mới đã được phát triển: sử dụng phương pháp tán xạ quang học (optical scattering) để trích xuất tín hiệu dưới dạng chuỗi thời gian một chiều (1D) kết hợp với công nghệ biên dịch mạng nơ-ron chuyên biệt mang tên NeuralCasting9. Việc chuyển đổi mô hình dữ liệu từ không gian đa chiều của thị giác máy tính sang xử lý tín hiệu điện áp 1D không chỉ tối ưu hóa tuyệt đối tài nguyên phần cứng mà còn khai thác được các đặc tính vật lý lượng tử của sự tương tác giữa ánh sáng và vật chất, mở ra khả năng phát hiện vi nhựa với độ trễ siêu thấp và độ chính xác vượt trội9.

## Nguyên Lý Tán Xạ Quang Học Trong Môi Trường Vi Lưu

Cốt lõi của việc tạo ra dữ liệu 1D chất lượng cao cho thuật toán AI nằm ở việc kiểm soát và phân tích sự tương tác giữa các photon ánh sáng và các hạt vi nhựa đang chuyển động. Quá trình này được chi phối bởi các định luật vật lý về động lực học lưu chất và quang học điện từ.

### Tương Tác Giữa Photon Ánh Sáng Và Vi Nhựa

Khi một dòng nước chứa các mẫu vật lơ lửng được dẫn qua một buồng vi lưu (microfluidic channel) và đi ngang qua một chùm tia sáng đồng pha (thường là tia Laser hoặc đèn LED dải hẹp), các hạt vật chất này sẽ đóng vai trò như những vật thể cản trở và làm thay đổi quỹ đạo của ánh sáng9. Trong vật lý quang học, cơ chế tán xạ được phân loại dựa trên tỷ lệ giữa kích thước hạt và bước sóng của ánh sáng tới. Đối với các phân tử khí hoặc các hạt siêu nhỏ (nhỏ hơn rất nhiều so với bước sóng ánh sáng), quá trình này được mô tả bởi tán xạ Rayleigh1. Tuy nhiên, do vi nhựa có dải kích thước từ vài micromet đến vài milimet, tức là tương đương hoặc lớn hơn bước sóng của ánh sáng khả kiến (thường từ 400 nm đến 700 nm), sự phân bố ánh sáng tán xạ bị chi phối hoàn toàn bởi lý thuyết tán xạ Mie (Mie Scattering)16.

Sự khác biệt về chỉ số khúc xạ (refractive index) giữa môi trường chất lỏng và hạt vật chất là yếu tố quyết định cường độ và góc tán xạ. Môi trường nước thông thường có chỉ số khúc xạ xấp xỉ 1.33, trong khi các loại vi nhựa phổ biến như Polystyrene (PS) hay Polyethylene (PE) có chỉ số khúc xạ dao động quanh mức 1.5915. Sự chênh lệch (refractive index contrast) này tạo ra các tín hiệu tán xạ mang thông tin vật lý đặc trưng của hạt, được thu nhận ở ba góc độ chính:

| Phân Loại Góc Tán Xạ | Cơ Chế Vật Lý Chủ Đạo | Thông Tin Vật Lý Trích Xuất | Đặc Điểm Cường Độ |
| :--- | :--- | :--- | :--- |
| **Tán xạ góc hẹp** (Forward Scattering - FSC) | Giao thoa và nhiễu xạ quang học quanh rìa hạt vật chất. | Tỷ lệ thuận với thiết diện cắt ngang và kích thước vật lý tổng thể của hạt. | Cường độ tín hiệu rất mạnh, dễ thu nhận bằng cảm biến cơ bản15. |
| **Tán xạ góc rộng** (Side Scattering - SSC) | Sự khúc xạ và phản xạ phức tạp qua nhiều lớp vật liệu. | Phản ánh mức độ phức tạp của cấu trúc vi mô, độ gồ ghề bề mặt và tính không đồng nhất bên trong hạt. | Cường độ trung bình, phụ thuộc vào hình thái bất đối xứng15. |
| **Tán xạ ngược** (Backscattering - BSC) | Phản xạ toàn phần và nhiễu xạ ngược từ ranh giới chiết suất. | Cực kỳ nhạy cảm với sự chênh lệch chỉ số khúc xạ giữa hạt và môi trường dung môi (nước). | Cường độ thấp nhưng là thông số then chốt để phân biệt bản chất vật liệu (nhựa vs. cát/sinh học)15. |

Để phục vụ cho hệ thống Edge AI tối giản, thay vì sử dụng các mảng cảm biến đa góc phức tạp như trong máy đo tế bào dòng chảy (Flow Cytometer) truyền thống, thiết kế hướng tới việc sử dụng cấu hình đo lường sự suy giảm cường độ ánh sáng truyền qua (Light Obscuration) hoặc tán xạ góc hẹp (FSC). Cấu hình này đảm bảo thu được tín hiệu có tỷ lệ tín hiệu trên nhiễu (Signal-to-Noise Ratio - SNR) cao nhất với chi phí phần cứng thấp nhất.

## Thiết Kế Hệ Thống Quang - Điện (Optoelectronic Design) Trích Xuất Dữ Liệu

Để trích xuất chính xác tín hiệu quang học dưới dạng đồ thị 1D với độ nhiễu thấp nhất, thiết kế của hệ thống cảm biến quang - điện (optoelectronic) đòi hỏi sự kết hợp chặt chẽ giữa các thành phần phát sáng, cảm biến thu sáng và vi mạch xử lý tín hiệu tương tự.

### Nguồn Sáng Và Mô Hình Vi Lưu Tập Trung

Hệ thống sử dụng các điốt laser (Laser Diodes) có công suất thấp hoặc đèn LED siêu sáng làm nguồn phát19. Các bước sóng ngắn như tia cực tím (UV) hoặc tia xanh lam (bước sóng khoảng 400 nm đến 450 nm) thường được ưu tiên do chúng làm tăng hiệu suất tán xạ của các hạt polyme nhỏ theo định luật tán xạ, trong khi các bước sóng như 532 nm, 650 nm hoặc 940 nm lại mang lại lợi thế về giá thành linh kiện thương mại9.

Ánh sáng từ nguồn phát được chuẩn trực thành một chùm tia hẹp chiếu xuyên qua một kênh vi lưu. Để đảm bảo các hạt vi nhựa không di chuyển hỗn loạn, kỹ thuật hội tụ thủy động lực học (Hydrodynamic Flow Focusing) được áp dụng. Bằng cách sử dụng các dòng chất lỏng vỏ bọc (sheath flow) bơm song song cùng với dòng mẫu (sample flow), các hạt vi nhựa bị ép vào trung tâm của kênh dẫn, buộc chúng phải di chuyển theo một hàng dọc và đi qua tâm của chùm tia laser với một vận tốc không đổi15.

### Module Thu Sáng Bằng Điốt Quang (Photodiode)

Tại vị trí đối diện với nguồn sáng (hoặc ở một góc đo tán xạ cố định), một cảm biến quang học đơn điểm như điốt quang (photodiode, ví dụ: BPW34 hoặc các module quang trở tương đương) được bố trí để thu nhận lượng photon truyền tới9. Cảm tạo này hoạt động dựa trên hiệu ứng quang điện trong cấu trúc lớp bán dẫn P-N. Khi các photon có năng lượng lớn hơn vùng cấm (bandgap) của vật liệu silicon (khoảng 1.12 eV) đập vào vùng nghèo (depletion region), chúng kích thích các điện tử nhảy từ vùng hóa trị lên vùng dẫn, tạo ra các cặp điện tử - lỗ trống22.

Dưới tác dụng của điện trường ngược (reverse bias), các hạt tải điện này di chuyển và tạo ra một dòng quang điện (photocurrent - $I_{ph}$) tỷ lệ tuyến tính với cường độ ánh sáng tới bề mặt cảm biến. Khi một hạt vi nhựa che khuất hoặc làm tán xạ chùm tia laser, số lượng photon đập vào cảm biến thay đổi, dẫn đến sự biến thiên trực tiếp của dòng quang điện này19.

### Mạch Khuếch Đại Xuyên Trở (Transimpedance Amplifier - TIA)

Dòng quang điện sinh ra từ photodiode thường vô cùng nhỏ, dao động ở mức nano-ampe (nA) đến micro-ampe ($\mu\text{A}$)19. Bộ chuyển đổi tương tự - số (ADC) tích hợp trên vi điều khiển ESP32 không thể đọc trực tiếp các dòng điện vi mô này. Do đó, một mạch khuếch đại chuyên dụng là bộ khuếch đại xuyên trở (Transimpedance Amplifier - TIA) được tích hợp để chuyển đổi dòng điện thành tín hiệu điện áp tỷ lệ23.

Bộ khuếch đại TIA thường được xây dựng xung quanh một bộ khuếch đại thuật toán (Op-Amp) có trở kháng đầu vào cực cao (như JFET hoặc CMOS) nhằm giảm thiểu dòng rò (bias current) làm sai lệch kết quả đo. Phương trình lý tưởng xác định điện áp đầu ra của mạch TIA là:

$$V_{out} = I_{ph} \times R_f + V_{ref}$$

Trong đó, $R_f$ là điện trở hồi tiếp (feedback resistor) xác định hệ số khuếch đại của toàn mạch, và $V_{ref}$ là điện áp tham chiếu tĩnh được áp vào chân không đảo (non-inverting input) của Op-Amp để dịch chuyển mức điện áp đầu ra phù hợp với dải đọc của ADC (thường từ 0V đến 3.3V đối với vi điều khiển)24.

Mặc dù việc sử dụng giá trị $R_f$ lớn (hàng Mega-Ohm) giúp tăng cường độ nhạy của hệ thống với các hạt vi nhựa siêu nhỏ, nó cũng mang lại những hệ lụy nghiêm trọng về tính ổn định của mạch. Điện dung ký sinh của điốt quang ($C_d$) kết hợp với điện dung đầu vào vi sai và đồng pha của Op-Amp ($C_{cm}$ và $C_{diff}$) tạo ra một cực (pole) trong hàm truyền của mạch phản hồi25. Sự kết hợp này gây ra độ trễ pha (phase shift) tiệm cận 360 độ tại tần số giao cắt, dẫn đến hiện tượng dao động (ringing hoặc oscillation) không kiểm soát, làm biến dạng hoàn toàn tín hiệu 1D của hạt vi nhựa.

Để giải quyết triệt để sự bất ổn định này, một tụ điện hồi tiếp ($C_f$) được mắc song song với điện trở $R_f$. Tụ điện này đóng vai trò tạo ra một điểm không (zero) trong hàm truyền để bù trừ pha (phase compensation) và thiết lập một tần số cắt (cutoff frequency - $f_p$) giới hạn băng thông của hệ thống. Giá trị của tụ điện bù pha phải tuân thủ bất đẳng thức:

$$C_f \ge \sqrt{\frac{C_d + C_{cm} + C_{diff}}{2\pi R_f f_{GBW}}}$$

24

Việc thiết lập tần số cắt $f_p$ biến mạch TIA thành một bộ lọc thông thấp (low-pass filter) lý tưởng. Bằng cách tinh chỉnh $f_p$ đồng bộ với vận tốc của dòng chảy vi lưu, mạch sẽ triệt tiêu hoàn toàn các nhiễu tần số cao từ ánh sáng nền hoặc nhiễu điện từ, đồng thời giữ lại trọn vẹn đặc tuyến quang học động học (dynamic optical signature) khi hạt vật chất đi qua vùng chiếu sáng28.

## Mô Hình Hóa Toán Học Và Sinh Dữ Liệu Tổng Hợp (Synthetic Data Generation)

Điện áp đầu ra từ mạch khuếch đại TIA được đưa trực tiếp vào chân ADC của vi điều khiển ESP32, nơi tín hiệu được số hóa liên tục ở tốc độ lấy mẫu cao (ví dụ: hàng ngàn mẫu mỗi giây). Để cung cấp dữ liệu huấn luyện cho mạng nơ-ron, hoặc mô phỏng môi trường hoạt động trong quá trình thiết kế hệ thống, quá trình biến thiên ánh sáng này được mô hình hóa toán học một cách chặt chẽ.

### Bản Chất Xung Gaussian Của Tín Hiệu 1D

Các chùm tia laser dùng trong đo lường quang học (đặc biệt là chế độ không gian TEM00) có sự phân bố cường độ không đồng đều, với cường độ sáng mạnh nhất ở tâm và giảm dần về phía rìa theo dạng hình chuông14. Khi một hạt vi nhựa chuyển động cắt ngang qua thiết diện của chùm tia này, cường độ ánh sáng bị che khuất hoặc tán xạ sẽ tăng dần khi mép hạt đi vào vùng sáng, đạt cực đại khi tâm hạt nằm ngay trục quang học, và giảm dần khi hạt đi ra ngoài5. Động lực học này tạo ra một xung tín hiệu (pulse) mang đậm đặc tính của hàm phân bố Gaussian.

Về mặt mô hình hóa toán học, tín hiệu số hóa $y[n]$ thu được có thể được biểu diễn tổng quát theo phương trình tuyến tính:

$$y[n] = b \cdot (\mathbf{H} \mathbf{x}[n]) + v[n]$$

2

Các thành phần trong phương trình này được định nghĩa như sau:
*   $y[n]$: Mảng tín hiệu điện áp một chiều (1D) theo chuỗi thời gian thu được từ ADC2.
*   $b$: Biến ngẫu nhiên tuân theo phân phối Bernoulli. Trong đó, giá trị $b=1$ đại diện cho sự kiện có mặt của hạt vi nhựa, và $b=0$ đại diện cho trạng thái dòng chảy trống2.
*   $\mathbf{H}$: Ma trận phản hồi hệ thống (System Response Matrix), bao hàm các đặc tính truyền đạt của cảm biến photodiode, mạch khuếch đại TIA và bộ lọc chống răng lược của ADC2.
*   $\mathbf{x}[n]$: Véc-tơ ngẫu nhiên đại diện cho hình thái vật lý của tín hiệu, chủ yếu là hình dạng đỉnh Gaussian chịu ảnh hưởng bởi đường kính chùm tia, kích thước hạt và vận tốc của dòng vi lưu2.
*   $v[n]$: Nhiễu đo lường ngẫu nhiên, thường được giả định là nhiễu trắng Gaussian với trung bình bằng không ($v[n] \sim \mathcal{N}(0, \sigma^2)$). Thành phần này mô phỏng các nhiễu loạn từ độ đục của dòng nước, bọt khí cực nhỏ, nhiễu nhiệt (Johnson-Nyquist noise) của điện trở và nhiễu nổ (Shot noise) của cảm biến quang2.

### Kỹ Thuật "Cửa Sổ Trượt" Và Chuẩn Hóa Mảng 41 Mẫu

Một trong những thách thức lớn nhất khi áp dụng Trí tuệ Nhân tạo tại biên là các mô hình biên dịch tĩnh (như cấu trúc của NeuralCasting) yêu cầu một khối lượng dữ liệu đầu vào (input tensor) có kích thước hoàn toàn cố định, không thể xử lý một luồng dữ liệu vô tận9. Thông qua quá trình phân tích và tối ưu hóa thời gian thực, các kỹ sư đã xác định rằng một cửa sổ thời gian gồm chính xác 41 điểm dữ liệu (41-sample window) cung cấp không gian vừa đủ để bắt trọn toàn bộ hình thái của một xung Gaussian phát sinh từ các hạt vi nhựa trong điều kiện lưu chất tiêu chuẩn5.

Để thực hiện trích xuất dữ liệu, vi điều khiển duy trì một bộ đệm vòng (ring buffer) ghi nhận liên tục dòng dữ liệu ADC. Thuật toán giám sát một ngưỡng kích hoạt biên độ (Trigger Threshold). Tại khoảnh khắc điện áp vượt qua (hoặc sụt giảm dưới) ngưỡng này do sự cản sáng của hạt vật chất, hệ thống xác định một "sự kiện" (event) đã xảy ra. Vi điều khiển lập tức khóa bộ đệm, trích xuất chính xác 20 điểm dữ liệu trước khi đạt đỉnh xung, 1 điểm tại đỉnh xung, và 20 điểm dữ liệu sau đỉnh xung9. Cơ chế này đảm bảo mọi hạt vi nhựa đi qua đều tạo ra một mảng 1D có độ dài 41 phần tử, mà trong đó đỉnh quang học luôn được căn giữa hoàn hảo.

Để mô phỏng môi trường thực tế phục vụ quá trình huấn luyện AI, các bộ dữ liệu tổng hợp (synthetic datasets) được tạo ra dựa trên phương trình toán học nêu trên. Các nhà nghiên cứu liên tục thay đổi các thông số đầu vào như Tỷ lệ Tín hiệu trên Nhiễu (Signal-to-Noise Ratio - SNR), sự thay đổi biên độ (amplitude variations), và xác suất tiên nghiệm (a priori probability - $p$) để giả lập đa dạng các điều kiện độ đục của nước và kích thước hạt khác nhau, từ đó giúp mạng nơ-ron học được khả năng khái quát hóa và tăng cường tính bền bỉ trước các tác động của môi trường2.

## Tiền Xử Lý Dữ Liệu Và Khung Lượng Tử Hóa Tuyến Tính

Trước khi mảng dữ liệu 1D gồm 41 phần tử được đưa vào mạng nơ-ron để tiến hành suy luận, nó phải trải qua một quy trình tiền xử lý và ép kiểu dữ liệu cực kỳ khắt khe nhằm đáp ứng các giới hạn khắc nghiệt về mặt kiến trúc phần cứng của hệ thống nhúng.

### Tiền Xử Lý Chuẩn Hóa Biên Độ

Các giá trị thô thu được từ bộ chuyển đổi ADC thường dao động trong một dải số nguyên (ví dụ: từ 0 đến 4095 đối với bộ ADC 12-bit của ESP32). Tuy nhiên, mức độ chiếu sáng nền (background illumination) không bao giờ cố định do sự thay đổi độ trong suốt của nước theo thời gian hoặc sự lão hóa của nguồn sáng laser9. Do đó, việc đưa trực tiếp dữ liệu thô vào mạng nơ-ron sẽ gây ra hiện tượng sai lệch phân phối (distribution shift). Để khắc phục, hệ thống áp dụng kỹ thuật loại trừ nền (Background Subtraction) nhằm dịch chuyển toàn bộ đường cong tín hiệu về mức cơ sở 0, sau đó sử dụng thuật toán chuẩn hóa Min-Max (Min-Max Scaling) để co giãn các biến động đỉnh tán xạ về một dải giá trị tiêu chuẩn [0, 1] hoặc phân bố xoay quanh giá trị trung bình9.

### Lượng Tử Hóa Tuyến Tính (Linear Quantization)

Quá trình huấn luyện các mô hình học sâu truyền thống trên máy tính thường được thực hiện trong không gian số dấu phẩy động 32-bit (Float32). Mặc dù định dạng Float32 mang lại độ chính xác biểu diễn cực cao, nó lại tiêu tốn một lượng tài nguyên bộ nhớ khổng lồ và đòi hỏi hàng loạt chu kỳ xung nhịp (clock cycles) phức tạp của bộ số học logic (ALU) để hoàn thành một phép toán33. Đối với các vi điều khiển Edge AI hoạt động bằng năng lượng pin, việc duy trì cấu trúc Float32 là một sự lãng phí không thể chấp nhận được.

Giải pháp cốt lõi là kỹ thuật lượng tử hóa (Quantization) – quá trình giảm độ phân giải của các dữ liệu từ dấu phẩy động 32-bit xuống dạng số nguyên 8-bit (Int8)9. Phương pháp lượng tử hóa tuyến tính đồng nhất (Uniform Linear Quantization) được áp dụng rộng rãi cho các trọng số (weights) và giá trị kích hoạt (activations) của mạng lưới thần kinh, và được toán học hóa thông qua phương trình ánh xạ:

$$Q = \text{round}\left(\frac{R}{S}\right) + Z$$

13

Trong cơ chế này:
*   $R$: Ma trận trọng số gốc của mô hình ở định dạng Float32, chứa đựng tri thức mà mạng đã học được.
*   $Q$: Ma trận trọng số sau khi lượng tử hóa, được lưu trữ dưới dạng số nguyên 8-bit, giúp giảm dung lượng mô hình xuống đúng 4 lần.
*   $Z$ (Zero Point): Biến số dịch chuyển điểm gốc. Thuộc tính này đảm bảo rằng giá trị số thực 0 luôn được ánh xạ chính xác vào một số nguyên xác định, một yêu cầu cực kỳ quan trọng để bảo toàn tính toàn vẹn của các phép toán chứa giá trị 0 (đặc biệt là sau các lớp kích hoạt như ReLU)9.
*   $S$ (Scale Factor): Hệ số tỷ lệ dương, điều chỉnh bước nhảy giữa các khoảng giá trị lượng tử hóa liên tiếp, đảm bảo toàn bộ dải động của ma trận Float32 được bao phủ tối ưu trong không gian 256 giá trị của Int89.

Thông qua quá trình lượng tử hóa, mảng dữ liệu 41 phần tử từ cảm biến quang học cũng được ép kiểu (cast) về không gian số nguyên từ -128 đến 127 trước khi thực hiện các phép nhân ma trận. Toàn bộ tính toán suy luận (inference) nặng nề nay được chuyển đổi thành các phép nhân tích lũy số nguyên cơ bản (Integer Multiply-Accumulate), tận dụng tối đa khả năng xử lý vector và tập lệnh của các bộ vi xử lý nhúng hiện đại9.

## Trình Biên Dịch NeuralCasting: Kiến Trúc Và Khả Năng Tích Hợp

Trong các hệ sinh thái TinyML truyền thống, các mô hình học máy (sau khi huấn luyện và lượng tử hóa) thường được triển khai lên vi điều khiển thông qua các bộ máy thông dịch trung gian (Inference Engines) như TensorFlow Lite for Microcontrollers (TFLM) hoặc ONNX Runtime. Các trình thông dịch này hoạt động theo cơ chế nạp cấu trúc mô hình vào bộ nhớ RAM, phân tích đồ thị cấu trúc một cách động tại thời điểm chạy (runtime), và tuần tự gọi các hàm thư viện toán học tương ứng9.

Tuy nhiên, cơ chế thông dịch này tạo ra một lớp trừu tượng (abstraction layer) phần mềm gây lãng phí bộ nhớ và dẫn đến các biến động độ trễ không thể dự đoán trước. Sự xuất hiện của các chóp độ trễ đột biến (latency spikes) – đôi khi kéo dài hàng ngàn micro-giây trong quá trình dọn rác bộ nhớ hoặc phân bổ lại ngăn xếp – có thể làm hệ thống bỏ lỡ hoàn toàn tín hiệu quang học của một hạt vi nhựa vừa lướt qua9.

NeuralCasting (được nghiên cứu và phát triển bởi Alessandro Cerioli, Daniele Sasso và các cộng sự) ra đời nhằm loại bỏ triệt để điểm nghẽn này. NeuralCasting không phải là một bộ máy suy luận trung gian, mà là một trình biên dịch phía trước (front-end compiler) dựa trên ngôn ngữ Python, hoạt động hoàn toàn ngoại tuyến (offline) trên máy tính trước khi mã được nạp vào vi điều khiển9. Kiến trúc hoạt động của trình biên dịch này tuân theo một quy trình đa bước chặt chẽ:
1.  **Phân Tích Cú Pháp Và Xây Dựng Đồ Thị** (Parser & DAG Assembler): NeuralCasting đọc mô hình trí tuệ nhân tạo ở định dạng chuẩn mở ONNX (Open Neural Network Exchange). Nó giải nén file, bóc tách thông tin của từng lớp mạng, và xây dựng một cấu trúc dữ liệu đồ thị có hướng không chu trình (Directed Acyclic Graph - DAG). Đồ thị này lưu trữ mối quan hệ logic, trình tự tính toán và tham chiếu bộ nhớ của tất cả các toán tử9.
2.  **Khớp Khuôn Mẫu** (Template Matching) Cho Lượng Tử Hóa: Khi trình duyệt đồ thị duyệt qua các nút đại diện cho toán tử lượng tử hóa (Q-Units), chẳng hạn như QuantizeLinear, DequantizeLinear, hoặc phép nhân ma trận lượng tử hóa tổng quát QGemm / QLinearMatMul, NeuralCasting sẽ trích xuất các siêu dữ liệu thiết yếu như ma trận trọng số, Zero Points ($Z$), và hệ số tỷ lệ ($S$)9. Những siêu dữ liệu này được đối chiếu với các "khuôn mẫu" (templates) mã ngôn ngữ C có sẵn trong thư viện nội bộ.
3.  **Sinh Mã Gốc (Native C Code Generation) Và Quản Lý Bộ Nhớ**: Trình biên dịch tạo ra một đoạn mã C/C++ thuần túy, nội suy trực tiếp các ma trận toán học thành các vòng lặp for lồng nhau dựa hoàn toàn trên các thư viện C tiêu chuẩn mà không cần thêm bất kỳ gói phụ thuộc nào9. Quan trọng hơn, NeuralCasting cung cấp cơ chế phân bổ bộ nhớ tĩnh. Người dùng có thể chỉ định cấp phát trực tiếp các ma trận trọng số vào phân vùng dữ liệu toàn cục (Data Segment), hoặc phân vùng động (Heap) sử dụng các lệnh cấp phát bộ nhớ một lần (malloc) khi khởi động9. Đối với bài toán xử lý 41-sample Gaussian, việc cấp phát thẳng vào phân vùng dữ liệu giúp triệt tiêu hoàn toàn sự phân mảnh bộ nhớ (memory fragmentation) vốn là tử huyệt của các hệ thống trần (bare-metal)9.

Sản phẩm đầu ra của quy trình này là các tập tin .c và .h chứa một hàm suy luận (inference function) được tối ưu hóa cực đoan. Khi hoạt động trên bo mạch ESP32, vi điều khiển chỉ việc nhận mảng 1D từ ADC, gọi hàm C này, và nhận lại kết quả phân loại gần như tức thời. Kiến trúc này cho phép phân tích Thời gian Thực thi Xấu nhất (Worst-Case Execution Time - WCET) một cách có tính toán (deterministic), đảm bảo hệ thống có khả năng đáp ứng các yêu cầu thời gian thực khắt khe nhất trong động lực học dòng chảy11.

## Đánh Giá Hiệu Năng Thực Nghiệm Và Tối Ưu Hóa Kiến Trúc Mạng (NAS)

Để chuyển hóa tín hiệu 1D chứa đựng động thái tán xạ của vi nhựa thành quyết định phân loại chính xác, một thuật toán Tìm kiếm Kiến trúc Mạng Nơ-ron (Neural Architecture Search - NAS) đã được thực thi. Phương pháp tìm kiếm lưới (Grid Search) được áp dụng nhằm thiết kế và lựa chọn tự động một kiến trúc mô hình học sâu đạt điểm cân bằng hoàn hảo giữa độ chính xác dự đoán và chi phí tài nguyên phần cứng4.

Nghiên cứu tiến hành đánh giá và đối đầu hai dòng kiến trúc thần kinh phổ biến:
1.  **Mạng Perceptron Đa Lớp** (Multi-Layer Perceptron - MLP): Thuật toán NAS duyệt qua không gian tham số bao gồm số lượng lớp ẩn (1, 2, hoặc 3 lớp) và số lượng nơ-ron mỗi lớp (8, 16, 32, hoặc 64). Kết quả tối ưu hội tụ về một kiến trúc tối giản đến mức kinh ngạc: Một mạng MLP chỉ gồm 1 lớp ẩn duy nhất với 8 nơ-ron9.
2.  **Mạng Nơ-ron Hồi Quy Có Cổng** (Gated Recurrent Unit - GRU): Thuật toán tìm kiếm kích thước trạng thái ẩn (hidden size) lý tưởng trong khoảng (8, 16, 32, 64), và hệ thống cũng lựa chọn cấu hình nhỏ nhất là kích thước ẩn bằng 89.

Kết quả thử nghiệm và tác động của lượng tử hóa trên hai kiến trúc này cung cấp những hiểu biết sâu sắc về hành vi của AI tại biên:

| Tiêu Chí Đánh Giá | Mạng Perceptron Đa Lớp (MLP) | Mạng Nơ-ron Hồi Quy (GRU) |
| :--- | :--- | :--- |
| **Cấu trúc tối ưu (NAS)** | 1 lớp ẩn, 8 nơ-ron9 | Kích thước ẩn (Hidden size) là 89 |
| **Độ chính xác nguyên bản (Float32)** | ~ 99.3%9 | ~ 99.5%9 |
| **Độ chính xác sau lượng tử hóa (Int8)** | 99.1% (Hầu như không suy giảm)5 | 98.5% (Suy giảm rõ rệt)5 |
| **Bản chất xử lý tín hiệu** | Đọc song song mảng 41 phần tử | Xử lý tuần tự theo mốc thời gian |
| **Khối lượng tính toán (MACs)** | Cực kỳ nhỏ, tiêu tốn ít Flash/RAM | Lớn hơn nhiều do cơ chế điều khiển cổng bộ nhớ |
| **Độ trễ suy luận (Latency)** | Siêu thấp (Chỉ vài chục micro-giây)9 | Chậm hơn rõ rệt so với MLP9 |

**Biện luận kỹ thuật**: Mặc dù GRU về mặt lý thuyết là kiến trúc sinh ra để xử lý các dữ liệu chuỗi thời gian (time-series) phức tạp, ứng dụng của nó trong trường hợp tín hiệu tán xạ 1D lại bộc lộ những điểm yếu chí mạng. Tín hiệu quang học của một hạt vi nhựa khi cắt ngang chùm sáng là một chuỗi biến thiên cực kỳ ngắn (chỉ 41 mẫu) và mang một đặc điểm hình thái không gian cố định (đường cong hình chuông Gaussian)9. Mạng MLP, chỉ với 8 nơ-ron liên kết đầy đủ, có năng lực nhận diện hoàn hảo các đặc điểm hình học của đường cong tĩnh này mà không cần đến khả năng ghi nhớ dài hạn9.

Điểm quyết định nằm ở sức chịu đựng với quá trình ép kiểu (Quantization Robustness). Việc mạng MLP bảo toàn được độ chính xác ở mức 99.1% sau khi nén xuống định dạng số nguyên 8-bit, trong khi GRU bị sụt giảm xuống còn 98.5%, minh chứng một thực tế toán học: các cơ chế cổng phi tuyến tính (update gate và reset gate) dùng trong RNN/GRU cực kỳ nhạy cảm với sai số làm tròn khi mất đi phần thập phân của Float329.

Sự kết hợp giữa kiến trúc MLP 1 lớp và khả năng sinh mã C trực tiếp của NeuralCasting tạo ra một "vi hạt" AI nhỏ gọn đến mức nó chỉ chiếm vài Kilobyte (KB) dung lượng bộ nhớ. Điều này cho phép triển khai mô hình không chỉ trên hệ sinh thái ESP32 mà còn trên các vi điều khiển có tài nguyên siêu thấp như Arduino Nano 33 BLE (sử dụng lõi ARM Cortex-M4), duy trì độ ổn định xử lý tuyệt đối trong hàng ngàn chu kỳ suy luận liên tục9.

## So Sánh Kiến Trúc Quang Học 1D Và Các Hệ Thống Thị Giác 2D

Dự án giám sát vi nhựa tự trị ban đầu được hình thành dựa trên các nguyên lý kính hiển vi hình ảnh 2D, tiêu biểu là các nền tảng như Matchboxscope, Fluidiscope hoặc cấu hình không thấu kính HoloESP9. Tuy nhiên, sự chuyển đổi chiến lược sang kiến trúc thu thập dữ liệu tán xạ 1D là một quyết định mang tính bản lề, giải quyết triệt để những rào cản vật lý khắc nghiệt nhất.
*   **Vượt Qua Rào Cản Tiêu Cự Cơ Học** (Depth of Field): Với các hệ thống dùng camera 2D (như ESPressoscope sử dụng module OV2640), việc tạo ra một kính hiển vi đòi hỏi thao tác vặn ngược thấu kính nguyên bản để thay đổi điểm lấy nét9. Kỹ thuật "hack" quang học này thu hẹp độ sâu trường ảnh (Depth of Field) xuống mức cực mỏng. Bất kỳ sự rung lắc siêu nhỏ nào của buồng vi lưu hoặc sự thay đổi nhiệt độ đều làm hình ảnh hạt vi nhựa bị mất nét (out of focus) và xuất hiện các hiện tượng quang sai cầu (spherical aberration) trầm trọng ở rìa khung hình9. Ngược lại, phương pháp tán xạ 1D loại bỏ hoàn toàn cụm thấu kính tạo ảnh phức tạp. Cảm biến điốt quang chỉ đo lường sự biến thiên cường độ photon tổng thể, do đó hoàn toàn miễn nhiễm với các sai số về tiêu cự cơ học.
*   **Khắc Phục Hiện Tượng Nhòe Chuyển Động** (Motion Blur): Để một hệ thống thị giác máy tính 2D có thể "đóng băng" hình ảnh của một hạt vi nhựa đang chuyển động với vận tốc cao trong dòng chảy, camera bắt buộc phải hoạt động với tốc độ màn trập (shutter speed) cực nhanh. Phơi sáng ngắn đòi hỏi một hệ thống chiếu sáng có cường độ khổng lồ để bù đắp lượng photon thiếu hụt, gây tiêu hao pin nghiêm trọng và sinh nhiệt làm hỏng vi mạch9. Sự xuất hiện của vệt mờ chuyển động làm biến dạng cấu trúc không gian của hạt, khiến mạng nơ-ron nhận diện sai. Trong kiến trúc 1D, các cảm biến điốt quang có thời gian đáp ứng (response time) đạt đến ngưỡng nano-giây22, dễ dàng theo kịp và đồ thị hóa hoàn hảo đường cong ánh sáng tán xạ của hạt nhựa lao qua với vận tốc cao mà không hề gặp hiện tượng nhòe tín hiệu.
*   **Lợi Thế Tuyệt Đối Về Sức Mạch Tính Toán So Với Giao Thoa Toàn Ảnh** (Holography): Cấu hình HoloESP mang lại một thiết kế quang học đột phá: tháo bỏ thấu kính, nhỏ trực tiếp mẫu vật lên cảm biến và chiếu sáng bằng đèn LED 450nm qua một lỗ pinhole 0.1 mm để tạo ra bức ảnh giao thoa toàn ký (Hologram) với trường nhìn 3D cực rộng và độ phân giải 3 Megapixel7. Mặc dù về mặt thu thập dữ liệu quang học đây là một hệ thống xuất sắc, bức ảnh nhiễu xạ thu được không thể được mạng nơ-ron trên MCU đọc trực tiếp7. Nó bắt buộc phải trải qua quá trình tái tạo hình ảnh (Digital Reconstruction) bằng các phép biến đổi không gian Fourier và thuật toán lan truyền ngược. Khối lượng tính toán ma trận khổng lồ này đánh gục bất kỳ vi điều khiển Edge AI nào, buộc hệ thống phải đẩy dữ liệu lên máy chủ web hoặc Raspberry Pi để xử lý9. Tín hiệu điện áp 1D kết hợp với mã C tĩnh của NeuralCasting cho phép vi điều khiển tự thực thi toàn bộ quy trình tính toán ngay tại thiết bị, duy trì vững chắc tính "tự trị" (Autonomous) và bảo mật dữ liệu mà không phụ thuộc vào kết nối mạng.

## Kết Luận

Nghiên cứu chuyên sâu về phương pháp thu thập tín hiệu quang học 1D kết hợp với Trí tuệ Nhân tạo tại biên thông qua trình biên dịch NeuralCasting đã định hình một lộ trình kỹ thuật hoàn toàn mới trong lĩnh vực quan trắc vi nhựa tự động. Bằng cách dịch chuyển mô hình từ thị giác máy tính 2D sang khai thác trực tiếp bản chất vật lý của sự tương tác quang học (Mie Scattering), hệ thống đã giải quyết dứt điểm các giới hạn về khả năng tính toán, hiện tượng nhòe chuyển động và sự bất ổn định quang cơ học.

Cấu trúc cảm biến điốt quang, được tối ưu hóa băng thông nhờ bộ khuếch đại xuyên trở (TIA) có tính toán bù pha chính xác, đã tạo ra một tín hiệu xung Gaussian nguyên bản, phản chiếu trọn vẹn đặc tính của các hạt vật chất lơ lửng. Việc sử dụng mạng nơ-ron tĩnh cực kỳ tối giản (Quantized MLP 8-bit) không chỉ bảo toàn được độ chính xác phân loại ấn tượng ở mức 99.1% mà còn phù hợp hoàn hảo với kiến trúc sinh mã C trực tiếp của NeuralCasting. Việc loại bỏ các bộ máy suy luận trung gian nặng nề đã giải phóng vi điều khiển khỏi nguy cơ tràn bộ nhớ và các rủi ro về độ trễ, biến thiết bị giám sát nước chi phí thấp thành một cỗ máy phân tích độc lập với hiệu suất hoạt động cực kỳ ổn định. Phương pháp này không chỉ mở ra khả năng thương mại hóa các trạm quan trắc tự trị mà còn đặt nền móng vững chắc cho các ứng dụng Edge AI phục vụ mục tiêu bảo vệ sinh thái trong tương lai.

## Works cited

1. Unraveling Microplastics: Sources, Environment and Health Impacts, and Detection Techniques - Preprints.org, https://www.preprints.org/manuscript/202601.1415
2. A Benchmarking on Optofluidic Microplastic Pattern Recognition: A Systematic Comparison Between Statistical Detection Models and - IRIS, https://www.iris.unicampus.it/retrieve/0069cb8a-fd6b-4d44-922e-aafe8c114191/A_Benchmarking_on_Optofluidic_Microplastic_Pattern_Recognition_A_Systematic_Comparison_Between_Statistical_Detection_Models_and_ML-Based_Algorithms.pdf
3. Unraveling Microplastics: Sources, Environment and Health Impacts, and Detection Techniques - MDPI, https://www.mdpi.com/2076-3298/13/3/134
4. Comprehensive overview of hyperparameter optimization for each machine learning algorithm. - ResearchGate, https://www.researchgate.net/figure/Comprehensive-overview-of-hyperparameter-optimization-for-each-machine-learning-algorithm_tbl1_377996047
5. (PDF) A Benchmarking on Optofluidic Microplastic Pattern Recognition: A Systematic Comparison Between Statistical Detection Models and ML-Based Algorithms - ResearchGate, https://www.researchgate.net/publication/377996047_A_benchmarking_on_Optofluidic_microplastic_pattern_recognition_A_systematic_comparison_between_statistical_detection_models_and_ML-based_algorithms
6. A semi-automated Raman micro-spectroscopy method for morphological and chemical characterizations of microplastic litter | Request PDF - ResearchGate, https://www.researchgate.net/publication/309892615_A_semi-automated_Raman_micro-spectroscopy_method_for_morphological_and_chemical_characterizations_of_microplastic_litter
7. (PDF) Encoding Holographic Data Into Synthetic Video Streams for Enhanced Microplastic Detection - ResearchGate, https://www.researchgate.net/publication/394002522_Encoding_Holographic_Data_into_Synthetic_Video_Streams_for_Enhanced_Microplastic_Detection
8. (PDF) Towards the Development of Portable and In Situ Optical Devices for Detection of Micro-and Nanoplastics in Water: A Review on the Current Status - ResearchGate, https://www.researchgate.net/publication/349703146_Towards_the_Development_of_Portable_and_In_Situ_Optical_Devices_for_Detection_of_Micro-and_Nanoplastics_in_Water_A_Review_on_the_Current_Status
9. Aqua Scope, uploaded:Aqua Scope
10. Towards the Development of Portable and In Situ Optical Devices for Detection of Micro-and Nanoplastics in Water: A Review on the Current Status - PMC, https://pmc.ncbi.nlm.nih.gov/articles/PMC7956778/
11. alecerio/NeuralCasting: Front-end compiler for ONNX - GitHub, https://github.com/alecerio/NeuralCasting
12. Time-predictable Deep Noise Suppression on an Edge Device, https://www.jopdesign.com/doc/rt_neuralcasting.pdf
13. Efficient Detection of Microplastics on Edge Devices With Tailored Compiler for TinyML Applications - IRIS, https://www.iris.unicampus.it/retrieve/2a566853-f5f8-4de8-ac45-371064302372/Efficient_Detection_of_Microplastics_on_Edge_Devices_With_Tailored_Compiler_for_TinyML_Applications.pdf
14. Continuous Sizing and Identification of Microplastics in Water - ResearchGate, https://www.researchgate.net/publication/367041765_Continuous_Sizing_and_Identification_of_Microplastics_in_Water
15. Backscattering-Based Discrimination of Microparticles Using an Optofluidic Multiangle Scattering Chip - PMC, https://pmc.ncbi.nlm.nih.gov/articles/PMC9161266/
16. Detection of Particles, Bacteria and Viruses using Consumer Optoelectronic Components - UPCommons, https://upcommons.upc.edu/bitstreams/234e7d04-00be-45dc-8bc4-c607a5ecedc4/download
17. The Mie Theory Basics and Applications | Request PDF - ResearchGate, https://www.researchgate.net/publication/266187116_The_Mie_Theory_Basics_and_Applications
18. Backscattering-Based Discrimination of Microparticles Using an Optofluidic Multiangle Scattering Chip | ACS Omega - ACS Publications, https://pubs.acs.org/doi/10.1021/acsomega.1c06343
19. A handheld fiber-optic tissue sensing device for spine surgery - Amsterdam UMC, https://pure.amsterdamumc.nl/ws/portalfiles/portal/142427056/A-handheld-fiber-optic-tissue-sensing-device-for-spine-surgery.pdf
20. A handheld fiber-optic tissue sensing device for spine surgery - TU Delft Research Portal, https://pure.tudelft.nl/ws/portalfiles/portal/233235835/journal.pone.0314706.pdf
21. Đầu laser 5v - Màu sắc - Ánh sáng \| Điện tử Spider, https://dientuspider.com/shop/product/dau-laser-5v
22. Optoelectronics - optoprim, https://www.optoprim.com/wp-content/uploads/2022/02/OSI_Parts_Catalog.pdf
23. Photodiodes - RP Photonics, https://www.rp-photonics.com/photodiodes.html
24. Transimpedance Amplifier : Circuit, Working and Its Applications - ElProCus, https://www.elprocus.com/transimpedance-amplifier/
25. 1 MHz, Single-Supply, Photodiode Amplifier Reference Design - Texas Instruments, https://www.ti.com/lit/pdf/tidu535
26. Photodiode Amplifier Circuit (Rev. B) - Texas Instruments, https://www.ti.com/lit/pdf/sboa220
27. Stabilize Your Transimpedance Amplifier - Analog Devices, https://www.analog.com/en/resources/technical-articles/stabilize-transimpedance-amplifier-circuit-design.html
28. Photodiode Circuit Frequency Characteristics and Pulse Response Article No. 029 \[For Beginners\] - note, https://note.com/major_spirea4370/n/n5380b7ef1041?hl=en
29. Photodiode Opamp Amplifier (Transimpedance Ampl.) - changpuak.ch, https://www.changpuak.ch/electronics/PhotodiodeOpampAmplifier.php
30. A Benchmarking On Optofluidic Microplastic Pattern Recognition A, https://www.scribd.com/document/761846986/A-Benchmarking-on-Optofluidic-Microplastic-Pattern-Recognition-A-Systematic-Comparison-Between-Statistical-Detection-Models-and-ML-Based-Algorithms
31. ESP32 - Vi Điều Khiển Đa Năng Cho Dự Án IoT, https://chotroihn.vn/esp32-vi-dieu-khien-da-nang-cho-du-an-iot
32. A machine learning algorithm for high throughput identification of FTIR spectra: Application on microplastics collected in the Mediterranean Sea \| Request PDF - ResearchGate, https://www.researchgate.net/publication/333651004_A_machine_learning_algorithm_for_high_throughput_identification_of_FTIR_spectra_Application_on_microplastics_collected_in_the_Mediterranean_Sea
33. Neural Network Quantization for Microcontrollers: A Comprehensive Survey of Methods, Platforms, and Applications - ResearchGate, https://www.researchgate.net/publication/394831145_Neural_Network_Quantization_for_Microcontrollers_A_Comprehensive_Survey_of_Methods_Platforms_and_Applications
34. Quantized Neural Networks for Microcontrollers: A Comprehensive Review of Methods, Platforms, and Applications - arXiv, https://arxiv.org/html/2508.15008v1
35. Insights into Interpreters, Compilers, and Optimizers for Neural Networks, https://webs.um.es/aros/papers/pdfs/salladi-codai25.pdf
36. NeuralCasting: A Front-End Compilation Infrastructure for Neural Networks \| Request PDF, https://www.researchgate.net/publication/384916796_NeuralCasting_A_Front-End_Compilation_Infrastructure_for_Neural_Networks
