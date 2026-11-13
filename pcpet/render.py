"""Turns (species, variant, pose) into cached images and window masks."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBitmap, QImage, QPainter, QRegion

from .art import Pose, draw_pet
from .species import Species

# Poses drawn on the ground get a soft shadow under the feet.
SHADOW_POSES = frozenset({"stand", "walk", "run", "sit", "sleep", "happy", "eat", "land"})
# Climbing reuses the walking/standing art, rotated onto the wall.
ART_POSE = {"climb": "walk", "cling": "stand"}


def paint_sprite(p: QPainter, species: Species, variant_id: str, pose: Pose, size: float,
                 facing: int = 1, rotation: int = 0):
    """Paint one sprite into a ``size`` x ``size`` square at the painter origin."""
    variant = species.variant(variant_id)
    art_pose = Pose(ART_POSE.get(pose.name, pose.name), pose.frame, pose.blink)
    shadow = rotation == 0 and pose.name in SHADOW_POSES
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    half = size / 2.0
    p.translate(half, half)
    if rotation:
        p.rotate(rotation)
    if facing < 0:
        p.scale(-1.0, 1.0)
    p.translate(-half, -half)
    p.scale(size / 100.0, size / 100.0)
    draw_pet(p, species, variant, art_pose, shadow)
    p.restore()


def render_image(species: Species, variant_id: str, pose: Pose, size: int, dpr: float = 1.0,
                 facing: int = 1, rotation: int = 0) -> QImage:
    px = max(1, int(round(size * dpr)))
    img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    img.setDevicePixelRatio(dpr)
    p = QPainter(img)
    paint_sprite(p, species, variant_id, pose, float(size), facing, rotation)
    p.end()
    return img


def mask_from_image(img: QImage) -> QRegion:
    """A window mask (in logical pixels) covering every visible pixel, grown by 1px.

    Growing the shape keeps soft anti-aliased edges inside the mask, so the
    sprite never looks clipped on X11 where the mask also defines the
    clickable area.
    """
    dpr = img.devicePixelRatio()
    w = max(1, int(round(img.width() / dpr)))
    h = max(1, int(round(img.height() / dpr)))
    small = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    small.fill(Qt.GlobalColor.transparent)
    p = QPainter(small)
    src = QImage(img)
    src.setDevicePixelRatio(1.0)
    scaled = src.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        p.drawImage(QPoint(dx, dy), scaled)
    p.end()
    bitmap = QBitmap.fromImage(small.createAlphaMask())
    return QRegion(bitmap)


class SpriteRenderer:
    """Renders sprites on demand and keeps recently used frames in an LRU cache."""

    def __init__(self, budget_bytes: int = 48 * 1024 * 1024):
        self.budget = budget_bytes
        self._cache: OrderedDict = OrderedDict()
        self._bytes = 0

    def clear(self):
        self._cache.clear()
        self._bytes = 0

    def frame(self, species: Species, variant_id: str, pose: Pose, size: int, dpr: float,
              facing: int, rotation: int, want_mask: bool = False):
        key = (species.id, variant_id, pose, size, round(dpr, 3), facing, rotation)
        entry = self._cache.get(key)
        if entry is None:
            img = render_image(species, variant_id, pose, size, dpr, facing, rotation)
            entry = [img, None]
            self._cache[key] = entry
            self._bytes += img.sizeInBytes()
            while self._bytes > self.budget and len(self._cache) > 1:
                _, old = self._cache.popitem(last=False)
                self._bytes -= old[0].sizeInBytes()
        else:
            self._cache.move_to_end(key)
        if want_mask and entry[1] is None:
            entry[1] = mask_from_image(entry[0])
        return entry[0], entry[1]

    @property
    def cached_bytes(self) -> int:
        return self._bytes

    def __len__(self) -> int:
        return len(self._cache)
