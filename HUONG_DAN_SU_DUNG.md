# 💥 AGENTLASH 💥
> *Ứng dụng Desktop Overlay giải trí đỉnh cao: Biến chuột thành roi da quất tung màn hình trong lúc đợi Agent làm việc!*

---

## 🚀 Cách Chạy Ứng Dụng
- **Cách 1**: Nhấp đúp chuột vào file `ChayAgentLash.bat` ở thư mục gốc.
- **Cách 2**: Chạy trực tiếp file độc lập trong thư mục `dist\`.
- *(Không cần cài đặt Python, không cần cài thư viện, chạy được ngay trên mọi máy Windows 10/11)*.

### Hai phiên bản
| File | Dành cho |
| :--- | :--- |
| `dist\AgentLash.exe` | **Bản thường**: chỉ có quất roi giải trí, không chứa phần nhận thức bảo mật. |
| `dist\AgentLash_Security.exe` | **Bản bảo mật**: như bản thường + màn hình Nhận Thức An Ninh Thông Tin tự hiện sau **10 phút sử dụng** (phím F9 để mở ngay). |

## 🎁 Gửi Cho Bạn Bè
- Chỉ cần gửi **duy nhất 1 file** `.exe` (bản thường hoặc bản bảo mật). Mọi hình ảnh, âm thanh đã nằm sẵn bên trong.
- Người nhận đặt file ở đâu cũng được (Desktop, Downloads...) rồi nhấp đúp để chạy.
- Lần đầu chạy, Windows có thể hiện cảnh báo **"Windows protected your PC"** (do file không có chữ ký số):
  bấm **More info → Run anyway**.
- Nếu gửi qua Gmail/Zalo bị chặn file .exe, hãy nén thành `.zip` trước khi gửi.
- Ứng dụng tự tạo `config.json` và `AgentLash.log` cạnh file .exe để lưu cài đặt.

---

## ✨ Các Tính Năng Nổi Bật

### 1. Hiệu Ứng Vật Lý & Động Học Roi Chân Thực (Verlet & Kinematics)
- **Cán roi bám theo con trỏ chuột**: Cán roi chuyển động mượt mà theo chuột, dây roi rủ mềm và đung đưa theo quán tính.
- **Cú quất roi sóng cơ học**: Khi click, roi vung từ trên xuống, một vòng sóng chạy dọc thân roi và ngọn roi búng đúng vào điểm bạn click, rồi giật nảy lại.
- Hoạt động đúng trên màn hình scale 125% / 150% / 200% và nhiều màn hình.

### 2. Năm Phong Cách Vũ Khí & Hoạt Ảnh Funny
| Kiểu Vũ Khí | Tạo Hình Con Trỏ | Hiệu Ứng Trúng Đích (VFX) | Âm Thanh & Voice |
| :--- | :--- | :--- | :--- |
| **💥 Comic Pop-Art** *(Mặc định)* | Roi viền đen vàng đỏ hoạt họa pop-art | Vòng sao choáng váng xoay tít, chữ nổ đổi ngẫu nhiên `BONK!`, `POW!`, `BAM!`, `K.O!` | Tiếng lò xo "Boinggg!" + gõ mỏ hoạt hình "CỘC!" |
| **⚡ Cyberpunk Neon** | Tay cầm hi-tech phát plasma neon | Màn hình glitch, dòng mã nhị phân `0101` văng tung tóe, chữ `SYNTAX ERROR!`, `ZAP!` | Âm thanh cắm rút USB Windows tạch tạch + modem glitch |
| **🤠 Classic Western** | Roi da bò bện viễn Tây cổ điển | Vết rách xước bốc khói, bụi cát sa mạc mịt mù + bụi cỏ khô cuộn tròn lăn qua | Tiếng huýt sáo miền viễn Tây Clint Eastwood + tiếng "YEE-HAW!" |
| **⚡ Kìm Điện Cam-pu-chia** | Dùi cui kìm điện 2 ngạnh sọc vàng phóng hồ quang | Màn hình rung giật điện, tia sét cao thế dày đặc chớp nháy `BZZZT!` | Tiếng giật điện taser + Tiếng Tom hét + *"Alo tỉnh ngủ chưa em ơi?!"* |
| **🗡️ Thanh Kiếm Trung Cổ** | Chuôi kiếm mạ vàng, lưỡi thép sắc lẹm rãnh huyết | Vết chém xé toạc màn hình, nứt vỡ kính mạng nhện `SMASH!` | Tiếng thét gầm uy lực **"TRẢM!"** + chém sắt rợn người |

### 3. Âm Thanh & Chế Độ Văn Phòng
- **💥 Theo kiểu vũ khí** *(mặc định)*: Âm thanh nổ và voice tương ứng từng kiểu.
- **🤫 Chế độ Văn Phòng Yên Tĩnh (Office Mode)**:
  - Thu nhỏ kích thước vũ khí bằng con trỏ chuột Windows (vô cùng kín đáo, không vướng mắt).
  - Tự động tắt âm thanh để bạn thoải mái dùng trong giờ làm việc.
  - Bật/Tắt tức thì từ menu khay hệ thống.
- **🔉 Âm lượng**: 100% / 75% / 50% / 25%. Click liên tục không bị cắt tiếng.

### 4. Khay Hệ Thống (System Tray) & Phím Tắt
- **Phím F8** hoặc **nhấp đúp icon ở khay**: Bật/Tắt nhanh quất roi. Khi tắt, ứng dụng không tốn CPU.
- **Phím F9** *(bản bảo mật)*: Kích hoạt nhanh **Trung Tâm Nhận Thức An Ninh Thông Tin** (dành cho demo / thuyết trình).
- Nhấp chuột phải vào icon khay hệ thống để:
  - Đổi kiểu roi, chế độ âm thanh, âm lượng.
  - Bật/tắt từng hiệu ứng, chỉnh **tốc độ quất**.
  - **Sáng kiến Nhận thức Bảo mật** *(bản bảo mật)*: Bật/tắt tự động hiện cảnh báo, chọn thời gian sử dụng trước khi hiện (5 / 10 / 20 / 30 phút).
  - Mở nhanh thư mục hoạt ảnh / âm thanh tùy chỉnh.
  - **Khởi động cùng Windows**.
- Chỉ chạy 1 bản duy nhất: mở lần hai sẽ báo "đang chạy rồi".

### 5. 🛡️ Sáng Kiến Nhận Thức An Ninh Thông Tin (Security Awareness Twist)
- **Cú Twist Bất Ngờ**: Khi người dùng mải mê click chuột quất roi (mặc định sau **10 phút sử dụng** — chỉ tính lúc ứng dụng đang bật, hiện 1 lần mỗi phiên — hoặc bấm `F9`), ứng dụng lập tức tạm dừng và bung mở bảng cảnh báo:
  > **“BẠN TIN TƯỞNG NÓ CHỈ VÌ NÓ TRÔNG CÓ VẺ VÔ HẠI. GIAO DIỆN VÔ HẠI KHÔNG PHẢI LÀ BẰNG CHỨNG AN TOÀN.”**
- **Bảng đối chiếu minh bạch (3 nhóm)**:
  - **Nhóm A (Thực tế)**: Liệt kê chính xác những gì app đã làm trên máy (PID, hook chuột Win32, transparent overlay, file log cục bộ).
  - **Nhóm B (Mô phỏng nguy cơ - dán nhãn MÔ PHỎNG)**: Diễn họa cách các phần mềm độc hại (infostealer/spyware) lợi dụng vỏ bọc ứng dụng vui nhộn để đọc trộm cookie, token phiên làm việc, quét clipboard hay kết nối C2 server.
  - **Nhóm C (Cam kết an toàn)**: Khẳng định 100% offline, không keylogger, không đọc cookie thật, không gửi dữ liệu ra ngoài.
- **Cẩm nang 7 bước tự vệ số**: Hướng dẫn thực hành kiểm tra chữ ký số, giám sát tiến trình Task Manager, kiểm tra kết nối mạng qua Resource Monitor / `netstat`.
- **Nhật ký kiểm toán**: Lưu trữ đầy đủ tại `security_audit.log` cạnh file thực thi.

---

## 🎨 Hoạt Ảnh & Âm Thanh Tùy Chỉnh
Không cần khởi động lại: file mới được nhận ngay ở cú quất tiếp theo.

**Hoạt ảnh** – menu khay → *Mở thư mục hoạt ảnh tùy chỉnh* (thư mục `assets\custom_animation\` cạnh file .exe):
- **File .gif**: phát toàn bộ ảnh động tại điểm trúng roi.
- **Chuỗi ảnh** `frame_01.png`, `frame_02.png`...: được ghép thành một hoạt ảnh.
- **Ảnh đơn .png/.jpg**: hiệu ứng nẩy tung (elastic pop-up) rồi tan biến.

**Âm thanh** – menu khay → *Mở thư mục âm thanh tùy chỉnh* (thư mục `assets\custom_sounds\`):
- Thả file **.wav / .mp3** vào; nhiều file sẽ được chọn ngẫu nhiên. Xóa hết để quay về âm thanh mặc định.

---

## 🛠️ Build Lại File .exe (dành cho người phát triển)
```
pip install PyQt6 pyinstaller
pyinstaller --noconfirm --clean AgentLash.spec
```
Một lệnh build cả 2 bản: `dist\AgentLash.exe` (bản thường) và `dist\AgentLash_Security.exe` (bản bảo mật).
Lỗi (nếu có) được ghi vào `AgentLash.log` cạnh file .exe.
