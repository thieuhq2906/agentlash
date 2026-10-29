import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal

user32 = ctypes.windll.user32

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_F8 = 0x77
SM_SWAPBUTTON = 23

class GlobalMouseHook(QThread):
    """
    Polls the physical mouse button / hotkey state.
    Cursor coordinates are NOT read here: GetCursorPos returns physical pixels, while Qt draws in
    logical (DPI-scaled) pixels, so the GUI thread reads QCursor.pos() instead.
    """
    click_event = pyqtSignal()
    hotkey_event = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True
        self.was_click_down = False
        self.was_f8_down = False

    def primary_button_vk(self):
        # GetAsyncKeyState reports physical buttons; left-handed users have the primary button on the right
        return VK_RBUTTON if user32.GetSystemMetrics(SM_SWAPBUTTON) else VK_LBUTTON

    def run(self):
        vk_click = self.primary_button_vk()
        last_swap_check = time.monotonic()
        while self.running:
            now = time.monotonic()
            if now - last_swap_check > 2.0:
                vk_click = self.primary_button_vk()
                last_swap_check = now

            # 1. Primary mouse button (edge-triggered on press)
            is_click_down = bool(user32.GetAsyncKeyState(vk_click) & 0x8000)
            if is_click_down and not self.was_click_down:
                self.click_event.emit()
            self.was_click_down = is_click_down

            # 2. Toggle Hotkey (F8)
            is_f8_down = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
            if is_f8_down and not self.was_f8_down:
                self.hotkey_event.emit()
            self.was_f8_down = is_f8_down

            # Sleep 5ms for ~200Hz polling rate (undetectable latency, <0.1% CPU)
            time.sleep(0.005)

    def stop(self):
        self.running = False
        self.wait(1000)
