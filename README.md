# 💥 AgentLash

Ứng dụng overlay giải trí cho Windows: biến chuột thành roi da quất tung màn hình trong lúc đợi AI agent làm việc.

## Cài đặt

**Qua npm** (cần [Node.js](https://nodejs.org) 18+):

```
npm install -g agentlash
agentlash
```

**Hoặc** tải `AgentLash.exe` ở trang [Releases](https://github.com/thieuhq2906/agentlash/releases) và nhấp đúp để chạy.
Windows có thể hiện "Windows protected your PC" vì file chưa có chữ ký số: bấm **More info → Run anyway**.

Hướng dẫn đầy đủ: [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)

## Phát triển

```
pip install PyQt6 pyinstaller
python main.py                                   # chạy từ mã nguồn
python -m PyInstaller --noconfirm --clean AgentLash.spec   # build dist/AgentLash.exe
```

| File | Vai trò |
| :--- | :--- |
| `main.py` | Khay hệ thống, menu, chống chạy 2 bản, ghi log lỗi |
| `overlay.py` | Cửa sổ trong suốt mỗi màn hình, vòng lặp hoạt ảnh, vẽ roi |
| `whip_physics.py` | Vật lý dây roi (Verlet) và động học cú quất |
| `impact_animation.py` | Hiệu ứng POW/ZAP/CRACK và hoạt ảnh tùy chỉnh |
| `sound_player.py` | Âm thanh qua MCI (phát chồng nhiều tiếng, âm lượng) |
| `global_hook.py` | Đọc nút chuột chính và phím F8 |
| `npm/` | Gói npm `agentlash`: trình khởi chạy tải exe từ Releases và kiểm tra SHA-256 |
| `tools/release.mjs` | Tool phát hành: build → tag → GitHub Release → npm publish |

## Phát hành phiên bản mới

```
node tools/release.mjs 1.0.1 --dry-run   # xem trước các bước
node tools/release.mjs 1.0.1
```

Yêu cầu: `gh auth login` và `npm login`. Tool từ chối chạy khi còn thay đổi chưa commit, tag đã tồn tại,
hoặc phiên bản đã có trên npm; và chỉ publish npm sau khi đã kiểm tra checksum của file exe trên GitHub.
