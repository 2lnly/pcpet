"""Procedural vector art for every species.

Everything is drawn in a 100 x 100 unit box with the character facing
right and standing on the line ``y = GROUND``.  The renderer takes care of
scaling to pixels, mirroring for left-facing pets and rotating for pets
that climb walls.  Keeping the art in code (instead of image files) means
pets stay crisp at any size and on any display density.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTransform,
)

from .species import Pose, Species, Variant

__all__ = ["Pose", "draw_pet", "draw_icon", "heart_path"]

GROUND = 96.0
OUTLINE_W = 2.6
TAU = math.tau


# --------------------------------------------------------------------------
# small drawing helpers
# --------------------------------------------------------------------------

_color_cache: dict[tuple, QColor] = {}


def col(value, alpha: int | None = None) -> QColor:
    key = (value, alpha)
    c = _color_cache.get(key)
    if c is None:
        c = QColor(value)
        if alpha is not None:
            c.setAlpha(alpha)
        _color_cache[key] = c
    return QColor(c)


def round_pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def shape(p: QPainter, path: QPainterPath, fill: QColor, outline: QColor, width: float = OUTLINE_W):
    """Fill a closed path and give it an outline."""
    p.setPen(round_pen(outline, width))
    p.setBrush(QBrush(fill))
    p.drawPath(path)


def tube(p: QPainter, path: QPainterPath, width: float, fill: QColor, outline: QColor):
    """Stroke an open path as a thick outlined tube (legs, tails, ears)."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(round_pen(outline, width + OUTLINE_W * 2))
    p.drawPath(path)
    p.setPen(round_pen(fill, width))
    p.drawPath(path)


def line_path(a, b) -> QPainterPath:
    path = QPainterPath(QPointF(*a))
    path.lineTo(QPointF(*b))
    return path


def cubic_path(pts) -> QPainterPath:
    path = QPainterPath(QPointF(*pts[0]))
    path.cubicTo(QPointF(*pts[1]), QPointF(*pts[2]), QPointF(*pts[3]))
    return path


def bezier_point(pts, t: float):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    u = 1 - t
    x = u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3
    y = u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3
    return x, y


def ellipse_path(cx: float, cy: float, w: float, h: float, angle: float = 0.0) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(0, 0), w / 2, h / 2)
    t = QTransform()
    t.translate(cx, cy)
    t.rotate(angle)
    return t.map(path)


def heart_path(cx: float, cy: float, s: float) -> QPainterPath:
    """A heart roughly ``s`` units wide centred on (cx, cy)."""
    path = QPainterPath(QPointF(cx, cy + s * 0.42))
    path.cubicTo(QPointF(cx - s * 0.62, cy + s * 0.02), QPointF(cx - s * 0.58, cy - s * 0.52),
                 QPointF(cx, cy - s * 0.22))
    path.cubicTo(QPointF(cx + s * 0.58, cy - s * 0.52), QPointF(cx + s * 0.62, cy + s * 0.02),
                 QPointF(cx, cy + s * 0.42))
    path.closeSubpath()
    return path


def draw_shadow(p: QPainter, cx: float, scale: float = 1.0, width: float = 30.0):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(0, 0, 0, 38)))
    p.drawEllipse(QPointF(cx, GROUND + 0.5), width * scale, 3.4 * scale)


def apply_whole(p: QPainter, dx=0.0, dy=0.0, angle=0.0, sx=1.0, sy=1.0, pivot=(50.0, GROUND)):
    px, py = pivot
    p.translate(px + dx, py + dy)
    if angle:
        p.rotate(angle)
    if sx != 1.0 or sy != 1.0:
        p.scale(sx, sy)
    p.translate(-px, -py)


# --------------------------------------------------------------------------
# faces
# --------------------------------------------------------------------------

def draw_eye(p: QPainter, x: float, y: float, k: float, style: str, colors: dict):
    outline = col(colors["outline"])
    if style in ("closed", "blink"):
        path = QPainterPath(QPointF(x - 3.2 * k, y))
        if style == "closed":
            path.quadTo(QPointF(x, y + 2.8 * k), QPointF(x + 3.2 * k, y))
        else:
            path.lineTo(QPointF(x + 3.2 * k, y + 0.4 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(round_pen(outline, 1.9 * k))
        p.drawPath(path)
        return
    if style == "happy":
        path = QPainterPath(QPointF(x - 3.4 * k, y + 1.2 * k))
        path.quadTo(QPointF(x, y - 3.6 * k), QPointF(x + 3.4 * k, y + 1.2 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(round_pen(outline, 2.0 * k))
        p.drawPath(path)
        return
    wide = style == "wide"
    rx, ry = (3.3 * k, 4.2 * k) if wide else (2.6 * k, 3.4 * k)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(col(colors["eye"])))
    p.drawEllipse(QPointF(x, y), rx, ry)
    pupil = colors.get("pupil")
    if pupil:
        p.setBrush(QBrush(col(pupil)))
        p.drawEllipse(QPointF(x + 0.2 * k, y + 0.2 * k), rx * 0.42, ry * 0.8)
    p.setBrush(QBrush(QColor(255, 255, 255, 235)))
    p.drawEllipse(QPointF(x + rx * 0.35, y - ry * 0.42), rx * 0.42, rx * 0.42)


def draw_mouth(p: QPainter, x: float, y: float, k: float, style: str, colors: dict):
    outline = col(colors["outline"])
    if style == "none":
        return
    if style in ("open", "munch"):
        path = QPainterPath(QPointF(x - 2.6 * k, y))
        path.quadTo(QPointF(x, y + (5.2 if style == "open" else 3.6) * k), QPointF(x + 2.6 * k, y))
        path.closeSubpath()
        p.setPen(round_pen(outline, 1.4 * k))
        p.setBrush(QBrush(col("#E86A7A")))
        p.drawPath(path)
        return
    if style == "o":
        p.setPen(round_pen(outline, 1.4 * k))
        p.setBrush(QBrush(col("#E86A7A")))
        p.drawEllipse(QPointF(x, y + 1.4 * k), 1.5 * k, 1.8 * k)
        return
    # "smile": the classic "w"
    path = QPainterPath(QPointF(x - 3.2 * k, y))
    path.quadTo(QPointF(x - 1.6 * k, y + 2.4 * k), QPointF(x, y))
    path.quadTo(QPointF(x + 1.6 * k, y + 2.4 * k), QPointF(x + 3.2 * k, y))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(round_pen(outline, 1.4 * k))
    p.drawPath(path)


def draw_cheeks(p: QPainter, xs, y: float, k: float, alpha: int = 110):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 128, 140, alpha)))
    for x in xs:
        p.drawEllipse(QPointF(x, y), 3.2 * k, 2.0 * k)


# --------------------------------------------------------------------------
# quadrupeds: cat, dog, fox, bunny share one rig with different looks
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class QuadLook:
    ears: str  # pointy | floppy | big | long
    tail: str  # long | wag | bushy | puff
    snout: bool
    whiskers: bool
    hop: bool
    body_w: float
    body_h: float
    head_r: float
    leg_w: float
    tail_w: float


LOOKS = {
    "cat": QuadLook("pointy", "long", False, True, False, 50, 28, 19, 8.5, 6.5),
    "dog": QuadLook("floppy", "wag", True, False, False, 52, 30, 19, 9.5, 7.0),
    "fox": QuadLook("big", "bushy", True, False, False, 52, 26, 18, 7.5, 11.0),
    "bunny": QuadLook("long", "puff", False, False, True, 46, 32, 17, 8.0, 0.0),
}


@dataclass
class Leg:
    hip: tuple
    foot: tuple
    far: bool
    big_foot: bool = False  # bunny back feet are drawn as ovals


@dataclass
class QuadRig:
    body: tuple  # cx, cy, w, h, angle
    head: tuple  # cx, cy, r
    legs: list = field(default_factory=list)
    haunch: tuple | None = None  # cx, cy, w, h
    paws: list = field(default_factory=list)  # loose paw ovals (sleeping, sitting)
    tail: tuple | None = None  # cubic control points
    eyes: str = "open"
    mouth: str = "smile"
    ear_tilt: float = 0.0
    head_tilt: float = 0.0
    whole: dict = field(default_factory=dict)
    shadow: float = 1.0


def _breath(frame: int) -> float:
    return (0.0, 0.6, 1.0, 0.6)[frame % 4]


def quad_rig(look: QuadLook, pose: Pose) -> QuadRig:
    if look.hop:
        return _bunny_rig(look, pose)
    name, f = pose.name, pose.frame
    bw, bh, hr, lw = look.body_w, look.body_h, look.head_r, look.leg_w
    bcx = 48.0
    bcy = 85.0 - bh / 2
    hip_y = bcy + bh * 0.18
    foot_y = GROUND - lw / 2 - OUTLINE_W / 2
    back_x = bcx - bw * 0.34
    front_x = bcx + bw * 0.2
    head = (bcx + bw * 0.45, bcy - bh / 2 - 8, hr)
    tb = (bcx - bw * 0.46, bcy - bh * 0.15)  # tail base

    def tail_up(swing=0.0, lift=0.0):
        bx, by = tb
        if look.tail == "long":
            return ((bx, by), (bx - 12, by - 4), (bx - 14, by - 20 - lift), (bx - 8 + swing, by - 28 - lift))
        if look.tail == "wag":
            return ((bx, by), (bx - 7, by - 3), (bx - 10, by - 10 - lift), (bx - 8 + swing, by - 19 - lift))
        if look.tail == "bushy":
            return ((bx + 2, by), (bx - 7, by + 1), (bx - 12, by - 3 - lift), (bx - 9 + swing * 0.4, by - 13 - lift))
        return None

    def legs_at(offsets):
        xs = (back_x, back_x + 7, front_x, front_x + 7)
        fars = (True, False, True, False)
        out = []
        for x, far, (dx, lift) in zip(xs, fars, offsets):
            out.append(Leg((x, hip_y), (x + dx, foot_y - lift), far))
        return out

    standing = [(0, 0)] * 4
    rig = QuadRig(body=(bcx, bcy, bw, bh, 0.0), head=head, legs=legs_at(standing), tail=tail_up())

    if name in ("stand", "cling"):
        b = _breath(f)
        rig.body = (bcx, bcy - b * 0.3, bw, bh + b * 0.8, 0.0)
        rig.head = (head[0], head[1] - b * 0.5, hr)
        rig.tail = tail_up(swing=math.sin(f / 4 * TAU) * 4)
    elif name in ("walk", "climb"):
        ph = f / 8 * TAU
        offs = []
        for shift in (math.pi, 0.0, 0.0, math.pi):  # far-back, near-back, far-front, near-front
            a = ph + shift
            offs.append((6.0 * math.sin(a), max(0.0, math.cos(a)) * 3.5))
        rig.legs = legs_at(offs)
        bob = abs(math.sin(ph)) * 1.4
        rig.body = (bcx, bcy - bob, bw, bh, 0.0)
        rig.head = (head[0], head[1] - bob * 1.1, hr)
        rig.tail = tail_up(swing=math.sin(ph) * 3)
    elif name == "run":
        ph = f / 6 * TAU
        offs = []
        for x_shift, a_shift in ((0.0, math.pi), (0.0, math.pi + 0.6), (0.0, 0.0), (0.0, 0.6)):
            a = ph + a_shift
            offs.append((10.0 * math.sin(a), max(0.0, math.cos(a)) * 5.0))
        rig.legs = legs_at(offs)
        bob = abs(math.sin(ph)) * 3.0
        rig.body = (bcx, bcy - bob, bw + 3, bh - 1, 3.0 * math.sin(ph))
        rig.head = (head[0] + 2, head[1] - bob + 2, hr)
        rig.ear_tilt = -18
        bx, by = tb
        if look.tail == "long":
            rig.tail = ((bx, by), (bx - 10, by - 2), (bx - 14, by - 8), (bx - 15.5, by - 14 + math.sin(ph) * 3))
        elif look.tail == "wag":
            rig.tail = ((bx, by), (bx - 7, by - 3), (bx - 10, by - 7), (bx - 12, by - 12 + math.sin(ph) * 2))
        else:
            rig.tail = ((bx + 2, by), (bx - 6, by), (bx - 11, by - 2), (bx - 12, by - 8 + math.sin(ph) * 2))
    elif name == "sit":
        b = _breath(f)
        rig.body = (bcx - 3, bcy + 2, bw * 0.8, bh, -48.0)
        rig.haunch = (bcx - 10, 85.0, bw * 0.52, 20 + b * 0.3)
        fx = bcx + bw * 0.12
        rig.legs = [Leg((fx - 5, bcy - 2), (fx - 4, foot_y), True), Leg((fx, bcy - 2), (fx + 1, foot_y), False)]
        rig.paws = [(bcx - 2, 93.2, 13, 6)]
        rig.head = (bcx + bw * 0.24, bcy - bh / 2 - 15 - b * 0.4, hr)
        sw = math.sin(f / 4 * TAU) * 2
        rig.tail = ((bcx - 18, 88), (bcx - 32, 95), (bcx - 10 + sw, 99), (bcx + 6 + sw, 93.5))
        if look.tail == "bushy":
            rig.tail = ((bcx - 18, 86), (bcx - 32, 92), (bcx - 14 + sw, 98), (bcx + 4 + sw, 91.5))
    elif name == "sleep":
        b = _breath(f)
        rig.body = (bcx - 2, 84.0 - b * 0.5, bw + 6, bh * 0.78 + b * 1.2, 0.0)
        rig.legs = []
        rig.paws = [(bcx + bw * 0.5, 92.5, 11, 6)]
        rig.head = (bcx + bw * 0.44, 75.0 + b * 0.3, hr * 0.95)
        rig.head_tilt = 8
        rig.eyes = "closed"
        rig.mouth = "smile"
        rig.ear_tilt = -8
        rig.tail = ((bcx - bw * 0.48, 87), (bcx - bw * 0.7, 96), (bcx - 14, 98.5), (bcx + 6, 94.5))
        if look.tail == "bushy":
            rig.tail = ((bcx - bw * 0.48, 85), (bcx - bw * 0.72, 93), (bcx - 16, 97.5), (bcx + 4, 92))
        if look.tail == "wag":
            rig.tail = ((bcx - bw * 0.5, 86), (bcx - bw * 0.62, 92), (bcx - bw * 0.58, 96), (bcx - bw * 0.42, 95))
    elif name == "air":
        flap = 1.5 if f % 2 else 0.0
        rig.legs = legs_at([(-7, 5 + flap), (-6, 6 - flap), (8, 5 - flap), (9, 6 + flap)])
        rig.eyes = "wide"
        rig.mouth = "o"
        rig.ear_tilt = 6
        rig.tail = tail_up(lift=4)
        rig.shadow = 0.0
    elif name == "drag":
        sw = (-1.0, 0.0, 1.0, 0.0)[f % 4]
        rig.legs = legs_at([(-1 + sw, -2.0), (0.5 + sw, -1.0), (-0.5 + sw, -1.0), (1 + sw, -2.0)])
        rig.body = (bcx, bcy, bw - 2, bh + 2, 0.0)
        rig.eyes = "wide"
        rig.mouth = "o"
        bx, by = tb
        rig.tail = ((bx, by), (bx - 6, by + 6), (bx - 6 + sw * 2, by + 14), (bx - 3 + sw * 3, by + 21))
        rig.whole = {"angle": sw * 5.0, "pivot": (50.0, 40.0)}
        rig.shadow = 0.0
    elif name == "happy":
        up = math.sin(f / 4 * math.pi) * 7.0
        rig.whole = {"dy": -up}
        rig.legs = legs_at([(-1, up * 0.2), (0, up * 0.25), (1, up * 0.25), (2, up * 0.2)])
        rig.eyes = "happy"
        rig.mouth = "open"
        rig.ear_tilt = 4
        rig.tail = tail_up(swing=(-5.0, 5.0)[f % 2], lift=2)
        rig.shadow = 1.0 - up / 14.0
    elif name == "eat":
        chew = (0.0, 1.5, 0.0, 1.5)[f % 4]
        rig.head = (bcx + bw * 0.5, bcy + 1 + chew, hr)
        rig.head_tilt = 6
        rig.legs = legs_at([(0, 0), (0, 0), (-2, 0), (-2, 0)])
        rig.eyes = "happy" if f % 4 in (1, 2) else "closed"
        rig.mouth = "munch" if f % 2 else "smile"
        rig.tail = tail_up(swing=math.sin(f / 4 * TAU) * 4)
    elif name == "land":
        rig.whole = {"sx": 1.06, "sy": 0.86}
        rig.eyes = "closed"
        rig.mouth = "o"
    return rig


def _bunny_rig(look: QuadLook, pose: Pose) -> QuadRig:
    name, f = pose.name, pose.frame
    bw, bh, hr, lw = look.body_w, look.body_h, look.head_r, look.leg_w
    bcx, bcy = 46.0, 94.0 - bh / 2
    foot_y = GROUND - lw / 2 - OUTLINE_W / 2
    head = (bcx + bw * 0.4, bcy - bh / 2 - 6, hr)

    def legs(back_dx=0.0, front_dx=0.0, lift=0.0, back_lift=0.0):
        return [
            Leg((bcx - 14, 92.0 - back_lift), (bcx - 14 + back_dx, 92.0 - back_lift), True, big_foot=True),
            Leg((bcx - 6, 93.0 - back_lift), (bcx - 6 + back_dx, 93.0 - back_lift), False, big_foot=True),
            Leg((bcx + 10, bcy + 6), (bcx + 11 + front_dx, foot_y - lift), True),
            Leg((bcx + 16, bcy + 6), (bcx + 17 + front_dx, foot_y - lift), False),
        ]

    rig = QuadRig(body=(bcx, bcy, bw, bh, 0.0), head=head, legs=legs(), tail=None)

    def hop(t: float, height: float, air_frac: float):
        if t < air_frac:
            return math.sin(math.pi * t / air_frac) * height
        return 0.0

    if name in ("stand", "cling"):
        b = _breath(f)
        rig.body = (bcx, bcy - b * 0.4, bw, bh + b * 0.8, 0.0)
        rig.head = (head[0], head[1] - b * 0.6, hr)
        rig.ear_tilt = math.sin(f / 4 * TAU) * 2
    elif name in ("walk", "run", "climb", "happy"):
        frames = 6 if name == "run" else (4 if name == "happy" else 8)
        height = {"run": 9.0, "happy": 8.0}.get(name, 8.0)
        h = hop((f % frames) / frames, height, 0.7 if name == "run" else 0.62)
        k = h / height
        rig.whole = {"dy": -h}
        rig.legs = legs(back_dx=-6 * k, front_dx=4 * k, lift=2.5 * k, back_lift=2 * k)
        rig.ear_tilt = -12 * k
        rig.shadow = 1.0 - h / 24.0
        if name == "happy":
            rig.eyes = "happy"
            rig.mouth = "open"
            rig.legs = legs()
    elif name == "sit":
        b = _breath(f)
        rig.body = (bcx, bcy + 2, bw + 4, bh - 2 + b * 0.6, 0.0)
        rig.legs = []
        rig.paws = [(bcx + 14, 93.0, 9, 5.5), (bcx - 10, 93.5, 18, 6)]
        rig.head = (head[0], head[1] + 2 - b * 0.4, hr)
    elif name == "sleep":
        b = _breath(f)
        rig.body = (bcx, 84.0 - b * 0.5, bw + 8, bh * 0.75 + b * 1.2, 0.0)
        rig.legs = []
        rig.paws = [(bcx + 22, 93.0, 9, 5.5)]
        rig.head = (bcx + bw * 0.42, 76.0 + b * 0.3, hr * 0.95)
        rig.head_tilt = 6
        rig.ear_tilt = -62
        rig.eyes = "closed"
    elif name == "air":
        rig.legs = legs(back_dx=-8, front_dx=5, lift=4, back_lift=4)
        rig.eyes = "wide"
        rig.mouth = "o"
        rig.ear_tilt = 8
        rig.shadow = 0.0
    elif name == "drag":
        sw = (-1.0, 0.0, 1.0, 0.0)[f % 4]
        rig.legs = [
            Leg((bcx - 12, 90.0), (bcx - 12 + sw, 98.0), True),
            Leg((bcx - 4, 90.0), (bcx - 4 + sw, 98.0), False),
            Leg((bcx + 10, bcy + 6), (bcx + 10 + sw, foot_y + 1), True),
            Leg((bcx + 16, bcy + 6), (bcx + 16 + sw, foot_y + 1), False),
        ]
        rig.eyes = "wide"
        rig.mouth = "o"
        rig.ear_tilt = 10
        rig.whole = {"angle": sw * 5.0, "pivot": (50.0, 40.0)}
        rig.shadow = 0.0
    elif name == "eat":
        chew = (0.0, 1.5, 0.0, 1.5)[f % 4]
        rig.head = (bcx + bw * 0.5, bcy - 2 + chew, hr)
        rig.head_tilt = 6
        rig.eyes = "happy" if f % 4 in (1, 2) else "closed"
        rig.mouth = "munch" if f % 2 else "smile"
        rig.ear_tilt = -10
    elif name == "land":
        rig.whole = {"sx": 1.1, "sy": 0.84}
        rig.eyes = "closed"
        rig.mouth = "o"
    return rig


def _draw_ears(p: QPainter, look: QuadLook, colors: dict, hx: float, hy: float, r: float, tilt: float,
               front: bool):
    """Ears drawn behind the head (front=False) or on top of it (front=True)."""
    body = col(colors["body"])
    outline = col(colors["outline"])
    inner = col(colors.get("inner_ear", colors.get("accent", colors["body"])))
    if look.ears in ("pointy", "big") and not front:
        size = 1.0 if look.ears == "pointy" else 1.18
        for base_deg in (-128.0, -52.0):
            a = math.radians(base_deg + tilt)
            spread = 0.40 if look.ears == "pointy" else 0.36
            b1 = (hx + r * 0.92 * math.cos(a - spread), hy + r * 0.92 * math.sin(a - spread))
            b2 = (hx + r * 0.92 * math.cos(a + spread), hy + r * 0.92 * math.sin(a + spread))
            tip = (hx + r * 1.5 * size * math.cos(a), hy + r * 1.5 * size * math.sin(a))
            path = QPainterPath(QPointF(*b1))
            path.lineTo(QPointF(*tip))
            path.lineTo(QPointF(*b2))
            path.closeSubpath()
            shape(p, path, body, outline)
            i1 = (hx + r * 0.95 * math.cos(a - spread * 0.55), hy + r * 0.95 * math.sin(a - spread * 0.55))
            i2 = (hx + r * 0.95 * math.cos(a + spread * 0.55), hy + r * 0.95 * math.sin(a + spread * 0.55))
            itip = (hx + r * 1.36 * size * math.cos(a), hy + r * 1.36 * size * math.sin(a))
            path = QPainterPath(QPointF(*i1))
            path.lineTo(QPointF(*itip))
            path.lineTo(QPointF(*i2))
            path.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(inner))
            p.drawPath(path)
    elif look.ears == "long" and not front:
        for dx, lean in ((-5.5, -8.0), (5.0, 6.0)):
            a = math.radians(-90 + lean + tilt)
            base = (hx + dx, hy - r * 0.7)
            length = 24.0
            tip = (base[0] + length * math.cos(a), base[1] + length * math.sin(a))
            tube(p, line_path(base, tip), 8.5, body, outline)
            mid = (base[0] + length * 0.25 * math.cos(a), base[1] + length * 0.25 * math.sin(a))
            p.setPen(round_pen(inner, 3.6))
            p.drawLine(QPointF(*mid), QPointF(*tip))
    elif look.ears == "floppy" and front:
        accent = col(colors.get("accent", colors["body"]))
        for side in (-1, 1):
            cx = hx + side * r * 0.86
            cy = hy - r * 0.05
            path = ellipse_path(cx, cy, 11.0, 21.0, side * (-14.0 + tilt * 0.3))
            shape(p, path, accent, outline)


def draw_quadruped(p: QPainter, species_id: str, colors: dict, pose: Pose, shadow: bool,
                   head_only: bool = False):
    look = LOOKS[species_id]
    rig = quad_rig(look, pose)
    body = col(colors["body"])
    belly = col(colors.get("belly", colors["body"]))
    outline = col(colors["outline"])
    accent = col(colors.get("accent", colors["body"]))
    far_body = body.darker(112)
    socks = colors.get("socks")

    if shadow and rig.shadow > 0 and not head_only:
        draw_shadow(p, 48.0, rig.shadow, 30.0 if not look.hop else 26.0)

    p.save()
    apply_whole(p, **rig.whole)
    if head_only:
        _draw_head(p, look, rig, colors, pose)
        p.restore()
        return

    # tail (behind everything)
    if rig.tail is not None and look.tail != "puff":
        path = cubic_path(rig.tail)
        tube(p, path, look.tail_w, body, outline)
        tip_color = colors.get("tail_tip")
        if tip_color:
            pts = [bezier_point(rig.tail, 0.72 + i * 0.04) for i in range(8)]
            tip_path = QPainterPath(QPointF(*pts[0]))
            for pt in pts[1:]:
                tip_path.lineTo(QPointF(*pt))
            p.setPen(round_pen(col(tip_color), look.tail_w))
            p.drawPath(tip_path)

    # legs: far ones darker, all behind the body
    for leg in rig.legs:
        fill = far_body if leg.far else body
        if leg.big_foot:
            fx, fy = leg.foot
            path = ellipse_path(fx, fy, 18.0 if leg.far else 21.0, 8.0, 0.0)
            shape(p, path, fill, outline)
            continue
        tube(p, line_path(leg.hip, leg.foot), look.leg_w, fill, outline)
        if socks:
            fx, fy = leg.foot
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(col(socks).darker(112) if leg.far else col(socks)))
            p.drawEllipse(QPointF(fx, fy), look.leg_w / 2, look.leg_w / 2)

    # body
    bcx, bcy, bw, bh, bang = rig.body
    body_path = ellipse_path(bcx, bcy, bw, bh, bang)
    shape(p, body_path, body, outline)
    p.save()
    p.setClipPath(body_path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(belly))
    if pose.name == "sit":
        p.drawEllipse(QPointF(bcx + bw * 0.3, bcy - bh * 0.05), bw * 0.28, bh * 0.55)
    else:
        p.drawEllipse(QPointF(bcx + bw * 0.22, bcy + bh * 0.42), bw * 0.32, bh * 0.36)
    if colors.get("stripes") and pose.name != "sit":
        p.setPen(round_pen(accent, 2.4))
        for i in range(3):
            x = bcx - bw * 0.12 + i * 7.5
            p.drawLine(QPointF(x, bcy - bh * 0.62), QPointF(x - 1.5, bcy - bh * 0.18))
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(round_pen(outline, OUTLINE_W))
    p.drawPath(body_path)

    if rig.haunch is not None:
        hx_, hy_, hw_, hh_ = rig.haunch
        shape(p, ellipse_path(hx_, hy_, hw_, hh_, -10.0), body, outline)
    for (px_, py_, pw_, ph_) in rig.paws:
        shape(p, ellipse_path(px_, py_, pw_, ph_), col(socks) if socks else body, outline)

    if look.tail == "puff":
        tx, ty = rig.body[0] - rig.body[2] * 0.48, rig.body[1] - rig.body[3] * 0.05
        shape(p, ellipse_path(tx, ty, 13.0, 12.0), belly if belly != body else body.lighter(108), outline)

    _draw_head(p, look, rig, colors, pose)
    p.restore()


def _draw_head(p: QPainter, look: QuadLook, rig: QuadRig, colors: dict, pose: Pose):
    body = col(colors["body"])
    belly = col(colors.get("belly", colors["body"]))
    outline = col(colors["outline"])
    accent = col(colors.get("accent", colors["body"]))
    hx, hy, r = rig.head
    p.save()
    if rig.head_tilt:
        p.translate(hx, hy)
        p.rotate(rig.head_tilt)
        p.translate(-hx, -hy)
    _draw_ears(p, look, colors, hx, hy, r, rig.ear_tilt, front=False)
    head_path = ellipse_path(hx, hy, r * 2.08, r * 1.92)
    shape(p, head_path, body, outline)
    k = r / 19.0
    fx, fy = hx + 2.5 * k, hy + 2.0 * k
    if colors.get("stripes"):
        p.save()
        p.setClipPath(head_path)
        p.setPen(round_pen(accent, 2.2))
        for dx in (-4.5, 0.0, 4.5):
            p.drawLine(QPointF(hx + dx, hy - r * 0.98), QPointF(hx + dx * 0.8, hy - r * 0.62))
        p.restore()
    eyes = "blink" if (pose.blink and rig.eyes == "open") else rig.eyes
    if look.snout:
        sx, sy = fx, fy + 6.8 * k
        shape(p, ellipse_path(sx, sy, 16.5 * k, 11.5 * k), belly, outline, 2.0)
        draw_eye(p, fx - 7.6 * k, fy - 3.4 * k, k, eyes, colors)
        draw_eye(p, fx + 7.6 * k, fy - 3.4 * k, k, eyes, colors)
        draw_cheeks(p, (fx - 12.0 * k, fx + 12.0 * k), fy + 2.6 * k, k)
        nose = QPainterPath()
        nose.addRoundedRect(QRectF(sx - 3.2 * k, sy - 4.8 * k, 6.4 * k, 4.2 * k), 2.0 * k, 2.0 * k)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col(colors.get("nose", colors["outline"]))))
        p.drawPath(nose)
        draw_mouth(p, sx, sy - 0.2 * k, k * 0.9, rig.mouth, colors)
    else:
        draw_eye(p, fx - 7.0 * k, fy - 1.6 * k, k, eyes, colors)
        draw_eye(p, fx + 7.0 * k, fy - 1.6 * k, k, eyes, colors)
        draw_cheeks(p, (fx - 11.5 * k, fx + 11.5 * k), fy + 4.0 * k, k)
        nose = QPainterPath(QPointF(fx - 2.1 * k, fy + 2.6 * k))
        nose.lineTo(QPointF(fx + 2.1 * k, fy + 2.6 * k))
        nose.lineTo(QPointF(fx, fy + 4.6 * k))
        nose.closeSubpath()
        p.setPen(round_pen(col(colors.get("nose", "#E59AA6")), 1.2 * k))
        p.setBrush(QBrush(col(colors.get("nose", "#E59AA6"))))
        p.drawPath(nose)
        draw_mouth(p, fx, fy + 5.0 * k, k, rig.mouth, colors)
        if look.whiskers:
            p.setPen(round_pen(col(colors["outline"], 150), 0.9 * k))
            for side in (-1, 1):
                for dy, spread in ((0.0, -1.2), (2.2, 1.0)):
                    x0 = fx + side * 9.5 * k
                    p.drawLine(QPointF(x0, fy + (4.0 + dy) * k),
                               QPointF(x0 + side * 7.5 * k, fy + (4.0 + dy + spread) * k))
    _draw_ears(p, look, colors, hx, hy, r, rig.ear_tilt, front=True)
    p.restore()


# --------------------------------------------------------------------------
# chick
# --------------------------------------------------------------------------

def draw_chick(p: QPainter, colors: dict, pose: Pose, shadow: bool):
    name, f = pose.name, pose.frame
    body = col(colors["body"])
    wing = col(colors["wing"])
    outline = col(colors["outline"])
    beak = col(colors["beak"])
    cx, cy, r = 50.0, 69.0, 23.0
    whole: dict = {}
    eyes, mouth_open = "open", False
    wing_angle, wing_lift = -12.0, 0.0
    feet = [(0.0, 0.0), (0.0, 0.0)]  # (dx, lift) for far, near
    show_feet = True
    sx, sy = 1.0, 1.0
    shadow_k = 1.0

    if name in ("stand", "cling"):
        b = _breath(f)
        sy = 1.0 + b * 0.015
    elif name in ("walk", "climb", "run"):
        frames = 6 if name == "run" else 8
        ph = (f % frames) / frames * TAU
        amp = 9.0 if name == "run" else 6.0
        whole = {"angle": amp * math.sin(ph)}
        feet = [(0.0, max(0.0, -math.sin(ph)) * 3.0), (0.0, max(0.0, math.sin(ph)) * 3.0)]
        if name == "run":
            wing_angle = -40.0 + 20.0 * math.sin(ph * 2)
    elif name == "sit":
        b = _breath(f)
        cy, show_feet = 72.0, False
        sx, sy = 1.08, 0.94 + b * 0.012
    elif name == "sleep":
        b = _breath(f)
        cy, show_feet = 72.5, False
        sx, sy = 1.1, 0.92 + b * 0.02
        eyes = "closed"
        whole = {"angle": 5.0}
    elif name == "air":
        wing_angle = (-70.0, -25.0)[f % 2]
        eyes = "wide"
        mouth_open = True
        feet = [(-1.0, -2.0), (1.0, -2.0)]
        shadow_k = 0.0
    elif name == "drag":
        sw = (-1.0, 0.0, 1.0, 0.0)[f % 4]
        wing_angle = -60.0 + 30.0 * (f % 2)
        eyes = "wide"
        mouth_open = True
        feet = [(sw, -3.0), (sw, -3.0)]
        whole = {"angle": sw * 6.0, "pivot": (50.0, 45.0)}
        shadow_k = 0.0
    elif name == "happy":
        up = math.sin(f / 4 * math.pi) * 7.0
        whole = {"dy": -up}
        wing_angle = (-55.0, -20.0)[f % 2]
        eyes = "happy"
        mouth_open = True
        shadow_k = 1.0 - up / 14.0
    elif name == "eat":
        peck = f % 2 == 1
        whole = {"angle": 24.0 if peck else 4.0, "pivot": (50.0, GROUND)}
        eyes = "closed" if peck else "happy"
    elif name == "land":
        sx, sy = 1.12, 0.84
        eyes = "closed"
        feet = [(0.0, 0.0), (0.0, 0.0)]

    if pose.blink and eyes == "open":
        eyes = "blink"

    if shadow and shadow_k > 0:
        draw_shadow(p, 50.0, shadow_k, 22.0)
    p.save()
    apply_whole(p, **whole)

    if show_feet:
        for (dx, lift), x, far in zip(feet, (44.0, 56.0), (True, False)):
            leg_color = beak.darker(115) if far else beak
            top = (x + dx, cy + r * sy - 4)
            foot = (x + dx, GROUND - 1.2 - lift)
            p.setPen(round_pen(outline, 3.6 + OUTLINE_W))
            p.drawLine(QPointF(*top), QPointF(*foot))
            for tdx in (-3.2, 0.0, 3.2):
                p.drawLine(QPointF(*foot), QPointF(foot[0] + tdx + 1.2, foot[1] + 0.2))
            p.setPen(round_pen(leg_color, 3.0))
            p.drawLine(QPointF(*top), QPointF(*foot))
            for tdx in (-3.2, 0.0, 3.2):
                p.drawLine(QPointF(*foot), QPointF(foot[0] + tdx + 1.2, foot[1] + 0.2))

    p.save()
    p.translate(cx, GROUND)
    p.scale(sx, sy)
    p.translate(-cx, -GROUND)
    # tuft
    p.setPen(round_pen(outline, 2.0 + OUTLINE_W))
    tuft = QPainterPath(QPointF(cx - 1, cy - r + 1))
    tuft.quadTo(QPointF(cx - 4, cy - r - 7), QPointF(cx + 1, cy - r - 8))
    tuft2 = QPainterPath(QPointF(cx + 1, cy - r + 1))
    tuft2.quadTo(QPointF(cx + 3, cy - r - 5), QPointF(cx + 7, cy - r - 5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(tuft)
    p.drawPath(tuft2)
    p.setPen(round_pen(body, 2.0))
    p.drawPath(tuft)
    p.drawPath(tuft2)
    # body
    grad = QRadialGradient(QPointF(cx - 8, cy - 10), r * 1.6)
    grad.setColorAt(0.0, body.lighter(112))
    grad.setColorAt(1.0, body)
    p.setPen(round_pen(outline, OUTLINE_W))
    p.setBrush(QBrush(grad))
    p.drawEllipse(QPointF(cx, cy), r, r)
    # face
    ex = cx + 9.0
    draw_eye(p, ex - 6.0, cy - 7.0, 1.0, eyes, colors)
    draw_eye(p, ex + 6.0, cy - 7.5, 1.0, eyes, colors)
    draw_cheeks(p, (ex - 10.0, ex + 10.0), cy + 0.5, 1.0, 95)
    bx, by = ex + 1.0, cy - 0.5
    upper = QPainterPath(QPointF(bx - 4.5, by - 1.2))
    upper.lineTo(QPointF(bx + 5.5, by + 0.2))
    upper.lineTo(QPointF(bx - 3.0, by + 2.4))
    upper.closeSubpath()
    lower = QPainterPath(QPointF(bx - 3.5, by + 2.0))
    lower.lineTo(QPointF(bx + 3.5, by + (5.5 if mouth_open else 2.6)))
    lower.lineTo(QPointF(bx - 2.5, by + (4.5 if mouth_open else 3.4)))
    lower.closeSubpath()
    shape(p, lower, beak.darker(110), outline, 1.6)
    shape(p, upper, beak, outline, 1.6)
    # wing
    wx, wy = cx - 9.0, cy + 4.0
    p.save()
    p.translate(wx + 6, wy - 3)
    p.rotate(wing_angle)
    p.translate(-(wx + 6), -(wy - 3))
    shape(p, ellipse_path(wx, wy + wing_lift, 19.0, 12.5, -8.0), wing, outline, 2.2)
    p.restore()
    p.restore()
    p.restore()


# --------------------------------------------------------------------------
# slime
# --------------------------------------------------------------------------

def slime_path(cx: float, w: float, h: float, base: float = GROUND) -> QPainterPath:
    l, r = cx - w / 2, cx + w / 2
    path = QPainterPath(QPointF(l + 5, base))
    path.cubicTo(QPointF(l - 1.5, base), QPointF(l, base - h * 0.55), QPointF(cx - w * 0.3, base - h * 0.9))
    path.cubicTo(QPointF(cx - w * 0.13, base - h * 1.03), QPointF(cx + w * 0.13, base - h * 1.03),
                 QPointF(cx + w * 0.3, base - h * 0.9))
    path.cubicTo(QPointF(r, base - h * 0.55), QPointF(r + 1.5, base), QPointF(r - 5, base))
    path.quadTo(QPointF(cx, base + 1.8), QPointF(l + 5, base))
    path.closeSubpath()
    return path


def draw_slime(p: QPainter, colors: dict, pose: Pose, shadow: bool):
    name, f = pose.name, pose.frame
    body = col(colors["body"])
    light = col(colors["light"])
    outline = col(colors["outline"])
    w, h = 62.0, 44.0
    dy, sx, sy = 0.0, 1.0, 1.0
    eyes, mouth = "open", "smile"
    shadow_k = 1.0
    angle = 0.0
    pivot = (50.0, GROUND)

    if name in ("stand", "cling"):
        b = _breath(f)
        sy = 1.0 + 0.03 * b
        sx = 1.0 - 0.015 * b
    elif name in ("walk", "climb", "run"):
        frames = 6 if name == "run" else 8
        ph = (f % frames) / frames * TAU
        sy = 1.0 + 0.13 * math.sin(ph)
        sx = 1.0 / sy
        dy = -max(0.0, math.sin(ph)) * (8.0 if name == "run" else 5.0)
        shadow_k = 1.0 + dy / 20.0
    elif name == "sit":
        b = _breath(f)
        sy, sx = 0.92 + 0.02 * b, 1.06
    elif name == "sleep":
        b = _breath(f)
        sy, sx = 0.8 + 0.03 * b, 1.13
        eyes = "closed"
        mouth = "none"
    elif name == "air":
        sy, sx = 1.1, 0.92
        eyes, mouth = "wide", "o"
        shadow_k = 0.0
    elif name == "drag":
        sw = (-1.0, 0.0, 1.0, 0.0)[f % 4]
        sy, sx = 1.22, 0.84
        eyes, mouth = "wide", "o"
        angle = sw * 5.0
        pivot = (50.0, 45.0)
        shadow_k = 0.0
    elif name == "happy":
        up = math.sin(f / 4 * math.pi) * 7.0
        dy = -up
        sy = 1.0 + 0.06 * math.sin(f / 4 * math.pi)
        sx = 1.0 / sy
        eyes, mouth = "happy", "open"
        shadow_k = 1.0 - up / 14.0
    elif name == "eat":
        sy = (1.0, 0.92, 1.0, 0.92)[f % 4]
        sx = 1.0 / sy
        eyes = "happy" if f % 4 in (1, 2) else "closed"
        mouth = "munch" if f % 2 else "smile"
    elif name == "land":
        sy, sx = 0.72, 1.24
        eyes, mouth = "closed", "o"

    if pose.blink and eyes == "open":
        eyes = "blink"

    if shadow and shadow_k > 0:
        draw_shadow(p, 50.0, shadow_k, 30.0 * sx)
    p.save()
    apply_whole(p, dy=dy, angle=angle, pivot=pivot)
    p.translate(50.0, GROUND)
    p.scale(sx, sy)
    p.translate(-50.0, -GROUND)
    path = slime_path(50.0, w, h)
    grad = QRadialGradient(QPointF(40.0, GROUND - h * 0.75), w * 0.9)
    grad.setColorAt(0.0, light)
    grad.setColorAt(0.55, body)
    grad.setColorAt(1.0, body.darker(115))
    p.setPen(round_pen(outline, OUTLINE_W))
    p.setBrush(QBrush(grad))
    p.drawPath(path)
    # shine
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255, 190)))
    p.drawPath(ellipse_path(50.0 - w * 0.25, GROUND - h * 0.7, 9.0, 5.5, -32.0))
    p.drawEllipse(QPointF(50.0 - w * 0.36, GROUND - h * 0.5), 1.8, 1.8)
    # face (not squashed as much, so undo some of the scale)
    p.restore()
    p.save()
    apply_whole(p, dy=dy, angle=angle, pivot=pivot)
    face_y = GROUND - h * sy * 0.5
    fx = 56.0
    k = 1.05
    p.translate(fx, face_y)
    p.scale(math.sqrt(sx), math.sqrt(sy))
    p.translate(-fx, -face_y)
    draw_eye(p, fx - 7.0, face_y - 1.0, k, eyes, colors)
    draw_eye(p, fx + 7.0, face_y - 1.0, k, eyes, colors)
    draw_cheeks(p, (fx - 12.0, fx + 12.0), face_y + 4.5, 1.0, 100)
    draw_mouth(p, fx, face_y + 4.5, 1.0, mouth, colors)
    p.restore()


# --------------------------------------------------------------------------
# entry point used by the renderer
# --------------------------------------------------------------------------

def draw_pet(p: QPainter, species: Species, variant: Variant, pose: Pose, shadow: bool = True):
    colors = variant.colors
    if species.id in LOOKS:
        draw_quadruped(p, species.id, colors, pose, shadow)
    elif species.id == "chick":
        draw_chick(p, colors, pose, shadow)
    elif species.id == "slime":
        draw_slime(p, colors, pose, shadow)
    else:  # pragma: no cover - every registered species has art
        raise KeyError(species.id)


# --------------------------------------------------------------------------
# small icons used by speech bubbles and the tray
# --------------------------------------------------------------------------

def draw_icon(p: QPainter, kind: str, cx: float, cy: float, s: float):
    """Draw a symbol about ``s`` units tall centred on (cx, cy)."""
    outline = QColor("#4A2E2E")
    if kind == "heart":
        shape(p, heart_path(cx, cy + s * 0.05, s * 1.05), QColor("#FF5C7A"), outline, s * 0.09)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, 200)))
        p.drawEllipse(QPointF(cx - s * 0.2, cy - s * 0.12), s * 0.09, s * 0.07)
    elif kind == "food":
        # a little fish
        body = ellipse_path(cx - s * 0.08, cy, s * 0.78, s * 0.48)
        tail = QPainterPath(QPointF(cx + s * 0.22, cy))
        tail.lineTo(QPointF(cx + s * 0.52, cy - s * 0.26))
        tail.lineTo(QPointF(cx + s * 0.52, cy + s * 0.26))
        tail.closeSubpath()
        shape(p, tail, QColor("#6FB7E8"), outline, s * 0.08)
        shape(p, body, QColor("#8FCBF2"), outline, s * 0.08)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(outline))
        p.drawEllipse(QPointF(cx - s * 0.28, cy - s * 0.04), s * 0.055, s * 0.055)
    elif kind == "note":
        p.setPen(round_pen(outline, s * 0.1))
        p.setBrush(QBrush(outline))
        p.drawEllipse(QPointF(cx - s * 0.18, cy + s * 0.3), s * 0.17, s * 0.13)
        p.drawLine(QPointF(cx - s * 0.02, cy + s * 0.28), QPointF(cx - s * 0.02, cy - s * 0.4))
        p.drawLine(QPointF(cx - s * 0.02, cy - s * 0.4), QPointF(cx + s * 0.3, cy - s * 0.24))
    elif kind == "sparkle":
        path = QPainterPath(QPointF(cx, cy - s * 0.5))
        for i in range(1, 9):
            a = -math.pi / 2 + i * math.pi / 4
            rr = s * (0.5 if i % 2 == 0 else 0.16)
            path.lineTo(QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a)))
        path.closeSubpath()
        shape(p, path, QColor("#FFD84D"), QColor("#B8860B"), s * 0.06)
    else:
        font = QFont()
        font.setBold(True)
        font.setPixelSize(max(1, int(round(s))))
        p.setFont(font)
        p.setPen(QPen(outline))
        p.drawText(QRectF(cx - s, cy - s, s * 2, s * 2), Qt.AlignmentFlag.AlignCenter, kind)
