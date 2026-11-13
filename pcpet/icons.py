"""The app / tray icon, drawn in code."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap

from .art import draw_quadruped
from .species import SPECIES, Pose


def paint_icon(p: QPainter, size: float):
    """A happy cat's head filling a ``size`` square."""
    colors = SPECIES["cat"].variant("orange").colors
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # In the art box the head (with ears) spans about x 46..95, y 20..69.
    scale = size / 52.0
    p.translate(QPointF(size / 2, size / 2))
    p.scale(scale, scale)
    p.translate(QPointF(-70.5, -45.5))
    draw_quadruped(p, "cat", colors, Pose("happy", 0), shadow=False, head_only=True)
    p.restore()


def icon_image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    paint_icon(p, float(size))
    p.end()
    return img


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 22, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(icon_image(s)))
    return icon
