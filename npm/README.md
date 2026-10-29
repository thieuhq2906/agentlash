# 💥 AgentLash

Biến chuột thành roi da quất tung màn hình Windows trong lúc đợi AI agent làm việc!
Click bất cứ đâu → roi vung, búng ngọn vào đúng điểm click, nổ **POW! / ZAP! / CRACK!** kèm âm thanh.

> Chỉ chạy trên **Windows 10/11**.

## Cài đặt

```
npm install -g agentlash
agentlash
```

Hoặc chạy một lần không cần cài: `npx agentlash`

Lần chạy đầu tiên, lệnh sẽ tải bản `AgentLash.exe` (~38 MB) từ
[GitHub Releases](https://github.com/thieuhq2906/agentlash/releases) về
`%LOCALAPPDATA%\AgentLash` và **kiểm tra mã SHA-256** trước khi chạy.
Gói npm không có script cài đặt (`postinstall`) nào.

## Lệnh

| Lệnh | Tác dụng |
| :--- | :--- |
| `agentlash` | Bật ứng dụng |
| `agentlash stop` | Tắt ứng dụng |
| `agentlash update` | Tải lại bản exe khớp phiên bản gói |
| `agentlash folder` | Mở thư mục cài đặt (cài đặt, hoạt ảnh / âm thanh tùy chỉnh) |
| `agentlash uninstall` | Tắt, xóa file đã tải, tắt khởi động cùng Windows |

Cập nhật lên bản mới: `npm install -g agentlash@latest` rồi chạy `agentlash`.

## Trong ứng dụng

- **F8** hoặc nhấp đúp icon ở khay hệ thống: Bật/Tắt nhanh.
- Chuột phải icon ở khay: đổi kiểu roi (Comic / Cyberpunk / Western), âm thanh, âm lượng, tốc độ quất, khởi động cùng Windows.
- Thả `.gif` / `.png` vào thư mục `assets\custom_animation`, `.wav` / `.mp3` vào `assets\custom_sounds` để dùng hoạt ảnh, âm thanh riêng.

Ứng dụng chỉ đọc trạng thái nút chuột chính và phím F8, không ghi lại phím gõ, không kết nối mạng.
