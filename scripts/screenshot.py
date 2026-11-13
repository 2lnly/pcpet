"""Render the README hero image (a fake desktop with pets) and the app icon.

    python scripts/screenshot.py docs/screenshot.png assets/icon.png
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from pcpet.icons import icon_image  # noqa: E402
from pcpet.model import Env, Pet  # noqa: E402
from pcpet.render import paint_sprite  # noqa: E402
from pcpet.species import ANIMS, SPECIES, Pose  # noqa: E402
from pcpet.windows import EffectWindow  # noqa: E402

W, H, BAR = 1200, 440, 44
FLOOR = H - BAR
S = 110


def place(species, variant, x, state, *, facing=1, y=None, rotation=0, wall=None, frame=1, events=()):
    pet = Pet(SPECIES[species], variant, species, S, x, FLOOR - S if y is None else y, rng=random.Random(3))
    pet._env = Env(0, 0, W, FLOOR)
    pet._enter(state)
    pet.facing = facing
    pet.rotation = rotation
    pet.wall = wall
    fx = EffectWindow(pet)
    fx.bounds = (0, 0, W, FLOOR)
    for ev in events:
        fx.add(ev, True)
    for p in fx.effects.particles:  # let particles drift a little
        p.age = max(p.age, 0.0) + 0.35
        p.y += p.vy * 0.35
    if fx.effects.bubble:
        fx.effects.bubble.age = 0.5
    return pet, fx, frame


def main() -> int:
    out, icon_out = sys.argv[1], sys.argv[2]
    app = QApplication(sys.argv[:1])  # noqa: F841
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0, QColor("#8EC5FC"))
    g.setColorAt(1, QColor("#E0C3FC"))
    p.fillRect(img.rect(), g)
    # a fake window
    p.setPen(QPen(QColor(0, 0, 0, 40), 1))
    p.setBrush(QColor(255, 255, 255, 215))
    p.drawRoundedRect(QRectF(300, 40, 520, 250), 12, 12)
    p.setBrush(QColor(240, 240, 245, 230))
    p.drawRoundedRect(QRectF(300, 40, 520, 34), 12, 12)
    p.fillRect(QRectF(300, 60, 520, 14), QColor(240, 240, 245, 230))
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        p.setBrush(QColor(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(320 + i * 20, 57), 6, 6)
    p.setBrush(QColor(0, 0, 0, 22))
    for i in range(6):
        p.drawRoundedRect(QRectF(330, 100 + i * 28, 300 + (i * 53) % 160, 12), 6, 6)
    # taskbar
    p.fillRect(QRectF(0, FLOOR, W, BAR), QColor(30, 34, 48, 235))
    for i in range(5):
        p.setBrush(QColor(255, 255, 255, 60 if i else 120))
        p.drawRoundedRect(QRectF(W / 2 - 110 + i * 46, FLOOR + 8, 30, 28), 7, 7)

    scene = [
        place("cat", "orange", 40, "walk", frame=2, events=[("bubble", "meow!")]),
        place("dog", "golden", 205, "eat", facing=1, frame=1, events=[("bowl", 4.0)]),
        place("bunny", "white", 430, "happy", facing=-1, frame=2, events=[("hearts", 3)]),
        place("chick", "yellow", 590, "sleep", facing=1, frame=1, events=[("zzz",), ("zzz",)]),
        place("fox", "red", 860, "drag", facing=-1, y=120, frame=1, events=[("bubble", "!")]),
        place("slime", "blue", W - S, "climb", y=150, rotation=-90, wall="right", frame=3,
              events=[("bubble", "note")]),
        place("cat", "tuxedo", 700, "sit", facing=1, frame=0),
    ]
    for pet, fx, frame in scene:
        name = pet.pose().name
        pose = Pose(name, frame % ANIMS[name][0], False)
        p.save()
        p.translate(pet.x, pet.y)
        paint_sprite(p, pet.species, pet.variant_id, pose, S, pet.facing, pet.rotation)
        p.restore()
        ax = pet.x + S / 2 - fx.width() / 2
        ay = pet.y + S - (fx.height() - 8)
        fx.move(int(round(ax)), int(round(ay)))
        fx.render(p, QPoint(int(round(ax)), int(round(ay))), renderFlags=QWidget.RenderFlag.DrawChildren)
    # mouse pointer holding the fox
    cx, cy = 860 + S / 2, 120 + S * 0.35
    arrow = QPainterPath(QPointF(cx, cy))
    for dx, dy in ((0, 22), (6, 16), (11, 26), (15, 24), (10, 15), (17, 15)):
        arrow.lineTo(QPointF(cx + dx, cy + dy))
    arrow.closeSubpath()
    p.setPen(QPen(QColor("white"), 1.6))
    p.setBrush(QColor("black"))
    p.drawPath(arrow)
    p.end()
    img.save(out)
    icon_image(512).save(icon_out)
    print(out, icon_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
