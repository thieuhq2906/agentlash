import math
import random
import ctypes
import logging
from ctypes import wintypes
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QObject
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QCursor, QPolygonF, QGuiApplication
from PyQt6.QtWidgets import QWidget, QApplication

from config import config
from whip_physics import IdleWhipPhysics, ActiveStrike, SparkParticle, HANDLE_LENGTH
from impact_animation import ImpactManager
from sound_player import sound_player

user32 = ctypes.windll.user32
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_NOOWNERZORDER = 0x0001, 0x0002, 0x0010, 0x0200

FRAME_MS = 16
AUDIO_LEAD_MS = 35  # start the crack sound this much before the visual crack (audio output latency)
IDLE_FRAME_MS = 50
STRIKE_REACH = 175.0  # distance from the swinging hand to the click point
TIP_TRAIL_FRAMES = 9   # frames of tip positions kept for the motion streak
GHOST_FRAMES = 3       # previous cord shapes drawn as fading afterimages

# Accent colour of the tip streak / crack flash per weapon
STRIKE_ACCENT = {
    "comic": (255, 220, 0), "cyber": (0, 240, 255), "classic": (255, 214, 150),
    "taser": (125, 211, 252), "sword": (226, 232, 240),
}

log = logging.getLogger(__name__)

# Cord colour layers per style: (colour, width at handle, width at tip), drawn back to front
CORD_LAYERS = {
    "comic": [((0, 0, 0, 255), 9.0, 3.6), ((230, 35, 35, 255), 5.6, 1.8), ((255, 228, 0, 255), 2.6, 0.7)],
    "cyber": [((255, 0, 150, 80), 15.0, 6.0), ((0, 240, 255, 235), 6.0, 2.2), ((255, 255, 255, 255), 2.4, 0.8)],
    "classic": [((40, 22, 8, 220), 7.5, 2.4), ((135, 78, 34, 255), 5.0, 1.4), ((200, 140, 80, 200), 1.6, 0.4)],
    "taser": [((20, 24, 30, 255), 9.0, 4.5), ((234, 179, 8, 255), 5.5, 2.4), ((56, 189, 248, 255), 2.5, 1.0)],
    "sword": [((30, 41, 59, 240), 9.0, 1.5), ((148, 163, 184, 255), 7.0, 1.2), ((248, 250, 252, 255), 3.0, 0.8)],
}

# Geometry works on plain (x, y) float tuples: calling QPointF.x()/.y() hundreds of thousands of times per
# second was the main cost of drawing whips.
def smooth_xy(xy, subdivisions=3):
    """Catmull-Rom smoothing of a polyline given as (x, y) tuples"""
    n = len(xy)
    if n < 3:
        return list(xy)
    steps = [(k / subdivisions, (k / subdivisions) ** 2, (k / subdivisions) ** 3) for k in range(subdivisions)]
    out = []
    for i in range(n - 1):
        x0, y0 = xy[i - 1 if i else 0]
        x1, y1 = xy[i]
        x2, y2 = xy[i + 1]
        x3, y3 = xy[i + 2 if i + 2 < n else n - 1]
        ax, ay = -x0 + 3 * x1 - 3 * x2 + x3, -y0 + 3 * y1 - 3 * y2 + y3
        bx, by = 2 * x0 - 5 * x1 + 4 * x2 - x3, 2 * y0 - 5 * y1 + 4 * y2 - y3
        cx, cy = x2 - x0, y2 - y0
        for t, t2, t3 in steps:
            out.append((x1 + 0.5 * (cx * t + bx * t2 + ax * t3), y1 + 0.5 * (cy * t + by * t2 + ay * t3)))
    out.append(xy[-1])
    return out

def ribbon_frame(sxy):
    """(x, y, normal_x, normal_y) for every point of a smoothed polyline"""
    n = len(sxy)
    frame = []
    for i, (x, y) in enumerate(sxy):
        ax, ay = sxy[i - 1] if i else sxy[0]
        bx, by = sxy[i + 1] if i + 1 < n else sxy[-1]
        tx, ty = bx - ax, by - ay
        tl = math.hypot(tx, ty) or 1.0
        frame.append((x, y, -ty / tl, tx / tl))
    return frame

def ribbon_polygon(frame, w_start, w_end):
    """Filled polygon along a ribbon frame whose width shrinks from w_start to w_end (whip thinning to the tip)"""
    n = len(frame)
    k = (w_end - w_start) / (n - 1) if n > 1 else 0.0
    left, right = [], []
    for i, (x, y, nx, ny) in enumerate(frame):
        h = (w_start + k * i) / 2.0
        left.append(QPointF(x + nx * h, y + ny * h))
        right.append(QPointF(x - nx * h, y - ny * h))
    right.reverse()
    return QPolygonF(left + right)

def cord_frame(pts, subdivisions=3):
    return ribbon_frame(smooth_xy([(p.x(), p.y()) for p in pts], subdivisions))

def catmull_rom(pts, subdivisions=3):
    """Smooths a polyline by inserting Catmull-Rom samples between points"""
    return [QPointF(x, y) for x, y in smooth_xy([(p.x(), p.y()) for p in pts], subdivisions)]

def tapered_ribbon(pts, w_start, w_end):
    """Filled polygon following pts whose width shrinks from w_start to w_end"""
    return ribbon_polygon(ribbon_frame([(p.x(), p.y()) for p in pts]), w_start, w_end)

def points_rect(pts, margin):
    xs = [p.x() for p in pts]
    ys = [p.y() for p in pts]
    return QRectF(min(xs) - margin, min(ys) - margin, max(xs) - min(xs) + 2 * margin, max(ys) - min(ys) + 2 * margin)

def draw_cord(painter, pts, style, alpha=1.0, width_scale=1.0, frame=None):
    if len(pts) < 2:
        return
    if frame is None:
        frame = cord_frame(pts)
    smooth = [QPointF(frame[0][0], frame[0][1]), QPointF(frame[-2][0], frame[-2][1]), QPointF(frame[-1][0], frame[-1][1])]
    painter.setPen(Qt.PenStyle.NoPen)
    for (r, g, b, a), w0, w1 in CORD_LAYERS.get(style, CORD_LAYERS["comic"]):
        painter.setBrush(QColor(r, g, b, int(a * alpha)))
        painter.drawPolygon(ribbon_polygon(frame, w0 * width_scale, w1 * width_scale))
        # Round the thick end so it tucks into the handle cleanly
        painter.drawEllipse(smooth[0], w0 * width_scale / 2, w0 * width_scale / 2)
    if style == "classic":
        # Red "popper" at the tip of a bullwhip
        painter.setBrush(QColor(230, 30, 30, int(255 * alpha)))
        painter.drawEllipse(smooth[-1], 2.6 * width_scale, 2.6 * width_scale)
    elif style == "taser":
        # Đầu 2 chấu điện cực chích điện & hồ quang phóng ra
        tip = smooth[-1]
        p_prev = smooth[-2] if len(smooth) >= 2 else tip
        ang = math.degrees(math.atan2(tip.y() - p_prev.y(), tip.x() - p_prev.x()))
        painter.save()
        painter.translate(tip)
        painter.rotate(ang)
        painter.setPen(QPen(QColor(226, 232, 240, int(255 * alpha)), 2.0 * width_scale))
        painter.drawLine(QPointF(0, -4.5 * width_scale), QPointF(7 * width_scale, -4.5 * width_scale))
        painter.drawLine(QPointF(0, 4.5 * width_scale), QPointF(7 * width_scale, 4.5 * width_scale))
        painter.setPen(QPen(QColor(56, 189, 248, int(255 * alpha)), 1.8 * width_scale))
        jitter = random.uniform(-2.5, 2.5) * width_scale
        painter.drawLine(QPointF(7 * width_scale, -4.5 * width_scale), QPointF(5 * width_scale + jitter, 0))
        painter.drawLine(QPointF(5 * width_scale + jitter, 0), QPointF(7 * width_scale, 4.5 * width_scale))
        painter.restore()
    elif style == "sword":
        # Mũi kiếm sắc nhọn vát nhọn
        tip = smooth[-1]
        p_prev = smooth[-2] if len(smooth) >= 2 else tip
        ang = math.degrees(math.atan2(tip.y() - p_prev.y(), tip.x() - p_prev.x()))
        painter.save()
        painter.translate(tip)
        painter.rotate(ang)
        sword_tip = QPolygonF([
            QPointF(11 * width_scale, 0),
            QPointF(-2 * width_scale, -3.5 * width_scale),
            QPointF(-2 * width_scale, 3.5 * width_scale)
        ])
        painter.setPen(QPen(QColor(148, 163, 184, int(255 * alpha)), 1.2))
        painter.setBrush(QColor(248, 250, 252, int(255 * alpha)))
        painter.drawPolygon(sword_tip)
        painter.restore()

def draw_ghost(painter, frame, style, alpha, width_scale=1.0):
    """Cheap single-layer silhouette of a previous cord shape (ribbon frame), used for motion afterimages"""
    (r, g, b, a), w0, w1 = CORD_LAYERS.get(style, CORD_LAYERS["comic"])[1]
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(r, g, b, int(a * alpha)))
    painter.drawPolygon(ribbon_polygon(frame, w0 * width_scale, w1 * width_scale))

def draw_handle(painter, butt: QPointF, angle_deg, style, alpha=1.0, scale=1.0):
    """Vector-drawn whip handle from butt (held end) along angle_deg, HANDLE_LENGTH long"""
    L = HANDLE_LENGTH * scale
    W = 11.0 * scale
    painter.save()
    painter.translate(butt)
    painter.rotate(angle_deg)
    painter.setOpacity(painter.opacity() * alpha)
    body = QRectF(0, -W / 2, L, W)

    if style == "cyber":
        painter.setPen(QPen(QColor(0, 240, 255, 90), 6 * scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 4 * scale, 4 * scale)  # glow
        painter.setPen(QPen(QColor(0, 240, 255), 1.6 * scale))
        painter.setBrush(QColor(28, 32, 44))
        painter.drawRoundedRect(body, 4 * scale, 4 * scale)
        painter.setPen(QPen(QColor(0, 240, 255, 220), 1.4 * scale))
        for x in range(int(10 * scale), int(L - 6 * scale), max(3, int(6 * scale))):
            painter.drawLine(QPointF(x, -2.5 * scale), QPointF(x, 2.5 * scale))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0 * scale))
        painter.drawLine(QPointF(4 * scale, 0), QPointF(L - 4 * scale, 0))
        painter.setPen(QPen(QColor(255, 0, 150), 1.5 * scale))
        painter.setBrush(QColor(200, 0, 120))
        painter.drawEllipse(QPointF(0, 0), 6.5 * scale, 6.5 * scale)
        painter.setBrush(QColor(0, 240, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(L - 5 * scale, -W / 2 - 1 * scale, 5 * scale, W + 2 * scale))
    elif style == "classic":
        painter.setPen(QPen(QColor(45, 25, 10), 1.6 * scale))
        painter.setBrush(QColor(110, 62, 28))
        painter.drawRoundedRect(body, 3 * scale, 3 * scale)
        painter.setPen(QPen(QColor(70, 38, 15, 220), 1.1 * scale))
        painter.setClipRect(body)
        for x in range(-int(W), int(L), max(3, int(5 * scale))):
            painter.drawLine(QPointF(x, -W / 2), QPointF(x + W, W / 2))
            painter.drawLine(QPointF(x + W, -W / 2), QPointF(x, W / 2))
        painter.setClipping(False)
        painter.setPen(QPen(QColor(120, 90, 25), 1.2 * scale))
        painter.setBrush(QColor(212, 170, 70))
        painter.drawEllipse(QPointF(0, 0), 6.5 * scale, 6.5 * scale)
        painter.drawRect(QRectF(L - 5 * scale, -W / 2 - 0.5 * scale, 5 * scale, W + 1 * scale))
    elif style == "taser":
        # Kìm chích điện Cam-pu-chia
        painter.setPen(QPen(QColor(15, 15, 20), 1.8 * scale))
        painter.setBrush(QColor(30, 35, 42))
        painter.drawRoundedRect(body, 3 * scale, 3 * scale)
        painter.setClipRect(body)
        painter.setPen(QPen(QColor(234, 179, 8, 220), 2.5 * scale))
        for x in range(-10, int(L) + 10, max(4, int(7 * scale))):
            painter.drawLine(QPointF(x, -W / 2), QPointF(x + 5 * scale, W / 2))
        painter.setClipping(False)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(239, 68, 68))
        painter.drawEllipse(QPointF(10 * scale, -1 * scale), 2.5 * scale, 2.5 * scale)
        painter.setPen(QPen(QColor(226, 232, 240), 1.8 * scale))
        painter.drawLine(QPointF(L, -3.5 * scale), QPointF(L + 5 * scale, -3.5 * scale))
        painter.drawLine(QPointF(L, 3.5 * scale), QPointF(L + 5 * scale, 3.5 * scale))
    elif style == "sword":
        # Thanh kiếm Trảm: Crossguard mạ vàng + chuôi bọc da sẫm
        painter.setPen(QPen(QColor(180, 83, 9), 1.5 * scale))
        painter.setBrush(QColor(245, 158, 11))
        painter.drawRoundedRect(QRectF(L - 4 * scale, -14 * scale, 6 * scale, 28 * scale), 2 * scale, 2 * scale)
        painter.setPen(QPen(QColor(30, 20, 15), 1.5 * scale))
        painter.setBrush(QColor(67, 35, 18))
        painter.drawRoundedRect(QRectF(2 * scale, -W / 2, L - 6 * scale, W), 2 * scale, 2 * scale)
        painter.setPen(QPen(QColor(217, 119, 6), 1.0 * scale))
        for x in range(int(4 * scale), int(L - 6 * scale), max(3, int(5 * scale))):
            painter.drawLine(QPointF(x, -W / 2), QPointF(x + 2 * scale, W / 2))
        painter.setBrush(QColor(217, 119, 6))
        painter.drawEllipse(QPointF(0, 0), 6.5 * scale, 6.5 * scale)
    else:  # comic
        painter.setPen(QPen(QColor(0, 0, 0), 2.4 * scale))
        painter.setBrush(QColor(225, 35, 35))
        painter.drawRoundedRect(body, 4 * scale, 4 * scale)
        painter.setClipRect(body)
        painter.setPen(QPen(QColor(255, 214, 0), 3.0 * scale))
        for x in range(int(4 * scale), int(L + 6 * scale), max(4, int(8 * scale))):
            painter.drawLine(QPointF(x, -W / 2), QPointF(x + 6 * scale, W / 2))
        painter.setClipping(False)
        painter.setPen(QPen(QColor(0, 0, 0), 2.4 * scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 4 * scale, 4 * scale)
        painter.setBrush(QColor(225, 35, 35))
        painter.drawEllipse(QPointF(0, 0), 7.0 * scale, 7.0 * scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawEllipse(QPointF(-2 * scale, -2.5 * scale), 2.0 * scale, 2.0 * scale)
        painter.setBrush(QColor(0, 0, 0))
        painter.drawRect(QRectF(L - 4 * scale, -W / 2 - 1 * scale, 4 * scale, W + 2 * scale))
    painter.restore()

class OverlayWindow(QWidget):
    """Transparent, click-through, always-on-top window covering one monitor. Paints the shared scene."""
    def __init__(self, scene, screen):
        super().__init__()
        self.scene = scene
        self.screen_ref = screen
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.sync_geometry()

    def sync_geometry(self):
        # 1px shorter than the monitor so Windows doesn't treat it as a fullscreen app (taskbar / notifications)
        self.global_rect = QRectF(self.screen_ref.geometry().adjusted(0, 0, 0, -1))
        self.setGeometry(self.global_rect.toRect())

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_win32_clickthrough()

    def apply_win32_clickthrough(self):
        try:
            hwnd = int(self.winId())
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        except Exception as e:
            log.warning("Error applying win32 click-through: %s", e)

    def keep_on_top(self):
        if self.isVisible():
            user32.SetWindowPos(int(self.winId()), HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)

    def invalidate_global(self, rect: QRectF):
        local = rect.intersected(self.global_rect)
        if not local.isEmpty():
            local.translate(-self.global_rect.topLeft())
            self.update(local.toAlignedRect().adjusted(-2, -2, 2, 2))

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.translate(-self.global_rect.topLeft())
            # Only draw what touches the area being repainted (each monitor has its own window)
            visible = QRectF(event.rect()).translated(self.global_rect.topLeft())
            self.scene.render(painter, visible)
        except Exception:
            log.exception("Error while painting overlay")
        finally:
            painter.end()

class WhipScene(QObject):
    """Owns the animation state (in global logical coordinates) and one OverlayWindow per monitor"""
    def __init__(self):
        super().__init__()
        self.windows = []
        self.idle_whip = IdleWhipPhysics()
        self.active_strikes = []
        self.sparks = []
        self.impact_mgr = ImpactManager()
        self.prev_dirty = QRectF()
        self.still_frames = 0
        self.active = False

        # Animation timer (~60 FPS)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)

        # Other always-on-top windows (Task Manager, video players...) can cover us; re-assert periodically
        self.topmost_timer = QTimer(self)
        self.topmost_timer.timeout.connect(self.keep_on_top)

        app = QGuiApplication.instance()
        app.screenAdded.connect(self.on_screens_changed)
        app.screenRemoved.connect(self.on_screens_changed)
        self.rebuild_windows()
        self.set_active(config.get("active", True))
        self.impact_mgr.prewarm(config.get("whip_style", "comic"))

    # ---------- windows / screens ----------
    def rebuild_windows(self):
        for w in self.windows:
            w.close()
        self.windows = []
        for screen in QGuiApplication.screens():
            try:
                screen.geometryChanged.disconnect(self.on_screens_changed)
            except TypeError:
                pass
            screen.geometryChanged.connect(self.on_screens_changed)
            self.windows.append(OverlayWindow(self, screen))
        if self.active:
            for w in self.windows:
                w.show()
        self.prev_dirty = QRectF()

    def on_screens_changed(self, *args):
        # Defer: Qt is still updating its screen list when these signals fire
        QTimer.singleShot(300, self.rebuild_windows)

    def keep_on_top(self):
        for w in self.windows:
            w.keep_on_top()

    # ---------- state ----------
    def set_active(self, active):
        self.active = active
        if active:
            pos = QCursor.pos()
            self.idle_whip.reset(pos.x(), pos.y())
            for w in self.windows:
                w.show()
            self.timer.start(FRAME_MS)
            self.topmost_timer.start(3000)
        else:
            self.timer.stop()
            self.topmost_timer.stop()
            self.active_strikes = []
            self.sparks = []
            self.impact_mgr.clear()
            self.prev_dirty = QRectF()
            for w in self.windows:
                w.hide()

    def wake(self):
        """Call after changing display options / on click so the loop runs at full speed"""
        self.still_frames = 0
        if self.active and (not self.timer.isActive() or self.timer.interval() != FRAME_MS):
            self.timer.start(FRAME_MS)

    def has_animations(self):
        return bool(self.active_strikes or self.sparks or self.impact_mgr.effects)

    # ---------- input ----------
    def strike_origin(self, x, y):
        """Where the 'hand' swings from: up-right of the click, mirrored when that would leave the screen"""
        screen = QGuiApplication.screenAt(QPointF(x, y).toPoint())
        area = QRectF(screen.availableGeometry()) if screen else QRectF(x - 1000, y - 1000, 2000, 2000)
        dx, dy = STRIKE_REACH * 0.75, -STRIKE_REACH * 0.66
        if x + dx > area.right() - 30:
            dx = -dx
        if y + dy < area.top() + 30:
            dy = -dy
        return x + dx, y + dy

    def on_mouse_click(self):
        if not self.active:
            return
        # Clicking our own tray menu / dialogs shouldn't crack the whip
        if QApplication.activePopupWidget() is not None or QApplication.activeModalWidget() is not None:
            return

        pos = QCursor.pos()
        x, y = float(pos.x()), float(pos.y())
        style = config.get("whip_style", "comic")

        if config.get("whip_animation", True):
            ox, oy = self.strike_origin(x, y)
            self.active_strikes.append(ActiveStrike(ox, oy, x, y, style=style,
                                                    duration_ms=config.get("strike_speed_ms", 90)))
            # Keep at most a few overlapping strikes when spam-clicking: drop strikes that already cracked
            # first; a strike dropped before its crack still gets its sound + impact so no click is lost
            while len(self.active_strikes) > 3:
                victim = next((s for s in self.active_strikes if s.cracked), self.active_strikes[0])
                if not victim.cracked:
                    victim.cracked = True
                    self.trigger_crack_impact(victim.target.x(), victim.target.y(), victim.style,
                                              sound=not victim.sound_played)
                self.active_strikes.remove(victim)
        else:
            self.trigger_crack_impact(x, y, style)
        self.wake()
        # Draw the first frame now instead of waiting for the next timer tick
        self.tick()

    def trigger_crack_impact(self, x, y, style, sound=True):
        if sound:
            sound_player.play_crack(style)

        # Impact visual (POW / ZAP / CRACK)
        self.impact_mgr.add_impact(x, y, style)

        # Flying sparks
        num_sparks = 18 if style == "cyber" else 14
        for _ in range(num_sparks):
            self.sparks.append(SparkParticle(x, y, style=style))
        if len(self.sparks) > 200:
            self.sparks = self.sparks[-200:]

    # ---------- frame loop ----------
    def tick(self):
        try:
            self.step()
        except Exception:
            log.exception("Error in animation frame")

    def step(self):
        show_idle = config.get("show_cursor_whip", True)
        if show_idle:
            pos = QCursor.pos()
            self.idle_whip.step(pos.x(), pos.y())

        # Update active strikes (state changes happen here, never in paint)
        for s in self.active_strikes:
            # The sound starts slightly early so what you hear lines up with what you see
            if not s.sound_played and s.ms_until_crack() <= AUDIO_LEAD_MS + FRAME_MS / 2:
                s.sound_played = True
                sound_player.play_crack(s.style)
            if s.update():
                self.trigger_crack_impact(s.target.x(), s.target.y(), s.style, sound=not s.sound_played)
                s.sound_played = True
            s.frame_pts, s.frame_p = s.evaluate_points()
            s.frame_alpha = s.alpha()
            # Motion history for afterimages and the tip streak (only while the whip is really moving)
            if not hasattr(s, "ghosts"):
                s.ghosts, s.tip_trail = [], []
            s.frame_cord = cord_frame(s.frame_pts)  # computed once per frame, shared by every monitor's paint
            s.ghosts = (s.ghosts + [s.frame_cord])[-(GHOST_FRAMES + 1):]
            if s.frame_p < s.p_crack + 0.12:
                s.tip_trail = (s.tip_trail + [s.frame_pts[-1]])[-TIP_TRAIL_FRAMES:]
            elif s.tip_trail:
                s.tip_trail = s.tip_trail[1:]
        self.active_strikes = [s for s in self.active_strikes if not s.finished]

        # Update sparks
        self.sparks = [sp for sp in self.sparks if sp.update()]

        # Update impacts
        self.impact_mgr.update()

        # Repaint only the area that changed: last frame's drawing (to erase it) + this frame's drawing
        # (compared on whole pixels: a settled rope still drifts by ~0.001px, which must not trigger repaints)
        dirty = QRectF(self.drawing_rect(show_idle).toAlignedRect())
        idle_moving = show_idle and not self.active_strikes and self.idle_whip.motion > 0.05
        if self.has_animations() or idle_moving or dirty != self.prev_dirty:
            region = self.prev_dirty.united(dirty) if not self.prev_dirty.isEmpty() else dirty
            if not region.isEmpty():
                for w in self.windows:
                    w.invalidate_global(region)
        self.prev_dirty = dirty

        # Nothing left to animate: stop the timer until the next click / option change
        if not show_idle and not self.has_animations():
            self.timer.stop()
            return

        # Settled rope + no effects for a while: poll the cursor less often until it moves again
        if idle_moving or self.has_animations():
            self.still_frames = 0
            if self.timer.interval() != FRAME_MS:
                self.timer.setInterval(FRAME_MS)
        else:
            self.still_frames += 1
            if self.still_frames > 30 and self.timer.interval() != IDLE_FRAME_MS:
                self.timer.setInterval(IDLE_FRAME_MS)

    def drawing_rect(self, show_idle):
        rect = QRectF()
        if show_idle and not self.active_strikes and self.idle_whip.initialized:
            pts = [QPointF(n.x, n.y) for n in self.idle_whip.nodes] + [self.idle_whip.handle_pos]
            rect = rect.united(points_rect(pts, 20))
        for s in self.active_strikes:
            pts = getattr(s, "frame_pts", None)
            if pts:
                extra = [QPointF(g[i][0], g[i][1]) for g in getattr(s, "ghosts", []) for i in (0, len(g) // 2, -1)]
                extra += getattr(s, "tip_trail", [])
                rect = rect.united(points_rect(pts + [s.origin] + extra, HANDLE_LENGTH + 30))
        if self.sparks:
            rect = rect.united(points_rect([QPointF(sp.x, sp.y) for sp in self.sparks], 40))  # + streak tails
        rect = rect.united(self.impact_mgr.bounding_rect())
        return rect

    # ---------- painting ----------
    def render(self, painter: QPainter, visible: QRectF = None):
        style = config.get("whip_style", "comic")

        # 1. Render Active Whip Strikes
        self.render_strikes(painter, visible)

        # 2. Render Idle Cursor Whip (hidden while a strike is in the air: the hand is busy swinging)
        if config.get("show_cursor_whip", True) and not self.active_strikes:
            self.render_idle_whip(painter, style, visible)

        # 3. Render Sparks
        self.render_sparks(painter)

        # 4. Render Impact Animations (POW / ZAP / CRACK)
        self.impact_mgr.render(painter, visible)

    def render_idle_whip(self, painter: QPainter, style: str, visible: QRectF = None):
        if not self.idle_whip.initialized:
            return
        if visible is not None:
            pts = [QPointF(n.x, n.y) for n in self.idle_whip.nodes] + [self.idle_whip.handle_pos]
            if not visible.intersects(points_rect(pts, HANDLE_LENGTH + 20)):
                return
        office = config.get("office_mode", False)
        scale = 0.35 if office else 1.0
        pts = [QPointF(n.x, n.y) for n in self.idle_whip.nodes]
        draw_cord(painter, pts, style, width_scale=scale)
        draw_handle(painter, self.idle_whip.handle_pos, self.idle_whip.handle_angle, style, scale=scale)

    def render_strikes(self, painter: QPainter, visible: QRectF = None):
        office = config.get("office_mode", False)
        scale = 0.35 if office else 1.0
        for strike in self.active_strikes:
            pts = getattr(strike, "frame_pts", None)
            alpha = getattr(strike, "frame_alpha", 1.0)
            if not pts or len(pts) < 2 or alpha <= 0.01:
                continue
            if visible is not None and not visible.intersects(points_rect(pts + [strike.origin], HANDLE_LENGTH + 80)):
                continue

            # Afterimages of the previous cord shapes (motion blur feel)
            ghosts = getattr(strike, "ghosts", [])[:-1]
            for i, g in enumerate(ghosts):
                draw_ghost(painter, g, strike.style, alpha * 0.16 * (i + 1), width_scale=1.1 * scale)

            self.render_tip_trail(painter, strike, alpha, scale)
            draw_cord(painter, pts, strike.style, alpha=alpha, width_scale=1.25 * scale, frame=getattr(strike, "frame_cord", None))
            self.render_crack_flash(painter, strike, scale)

            # Handle points away from the cord, continuing the line from the first cord segment
            first, second = pts[0], pts[2]
            angle = math.degrees(math.atan2(first.y() - second.y(), first.x() - second.x()))
            butt = QPointF(first.x() + math.cos(math.radians(angle)) * (HANDLE_LENGTH * scale),
                           first.y() + math.sin(math.radians(angle)) * (HANDLE_LENGTH * scale))
            draw_handle(painter, butt, angle + 180.0, strike.style, alpha=alpha, scale=scale)

    def render_tip_trail(self, painter: QPainter, strike, alpha, scale):
        """Tapered glowing streak along the path the whip tip travelled in the last few frames"""
        trail = getattr(strike, "tip_trail", [])
        if len(trail) < 3:
            return
        smooth = catmull_rom(trail)
        r, g, b = STRIKE_ACCENT.get(strike.style, STRIKE_ACCENT["comic"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(r, g, b, int(70 * alpha)))
        painter.drawPolygon(tapered_ribbon(smooth, 0.5, 16.0 * scale))
        painter.setBrush(QColor(255, 255, 255, int(170 * alpha)))
        painter.drawPolygon(tapered_ribbon(smooth, 0.2, 4.0 * scale))

    def render_crack_flash(self, painter: QPainter, strike, scale):
        """Four-point star flash at the tip for a moment right when the whip cracks"""
        t = (strike.frame_p - strike.p_crack) / 0.12
        if not 0.0 <= t < 1.0:
            return
        r, g, b = STRIKE_ACCENT.get(strike.style, STRIKE_ACCENT["comic"])
        size = (14.0 + 30.0 * t) * scale
        a = 1.0 - t
        painter.save()
        painter.translate(strike.target)
        painter.rotate(45.0 * t)
        painter.setPen(Qt.PenStyle.NoPen)
        for length, width, color in ((size, size * 0.22, QColor(r, g, b, int(200 * a))),
                                     (size * 0.7, size * 0.09, QColor(255, 255, 255, int(255 * a)))):
            painter.setBrush(color)
            for k in range(2):
                painter.drawPolygon(QPolygonF([QPointF(-length, 0), QPointF(0, -width), QPointF(length, 0), QPointF(0, width)]))
                painter.rotate(90)
        painter.restore()

    def render_sparks(self, painter: QPainter):
        """Sparks are drawn as short streaks along their velocity (reads as speed, not as dots)"""
        for sp in self.sparks:
            alpha = int(sp.life * 255)
            if alpha <= 0:
                continue
            r, g, b = sp.color
            width = max(1.0, sp.size * sp.life * 0.8)
            tail = QPointF(sp.x - sp.vx * 2.2, sp.y - sp.vy * 2.2)
            painter.setPen(QPen(QColor(r, g, b, alpha), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(tail, QPointF(sp.x, sp.y))

    def shutdown(self):
        self.timer.stop()
        self.topmost_timer.stop()
        for w in self.windows:
            w.close()
        self.windows = []
