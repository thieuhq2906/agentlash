import math
import random
import time
from PyQt6.QtCore import QPointF

HANDLE_LENGTH = 46.0

class VerletNode:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.old_x = float(x)
        self.old_y = float(y)

    def update(self, damping=0.92, gravity=0.4):
        vx = (self.x - self.old_x) * damping
        vy = (self.y - self.old_y) * damping + gravity
        self.old_x = self.x
        self.old_y = self.y
        self.x += vx
        self.y += vy

    def place(self, x, y):
        self.x = self.old_x = float(x)
        self.y = self.old_y = float(y)

class IdleWhipPhysics:
    """Verlet integration rope hanging from a handle held next to the mouse cursor.
    Must be stepped every frame (not only on mouse move) so the cord keeps swinging and settles."""
    REST_ANGLE = -55.0          # handle points up-right (degrees, screen coords)
    GRIP_OFFSET = QPointF(16, 22)  # handle butt sits below-right of the arrow tip, never covering the click point

    def __init__(self, num_nodes=14, segment_length=8):
        self.num_nodes = num_nodes
        self.segment_length = segment_length
        self.nodes = [VerletNode(0, 0) for _ in range(num_nodes)]
        self.handle_pos = QPointF(0, 0)   # butt of the handle (where the hand holds it)
        self.handle_angle = self.REST_ANGLE
        self.last_mouse = None
        self.initialized = False
        self.motion = 0.0  # how much the rope moved last step (used to skip repaints when settled)

    def tip_of_handle(self):
        rad = math.radians(self.handle_angle)
        return QPointF(self.handle_pos.x() + math.cos(rad) * HANDLE_LENGTH,
                       self.handle_pos.y() + math.sin(rad) * HANDLE_LENGTH)

    def reset(self, mouse_x, mouse_y):
        target = QPointF(mouse_x, mouse_y)
        self.last_mouse = target
        self.handle_pos = target + self.GRIP_OFFSET
        self.handle_angle = self.REST_ANGLE
        tip = self.tip_of_handle()
        for i, node in enumerate(self.nodes):
            node.place(tip.x() + i * 2.0, tip.y() + i * self.segment_length)
        self.initialized = True
        self.motion = 1.0

    def step(self, mouse_x, mouse_y):
        target = QPointF(mouse_x, mouse_y)
        if not self.initialized:
            self.reset(mouse_x, mouse_y)
            return

        # Teleport (e.g. cursor jumped to another monitor): don't fling the rope across the desktop
        if math.hypot(target.x() - self.last_mouse.x(), target.y() - self.last_mouse.y()) > 600:
            self.reset(mouse_x, mouse_y)
            return

        # Smooth handle tracking with spring interpolation
        target_handle = target + self.GRIP_OFFSET
        dx = target_handle.x() - self.handle_pos.x()
        dy = target_handle.y() - self.handle_pos.y()
        self.handle_pos = QPointF(self.handle_pos.x() + dx * 0.45, self.handle_pos.y() + dy * 0.45)

        # Handle tilts against the motion (inertia), then springs back to rest
        mv_x = target.x() - self.last_mouse.x()
        mv_y = target.y() - self.last_mouse.y()
        self.last_mouse = target
        tilt = max(-40.0, min(40.0, -mv_x * 1.6 + mv_y * 0.5))
        target_angle = self.REST_ANGLE + tilt
        self.handle_angle += (target_angle - self.handle_angle) * 0.2
        handle_motion = abs(dx) + abs(dy) + abs(target_angle - self.handle_angle)

        # Pin node 0 to the top of the handle
        tip = self.tip_of_handle()
        self.nodes[0].place(tip.x(), tip.y())

        before = [(n.x, n.y) for n in self.nodes]

        # Update remaining nodes with physics
        for i in range(1, self.num_nodes):
            self.nodes[i].update(damping=0.90, gravity=0.45)

        # Bending stiffness: the thick part of the cord keeps following the handle direction, the thin end droops
        rad = math.radians(self.handle_angle)
        prev_dir = (math.cos(rad), math.sin(rad))
        for i in range(1, self.num_nodes):
            base = self.nodes[i - 1]
            if i >= 2:
                px, py = base.x - self.nodes[i - 2].x, base.y - self.nodes[i - 2].y
                pl = math.hypot(px, py) or 1.0
                prev_dir = (px / pl, py / pl)
            k = 0.3 * (1.0 - i / self.num_nodes) ** 2
            n = self.nodes[i]
            n.x += (base.x + prev_dir[0] * self.segment_length - n.x) * k
            n.y += (base.y + prev_dir[1] * self.segment_length - n.y) * k

        # Distance constraints relaxation (multiple iterations for stiffness)
        for _ in range(5):
            for i in range(self.num_nodes - 1):
                n1 = self.nodes[i]
                n2 = self.nodes[i + 1]
                dx = n2.x - n1.x
                dy = n2.y - n1.y
                dist = math.hypot(dx, dy)
                if dist > 0.001:
                    diff = (dist - self.segment_length) / dist
                    if i == 0:
                        # n1 is pinned
                        n2.x -= dx * diff
                        n2.y -= dy * diff
                    else:
                        n1.x += dx * diff * 0.5
                        n1.y += dy * diff * 0.5
                        n2.x -= dx * diff * 0.5
                        n2.y -= dy * diff * 0.5

        rope_motion = max(abs(n.x - bx) + abs(n.y - by) for n, (bx, by) in zip(self.nodes, before))
        self.motion = max(rope_motion, handle_motion)

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

class ActiveStrike:
    """Whip crack animation: wind-up, a loop rolling down the cord, tip snapping into the target, recoil.
    All state changes happen in update(); evaluate_points() is a pure function of the current time."""
    RECOIL_MS = 260.0
    # The animation starts this far into the swing: the wind-up looked nice but made every click feel laggy
    WINDUP_SKIP = 0.35

    def __init__(self, origin_x, origin_y, target_x, target_y, style="comic", duration_ms=90):
        """duration_ms = real delay between the click and the crack"""
        self.origin = QPointF(origin_x, origin_y)
        self.target = QPointF(target_x, target_y)
        self.style = style
        self.crack_ms = float(max(40, duration_ms)) / (1.0 - self.WINDUP_SKIP)
        self.total_ms = self.crack_ms + self.RECOIL_MS
        self.p_crack = self.crack_ms / self.total_ms
        self.start_time = time.perf_counter() - self.crack_ms * self.WINDUP_SKIP / 1000.0
        self.sound_played = False
        self.cracked = False
        self.finished = False

        dx = target_x - origin_x
        dy = target_y - origin_y
        self.dist = max(1.0, math.hypot(dx, dy))
        self.dir_x = dx / self.dist
        self.dir_y = dy / self.dist
        # Bend direction: curve the whip so it arcs "over the top" (upwards on screen) when possible
        perp_x, perp_y = -self.dir_y, self.dir_x
        self.arch_sign = -1.0 if perp_y > 0 else 1.0
        if abs(perp_y) < 0.2:
            self.arch_sign = random.choice((-1.0, 1.0))
        self.perp_x = perp_x * self.arch_sign
        self.perp_y = perp_y * self.arch_sign

        # Number of sample points along the whip
        self.num_pts = 26

    def get_progress(self):
        elapsed = (time.perf_counter() - self.start_time) * 1000.0
        return min(1.0, elapsed / self.total_ms)

    def ms_until_crack(self):
        return self.crack_ms - (time.perf_counter() - self.start_time) * 1000.0

    def update(self):
        """Advances state. Returns True exactly once: on the frame the tip cracks."""
        p = self.get_progress()
        just_cracked = False
        if p >= self.p_crack and not self.cracked:
            self.cracked = True
            just_cracked = True
        if p >= 1.0:
            self.finished = True
        return just_cracked

    def handle_point(self, p):
        """Hand position: pulls back during wind-up, thrusts forward at the crack, settles back"""
        if p < self.p_crack:
            t = p / self.p_crack
            offset = -18.0 * math.sin(t * math.pi) if t < 0.5 else -18.0 + 46.0 * smoothstep((t - 0.5) * 2.0)
        else:
            s = (p - self.p_crack) / (1.0 - self.p_crack)
            offset = 28.0 * (1.0 - smoothstep(s))
        return QPointF(self.origin.x() + self.dir_x * offset, self.origin.y() + self.dir_y * offset)

    def evaluate_points(self):
        """Returns (points from handle to tip, progress). Does not mutate the strike."""
        p = self.get_progress()
        h = self.handle_point(p)
        dx = self.target.x() - h.x()
        dy = self.target.y() - h.y()
        L = self.dist

        pts = []
        if p < self.p_crack:
            t = p / self.p_crack
            # Whip starts coiled "behind" (big arc, tip far from target) and straightens as the loop travels
            straighten = (1.0 - t) ** 1.6
            wave_pos = t ** 1.35  # loop accelerates as the cord thins out
            for i in range(self.num_pts):
                u = i / float(self.num_pts - 1)  # 0.0 handle -> 1.0 tip
                arch = math.sin(u * math.pi * 0.5) * u * L * 0.55 * straighten
                loop = math.exp(-((u - wave_pos) ** 2) / 0.012) * L * 0.18 * (1.0 - u ** 3)  # tip lands exactly on target
                along = u * (0.80 + 0.20 * smoothstep(t))  # cord slightly "shorter" (rolled up) before extension
                off = arch - loop
                pts.append(QPointF(h.x() + dx * along + self.perp_x * off,
                                   h.y() + dy * along + self.perp_y * off))
        else:
            s = (p - self.p_crack) / (1.0 - self.p_crack)
            # Damped recoil wobble, strongest near the tip; tip bounces back a little from the target
            wobble = math.exp(-s * 3.2) * math.sin(s * 17.0) * L * 0.22
            pull_back = 0.12 * smoothstep(s)
            for i in range(self.num_pts):
                u = i / float(self.num_pts - 1)
                off = math.sin(u * math.pi * 0.9) * u * wobble
                along = u * (1.0 - pull_back * u)
                pts.append(QPointF(h.x() + dx * along + self.perp_x * off,
                                   h.y() + dy * along + self.perp_y * off))
        return pts, p

    def alpha(self):
        p = self.get_progress()
        s = (p - self.p_crack) / (1.0 - self.p_crack)
        return 1.0 if s < 0.45 else max(0.0, 1.0 - (s - 0.45) / 0.55)

SPARK_COLORS = {
    "cyber": ((0, 255, 255), (255, 0, 200), (255, 255, 255)),
    "classic": ((255, 180, 50), (240, 60, 30), (255, 235, 160)),
    "comic": ((255, 230, 0), (255, 40, 40), (255, 255, 255)),
    "sword": ((220, 230, 245), (180, 195, 215), (255, 240, 150), (255, 255, 255)),
    "taser": ((56, 189, 248), (254, 240, 138), (255, 255, 255), (14, 165, 233)),
}

class SparkParticle:
    """High-velocity impact spark or electric discharge particle"""
    def __init__(self, x, y, style="comic"):
        self.x = float(x)
        self.y = float(y)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(4.0, 14.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.style = style
        self.color = random.choice(SPARK_COLORS.get(style, SPARK_COLORS["comic"]))
        self.life = 1.0
        self.decay = random.uniform(0.035, 0.075)
        self.size = random.uniform(3.0, 7.0)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        if self.style not in ("cyber", "taser"):
            self.vy += 0.3  # gravity for dust/sparks
        self.life -= self.decay
        return self.life > 0
