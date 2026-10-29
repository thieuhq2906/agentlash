import sys
import os
import ctypes
import shutil
import logging
import traceback
from logging.handlers import RotatingFileHandler
from PyQt6.QtGui import QIcon, QAction, QActionGroup
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox
)

from config import config, get_asset_path, get_base_dir, get_bundle_dir, get_data_dir, APP_NAME
from overlay import WhipScene
from global_hook import GlobalMouseHook
from sound_player import sound_player

APP_TITLE = "AgentLash"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
ERROR_ALREADY_EXISTS = 183

log = logging.getLogger(APP_NAME)

def setup_logging():
    handler = RotatingFileHandler(os.path.join(get_data_dir(), f"{APP_NAME}.log"),
                                  maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    # Without a custom excepthook PyQt6 aborts the whole app on any exception raised inside a slot
    def excepthook(exc_type, exc, tb):
        log.error("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.excepthook = excepthook

def acquire_single_instance():
    """Returns the mutex handle, or None if another copy is already running"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}_SingleInstance")
    if handle and ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle

class AgentLashApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName(APP_NAME)

        # App Icon
        icon_path = get_asset_path(os.path.join("assets", "app_icon.png"))
        if os.path.exists(icon_path):
            self.icon = QIcon(icon_path)
            self.app.setWindowIcon(self.icon)
        else:
            self.icon = QIcon()

        # Overlay windows (one per monitor) + animation loop
        self.scene = WhipScene()
        sound_player.preload()

        # Create System Tray
        self.create_tray_icon()

        # Start Global Input Hook
        self.hook = GlobalMouseHook()
        self.hook.click_event.connect(self.scene.on_mouse_click)
        self.hook.hotkey_event.connect(self.toggle_active)
        self.hook.start()

        self.app.aboutToQuit.connect(self.cleanup)

        # Notify user
        if QSystemTrayIcon.isSystemTrayAvailable():
            if config.get("active", True):
                msg = "Đã kích hoạt! Click chuột bất cứ đâu trên màn hình để quất roi.\nPhím F8: Bật/Tắt nhanh."
            else:
                msg = "Đang TẠM DỪNG. Bấm F8 (hoặc menu ở khay hệ thống) để bật lại."
            self.tray.showMessage(f"{APP_TITLE} 💥", msg, QSystemTrayIcon.MessageIcon.Information, 3000)

    def add_choice_menu(self, parent, title, key, options, on_select=None, checked_if=None):
        """Submenu of exclusive checkable actions bound to one config key"""
        submenu = parent.addMenu(title)
        group = QActionGroup(submenu)
        group.setExclusive(True)
        current = config.get(key)
        actions = {}
        for value, label in options:
            act = QAction(label, submenu, checkable=True)
            act.setChecked(checked_if(value) if checked_if else current == value)
            act.triggered.connect(lambda _=False, v=value: (on_select or (lambda x: config.set(key, x)))(v))
            group.addAction(act)
            submenu.addAction(act)
            actions[value] = act
        return submenu, actions

    def add_toggle(self, menu, label, key):
        act = QAction(label, menu, checkable=True)
        act.setChecked(config.get(key, True))
        act.toggled.connect(lambda val: self.set_option(key, val))
        menu.addAction(act)
        return act

    def create_tray_icon(self):
        self.tray = QSystemTrayIcon(self.icon, self.app)
        self.tray.setToolTip(f"{APP_TITLE}\nPhím F8: Bật/Tắt")
        self.tray.activated.connect(self.on_tray_activated)

        # Keep a reference: QSystemTrayIcon does not own its context menu
        self.menu = menu = QMenu()

        # Title
        title_action = menu.addAction("💥 AGENTLASH")
        title_action.setEnabled(False)

        # Toggle Active
        self.toggle_action = menu.addAction("")
        self.toggle_action.triggered.connect(self.toggle_active)
        self.refresh_toggle_text()

        menu.addSeparator()

        # --- STYLE SELECTION ---
        self.add_choice_menu(menu, "🎨 Chọn Kiểu Roi", "whip_style", [
            ("comic", "💥 Comic Pop-Art (Nổ POW!)"),
            ("cyber", "⚡ Cyberpunk Neon (Tia điện ZAP!)"),
            ("classic", "🤠 Classic Western (Da bện CRACK!)"),
        ], on_select=self.set_style)

        # --- SOUND SELECTION ---
        sound_menu, _ = self.add_choice_menu(menu, "🔊 Âm Thanh", "sound_mode", [
            ("themed", "💥 Quất roi theo kiểu (Comic/Cyber/Classic)"),
            ("random", "🎲 Ngẫu nhiên các âm thanh"),
            ("mute", "🔇 Tắt âm thanh"),
        ], on_select=self.set_sound_mode,
            checked_if=lambda v: (not config.get("sound_enabled", True)) if v == "mute"
            else (config.get("sound_enabled", True) and config.get("sound_mode") == v))

        sound_menu.addSeparator()
        self.add_choice_menu(sound_menu, "🔉 Âm lượng", "volume", [
            (1.0, "100%"), (0.75, "75%"), (0.5, "50%"), (0.25, "25%"),
        ], checked_if=lambda v: abs(config.get("volume", 1.0) - v) < 0.01)

        # --- ANIMATION OPTIONS ---
        fx_menu = menu.addMenu("⚙️ Tùy Chọn Hoạt Ảnh")
        self.add_toggle(fx_menu, "Cán roi bám theo chuột", "show_cursor_whip")
        self.add_toggle(fx_menu, "Hoạt ảnh vung dây roi", "whip_animation")
        self.add_toggle(fx_menu, "Hoạt ảnh nổ khi trúng đòn (POW/ZAP/CRACK)", "pow_animation")
        self.add_toggle(fx_menu, "Dùng hoạt ảnh tùy chỉnh (nếu có)", "custom_animation_enabled")
        fx_menu.addSeparator()
        speed = config.get("strike_speed_ms", 180)
        self.add_choice_menu(fx_menu, "⏱️ Tốc độ quất", "strike_speed_ms", [
            (120, "Rất nhanh"), (180, "Nhanh (mặc định)"), (260, "Vừa"), (380, "Chậm"),
        ], checked_if=lambda v: v == speed or (v == 180 and speed not in (120, 180, 260, 380)))

        menu.addSeparator()

        # Folders
        open_anim_act = menu.addAction("📂 Mở thư mục hoạt ảnh tùy chỉnh (GIF/PNG)")
        open_anim_act.triggered.connect(lambda: self.open_folder("custom_animation"))

        open_sound_act = menu.addAction("📂 Mở thư mục âm thanh tùy chỉnh (WAV/MP3)")
        open_sound_act.triggered.connect(lambda: self.open_folder("custom_sounds"))

        if getattr(sys, "frozen", False):
            self.autostart_action = QAction("🚀 Khởi động cùng Windows", menu, checkable=True)
            self.autostart_action.setChecked(self.is_autostart_enabled())
            self.autostart_action.toggled.connect(self.set_autostart)
            menu.addAction(self.autostart_action)

        # Instructions / About
        about_act = menu.addAction("ℹ️ Hướng Dẫn Sử Dụng")
        about_act.triggered.connect(self.show_about)

        menu.addSeparator()

        # Exit
        exit_action = menu.addAction("❌ Thoát (Exit)")
        exit_action.triggered.connect(self.exit_app)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_active()

    def set_option(self, key, value):
        config.set(key, value)
        self.scene.wake()

    def set_style(self, style):
        config.set("whip_style", style)
        sound_player.preload()
        self.scene.wake()

    def set_sound_mode(self, mode):
        if mode == "mute":
            config.set("sound_enabled", False)
            return
        config.set("sound_enabled", True)
        config.set("sound_mode", mode)
        sound_player.preload()

    def refresh_toggle_text(self):
        on = config.get("active", True)
        self.toggle_action.setText("⚡ Đang Bật (Bấm F8 để Tắt)" if on else "⏸️ Đang Tắt (Bấm F8 để Bật)")

    def toggle_active(self):
        new_state = not config.get("active", True)
        config.set("active", new_state)
        self.scene.set_active(new_state)
        self.refresh_toggle_text()
        if QSystemTrayIcon.isSystemTrayAvailable():
            status_text = "Đã bật hiệu ứng quất roi!" if new_state else "Đã tạm dừng hiệu ứng."
            self.tray.showMessage("AgentLash", status_text, QSystemTrayIcon.MessageIcon.Information, 1500)

    def open_folder(self, name):
        folder = os.path.join(get_base_dir(), "assets", name)
        try:
            os.makedirs(folder, exist_ok=True)
            readme = os.path.join(folder, "README.txt")
            bundled_readme = os.path.join(get_bundle_dir(), "assets", name, "README.txt")
            if not os.path.exists(readme) and os.path.exists(bundled_readme):
                shutil.copyfile(bundled_readme, readme)
            os.startfile(folder)
        except OSError as e:
            QMessageBox.warning(None, APP_TITLE, f"Không mở được thư mục:\n{folder}\n\n{e}")

    # ---------- Start with Windows ----------
    def autostart_command(self):
        return f'"{sys.executable}"'

    def is_autostart_enabled(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                return value == self.autostart_command()
        except OSError:
            return False

    def set_autostart(self, enable):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, self.autostart_command())
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
        except OSError as e:
            log.error("Cannot change autostart: %s", e)
            QMessageBox.warning(None, APP_TITLE, f"Không thay đổi được cài đặt khởi động:\n{e}")

    def show_about(self):
        QMessageBox.information(
            None,
            "AgentLash",
            "💥 ỨNG DỤNG ROI DA GIẢI TRÍ KHI ĐỢI AGENT 💥\n\n"
            "• Click chuột trái bất cứ đâu trên màn hình để quất roi!\n"
            "• Phím F8 (hoặc nhấp đúp icon ở khay hệ thống): Bật/Tắt nhanh.\n"
            "• 3 Kiểu roi độc đáo: Comic Pop-Art (POW!), Cyberpunk Neon (ZAP!), Classic Western (CRACK!).\n"
            "• Tiếng quất roi đanh gọn theo từng kiểu roi (thêm tiếng của bạn vào thư mục 'custom_sounds').\n"
            "• Hoạt ảnh riêng: thả file .gif / .png (hoặc chuỗi frame_01.png, frame_02.png...) vào thư mục 'custom_animation'.\n"
            "• Âm thanh riêng: thả file .wav / .mp3 vào thư mục 'custom_sounds'.\n"
            "  (Không cần khởi động lại, ứng dụng tự nhận file mới.)\n\n"
            "Chúc bạn quất agent thật vui vẻ trong lúc đợi hoàn thành task! 😄"
        )

    def cleanup(self):
        self.hook.stop()
        self.scene.shutdown()
        sound_player.close()
        self.tray.hide()

    def exit_app(self):
        self.app.quit()

    def run(self):
        return self.app.exec()

def main():
    setup_logging()
    mutex = acquire_single_instance()
    if mutex is None:
        app = QApplication(sys.argv)
        QMessageBox.information(None, APP_TITLE,
                                "AgentLash đang chạy rồi!\nXem icon ở khay hệ thống (góc phải dưới màn hình).")
        return 0
    try:
        return AgentLashApp().run()
    except Exception:
        log.exception("Fatal error")
        raise

if __name__ == "__main__":
    sys.exit(main())
