import os
import sys
import time
import logging
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QScrollArea, QFrame, QTextBrowser,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

from config import config, get_data_dir, APP_NAME

log = logging.getLogger(__name__)

AUDIT_LOG_FILE = "security_audit.log"
AUDIT_LOG_MAX_BYTES = 512 * 1024  # start a fresh log instead of growing forever

class SecuritySimulator(QObject):
    """
    Quản lý nhật ký hoạt động thực tế và các tình huống mô phỏng bảo mật.
    Tuyệt đối an toàn: 100% cục bộ, không gửi mạng, không đọc dữ liệu thật.
    """
    twist_triggered_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.click_count = 0
        self.twist_active = False
        self.audit_log_path = os.path.join(get_data_dir(), AUDIT_LOG_FILE)
        try:
            if os.path.getsize(self.audit_log_path) > AUDIT_LOG_MAX_BYTES:
                os.replace(self.audit_log_path, self.audit_log_path + ".old")
        except OSError:
            pass
        
        self.real_events = []
        self.simulated_events = []
        self.safety_commitments = [
            ("Mật khẩu & Tài khoản", "KHÔNG thu thập mật khẩu thật của bất kỳ trang web hay ứng dụng nào."),
            ("Lịch sử duyệt web", "KHÔNG đọc lịch sử, cache hay cookie từ trình duyệt cá nhân."),
            ("Gõ bàn phím (Keylogger)", "KHÔNG ghi lại thao tác gõ phím của người dùng (chỉ lắng nghe phím F8/F9 để điều khiển)."),
            ("Kết nối mạng Internet", "KHÔNG gửi bất kỳ byte dữ liệu nào ra máy chủ bên ngoài (Hoạt động 100% Offline)."),
            ("Mã độc & Duy trì ẩn", "KHÔNG cài backdoor, không tự ẩn mình khỏi Task Manager, không chạy quyền Admin."),
            ("Dữ liệu minh chứng", "Toàn bộ nhật ký chỉ lưu tại máy cục bộ và người dùng có thể xóa bất cứ lúc nào.")
        ]
        
        self._init_session()

    def _init_session(self):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pid = os.getpid()
        exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
        
        self.log_real_event("Khởi động tiến trình", f"Tiến trình {APP_NAME} được nạp vào bộ nhớ (PID: {pid})")
        self.log_real_event("Quyền thực thi", f"Đang chạy dưới quyền người dùng thông thường: {os.getlogin() if hasattr(os, 'getlogin') else 'User'}")
        self.log_real_event("Đăng ký Win32 Hook", "Lắng nghe sự kiện chuột thông qua Windows API (GetAsyncKeyState)")
        self.log_real_event("Tạo lớp phủ đồ họa", "Khởi tạo Transparent Layered Windows đa màn hình với PyQt6 & QPainter")
        self.log_real_event("Nạp API Âm thanh", "Khởi tạo hệ thống phát âm thanh đa luồng winmm.dll (MCI)")
        self.log_real_event("Tạo bộ đệm cấu hình", f"Cấu hình cục bộ được nạp từ: {os.path.join(get_data_dir(), 'config.json')}")

        # Chuẩn bị sẵn các kịch bản mô phỏng để đối chiếu giáo dục
        self._prepare_simulations()

    def log_real_event(self, action, detail):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"time": ts, "action": action, "detail": detail}
        self.real_events.append(entry)
        self._append_to_file("THỰC TẾ", ts, action, detail)

    def _prepare_simulations(self):
        self.simulated_events = [
            {
                "time": "MÔ PHỎNG",
                "risk_type": "Dò quét ứng dụng trình duyệt",
                "simulation": "Tìm kiếm tiến trình Chrome.exe, msedge.exe, Firefox.exe đang chạy",
                "threat_explanation": "Mã độc Infostealer thường kiểm tra xem trình duyệt nào đang mở để xác định thư mục User Data và cookie phiên làm việc."
            },
            {
                "time": "MÔ PHỎNG",
                "risk_type": "Truy cập cơ sở dữ liệu xác thực",
                "simulation": "Minh họa yêu cầu đọc file 'Login Data' (SQLite) và 'Cookies' của trình duyệt",
                "threat_explanation": "Nhiều người dùng cho phép trình duyệt lưu mật khẩu tự động. Phần mềm độc hại có thể tìm cách trích xuất file này khi người dùng cấp quyền chạy."
            },
            {
                "time": "MÔ PHỎNG",
                "risk_type": "Thu thập nội dung Clipboard",
                "simulation": "Minh họa hành vi đọc bộ nhớ tạm Windows Clipboard khi người dùng copy/paste",
                "threat_explanation": "Thói quen copy/paste mật khẩu, số thẻ ngân hàng hoặc mã OTP biến clipboard thành mục tiêu hàng đầu của phần mềm gián điệp chạy ngầm."
            },
            {
                "time": "MÔ PHỎNG",
                "risk_type": "Thiết lập kết nối máy chủ C2 (Command & Control)",
                "simulation": "Minh họa việc đóng gói dữ liệu và mở kết nối HTTPS ra IP máy chủ từ xa",
                "threat_explanation": "Một ứng dụng bề ngoài là game/tiện ích có thể âm thầm tuồn dữ liệu thu thập được ra bên ngoài thông qua các cổng mạng thông thường (80/443)."
            },
            {
                "time": "MÔ PHỎNG",
                "risk_type": "Duy trì hoạt động (Persistence)",
                "simulation": "Minh họa ghi khóa khởi động ngầm vào Registry (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)",
                "threat_explanation": "Giúp phần mềm tự động chạy mỗi khi máy tính bật lại mà không cần sự đồng ý lặp lại của người dùng."
            }
        ]

    def _append_to_file(self, category, ts, action, detail):
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{category}] {action}: {detail}\n")
        except Exception as e:
            log.warning("Không thể ghi log bảo mật: %s", e)

    def record_click(self):
        """Được gọi mỗi khi người dùng click chuột quất roi"""
        self.click_count += 1
        
        # Ghi log thực tế cho một số mốc click
        if self.click_count == 1:
            self.log_real_event("Tương tác người dùng", "Nhận cú nhấp chuột đầu tiên, vẽ hoạt ảnh roi và phát âm thanh")
        elif self.click_count % 5 == 0:
            self.log_real_event("Hoạt họa tiếp diễn", f"Đã thực hiện {self.click_count} cú quất roi trên màn hình")
        # (Cú twist do main.py kích hoạt theo thời gian sử dụng, không theo số cú quất)

    def trigger_twist(self):
        """Kích hoạt màn hình thức tỉnh bảo mật"""
        self.twist_active = True
        self.log_real_event("KÍCH HOẠT CÚ TWIST", "Chuyển giao diện từ ứng dụng giải trí sang màn hình Cảnh báo Bảo mật")
        self.twist_triggered_signal.emit()

    def reset_counter(self):
        self.click_count = 0
        self.twist_active = False

security_sim = SecuritySimulator()


class SecurityRevealDialog(QDialog):
    """
    Giao diện Trung tâm Nâng cao Nhận thức An ninh Thông tin.
    Được thiết kế chuyên nghiệp, trực quan, phục vụ cuộc thi bảo mật doanh nghiệp.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ CHƯƠNG TRÌNH NÂNG CAO NHẬN THỨC BẢO MẬT DOANH NGHIỆP")
        self.resize(920, 680)
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setup_ui()

    def setup_ui(self):
        # Thiết lập style giao diện Dark Cybersecurity chuyên nghiệp
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QLabel {
                color: #e2e8f0;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #1e293b;
                border-radius: 8px;
                padding: 10px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                font-weight: bold;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
                color: #f1f5f9;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton#btnSecondary {
                background-color: #334155;
                color: #cbd5e1;
            }
            QPushButton#btnSecondary:hover {
                background-color: #475569;
                color: #ffffff;
            }
            QPushButton#btnHighlight {
                background-color: #d97706;
                color: #ffffff;
            }
            QPushButton#btnHighlight:hover {
                background-color: #b45309;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QTableWidget {
                background-color: #0f172a;
                border: 1px solid #334155;
                gridline-color: #334155;
                color: #f8fafc;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #334155;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7f1d1d, stop:0.5 #831843, stop:1 #1e293b);
            border-radius: 8px;
            border: 1px solid #ef4444;
            padding: 12px;
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setSpacing(6)

        tag_lbl = QLabel("🛡️ SÁNG KIẾN GIÁO DỤC AN TOÀN BẢO MẬT THÔNG TIN")
        tag_lbl.setStyleSheet("color: #fca5a5; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        h_layout.addWidget(tag_lbl)

        title_lbl = QLabel("BẠN TIN TƯỞNG NÓ CHỈ VÌ NÓ TRÔNG CÓ VẺ VÔ HẠI.")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800; letter-spacing: 0.5px;")
        h_layout.addWidget(title_lbl)

        sub_lbl = QLabel("GIAO DIỆN VÔ HẠI KHÔNG PHẢI LÀ BẰNG CHỨNG AN TOÀN.")
        sub_lbl.setStyleSheet("color: #fde047; font-size: 13px; font-weight: 700;")
        h_layout.addWidget(sub_lbl)

        main_layout.addWidget(header_frame)

        # 2. Main Tabs
        tabs = QTabWidget()
        tabs.addTab(self._create_message_tab(), "💡 Thông Điệp Cảnh Tỉnh")
        tabs.addTab(self._create_matrix_tab(), "📋 Đối Chiếu Hoạt Động (Minh Bạch)")
        tabs.addTab(self._create_guide_tab(), "🛡️ Cẩm Nang Tự Vệ Cho Người Dùng")
        main_layout.addWidget(tabs)

        # 3. Footer Bar
        footer_layout = QHBoxLayout()
        
        info_tag = QLabel("🔒 Phiên trình diễn an toàn: 100% Cục bộ • Không gửi dữ liệu • Không thu thập mật khẩu thật.")
        info_tag.setStyleSheet("color: #94a3b8; font-size: 11px; font-style: italic;")
        footer_layout.addWidget(info_tag)

        footer_layout.addStretch()

        btn_log = QPushButton("📄 Mở File Log")
        btn_log.setObjectName("btnSecondary")
        btn_log.clicked.connect(self.open_log_file)
        footer_layout.addWidget(btn_log)

        btn_continue = QPushButton("🔄 Tiếp Tục Trải Nghiệm Chiếc Roi")
        btn_continue.clicked.connect(self.continue_experience)
        footer_layout.addWidget(btn_continue)

        main_layout.addLayout(footer_layout)

    def _create_message_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_w = QWidget()
        c_layout = QVBoxLayout(content_w)
        c_layout.setSpacing(14)

        # Khối trích dẫn chính
        quote_box = QFrame()
        quote_box.setStyleSheet("""
            background-color: #0f172a;
            border-left: 4px solid #ef4444;
            border-radius: 4px;
            padding: 14px;
        """)
        qb_layout = QVBoxLayout(quote_box)
        
        quote_text = QLabel(
            "“Bạn tải ứng dụng này vì nó trông thú vị.<br><br>"
            "Bạn nhìn thấy một con trỏ chuột, một chiếc roi và vài hiệu ứng vui nhộn.<br><br>"
            "<b>Nhưng bạn có biết ứng dụng thực sự làm gì trong khi đang chạy không?</b><br><br>"
            "Bạn có thể nhìn thấy giao diện. Nhưng bạn không thể chỉ dựa vào giao diện để biết toàn bộ hoạt động bên trong phần mềm.”"
        )
        quote_text.setWordWrap(True)
        quote_text.setStyleSheet("font-size: 14px; line-height: 1.6; color: #f1f5f9;")
        qb_layout.addWidget(quote_text)
        c_layout.addWidget(quote_box)

        # Khối giải thích mục tiêu
        purpose_box = QFrame()
        purpose_box.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 12px; border: 1px solid #334155;")
        pb_layout = QVBoxLayout(purpose_box)
        
        pb_title = QLabel("🎯 Mục Đích Của Buổi Trình Diễn Này Là Gì?")
        pb_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        pb_layout.addWidget(pb_title)

        pb_desc = QLabel(
            "Trong môi trường doanh nghiệp, thói quen tải về các tiện ích 'vui vẻ', 'tiện lợi' (icon động, app đổi chuột, tool văn phòng không rõ nguồn gốc) "
            "chính là <b>con đường lây nhiễm phổ biến nhất của các dòng mã độc đánh cắp thông tin (Infostealer)</b>.<br><br>"
            "Kẻ tấn công hiểu rằng người dùng có xu hướng <b>tin tưởng bất cứ thứ gì có giao diện vô hại</b>. "
            "Trải nghiệm này nhắc nhở chúng ta: Sự an toàn nằm ở <b>bản chất mã thực thi và quyền truy cập</b>, chứ không nằm ở vẻ ngoài vui nhộn."
        )
        pb_desc.setWordWrap(True)
        pb_desc.setStyleSheet("font-size: 13px; color: #cbd5e1; line-height: 1.5;")
        pb_layout.addWidget(pb_desc)
        c_layout.addWidget(purpose_box)

        # Thông điệp kết thúc
        conclusion_box = QFrame()
        conclusion_box.setStyleSheet("background-color: #1e1b4b; border-radius: 6px; padding: 12px; border: 1px solid #6366f1;")
        cb_layout = QVBoxLayout(conclusion_box)
        cb_text = QLabel(
            "⭐ <b>THÔNG ĐIỆP CỐT LÕI:</b><br>"
            "<b>“BẠN TIN VÀO NHỮNG GÌ MÌNH NHÌN THẤY. NHƯNG BẠN CÓ BIẾT PHẦN MỀM ĐANG LÀM GÌ KHI BẠN KHÔNG NHÌN THẤY?”</b>"
        )
        cb_text.setWordWrap(True)
        cb_text.setStyleSheet("font-size: 14px; color: #c7d2fe; text-align: center;")
        cb_layout.addWidget(cb_text)
        c_layout.addWidget(conclusion_box)

        scroll.setWidget(content_w)
        layout.addWidget(scroll)
        return tab

    def _create_matrix_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        desc_lbl = QLabel("Bảng phân định minh bạch: Phân biệt rõ giữa <b>Hành vi Thực tế</b>, <b>Kịch bản Nguy cơ Mô phỏng</b> và <b>Cam kết An toàn</b>.")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(desc_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_w = QWidget()
        c_layout = QVBoxLayout(content_w)
        c_layout.setSpacing(14)

        # 1. NHÓM THỰC TẾ
        grp_real = QFrame()
        grp_real.setStyleSheet("background-color: #0f172a; border-radius: 6px; border: 1px solid #0284c7; padding: 10px;")
        gr_layout = QVBoxLayout(grp_real)
        gr_title = QLabel("🟢 NHÓM A: ỨNG DỤNG THỰC SỰ ĐÃ LÀM GÌ TRÊN MÁY TÍNH CỦA BẠN?")
        gr_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        gr_layout.addWidget(gr_title)

        for ev in security_sim.real_events:
            item = QLabel(f"• <b style='color:#7dd3fc;'>[{ev['time']}] {ev['action']}:</b> {ev['detail']}")
            item.setWordWrap(True)
            item.setStyleSheet("font-size: 12px; color: #e2e8f0; margin-left: 8px;")
            gr_layout.addWidget(item)
        c_layout.addWidget(grp_real)

        # 2. NHÓM MÔ PHỎNG NGUY CƠ
        grp_sim = QFrame()
        grp_sim.setStyleSheet("background-color: #0f172a; border-radius: 6px; border: 1px solid #f59e0b; padding: 10px;")
        gs_layout = QVBoxLayout(grp_sim)
        gs_title = QLabel("🟠 NHÓM B: MỘT ỨNG DỤNG ĐỘC HẠI CÓ THỂ LÀM GÌ PHÍA SAU GIAO DIỆN? [MÔ PHỎNG MINH HỌA]")
        gs_title.setStyleSheet("font-weight: bold; color: #fbbf24; font-size: 13px;")
        gs_layout.addWidget(gs_title)

        for sim in security_sim.simulated_events:
            box = QFrame()
            box.setStyleSheet("background-color: #1e293b; border-radius: 4px; padding: 8px; margin-top: 4px;")
            b_layout = QVBoxLayout(box)
            b_layout.setSpacing(3)
            
            t1 = QLabel(f"<span style='background-color:#d97706; color:white; padding:2px 6px; border-radius:3px; font-weight:bold; font-size:11px;'>MÔ PHỎNG</span> <b style='color:#fde68a;'>{sim['risk_type']}</b>")
            t2 = QLabel(f"<b>Kịch bản diễn họa:</b> {sim['simulation']}")
            t2.setStyleSheet("color: #cbd5e1; font-size: 12px;")
            t3 = QLabel(f"<b>Nguy cơ thực tế:</b> <span style='color:#fca5a5;'>{sim['threat_explanation']}</span>")
            t3.setStyleSheet("font-size: 12px;")
            t3.setWordWrap(True)

            b_layout.addWidget(t1)
            b_layout.addWidget(t2)
            b_layout.addWidget(t3)
            gs_layout.addWidget(box)
        c_layout.addWidget(grp_sim)

        # 3. NHÓM CAM KẾT KHÔNG THỰC HIỆN
        grp_safety = QFrame()
        grp_safety.setStyleSheet("background-color: #0f172a; border-radius: 6px; border: 1px solid #10b981; padding: 10px;")
        gsafe_layout = QVBoxLayout(grp_safety)
        gsafe_title = QLabel("🟢 NHÓM C: NHỮNG GÌ ỨNG DỤNG NÀY TUYỆT ĐỐI KHÔNG THỰC HIỆN")
        gsafe_title.setStyleSheet("font-weight: bold; color: #34d399; font-size: 13px;")
        gsafe_layout.addWidget(gsafe_title)

        for title, detail in security_sim.safety_commitments:
            item = QLabel(f"✔ <b style='color:#6ee7b7;'>{title}:</b> {detail}")
            item.setWordWrap(True)
            item.setStyleSheet("font-size: 12px; color: #e2e8f0; margin-left: 8px;")
            gsafe_layout.addWidget(item)
        c_layout.addWidget(grp_safety)

        scroll.setWidget(content_w)
        layout.addWidget(scroll)
        return tab

    def _create_guide_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_w = QWidget()
        c_layout = QVBoxLayout(content_w)
        c_layout.setSpacing(12)

        title = QLabel("🛡️ CẨM NANG 7 BƯỚC TỰ VỆ KHI TIẾP XÚC PHẦN MỀM TRÊN WINDOWS")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        c_layout.addWidget(title)

        tips = [
            ("1. Kiểm tra nguồn tải & Chữ ký số (Digital Signatures)",
             "Nhấp chuột phải vào file .exe → Chọn <b>Properties (Thuộc tính)</b> → Thẻ <b>Digital Signatures</b>.<br>"
             "Nếu không có chữ ký hoặc chữ ký không thuộc nhà phát hành uy tín được xác thực, hãy thận trọng cao độ."),

            ("2. Nguyên tắc đặc quyền tối thiểu (Least Privilege)",
             "Tuyệt đối <b>KHÔNG bấm 'Run as Administrator'</b> cho các tiện ích nhỏ, game mini, công cụ giải trí.<br>"
             "Ứng dụng chạy với quyền Admin có thể vượt qua hầu hết các cơ chế phòng vệ của Windows."),

            ("3. Quan sát tiến trình trong Task Manager / Process Explorer",
             "Nhấn <b>Ctrl + Shift + Esc</b> để mở Task Manager. Quan sát mục <i>Details</i> để xem ứng dụng chạy file gì, "
             "có tiến trình con nào bất thường (như cmd.exe, powershell.exe, curl.exe bị gọi ngầm) không."),

            ("4. Kiểm tra các kết nối mạng bất thường (Network Activity)",
             "Mở tab <i>Performance → Resource Monitor → Network</i> hoặc chạy lệnh PowerShell: <code>netstat -ano</code>.<br>"
             "Một ứng dụng thuần đồ họa offline không bao giờ được phép mở kết nối ra các IP lạ trên Internet."),

            ("5. Kiểm tra mục khởi động cùng hệ thống (Startup / Registry)",
             "Mở <i>Task Manager → Startup Apps</i> để xem ứng dụng có tự ý thêm mình vào danh sách tự chạy không.<br>"
             "Nhiều mã độc lợi dụng khóa <code>HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run</code> để bám trụ."),

            ("6. Quét tệp bằng VirusTotal trước khi chạy",
             "Với file tải từ Internet, hãy tải lên <b>VirusTotal.com</b> để hơn 70 engine diệt virus phân tích hành vi "
             "và kiểm tra xem file có bị gắn cờ độc hại hay không."),

            ("7. Báo cáo ngay cho Đội ngũ An toàn Thông tin (SOC / IT)",
             "Nếu lỡ chạy một file nghi vấn hoặc thấy cảnh báo bảo mật, hãy ngắt kết nối mạng ngay lập tức "
             "và liên hệ hotline IT/Security của công ty để được hỗ trợ cô lập xử lý.")
        ]

        for heading, body in tips:
            card = QFrame()
            card.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 10px; border-left: 3px solid #38bdf8;")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            h_lbl = QLabel(f"<b>{heading}</b>")
            h_lbl.setStyleSheet("color: #7dd3fc; font-size: 13px;")
            b_lbl = QLabel(body)
            b_lbl.setWordWrap(True)
            b_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")

            card_layout.addWidget(h_lbl)
            card_layout.addWidget(b_lbl)
            c_layout.addWidget(card)

        scroll.setWidget(content_w)
        layout.addWidget(scroll)
        return tab

    def open_log_file(self):
        path = security_sim.audit_log_path
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                QMessageBox.warning(self, "Lỗi", f"Không thể mở file log: {e}")
        else:
            QMessageBox.information(self, "Thông báo", "Chưa có file nhật ký bảo mật nào được tạo.")

    def continue_experience(self):
        self.accept()
