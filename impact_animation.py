import os
import re
import time
import math
import random
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QImageReader
from config import config, get_asset_path, get_base_dir

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
SEQUENCE_RE = re.compile(r"^(.*?)(\d+)$")  # "frame_01" -> ("frame_", "01")
BUILTIN_SCALE = 0.6
CUSTOM_MAX_SIZE = 320.0  # Custom images are shrunk to fit this box so a 4K image doesn't cover the screen

class CustomAnimation:
    """A custom impact animation: one or more frames with per-frame durations (ms)"""
    def __init__(self, frames, delays):
        self.frames = frames
        self.delays = delays
        self.total_ms = sum(delays)
        w = max(pm.width() for pm in frames)
        h = max(pm.height() for pm in frames)
        self.fit_scale = min(1.0, CUSTOM_MAX_SIZE / max(w, h, 1))

    @property
    def is_animated(self):
        return len(self.frames) > 1

    def frame_at(self, elapsed_ms):
        if not self.is_animated:
            return self.frames[0]
        t = elapsed_ms
        for pm, d in zip(self.frames, self.delays):
            if t < d:
                return pm
            t -= d
        return self.frames[-1]

def load_gif(path):
    reader = QImageReader(path)
    reader.setDecideFormatFromContent(True)
    frames, delays = [], []
    while True:
        img = reader.read()
        if img.isNull():
            break
        frames.append(QPixmap.fromImage(img))
        delay = reader.nextImageDelay()
        delays.append(delay if delay > 10 else 80)
        if len(frames) >= 200:
            break
    return CustomAnimation(frames, delays) if frames else None

class ImpactEffect:
    """Represents a single active impact explosion (POW, ZAP, CRACK, or Custom Animation)"""
    def __init__(self, x, y, style="comic", custom_anim=None, duration_ms=480):
        self.x = float(x)
        self.y = float(y)
        self.style = style
        self.custom_anim = custom_anim
        if custom_anim is not None and custom_anim.is_animated:
            # Play the whole GIF/sequence once (bounded so a long GIF doesn't linger forever)
            duration_ms = max(300, min(3000, custom_anim.total_ms))
        self.duration_ms = duration_ms
        self.start_time = time.perf_counter()
        self.rotation = random.uniform(-10.0, 10.0)
        self.drift_y = 0.0

        # Ring shockwave
        self.ring_radius = 10.0
        self.max_ring_radius = random.uniform(80.0, 130.0)

        # Lightning branches for cyber style
        self.lightning_bolts = []
        if style == "cyber":
            for _ in range(5):
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(50, 120)
                mid_dist = dist * 0.5
                mid_angle = angle + random.uniform(-0.4, 0.4)
                p0 = QPointF(self.x, self.y)
                p1 = QPointF(self.x + math.cos(mid_angle) * mid_dist, self.y + math.sin(mid_angle) * mid_dist)
                p2 = QPointF(self.x + math.cos(angle) * dist, self.y + math.sin(angle) * dist)
                self.lightning_bolts.append((p0, p1, p2))

        # Slash cut for classic style
        if style == "classic":
            slash_angle = random.uniform(math.pi * 0.2, math.pi * 0.4)
            slash_len = random.uniform(90, 150)
            self.slash_p1 = QPointF(self.x - math.cos(slash_angle) * slash_len, self.y - math.sin(slash_angle) * slash_len)
            self.slash_p2 = QPointF(self.x + math.cos(slash_angle) * slash_len, self.y + math.sin(slash_angle) * slash_len)

    def elapsed_ms(self):
        return (time.perf_counter() - self.start_time) * 1000.0

    def get_progress(self):
        return min(1.0, self.elapsed_ms() / self.duration_ms)

    def is_finished(self):
        return self.get_progress() >= 1.0

    def get_scale_and_opacity(self):
        p = self.get_progress()
        self.drift_y = 0.0

        # Animated custom frames carry their own motion: just fade in/out
        if self.custom_anim is not None and self.custom_anim.is_animated:
            opacity = min(1.0, p / 0.05) if p < 0.05 else (1.0 if p < 0.85 else max(0.0, (1.0 - p) / 0.15))
            return 1.0, opacity

        # Phase 1: Rapid Elastic Pop-in (0.0 to 0.15)
        if p < 0.15:
            norm_t = p / 0.15
            scale = 0.15 + (1.20 - 0.15) * math.sin(norm_t * math.pi * 0.5)
            opacity = min(1.0, norm_t * 2.0)
        # Phase 2: Settle to 1.0 (0.15 to 0.35)
        elif p < 0.35:
            norm_t = (p - 0.15) / 0.20
            scale = 1.20 - 0.20 * math.sin(norm_t * math.pi * 0.5)
            opacity = 1.0
        # Phase 3: Hold & subtle comic vibration (0.35 to 0.65)
        elif p < 0.65:
            scale = 1.0 + math.sin((p - 0.35) * 40.0) * 0.03
            opacity = 1.0
        # Phase 4: Fade out & slight upward drift (0.65 to 1.0)
        else:
            norm_t = (p - 0.65) / 0.35
            scale = 1.0 + norm_t * 0.15
            opacity = max(0.0, 1.0 - norm_t ** 1.3)
            self.drift_y = -norm_t * 15.0

        return scale, opacity

class ImpactManager:
    def __init__(self):
        self.pixmaps = {}
        self.custom_anims = []
        self.custom_signature = None
        self.effects = []
        self.load_assets()

    def load_assets(self):
        paths = {
            "comic": get_asset_path(os.path.join("assets", "pow.png")),
            "cyber": get_asset_path(os.path.join("assets", "zap.png")),
            "classic": get_asset_path(os.path.join("assets", "crack.png")),
        }
        for style, path in paths.items():
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    self.pixmaps[style] = pm

        self.check_custom_assets()

    def custom_dir(self):
        return os.path.join(get_base_dir(), "assets", "custom_animation")

    def check_custom_assets(self, force=False):
        """(Re)loads assets/custom_animation/ when its contents changed. Cheap to call on every impact."""
        custom_dir = self.custom_dir()
        try:
            entries = sorted(
                (f, os.stat(os.path.join(custom_dir, f)).st_mtime) for f in os.listdir(custom_dir)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTS + (".gif",)
            )
        except OSError:
            entries = []
        if not force and entries == self.custom_signature:
            return
        self.custom_signature = entries
        self.custom_anims = []

        sequences = {}
        for f, _ in entries:
            full_path = os.path.join(custom_dir, f)
            stem, ext = os.path.splitext(f)
            ext = ext.lower()
            try:
                if ext == ".gif":
                    anim = load_gif(full_path)
                    if anim:
                        self.custom_anims.append(anim)
                    continue
                m = SEQUENCE_RE.match(stem)
                if m:
                    # frame_01.png, frame_02.png ... are grouped into one animation
                    sequences.setdefault(m.group(1).lower(), []).append((int(m.group(2)), full_path))
                else:
                    pm = QPixmap(full_path)
                    if not pm.isNull():
                        self.custom_anims.append(CustomAnimation([pm], [0]))
            except Exception as e:
                print(f"Error loading custom animation {f}: {e}")

        for _, items in sorted(sequences.items()):
            frames = [QPixmap(p) for _, p in sorted(items)]
            frames = [pm for pm in frames if not pm.isNull()]
            if frames:
                self.custom_anims.append(CustomAnimation(frames, [70] * len(frames)))

    def add_impact(self, x, y, style=None):
        if not config.get("pow_animation", True):
            return

        if style is None:
            style = config.get("whip_style", "comic")

        custom_anim = None
        if config.get("custom_animation_enabled", True):
            self.check_custom_assets()
            if self.custom_anims:
                custom_anim = random.choice(self.custom_anims)

        effect = ImpactEffect(x, y, style=style, custom_anim=custom_anim)
        self.effects.append(effect)

    def update(self):
        self.effects = [e for e in self.effects if not e.is_finished()]

    def clear(self):
        self.effects = []

    def bounding_rect(self):
        """Global-coordinate area the current effects may paint into"""
        rect = QRectF()
        for e in self.effects:
            r = e.max_ring_radius + 10
            if e.style == "classic":
                r = max(r, 160)
            pm = self.pixmap_for(e)
            if pm is not None:
                s = 1.2 * self.base_scale(e)
                r = max(r, math.hypot(pm.width(), pm.height()) * s / 2 + 25)
            rect = rect.united(QRectF(e.x - r, e.y - r - 20, 2 * r, 2 * r + 20))
        return rect

    def pixmap_for(self, e):
        if e.custom_anim is not None:
            return e.custom_anim.frame_at(e.elapsed_ms())
        return self.pixmaps.get(e.style, self.pixmaps.get("comic"))

    def base_scale(self, e):
        return e.custom_anim.fit_scale if e.custom_anim is not None else BUILTIN_SCALE

    def render(self, painter: QPainter):
        for e in self.effects:
            scale, opacity = e.get_scale_and_opacity()
            if opacity <= 0.001:
                continue

            p = e.get_progress()
            painter.save()

            # Render themed shockwave ring
            ring_r = e.ring_radius + (e.max_ring_radius - e.ring_radius) * (p ** 0.7)
            ring_alpha = int(opacity * 200 * (1.0 - p))
            if ring_alpha > 0:
                if e.style == "cyber":
                    pen = QPen(QColor(0, 240, 255, ring_alpha), 3)
                elif e.style == "classic":
                    pen = QPen(QColor(230, 80, 50, ring_alpha), 3)
                else: # comic
                    pen = QPen(QColor(255, 220, 0, ring_alpha), 4)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(e.x, e.y), ring_r, ring_r)

            # Render Cyberpunk Lightning Branches
            if e.style == "cyber" and e.lightning_bolts:
                bolt_alpha = int(opacity * 255 * (1.0 - p * 0.8))
                if bolt_alpha > 0:
                    bolt_pen = QPen(QColor(0, 255, 255, bolt_alpha), 3)
                    inner_pen = QPen(QColor(255, 255, 255, bolt_alpha), 1.5)
                    for p0, p1, p2 in e.lightning_bolts:
                        painter.setPen(bolt_pen)
                        painter.drawLine(p0, p1)
                        painter.drawLine(p1, p2)
                        painter.setPen(inner_pen)
                        painter.drawLine(p0, p1)
                        painter.drawLine(p1, p2)

            # Render Classic Western Slash mark
            if e.style == "classic" and hasattr(e, "slash_p1"):
                slash_alpha = int(opacity * 255 * (1.0 - p * 0.9))
                if slash_alpha > 0:
                    painter.setPen(QPen(QColor(220, 40, 30, slash_alpha), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    painter.drawLine(e.slash_p1, e.slash_p2)
                    painter.setPen(QPen(QColor(255, 220, 150, slash_alpha), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    painter.drawLine(e.slash_p1, e.slash_p2)

            # Select pixmap to render
            pm = self.pixmap_for(e)
            if pm is not None and not pm.isNull():
                s = scale * self.base_scale(e)
                target_w = pm.width() * s
                target_h = pm.height() * s

                painter.translate(e.x, e.y + e.drift_y)
                if e.custom_anim is None or not e.custom_anim.is_animated:
                    painter.rotate(e.rotation)
                painter.setOpacity(opacity)

                rect = QRectF(-target_w / 2.0, -target_h / 2.0, target_w, target_h)
                painter.drawPixmap(rect, pm, QRectF(pm.rect()))

            painter.restore()
