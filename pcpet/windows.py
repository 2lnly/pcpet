"""The on-screen windows: one per pet, plus a click-through effects layer."""

from __future__ import annotations

import time
from collections import deque

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

from . import platform_setup
from .art import draw_icon, heart_path, round_pen
from .effects import Effects
from .model import Pet
from .render import SpriteRenderer

OUTLINE = QColor("#4A2E2E")
DRAG_THRESHOLD = 6  # px of movement before a press becomes a drag


class EffectWindow(QWidget):
    """A transparent, click-through window that follows a pet around and
    shows its hearts, snores, speech bubbles and food bowl."""

    def __init__(self, pet: Pet):
        super().__init__(None, platform_setup.window_flags(click_through=True))
        platform_setup.setup_overlay_widget(self, click_through=True)
        self.setWindowTitle(f"{pet.name} effects")
        self.pet = pet
        self.effects = Effects()
        self.bounds = None  # screen area (l, t, r, b) the pet is on
        self._anchor = QPointF(0, 0)
        self._on_all_spaces = False
        self._resize_for(pet.size)

    def _resize_for(self, size: float):
        w = int(max(3 * size, 280))
        h = int(size * 1.5 + 120)
        self._margin = 8
        self.setFixedSize(w, h)
        self._anchor = QPointF(w / 2, h - self._margin)

    def add(self, event, show_bubbles: bool):
        pet = self.pet
        self.effects.add(event, pet.size, pet.facing, pet.visible_height(), show_bubbles)

    def sync(self, dt: float, hidden: bool = False):
        pet = self.pet
        self.effects.step(dt, bowl_allowed=pet.state == "eat")
        if not self.effects.active or hidden:
            if self.isVisible():
                self.hide()
            return
        if abs(self.width() - int(max(3 * pet.size, 280))) > 1:
            self._resize_for(pet.size)
        cx = pet.x + pet.size / 2
        bottom = pet.y + pet.size
        x = cx - self.width() / 2
        y = bottom + self._margin - self.height()
        if self.bounds is not None:
            # Keep the top-left corner on the pet's screen: effects past the
            # edge would be invisible anyway, and some systems (macOS) get
            # confused by windows that start outside every screen.
            l, t, r, _b = self.bounds
            if r - l >= self.width():
                x = min(max(x, l), r - self.width())
            y = max(y, t)
        x, y = round(x), round(y)
        self._anchor = QPointF(cx - x, bottom - y)
        if self.pos() != QPoint(x, y):
            self.move(x, y)
        if not self.isVisible():
            self.show()
            if not self._on_all_spaces:
                self._on_all_spaces = platform_setup.mac_join_all_spaces(self)
        self.update()

    # ------------------------------------------------------------------ painting
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        ax, ay = self._anchor.x(), self._anchor.y()
        pet = self.pet
        fx = self.effects
        if fx.bowl is not None:
            self._paint_bowl(p, ax + pet.facing * pet.size * 0.46, ay, pet.size, fx.bowl.remaining)
        for part in fx.particles:
            if part.age < 0:
                continue
            p.setOpacity(part.alpha)
            x, y = ax + part.x, ay + part.y
            if part.kind == "heart":
                p.setPen(round_pen(OUTLINE, max(1.0, part.size * 0.09)))
                p.setBrush(QBrush(QColor("#FF5C7A")))
                p.drawPath(heart_path(x, y, part.size))
            elif part.kind == "zzz":
                self._paint_z(p, x, y, part.size)
            elif part.kind == "dust":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(200, 200, 205, 170)))
                p.drawEllipse(QPointF(x, y), part.size, part.size * 0.8)
            elif part.kind == "sparkle":
                draw_icon(p, "sparkle", x, y, part.size)
        p.setOpacity(1.0)
        if fx.bubble is not None:
            self._paint_bubble(p, ax, ay - pet.visible_height() - 4)
        p.end()

    def _paint_z(self, p: QPainter, x: float, y: float, size: float):
        font = QFont()
        font.setBold(True)
        font.setPixelSize(max(8, int(size)))
        path = QPainterPath()
        path.addText(QPointF(x, y), font, "z")
        p.setPen(round_pen(QColor(255, 255, 255, 230), max(2.0, size * 0.22)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#5E6FB0")))
        p.drawPath(path)

    def _paint_bowl(self, p: QPainter, cx: float, ground: float, size: float, remaining: float):
        w, h = size * 0.34, size * 0.13
        top = ground - h
        # kibble first so the bowl rim overlaps it
        p.setPen(round_pen(OUTLINE, max(1.0, size * 0.012)))
        p.setBrush(QBrush(QColor("#B7773E")))
        count = int(remaining * 6 + 0.999)
        spots = [(-0.22, 0.0), (0.0, -0.35), (0.22, 0.0), (-0.11, -0.2), (0.11, -0.2), (0.0, 0.1)]
        for dx, dy in spots[:count]:
            p.drawEllipse(QPointF(cx + dx * w, top + dy * h), size * 0.032, size * 0.026)
        bowl = QPainterPath(QPointF(cx - w / 2, top))
        bowl.lineTo(QPointF(cx + w / 2, top))
        bowl.cubicTo(QPointF(cx + w * 0.46, ground), QPointF(cx + w * 0.3, ground), QPointF(cx, ground))
        bowl.cubicTo(QPointF(cx - w * 0.3, ground), QPointF(cx - w * 0.46, ground), QPointF(cx - w / 2, top))
        bowl.closeSubpath()
        p.setPen(round_pen(OUTLINE, max(1.2, size * 0.022)))
        p.setBrush(QBrush(QColor("#E8555F")))
        p.drawPath(bowl)
        p.setPen(round_pen(QColor(255, 255, 255, 150), max(1.0, size * 0.015)))
        p.drawLine(QPointF(cx - w * 0.3, top + h * 0.35), QPointF(cx - w * 0.12, top + h * 0.35))

    def _paint_bubble(self, p: QPainter, cx: float, bottom: float):
        bubble = self.effects.bubble
        size = self.pet.size
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(max(11, min(20, size * 0.15))))
        fm = QFontMetricsF(font)
        pad = font.pixelSize() * 0.6
        if bubble.is_icon:
            icon = font.pixelSize() * 1.35
            bw, bh = icon + pad * 2, icon + pad * 1.4
        else:
            bw = fm.horizontalAdvance(bubble.content) + pad * 2
            bh = fm.height() + pad * 1.1
        bw = max(bw, bh)
        tail = font.pixelSize() * 0.55
        # keep the bubble on screen
        left = cx - bw / 2
        top = bottom - tail - bh
        if self.bounds is not None:
            gx = self.x()
            gy = self.y()
            l, t, r, _b = self.bounds
            left = min(max(left, l - gx + 4), r - gx - 4 - bw)
            top = max(top, t - gy + 4)
        left = min(max(left, 2), self.width() - bw - 2)
        top = max(top, 2)
        tail_x = min(max(cx, left + bh * 0.5), left + bw - bh * 0.5)

        p.save()
        p.setOpacity(bubble.alpha)
        s = bubble.scale
        p.translate(tail_x, top + bh + tail)
        p.scale(s, s)
        p.translate(-tail_x, -(top + bh + tail))
        path = QPainterPath()
        radius = min(bh / 2, 12)
        path.addRoundedRect(QRectF(left, top, bw, bh), radius, radius)
        pointer = QPainterPath(QPointF(tail_x - tail * 0.7, top + bh - 1))
        pointer.lineTo(QPointF(tail_x, top + bh + tail))
        pointer.lineTo(QPointF(tail_x + tail * 0.7, top + bh - 1))
        pointer.closeSubpath()
        path = path.united(pointer)
        p.setPen(round_pen(OUTLINE, 2.0))
        p.setBrush(QBrush(QColor(255, 255, 255, 245)))
        p.drawPath(path)
        if bubble.is_icon:
            draw_icon(p, bubble.content, left + bw / 2, top + bh / 2, font.pixelSize() * 1.25)
        else:
            p.setFont(font)
            p.setPen(QPen(OUTLINE))
            p.drawText(QRectF(left, top, bw, bh), Qt.AlignmentFlag.AlignCenter, bubble.content)
        p.restore()


class PetWindow(QWidget):
    """A small transparent window showing one pet; handles petting and dragging."""

    def __init__(self, controller, pet: Pet, renderer: SpriteRenderer, use_mask: bool):
        super().__init__(None, platform_setup.window_flags())
        platform_setup.setup_overlay_widget(self)
        self.setWindowTitle(pet.name)
        self.ctrl = controller
        self.pet = pet
        self.renderer = renderer
        self.use_mask = use_mask
        self.effects = EffectWindow(pet)
        self._image = None
        self._key = None
        self._last_pos = None
        self._press = None  # (global pos, local pos)
        self._dragging = False
        self._samples: deque = deque(maxlen=12)
        self._on_all_spaces = False
        size = int(round(pet.size))
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(False)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._on_all_spaces:
            self._on_all_spaces = platform_setup.mac_join_all_spaces(self)

    # ------------------------------------------------------------------ frame update
    def sync(self, dt: float = 0.0, show_bubbles: bool = True, hidden: bool = False):
        pet = self.pet
        for event in pet.drain_events():
            self.effects.add(event, show_bubbles)
        size = int(round(pet.size))
        if self.width() != size or self.height() != size:
            self.setFixedSize(size, size)
            self._key = None
        pose = pet.pose()
        dpr = self.devicePixelRatioF()
        key = (pose, pet.facing, pet.rotation, pet.variant_id, size, dpr)
        if key != self._key:
            self._key = key
            image, mask = self.renderer.frame(pet.species, pet.variant_id, pose, size, dpr,
                                              pet.facing, pet.rotation, self.use_mask)
            self._image = image
            if self.use_mask and mask is not None and not mask.isEmpty():
                self.setMask(mask)
            self.update()
        pos = QPoint(round(pet.x), round(pet.y))
        if pos != self._last_pos:
            self._last_pos = pos
            self.move(pos)
        if pet.env is not None:
            env = pet.env
            self.effects.bounds = (env.left, env.top, env.right, env.bottom)
        self.effects.sync(dt, hidden)

    def paintEvent(self, event):
        if self._image is None:
            return
        p = QPainter(self)
        p.drawImage(QPoint(0, 0), self._image)
        p.end()

    def close_all(self):
        self.effects.hide()
        self.effects.close()
        self.effects.deleteLater()
        self.hide()
        self.close()
        self.deleteLater()

    # ------------------------------------------------------------------ mouse
    def cancel_drag(self):
        """Drop the pet if a drag ended without us seeing the mouse release."""
        if self._dragging:
            self.pet.release(0.0, 0.0)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.ctrl.on_drag_finished(self.pet)
        self._press = None
        self._dragging = False

    @property
    def dragging(self) -> bool:
        return self._dragging

    def mousePressEvent(self, event):
        if self.pet.state == "drag" and not self._dragging:
            self.pet.release(0.0, 0.0)  # left over from a lost mouse release
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = (event.globalPosition(), event.position())
            self._dragging = False
            self._samples.clear()
            self._samples.append((time.monotonic(), event.globalPosition()))
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self._press is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        g = event.globalPosition()
        if not self._dragging:
            delta = g - self._press[0]
            if abs(delta.x()) + abs(delta.y()) < DRAG_THRESHOLD:
                return
            self._dragging = True
            self.pet.start_drag()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.ctrl.on_drag_started(self.pet)
        local = self._press[1]
        self.pet.drag_to(g.x() - local.x(), g.y() - local.y())
        self._samples.append((time.monotonic(), g))
        self.sync(0.0, self.ctrl.show_bubbles)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        if self._dragging:
            vx, vy = self.release_velocity(time.monotonic())
            self.pet.release(vx, vy)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.ctrl.on_drag_finished(self.pet)
        else:
            self.ctrl.on_pet_clicked(self.pet)
        self._press = None
        self._dragging = False
        event.accept()

    def release_velocity(self, now: float):
        """Mouse speed over the last tenth of a second, used to throw the pet."""
        recent = [(t, pos) for t, pos in self._samples if now - t <= 0.1]
        if len(recent) < 2:
            return 0.0, 0.0
        (t0, p0), (t1, p1) = recent[0], recent[-1]
        span = t1 - t0
        if span < 0.01:
            return 0.0, 0.0
        return (p1.x() - p0.x()) / span, (p1.y() - p0.y()) / span

    def contextMenuEvent(self, event):
        if self._dragging:
            return
        self.ctrl.show_pet_menu(self.pet, event.globalPos())
        event.accept()
