import os
import re
import time
import math
import random
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QImageReader, QFont, QPolygonF, QPainterPath,
    QRadialGradient, QLinearGradient
)
from config import config, get_base_dir

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
SEQUENCE_RE = re.compile(r"^(.*?)(\d+)$")  # "frame_01" -> ("frame_", "01")
CUSTOM_MAX_SIZE = 320.0  # Custom images are shrunk to fit this box so a 4K image doesn't cover the screen
OFFICE_IMPACT_SCALE = 0.45  # Office mode: impacts shrink around the hit point
ART_SCALE = 2.0  # word art is pre-rendered at 2x so the pop-in overshoot and HiDPI screens stay crisp

# How far each style's effects (slash, bolts, cracks, flying bits) reach from the hit point
STYLE_REACH = {"comic": 170.0, "cyber": 185.0, "classic": 190.0, "taser": 180.0, "sword": 245.0}
DURATION_MS = {"comic": 950, "cyber": 900, "classic": 1050, "taser": 900, "sword": 1050}
WORDS = {
    "comic": ["POW!", "BONK!", "BAM!", "WHAM!", "K.O!", "OUCH!"],
    "cyber": ["ZAP!", "SYNTAX ERROR!", "STACK OVERFLOW!", "SEGFAULT!", "404!"],
    "classic": ["CRACK!", "YEE-HAW!", "GIDDY-UP!"],
    "taser": ["BZZZT!", "ZZZAP!", "TỈNH CHƯA?!"],
    "sword": ["TRẢM!", "SLASH!", "SMASH!"],
}
ACCENT = {
    "comic": QColor(255, 214, 0),
    "cyber": QColor(0, 240, 255),
    "classic": QColor(255, 196, 120),
    "taser": QColor(125, 211, 252),
    "sword": QColor(226, 232, 240),
}

# ---------- easing ----------
def clamp01(t):
    return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t

def ease_out_cubic(t):
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3

def ease_out_back(t, s=2.4):
    t = clamp01(t) - 1.0
    return 1.0 + (s + 1.0) * t ** 3 + s * t ** 2

def with_alpha(color, alpha):
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c

# ---------- custom animations ----------
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

# ---------- word art (rendered once per word/style, then cached) ----------
def make_font(style, text, px):
    vietnamese = not text.isascii()  # Impact / Rockwell have no Vietnamese glyphs
    font = QFont()
    if style == "comic":
        font.setFamilies(["Segoe UI Black"] if vietnamese else ["Impact", "Arial Black"])
    elif style == "cyber":
        font.setFamilies(["Bahnschrift", "Consolas"])
        font.setStretch(QFont.Stretch.SemiCondensed)
    elif style == "classic":
        font.setFamilies(["Georgia"] if vietnamese else ["Rockwell Extra Bold", "Georgia"])
    else:
        font.setFamilies(["Segoe UI Black", "Arial Black"])
    font.setPixelSize(px)
    font.setWeight(QFont.Weight.Black)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
    return font

def centered_text_path(font, text):
    path = QPainterPath()
    path.addText(0, 0, font, text)
    br = path.boundingRect()
    path.translate(-br.center().x(), -br.center().y())
    return path

def render_art(w, h, draw):
    """Runs draw(painter) on a transparent 2x pixmap of logical size w x h with the origin at its centre"""
    pm = QPixmap(math.ceil(w * ART_SCALE), math.ceil(h * ART_SCALE))
    pm.setDevicePixelRatio(ART_SCALE)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.translate(w / 2.0, h / 2.0)
    draw(p)
    p.end()
    return pm

def starburst(rx, ry, spikes, rng, inner=0.68, jitter=0.12):
    poly = QPolygonF()
    for i in range(spikes * 2):
        a = i * math.pi / spikes + rng.uniform(-0.08, 0.08)
        r = (1.0 if i % 2 == 0 else inner) * (1.0 + rng.uniform(-jitter, jitter))
        poly.append(QPointF(math.cos(a) * rx * r, math.sin(a) * ry * r))
    return poly

def glow_text(p, path, glow_color, fill, outline=None, widths=(16, 10, 6), alphas=(35, 60, 110)):
    p.setBrush(Qt.BrushStyle.NoBrush)
    for w, a in zip(widths, alphas):
        p.setPen(QPen(with_alpha(glow_color, a), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
    p.setPen(QPen(outline, 1.4) if outline else Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawPath(path)

def art_comic(word):
    rng = random.Random(word)
    path = centered_text_path(make_font("comic", word, 46), word)
    br = path.boundingRect()
    rx, ry = br.width() / 2 + 54, br.height() / 2 + 44
    outer = starburst(rx, ry, 15, rng, inner=0.72)
    inner = starburst(rx * 0.80, ry * 0.80, 15, rng, inner=0.78)

    def draw(p):
        p.translate(-4, -4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawPolygon(outer.translated(7, 7))                      # drop shadow
        p.setPen(QPen(QColor(0, 0, 0), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin))
        p.setBrush(QColor(230, 35, 35))
        p.drawPolygon(outer)
        grad = QRadialGradient(QPointF(0, 0), max(rx, ry) * 0.8)
        grad.setColorAt(0.0, QColor(255, 248, 170))
        grad.setColorAt(0.6, QColor(255, 220, 0))
        grad.setColorAt(1.0, QColor(255, 160, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPolygon(inner)
        # Ben-Day halftone dots, bigger towards the rim
        clip = QPainterPath()
        clip.addPolygon(inner)
        p.setClipPath(clip)
        p.setBrush(QColor(255, 120, 0, 150))
        step = 8.0
        y = -ry
        while y < ry:
            x = -rx + (step / 2 if int((y + ry) / step) % 2 else 0)
            while x < rx:
                d = math.hypot(x / rx, y / ry)
                r = 0.4 + 2.4 * clamp01(d - 0.25)
                if r > 0.6:
                    p.drawEllipse(QPointF(x, y), r, r)
                x += step
            y += step
        p.setClipping(False)
        # 3D extruded lettering
        for k in range(6, 0, -1):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(120, 10, 10))
            p.drawPath(path.translated(k * 0.9, k * 1.1))
        p.setPen(QPen(QColor(0, 0, 0), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        fill = QLinearGradient(QPointF(0, br.top()), QPointF(0, br.bottom()))
        fill.setColorAt(0.0, QColor(255, 255, 255))
        fill.setColorAt(0.55, QColor(255, 252, 220))
        fill.setColorAt(1.0, QColor(255, 214, 90))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(path)

    return {"main": render_art(rx * 2.25 + 20, ry * 2.25 + 20, draw)}

def art_cyber(word):
    path = centered_text_path(make_font("cyber", word, 40), word)
    br = path.boundingRect()
    pw, ph = br.width() + 52, br.height() + 34
    c = 12.0
    panel = QPolygonF([QPointF(-pw / 2 + c, -ph / 2), QPointF(pw / 2, -ph / 2), QPointF(pw / 2, ph / 2 - c),
                       QPointF(pw / 2 - c, ph / 2), QPointF(-pw / 2, ph / 2), QPointF(-pw / 2, -ph / 2 + c)])
    W, H = pw + 30, ph + 44
    label_font = QFont()
    label_font.setFamilies(["Consolas", "Cascadia Mono"])
    label_font.setPixelSize(10)
    label_font.setWeight(QFont.Weight.Bold)

    def draw_panel(p):
        bg = QLinearGradient(QPointF(-pw / 2, 0), QPointF(pw / 2, 0))
        bg.setColorAt(0, QColor(8, 14, 32, 225))
        bg.setColorAt(1, QColor(32, 8, 48, 225))
        p.setPen(QPen(QColor(0, 240, 255, 60), 8))
        p.setBrush(bg)
        p.drawPolygon(panel)
        clip = QPainterPath()
        clip.addPolygon(panel)
        p.setClipPath(clip)
        p.setPen(QPen(QColor(0, 240, 255, 22), 1))
        y = -ph / 2
        while y < ph / 2:
            p.drawLine(QPointF(-pw / 2, y), QPointF(pw / 2, y))
            y += 3
        p.setClipping(False)
        p.setPen(QPen(QColor(0, 240, 255), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(panel)
        p.setPen(QPen(QColor(255, 0, 170, 200), 1))
        p.drawPolygon(panel.translated(3, 3))
        # corner brackets
        p.setPen(QPen(QColor(255, 255, 255), 2.5))
        b = 10
        for sx, sy in ((-1, 1), (1, -1)):
            x0, y0 = sx * (pw / 2 + 6), sy * (ph / 2 + 6)
            p.drawLine(QPointF(x0, y0), QPointF(x0 - sx * b, y0))
            p.drawLine(QPointF(x0, y0), QPointF(x0, y0 - sy * b))
        p.setFont(label_font)
        p.setPen(QColor(255, 0, 170))
        p.drawText(QPointF(-pw / 2 + 2, -ph / 2 - 7), "// SYS_FAULT 0xDEAD")
        glow_text(p, path, QColor(0, 240, 255), QColor(210, 255, 255))

    def ghost(color):
        def draw(p):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawPath(path)
        return render_art(W, H, draw)

    return {"main": render_art(W, H, draw_panel),
            "ghost_a": ghost(QColor(255, 0, 170, 210)),
            "ghost_b": ghost(QColor(0, 140, 255, 210))}

def art_classic(word):
    path = centered_text_path(make_font("classic", word, 38), word)
    br = path.boundingRect()
    rw, rh = br.width() + 50, br.height() + 26
    bulge = 7.0

    def ribbon(w, h, dy=0.0):
        rp = QPainterPath()
        rp.moveTo(-w / 2, -h / 2 + dy)
        rp.quadTo(0, -h / 2 - bulge + dy, w / 2, -h / 2 + dy)
        rp.lineTo(w / 2, h / 2 + dy)
        rp.quadTo(0, h / 2 - bulge + dy, -w / 2, h / 2 + dy)
        rp.closeSubpath()
        return rp

    def tail(sign):
        x0 = sign * (rw / 2 - 6)
        x1 = sign * (rw / 2 + 30)
        poly = QPolygonF([QPointF(x0, -rh / 2 + 10), QPointF(x1, -rh / 2 + 10), QPointF(x1 - sign * 12, rh / 2 * 0.25 + 8),
                          QPointF(x1, rh / 2 + 12), QPointF(x0, rh / 2 + 12)])
        return poly

    def draw(p):
        dark = QColor(92, 52, 22)
        for sign in (-1, 1):
            p.setPen(QPen(dark, 2.5))
            p.setBrush(QColor(170, 120, 62))
            p.drawPolygon(tail(sign))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(110, 70, 30))
            fold = QPolygonF([QPointF(sign * (rw / 2 - 6), rh / 2 + 12), QPointF(sign * (rw / 2 + 4), rh / 2 + 12),
                              QPointF(sign * (rw / 2 - 6), rh / 2 + 2)])
            p.drawPolygon(fold)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawPath(ribbon(rw, rh).translated(4, 5))
        g = QLinearGradient(QPointF(0, -rh / 2), QPointF(0, rh / 2))
        g.setColorAt(0, QColor(250, 232, 186))
        g.setColorAt(1, QColor(214, 176, 112))
        p.setPen(QPen(dark, 3))
        p.setBrush(g)
        p.drawPath(ribbon(rw, rh))
        stitch = QPen(QColor(120, 72, 30, 170), 1.3, Qt.PenStyle.DashLine)
        p.setPen(stitch)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(ribbon(rw - 12, rh - 10))
        # little stars either side of the word
        for sign in (-1, 1):
            cx = sign * (br.width() / 2 + 13)
            star = QPolygonF()
            for i in range(10):
                r = 6.0 if i % 2 == 0 else 2.6
                a = i * math.pi / 5 - math.pi / 2
                star.append(QPointF(cx + math.cos(a) * r, math.sin(a) * r))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(dark)
            p.drawPolygon(star)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 246, 220))
        p.drawPath(path.translated(0, -1.5))
        p.setBrush(QColor(78, 38, 12))
        p.drawPath(path)

    return {"main": render_art(rw + 80, rh + 40, draw)}

def art_taser(word):
    path = centered_text_path(make_font("taser", word, 42), word)
    br = path.boundingRect()

    def draw(p):
        glow_text(p, path, QColor(56, 189, 248), QColor(255, 255, 255), outline=QColor(254, 240, 138),
                  widths=(20, 13, 7), alphas=(30, 55, 120))
        # zig-zag "voltage" underline
        zz = QPolygonF()
        x = br.left()
        y0 = br.bottom() + 9
        i = 0
        while x <= br.right():
            zz.append(QPointF(x, y0 + (4 if i % 2 else -4)))
            x += 9
            i += 1
        p.setPen(QPen(QColor(254, 240, 138), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(zz)

    return {"main": render_art(br.width() + 50, br.height() + 56, draw)}

def art_sword(word):
    path = centered_text_path(make_font("sword", word, 48), word)
    br = path.boundingRect()

    def draw(p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(160, 16, 24, 220))
        p.drawPath(path.translated(4, 4))                          # blood-red shadow
        p.setPen(QPen(QColor(15, 23, 42), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        steel = QLinearGradient(QPointF(0, br.top()), QPointF(0, br.bottom()))
        steel.setColorAt(0.0, QColor(255, 255, 255))
        steel.setColorAt(0.45, QColor(203, 213, 225))
        steel.setColorAt(0.5, QColor(100, 116, 139))
        steel.setColorAt(0.62, QColor(241, 245, 249))
        steel.setColorAt(1.0, QColor(148, 163, 184))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(steel)
        p.drawPath(path)

    return {"main": render_art(br.width() + 30, br.height() + 30, draw)}

ART_BUILDERS = {"comic": art_comic, "cyber": art_cyber, "classic": art_classic, "taser": art_taser, "sword": art_sword}
_art_cache = {}

def word_art(word, style):
    key = (word, style)
    art = _art_cache.get(key)
    if art is None:
        art = ART_BUILDERS.get(style, art_comic)(word)
        _art_cache[key] = art
    return art

def draw_centered(painter, pm, scale_x=1.0, scale_y=1.0, dx=0.0, dy=0.0):
    size = pm.deviceIndependentSize()
    w, h = size.width() * scale_x, size.height() * scale_y
    painter.drawPixmap(QRectF(dx - w / 2, dy - h / 2, w, h), pm, QRectF(pm.rect()))

def jagged_bolt(x0, y0, x1, y1, rng, segments=7, spread=0.22):
    """Lightning polyline from (x0,y0) to (x1,y1) by random perpendicular displacement"""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    pts = [QPointF(x0, y0)]
    for i in range(1, segments):
        t = i / segments
        off = rng.uniform(-1, 1) * length * spread * math.sin(t * math.pi)
        pts.append(QPointF(x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    pts.append(QPointF(x1, y1))
    return pts

# ---------- effects ----------
class ImpactEffect:
    """A single hit effect: flash + shockwave + style-specific art + popup word (or a custom animation)"""
    def __init__(self, x, y, style="comic", custom_anim=None, duration_ms=None):
        self.x = float(x)
        self.y = float(y)
        self.style = style if style in ART_BUILDERS else "comic"
        self.custom_anim = custom_anim
        if duration_ms is None:
            duration_ms = DURATION_MS.get(self.style, 950)
        if custom_anim is not None and custom_anim.is_animated:
            # Play the whole GIF/sequence once (bounded so a long GIF doesn't linger forever)
            duration_ms = max(300, min(3000, custom_anim.total_ms))
        self.duration_ms = duration_ms
        self.start_time = time.perf_counter()
        self.rotation = random.uniform(-9.0, 9.0)
        self.word = random.choice(WORDS[self.style])
        self.max_ring_radius = random.uniform(90.0, 135.0)
        self.seed = random.random()

        rng = random.Random(self.seed)
        if self.style == "comic":
            self.speed_lines = [(rng.uniform(0, 2 * math.pi), rng.uniform(55, 75), rng.uniform(115, 160)) for _ in range(20)]
            self.puffs = [(i * 2 * math.pi / 7 + rng.uniform(-0.2, 0.2), rng.uniform(26, 40), rng.uniform(13, 20)) for i in range(7)]
            self.stars = [i * 2 * math.pi / 4 for i in range(4)]
        elif self.style == "cyber":
            self.bits = [(rng.choice(["01", "10", "1101", "0x1F", "ERR", "NULL", "404"]),
                          rng.uniform(0, 2 * math.pi), rng.uniform(60, 150)) for _ in range(12)]
            self.pixels = [(rng.uniform(-120, 120), rng.uniform(-80, 80), rng.uniform(6, 22), rng.uniform(3, 8)) for _ in range(9)]
        elif self.style == "classic":
            self.dust = [(rng.uniform(-80, 80), rng.uniform(5, 40), rng.uniform(12, 24), rng.uniform(0, 1)) for _ in range(11)]
            self.slash_angle = rng.uniform(math.pi * 0.15, math.pi * 0.35)
        elif self.style == "taser":
            self.bolt_targets = [(rng.uniform(0, 2 * math.pi), rng.uniform(80, 160)) for _ in range(8)]
        elif self.style == "sword":
            self.slash_angle = rng.uniform(math.pi * 0.08, math.pi * 0.28) * rng.choice((-1, 1))
            self.slash_len = rng.uniform(210, 240)
            self.cracks = []
            for i in range(10):
                a = i * 2 * math.pi / 10 + rng.uniform(-0.25, 0.25)
                pts = [QPointF(0, 0)]
                r = 0.0
                ang = a
                while r < rng.uniform(95, 165):
                    r += rng.uniform(14, 26)
                    ang += rng.uniform(-0.25, 0.25)
                    pts.append(QPointF(math.cos(ang) * r, math.sin(ang) * r))
                self.cracks.append(pts)
            self.shards = [(rng.uniform(0, 2 * math.pi), rng.uniform(3.5, 7.5), rng.uniform(5, 11), rng.uniform(-14, 14))
                           for _ in range(9)]

    def elapsed_ms(self):
        return (time.perf_counter() - self.start_time) * 1000.0

    def get_progress(self):
        return min(1.0, self.elapsed_ms() / self.duration_ms)

    def is_finished(self):
        return self.get_progress() >= 1.0

class ImpactManager:
    def __init__(self):
        self.custom_anims = []
        self.custom_signature = None
        self.effects = []
        self.load_assets()

    def load_assets(self):
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
        if custom_anim is None:
            word_art(effect.word, effect.style)  # build the cached art now, not in the middle of a paint
        self.effects.append(effect)
        if len(self.effects) > 6:  # spam-clicking: older bubbles would be hidden under the new ones anyway
            self.effects = self.effects[-6:]

    def update(self):
        self.effects = [e for e in self.effects if not e.is_finished()]

    def clear(self):
        self.effects = []

    def prewarm(self, first_style=None):
        """Builds the word art ahead of time (the very first text render loads the font system, ~1s):
        the current style right away, the rest one word per event-loop turn so the UI never stalls"""
        order = [first_style] if first_style in WORDS else []
        order += [s for s in WORDS if s not in order]
        pending = [(w, s) for s in order for w in WORDS[s]]
        for w, s in pending[:len(WORDS.get(first_style, []))]:
            word_art(w, s)
        rest = pending[len(WORDS.get(first_style, [])):]

        def build_next():
            if rest:
                word_art(*rest.pop(0))
                QTimer.singleShot(15, build_next)
        QTimer.singleShot(15, build_next)

    def effect_rect(self, e):
        """Global-coordinate area one effect may paint into"""
        r = max(e.max_ring_radius + 12, STYLE_REACH.get(e.style, 180.0))
        if e.custom_anim is not None:
            pm = self.pixmap_for(e)
            r = max(r, math.hypot(pm.width(), pm.height()) * 1.25 * e.custom_anim.fit_scale / 2 + 25)
        else:
            size = word_art(e.word, e.style)["main"].deviceIndependentSize()
            r = max(r, math.hypot(size.width(), size.height()) * 1.3 / 2 + 30)
        return QRectF(e.x - r, e.y - r - 30, 2 * r, 2 * r + 30)

    def bounding_rect(self):
        """Global-coordinate area the current effects may paint into"""
        rect = QRectF()
        for e in self.effects:
            rect = rect.united(self.effect_rect(e))
        return rect

    def pixmap_for(self, e):
        return e.custom_anim.frame_at(e.elapsed_ms()) if e.custom_anim is not None else None

    # ---------- rendering ----------
    def render(self, painter: QPainter, visible: QRectF = None):
        office = config.get("office_mode", False)
        for e in self.effects:
            p = e.get_progress()
            if p >= 1.0:
                continue
            if visible is not None and not visible.intersects(self.effect_rect(e)):
                continue  # off this monitor / outside the repainted area
            painter.save()
            painter.translate(e.x, e.y)
            if office:
                painter.scale(OFFICE_IMPACT_SCALE, OFFICE_IMPACT_SCALE)
            try:
                self.render_flash(painter, e, p)
                if e.custom_anim is not None:
                    self.render_custom(painter, e, p)
                else:
                    getattr(self, f"render_{e.style}")(painter, e, p)
            finally:
                painter.restore()

    def render_flash(self, painter, e, p):
        """Hit flash (first ~12% of the effect) + expanding shockwave ring"""
        accent = ACCENT.get(e.style, ACCENT["comic"])
        t = p / 0.12
        if t < 1.0:
            r = 18 + 70 * ease_out_cubic(t)
            g = QRadialGradient(QPointF(0, 0), r)
            g.setColorAt(0.0, QColor(255, 255, 255, int(230 * (1 - t))))
            g.setColorAt(0.35, with_alpha(accent, 170 * (1 - t)))
            g.setColorAt(1.0, with_alpha(accent, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(g)
            painter.drawEllipse(QPointF(0, 0), r, r)
        t = p / 0.55
        if t < 1.0:
            r = 14 + (e.max_ring_radius - 14) * ease_out_cubic(t)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(with_alpha(accent, 210 * (1 - t)), 1.0 + 7.0 * (1 - t)))
            painter.drawEllipse(QPointF(0, 0), r, r)
            if e.style in ("comic", "sword"):
                painter.setPen(QPen(QColor(255, 255, 255, int(150 * (1 - t))), 1.5))
                painter.drawEllipse(QPointF(0, 0), r * 0.82, r * 0.82)

    def word_transform(self, p, appear=0.2, leave=0.72):
        """(scale, opacity, lift) for the popup word: overshoot pop-in, hold, fade + float away"""
        if p < appear:
            s = 0.15 + 0.85 * ease_out_back(p / appear)
            return s, min(1.0, p / (appear * 0.4)), 0.0
        if p < leave:
            return 1.0 + 0.025 * math.sin((p - appear) * 38.0), 1.0, 0.0
        t = (p - leave) / (1.0 - leave)
        return 1.0 + 0.12 * t, max(0.0, 1.0 - t ** 1.4), -22.0 * ease_out_cubic(t)

    def render_custom(self, painter, e, p):
        pm = self.pixmap_for(e)
        if e.custom_anim.is_animated:
            scale = 1.0
            opacity = min(1.0, p / 0.05) if p < 0.05 else (1.0 if p < 0.85 else max(0.0, (1.0 - p) / 0.15))
            lift = 0.0
        else:
            scale, opacity, lift = self.word_transform(p)
            painter.rotate(e.rotation)
        painter.setOpacity(opacity)
        s = scale * e.custom_anim.fit_scale
        w, h = pm.width() * s, pm.height() * s
        painter.drawPixmap(QRectF(-w / 2, -h / 2 + lift, w, h), pm, QRectF(pm.rect()))

    # --- Comic: speed lines, cartoon smoke puffs, starburst word, orbiting dizzy stars
    def render_comic(self, painter, e, p):
        t = clamp01(p / 0.35)
        if t < 1.0:
            painter.setPen(QPen(QColor(0, 0, 0, int(220 * (1 - t))), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            grow = ease_out_cubic(t / 0.5) if t < 0.5 else 1.0
            for a, r1, r2 in e.speed_lines:
                inner = r1 + (r2 - r1) * clamp01((t - 0.4) / 0.6)
                outer = r1 + (r2 - r1) * grow
                if outer > inner:
                    ca, sa = math.cos(a), math.sin(a)
                    painter.drawLine(QPointF(ca * inner, sa * inner), QPointF(ca * outer, sa * outer))
        t = clamp01(p / 0.5)
        if t < 1.0:
            for a, dist, rad in e.puffs:
                d = dist + 40 * ease_out_cubic(t)
                r = rad * (0.4 + 0.9 * ease_out_back(t / 0.4)) * (1 - t ** 2)
                if r > 0.5:
                    c = QPointF(math.cos(a) * d, math.sin(a) * d)
                    painter.setPen(QPen(QColor(0, 0, 0, int(255 * (1 - t))), 2.5))
                    painter.setBrush(QColor(255, 255, 255, int(255 * (1 - t))))
                    painter.drawEllipse(c, r, r)
        self.render_word(painter, e, p)
        if p > 0.22:
            t = (p - 0.22) / 0.78
            alpha = 255 * (1 - clamp01((t - 0.6) / 0.4))
            back, front = [], []
            for a0 in e.stars:
                a = a0 + t * 9.0
                depth = math.sin(a)
                (front if depth > 0 else back).append((a, depth))
            for a, depth in back + front:
                c = QPointF(math.cos(a) * 58, -52 + math.sin(a) * 15)
                size = 7.0 + 3.5 * depth
                star = QPolygonF()
                for i in range(10):
                    r = size if i % 2 == 0 else size * 0.45
                    sa = i * math.pi / 5 - math.pi / 2 + t * 4
                    star.append(QPointF(c.x() + math.cos(sa) * r, c.y() + math.sin(sa) * r))
                painter.setPen(QPen(QColor(0, 0, 0, int(alpha)), 1.6))
                painter.setBrush(QColor(255, 222, 0, int(alpha)))
                painter.drawPolygon(star)

    def render_word(self, painter, e, p, rotate=True):
        scale, opacity, lift = self.word_transform(p)
        if opacity <= 0.01:
            return
        painter.save()
        painter.translate(0, lift)
        if rotate:
            painter.rotate(e.rotation)
        painter.setOpacity(painter.opacity() * opacity)
        squash = 1.0 + (0.12 * math.sin(p * 40) * (1 - clamp01(p / 0.35)) if p < 0.35 else 0.0)
        draw_centered(painter, word_art(e.word, e.style)["main"], scale * squash, scale / squash)
        painter.restore()

    # --- Cyber: data bits flying out, glitch pixels, HUD panel with slice glitch + RGB split
    def render_cyber(self, painter, e, p):
        t = clamp01(p / 0.8)
        mono = QFont()
        mono.setFamilies(["Consolas", "Cascadia Mono"])
        mono.setPixelSize(12)
        mono.setWeight(QFont.Weight.Bold)
        painter.setFont(mono)
        for text, a, dist in e.bits:
            d = dist * ease_out_cubic(t)
            painter.setPen(QColor(0, 255, 200, int(230 * (1 - t))))
            painter.drawText(QPointF(math.cos(a) * d - 10, math.sin(a) * d), text)
        rng = random.Random(int(p * 30) + e.seed)
        if p < 0.6:
            for x, y, w, h in e.pixels:
                if rng.random() < 0.6:
                    c = QColor(0, 240, 255) if rng.random() < 0.5 else QColor(255, 0, 170)
                    painter.fillRect(QRectF(x * (0.6 + p), y * (0.6 + p), w, h), with_alpha(c, 200 * (1 - p / 0.6)))

        scale, opacity, lift = self.word_transform(p, appear=0.16, leave=0.75)
        if opacity <= 0.01:
            return
        art = word_art(e.word, "cyber")
        painter.save()
        painter.translate(0, lift)
        painter.rotate(e.rotation * 0.4)
        painter.setOpacity(painter.opacity() * opacity)
        glitch = 1.0 - clamp01(p / 0.4) if p < 0.4 else clamp01((p - 0.75) / 0.25)
        split = 2.0 + 9.0 * glitch
        draw_centered(painter, art["ghost_a"], scale, scale, -split, 0)
        draw_centered(painter, art["ghost_b"], scale, scale, split, 1)
        pm = art["main"]
        size = pm.deviceIndependentSize()
        w, h = size.width() * scale, size.height() * scale
        if glitch > 0.05:
            # draw the panel in horizontal slices shifted sideways
            slices = 7
            for i in range(slices):
                sy0 = i / slices
                shift = rng.uniform(-1, 1) * 16 * glitch if rng.random() < 0.55 else 0.0
                src = QRectF(0, pm.height() * sy0, pm.width(), pm.height() / slices)
                dst = QRectF(-w / 2 + shift, -h / 2 + h * sy0, w, h / slices)
                painter.drawPixmap(dst, pm, src)
        else:
            painter.drawPixmap(QRectF(-w / 2, -h / 2, w, h), pm, QRectF(pm.rect()))
        painter.restore()

    # --- Western: whip slash scar, rolling dust clouds, tumbleweed, unfurling ribbon
    def render_classic(self, painter, e, p):
        t = clamp01(p / 0.5)
        if t < 1.0:
            painter.save()
            painter.rotate(math.degrees(e.slash_angle))
            L = 150 * ease_out_cubic(t / 0.25)
            painter.setPen(QPen(QColor(120, 60, 20, int(220 * (1 - t))), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(-L, 0), QPointF(L, 0))
            painter.setPen(QPen(QColor(255, 230, 170, int(255 * (1 - t))), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(-L, 0), QPointF(L, 0))
            painter.restore()
        t = clamp01(p / 0.95)
        painter.setPen(Qt.PenStyle.NoPen)
        for dx, dy, r, phase in e.dust:
            grow = ease_out_cubic(clamp01(t * 1.6 - phase * 0.3))
            if grow <= 0:
                continue
            c = QPointF(dx * (0.7 + 0.8 * grow), dy + 14 * grow - 10)
            rr = r * (0.5 + 1.1 * grow)
            g = QRadialGradient(c, rr)
            a = 150 * (1 - t)
            g.setColorAt(0, QColor(222, 184, 135, int(a)))
            g.setColorAt(0.7, QColor(205, 160, 105, int(a * 0.6)))
            g.setColorAt(1, QColor(205, 160, 105, 0))
            painter.setBrush(g)
            painter.drawEllipse(c, rr, rr * 0.75)
        # tumbleweed rolling past with little hops
        tw_x = -110 + 220 * t
        tw_y = 46 - abs(math.sin(t * math.pi * 3)) * 18
        painter.save()
        painter.translate(tw_x, tw_y)
        painter.rotate(t * 900)
        a = int(220 * (1 - clamp01((t - 0.75) / 0.25)))
        painter.setPen(QPen(QColor(150, 105, 55, a), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for k in range(6):
            painter.drawEllipse(QRectF(-11, -6 + k * 0.3, 22, 12))
            painter.rotate(30)
        painter.restore()
        # ribbon unfurls horizontally
        scale, opacity, lift = self.word_transform(p, appear=0.22)
        if opacity > 0.01:
            unfurl = 0.15 + 0.85 * ease_out_back(clamp01(p / 0.22), 1.6)
            painter.save()
            painter.translate(0, lift - 6)
            painter.rotate(e.rotation * 0.5)
            painter.setOpacity(painter.opacity() * opacity)
            draw_centered(painter, word_art(e.word, "classic")["main"], scale * unfurl, scale)
            painter.restore()

    # --- Taser: crackling bolts regenerated every few frames, flickering electric word with jitter
    def render_taser(self, painter, e, p):
        rng = random.Random(int(e.elapsed_ms() / 45) + e.seed)
        live = 1.0 - clamp01((p - 0.55) / 0.35)
        if live > 0:
            for a, dist in e.bolt_targets:
                if rng.random() < 0.25:
                    continue
                a2 = a + rng.uniform(-0.35, 0.35)
                d = dist * rng.uniform(0.75, 1.05)
                pts = jagged_bolt(0, 0, math.cos(a2) * d, math.sin(a2) * d, rng)
                poly = QPolygonF(pts)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(56, 189, 248, int(70 * live)), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.drawPolyline(poly)
                painter.setPen(QPen(QColor(224, 242, 254, int(255 * live)), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.drawPolyline(poly)
                if rng.random() < 0.5:
                    mid = pts[len(pts) // 2]
                    br = jagged_bolt(mid.x(), mid.y(), mid.x() + rng.uniform(-40, 40), mid.y() + rng.uniform(-40, 40), rng, 4)
                    painter.setPen(QPen(QColor(254, 240, 138, int(200 * live)), 1.3))
                    painter.drawPolyline(QPolygonF(br))
            # crackling ring
            ring = QPolygonF()
            R = 34 + 10 * p
            for i in range(28):
                a = i * 2 * math.pi / 28
                r = R + rng.uniform(-6, 6)
                ring.append(QPointF(math.cos(a) * r, math.sin(a) * r))
            painter.setPen(QPen(QColor(125, 211, 252, int(200 * live)), 1.6))
            painter.drawPolygon(ring)
        scale, opacity, lift = self.word_transform(p, appear=0.15)
        if opacity > 0.01:
            flicker = 1.0 if p > 0.5 or rng.random() > 0.25 else 0.45
            jx = rng.uniform(-3, 3) * live
            jy = rng.uniform(-3, 3) * live
            painter.save()
            painter.translate(jx, lift + jy - 4)
            painter.rotate(e.rotation * 0.6)
            painter.setOpacity(painter.opacity() * opacity * flicker)
            draw_centered(painter, word_art(e.word, "taser")["main"], scale, scale)
            painter.restore()

    # --- Sword: crescent slash, spider-web glass cracks, flying shards, word cut in two halves
    def render_sword(self, painter, e, p):
        ang = math.degrees(e.slash_angle)
        # glass cracks spreading out
        grow = ease_out_cubic(p / 0.18)
        fade = 1.0 - clamp01((p - 0.6) / 0.4)
        if fade > 0:
            for pts in e.cracks:
                n = max(2, int(len(pts) * grow + 0.999))
                poly = QPolygonF(pts[:n])
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(0, 0, 0, int(80 * fade)), 2.4))
                painter.drawPolyline(poly.translated(1, 1))
                painter.setPen(QPen(QColor(241, 245, 249, int(230 * fade)), 1.3))
                painter.drawPolyline(poly)
            for ring_r in (32, 66):
                if grow * 160 < ring_r:
                    continue
                web = QPolygonF()
                for pts in e.cracks:
                    idx = min(len(pts) - 1, max(1, int(ring_r / 20)))
                    web.append(pts[idx])
                painter.setPen(QPen(QColor(226, 232, 240, int(150 * fade)), 1.0))
                painter.drawPolygon(web)
        # shards
        t = clamp01(p / 0.75)
        for a, speed, size, spin in e.shards:
            d = speed * 30 * t
            sx, sy = math.cos(a) * d, math.sin(a) * d + 160 * t * t
            painter.save()
            painter.translate(sx, sy)
            painter.rotate(spin * t * 40)
            painter.setPen(QPen(QColor(255, 255, 255, int(230 * (1 - t))), 1.0))
            painter.setBrush(QColor(186, 230, 253, int(170 * (1 - t))))
            painter.drawPolygon(QPolygonF([QPointF(0, -size), QPointF(size * 0.6, size * 0.5), QPointF(-size * 0.5, size * 0.4)]))
            painter.restore()
        # crescent slash streak
        t = clamp01(p / 0.55)
        if t < 1.0:
            painter.save()
            painter.rotate(ang)
            L = e.slash_len * ease_out_cubic(t / 0.18)
            width = 12.0 * (1.0 - t) ** 0.7
            for w_mul, color in ((2.6, QColor(147, 197, 253, int(90 * (1 - t)))), (1.0, QColor(255, 255, 255, int(255 * (1 - t))))):
                top, bottom = [], []
                for i in range(25):
                    u = i / 24
                    x = -L + 2 * L * u
                    hw = width * w_mul * math.sin(u * math.pi) ** 1.3 / 2
                    top.append(QPointF(x, -hw - 4 * math.sin(u * math.pi)))
                    bottom.append(QPointF(x, hw - 4 * math.sin(u * math.pi)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawPolygon(QPolygonF(top + bottom[::-1]))
            painter.restore()
        # word cut along the slash: two halves slide apart
        scale, opacity, lift = self.word_transform(p, appear=0.16, leave=0.7)
        if opacity <= 0.01:
            return
        pm = word_art(e.word, "sword")["main"]
        size = pm.deviceIndependentSize()
        w, h = size.width() * scale, size.height() * scale
        cut = ease_out_cubic((p - 0.18) / 0.3) if p > 0.18 else 0.0
        rad = e.slash_angle
        dxu, dyu = math.cos(rad), math.sin(rad)           # along the cut
        nx, ny = -dyu, dxu                                 # cut normal
        big = max(w, h) * 2
        for side in (-1, 1):
            half = QPainterPath()
            half.addPolygon(QPolygonF([
                QPointF(-dxu * big, -dyu * big), QPointF(dxu * big, dyu * big),
                QPointF(dxu * big + nx * big * side, dyu * big + ny * big * side),
                QPointF(-dxu * big + nx * big * side, -dyu * big + ny * big * side)]))
            off = 3.0 * cut              # thin gap opening along the cut...
            slide = 14.0 * cut * side    # ...while the halves slide past each other along it
            painter.save()
            painter.translate(nx * off * side + dxu * slide, ny * off * side + dyu * slide + lift)
            painter.setClipPath(half)
            painter.setOpacity(painter.opacity() * opacity)
            painter.drawPixmap(QRectF(-w / 2, -h / 2, w, h), pm, QRectF(pm.rect()))
            painter.restore()
