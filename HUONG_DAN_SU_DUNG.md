# 💥 AGENTLASH 💥
> *Ứng dụng Desktop Overlay giải trí đỉnh cao: Biến chuột thành roi da quất tung màn hình trong lúc đợi Agent làm việc!*

---

## 🚀 Cách Chạy Ứng Dụng
- **Cách 1**: Nhấp đúp chuột vào file `ChayAgentLash.bat` ở thư mục gốc.
- **Cách 2**: Chạy trực tiếp file độc lập `dist\AgentLash.exe`.
- *(Không cần cài đặt Python, không cần cài thư viện, chạy được ngay trên mọi máy Windows 10/11)*.

## 🎁 Gửi Cho Bạn Bè
- Chỉ cần gửi **duy nhất 1 file** `dist\AgentLash.exe` (~38 MB). Mọi hình ảnh, âm thanh đã nằm sẵn bên trong.
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

### 2. Ba Phong Cách Roi & Hoạt Ảnh Nổ Tương Ứng
| Kiểu Roi | Tạo Hình | Hiệu Ứng Trúng Đích |
| :--- | :--- | :--- |
| **💥 Comic Pop-Art** *(Mặc định)* | Roi viền đen, vàng đỏ hoạt họa pop-art | Nổ ngôi sao truyện tranh **"POW!"** |
| **⚡ Cyberpunk Neon** | Tay cầm hi-tech phát plasma | Dòng điện bùng nổ **"ZAP!"** cùng tia sét phân nhánh |
| **🤠 Classic Western** | Roi da bò bện cổ điển | Vết chém xé gió **"CRACK!"** tóe tia lửa |

### 3. Âm Thanh Quất Roi
- **💥 Theo kiểu roi** *(mặc định)*: Âm thanh nổ roi tương ứng từng kiểu.
- Muốn thêm tiếng hét, tiếng kêu vui nhộn: thả file của bạn vào thư mục âm thanh tùy chỉnh (xem bên dưới).
- **🎲 Ngẫu nhiên**.
- **🔉 Âm lượng**: 100% / 75% / 50% / 25%. Click liên tục không bị cắt tiếng.

### 4. Khay Hệ Thống (System Tray) & Phím Tắt
- **Phím F8** hoặc **nhấp đúp icon ở khay**: Bật/Tắt nhanh. Khi tắt, ứng dụng không tốn CPU.
- Nhấp chuột phải vào icon khay hệ thống để:
  - Đổi kiểu roi, chế độ âm thanh, âm lượng.
  - Bật/tắt từng hiệu ứng, chỉnh **tốc độ quất**.
  - Mở nhanh thư mục hoạt ảnh / âm thanh tùy chỉnh.
  - **Khởi động cùng Windows**.
- Chỉ chạy 1 bản duy nhất: mở lần hai sẽ báo "đang chạy rồi".

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
Kết quả: `dist\AgentLash.exe`. Lỗi (nếu có) được ghi vào `AgentLash.log` cạnh file .exe.
