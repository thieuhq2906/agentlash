import math
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
IDLE_FRAME_MS = 50
STRIKE_REACH = 175.0  # distance from the swinging hand to the click point

log = logging.getLogger(__name__)

# Cord colour layers per style: (colour, width at handle, width at tip), drawn back to front
CORD_LAYERS = {
    "comic": [((0, 0, 0, 255), 9.0, 3.6), ((230, 35, 35, 255), 5.6, 1.8), ((255, 228, 0, 255), 2.6, 0.7)],
    "cyber": [((255, 0, 150, 80), 15.0, 6.0), ((0, 240, 255, 235), 6.0, 2.2), ((255, 255, 255, 255), 2.4, 0.8)],
    "classic": [((40, 22, 8, 220), 7.5, 2.4), ((135, 78, 34, 255), 5.0, 1.4), ((200, 140, 80, 200), 1.6, 0.4)],
}

def catmull_rom(pts, subdivisions=3):
    """Smooths a polyline by inserting Catmull-Rom samples between points"""
    if len(pts) < 3:
        return list(pts)
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for k in range(subdivisions):
            t = k / subdivisions
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1.x()) + (-p0.x() + p2.x()) * t + (2 * p0.x() - 5 * p1.x() + 4 * p2.x() - p3.x()) * t2 + (-p0.x() + 3 * p1.x() - 3 * p2.x() + p3.x()) * t3)
            y = 0.5 * ((2 * p1.y()) + (-p0.y() + p2.y()) * t + (2 * p0.y() - 5 * p1.y() + 4 * p2.y() - p3.y()) * t2 + (-p0.y() + 3 * p1.y() - 3 * p2.y() + p3.y()) * t3)
            out.append(QPointF(x, y))
    out.append(pts[-1])
    return out

def tapered_ribbon(pts, w_start, w_end):
    """Filled polygon following pts whose width shrinks from w_start to w_end (a whip thinning towards the tip)"""
    n = len(pts)
    left, right = [], []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        tx, ty = b.x() - a.x(), b.y() - a.y()
        tl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / tl, tx / tl
        half = (w_start + (w_end - w_start) * (i / (n - 1))) / 2.0
        left.append(QPointF(p.x() + nx * half, p.y() + ny * half))
        right.append(QPointF(p.x() - nx * half, p.y() - ny * half))
    return QPolygonF(left + right[::-1])

def points_rect(pts, margin):
    xs = [p.x() for p in pts]
    ys = [p.y() for p in pts]
    return QRectF(min(xs) - margin, min(ys) - margin, max(xs) - min(xs) + 2 * margin, max(ys) - min(ys) + 2 * margin)

def draw_cord(painter, pts, style, alpha=1.0, width_scale=1.0):
    if len(pts) < 2:
        return
    smooth = catmull_rom(pts)
    painter.setPen(Qt.PenStyle.NoPen)
    for (r, g, b, a), w0, w1 in CORD_LAYERS.get(style, CORD_LAYERS["comic"]):
        painter.setBrush(QColor(r, g, b, int(a * alpha)))
        painter.drawPolygon(tapered_ribbon(smooth, w0 * width_scale, w1 * width_scale))
        # Round the thick end so it tucks into the handle cleanly
        painter.drawEllipse(smooth[0], w0 * width_scale / 2, w0 * width_scale / 2)
    if style == "classic":
        # Red "popper" at the tip of a bullwhip
        painter.setBrush(QColor(230, 30, 30, int(255 * alpha)))
        painter.drawEllipse(smooth[-1], 2.6 * width_scale, 2.6 * width_scale)

def draw_handle(painter, butt: QPointF, angle_deg, style, alpha=1.0):
    """Vector-drawn whip handle from butt (held end) along angle_deg, HANDLE_LENGTH long"""
    L = HANDLE_LENGTH
    W = 11.0
    painter.save()
    painter.translate(butt)
    painter.rotate(angle_deg)
    painter.setOpacity(painter.opacity() * alpha)
    body = QRectF(0, -W / 2, L, W)

    if style == "cyber":
        painter.setPen(QPen(QColor(0, 240, 255, 90), 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 4, 4)  # glow
        painter.setPen(QPen(QColor(0, 240, 255), 1.6))
        painter.setBrush(QColor(28, 32, 44))
        painter.drawRoundedRect(body, 4, 4)
        painter.setPen(QPen(QColor(0, 240, 255, 220), 1.4))
        for x in range(10, int(L) - 6, 6):
            painter.drawLine(QPointF(x, -2.5), QPointF(x, 2.5))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
        painter.drawLine(QPointF(4, 0), QPointF(L - 4, 0))
        painter.setPen(QPen(QColor(255, 0, 150), 1.5))
        painter.setBrush(QColor(200, 0, 120))
        painter.drawEllipse(QPointF(0, 0), 6.5, 6.5)
        painter.setBrush(QColor(0, 240, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(L - 5, -W / 2 - 1, 5, W + 2))
    elif style == "classic":
        painter.setPen(QPen(QColor(45, 25, 10), 1.6))
        painter.setBrush(QColor(110, 62, 28))
        painter.drawRoundedRect(body, 3, 3)
        painter.setPen(QPen(QColor(70, 38, 15, 220), 1.1))
        painter.setClipRect(body)
        for x in range(-int(W), int(L), 5):
            painter.drawLine(QPointF(x, -W / 2), QPointF(x + W, W / 2))
            painter.drawLine(QPointF(x + W, -W / 2), QPointF(x, W / 2))
        painter.setClipping(False)
        painter.setPen(QPen(QColor(120, 90, 25), 1.2))
        painter.setBrush(QColor(212, 170, 70))
        painter.drawEllipse(QPointF(0, 0), 6.5, 6.5)
        painter.drawRect(QRectF(L - 5, -W / 2 - 0.5, 5, W + 1))
    else:  # comic
        painter.setPen(QPen(QColor(0, 0, 0), 2.4))
        painter.setBrush(QColor(225, 35, 35))
        painter.drawRoundedRect(body, 4, 4)
        painter.setClipRect(body)
        painter.setPen(QPen(QColor(255, 214, 0), 3.0))
        for x in range(4, int(L) + 6, 8):
            painter.drawLine(QPointF(x, -W / 2), QPointF(x + 6, W / 2))
        painter.setClipping(False)
        painter.setPen(QPen(QColor(0, 0, 0), 2.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 4, 4)
        painter.setBrush(QColor(225, 35, 35))
        painter.drawEllipse(QPointF(0, 0), 7.0, 7.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawEllipse(QPointF(-2, -2.5), 2.0, 2.0)
        painter.setBrush(QColor(0, 0, 0))
        painter.drawRect(QRectF(L - 4, -W / 2 - 1, 4, W + 2))
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
            self.scene.render(painter)
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
                                                    duration_ms=config.get("strike_speed_ms", 180)))
            # Keep at most a few overlapping strikes when spam-clicking
            if len(self.active_strikes) > 4:
                self.active_strikes = self.active_strikes[-4:]
        else:
            self.trigger_crack_impact(x, y, style)
        self.wake()

    def trigger_crack_impact(self, x, y, style):
        # Play sound
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
            if s.update():
                self.trigger_crack_impact(s.target.x(), s.target.y(), s.style)
            s.frame_pts, s.frame_p = s.evaluate_points()
            s.frame_alpha = s.alpha()
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
                rect = rect.united(points_rect(pts + [s.origin], HANDLE_LENGTH + 20))
        if self.sparks:
            rect = rect.united(points_rect([QPointF(sp.x, sp.y) for sp in self.sparks], 10))
        rect = rect.united(self.impact_mgr.bounding_rect())
        return rect

    # ---------- painting ----------
    def render(self, painter: QPainter):
        style = config.get("whip_style", "comic")

        # 1. Render Active Whip Strikes
        self.render_strikes(painter)

        # 2. Render Idle Cursor Whip (hidden while a strike is in the air: the hand is busy swinging)
        if config.get("show_cursor_whip", True) and not self.active_strikes:
            self.render_idle_whip(painter, style)

        # 3. Render Sparks
        self.render_sparks(painter)

        # 4. Render Impact Animations (POW / ZAP / CRACK)
        self.impact_mgr.render(painter)

    def render_idle_whip(self, painter: QPainter, style: str):
        if not self.idle_whip.initialized:
            return
        pts = [QPointF(n.x, n.y) for n in self.idle_whip.nodes]
        draw_cord(painter, pts, style)
        draw_handle(painter, self.idle_whip.handle_pos, self.idle_whip.handle_angle, style)

    def render_strikes(self, painter: QPainter):
        for strike in self.active_strikes:
            pts = getattr(strike, "frame_pts", None)
            alpha = getattr(strike, "frame_alpha", 1.0)
            if not pts or len(pts) < 2 or alpha <= 0.01:
                continue

            draw_cord(painter, pts, strike.style, alpha=alpha, width_scale=1.25)

            # Handle points away from the cord, continuing the line from the first cord segment
            first, second = pts[0], pts[2]
            angle = math.degrees(math.atan2(first.y() - second.y(), first.x() - second.x()))
            butt = QPointF(first.x() + math.cos(math.radians(angle)) * HANDLE_LENGTH,
                           first.y() + math.sin(math.radians(angle)) * HANDLE_LENGTH)
            draw_handle(painter, butt, angle + 180.0, strike.style, alpha=alpha)

    def render_sparks(self, painter: QPainter):
        painter.setPen(Qt.PenStyle.NoPen)
        for sp in self.sparks:
            alpha = int(sp.life * 255)
            if alpha <= 0:
                continue
            r, g, b = sp.color
            painter.setBrush(QBrush(QColor(r, g, b, alpha)))
            painter.drawEllipse(QPointF(sp.x, sp.y), sp.size * sp.life, sp.size * sp.life)

    def shutdown(self):
        self.timer.stop()
        self.topmost_timer.stop()
        for w in self.windows:
            w.close()
        self.windows = []
