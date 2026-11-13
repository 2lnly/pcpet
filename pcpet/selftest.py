"""``pcpet --selftest SECONDS``: run the real app with scripted interactions.

Used by CI on Linux, macOS and Windows to make sure the app starts, draws,
reacts to the mouse, builds its menus, saves, and quits cleanly.
"""

from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from .species import SPECIES_ORDER
from .storage import SIZES


class SelfTest(QObject):
    def __init__(self, app, manager, seconds: float):
        super().__init__()
        self.app = app
        self.m = manager
        self.seconds = max(3.0, seconds)
        self.errors: list[str] = []
        self.done: list[str] = []
        self._old_hook = sys.excepthook
        sys.excepthook = self._hook

    def _hook(self, exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        self.errors.append(text)
        print(text, file=sys.stderr, flush=True)

    def _at(self, seconds: float, name: str, fn):
        def run():
            try:
                fn()
                self.done.append(name)
            except Exception:  # noqa: BLE001 - we report everything
                self._hook(*sys.exc_info())
        QTimer.singleShot(int(seconds * 1000), run)

    def check(self, condition: bool, message: str):
        if not condition:
            self.errors.append("check failed: " + message)
            print("check failed: " + message, file=sys.stderr, flush=True)

    # ------------------------------------------------------------------ helpers
    def _mouse(self, widget, kind, global_pos: QPointF, button, buttons):
        local = global_pos - QPointF(widget.pos())
        ev = QMouseEvent(kind, local, global_pos, button, buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, ev)

    def _grab_point(self, w) -> QPointF:
        return QPointF(w.pos()) + QPointF(w.width() / 2, w.height() * 0.7)

    def _click(self, pet):
        w = self.m.windows[pet.id]
        c = self._grab_point(w)
        L = Qt.MouseButton.LeftButton
        self._mouse(w, QEvent.Type.MouseButtonPress, c, L, L)
        self._mouse(w, QEvent.Type.MouseButtonRelease, c, L, Qt.MouseButton.NoButton)

    def _drag(self, pet, dx: float, dy: float):
        w = self.m.windows[pet.id]
        start = self._grab_point(w)
        L = Qt.MouseButton.LeftButton
        before = (float(w.x()), float(w.y()))
        self._mouse(w, QEvent.Type.MouseButtonPress, start, L, L)
        for i in range(1, 6):
            pos = start + QPointF(dx * i / 5, dy * i / 5)
            self._mouse(w, QEvent.Type.MouseMove, pos, Qt.MouseButton.NoButton, L)
        self.check(pet.state == "drag", f"{pet.name} should be dragged, is {pet.state}")
        moved = abs(pet.x - before[0] - dx) < 1.01 and abs(pet.y - before[1] - dy) < 1.01
        self.check(moved, f"{pet.name} should follow the mouse: {before} -> {(pet.x, pet.y)}")
        end = start + QPointF(dx, dy)
        self._mouse(w, QEvent.Type.MouseButtonRelease, end, L, Qt.MouseButton.NoButton)
        self.check(pet.state == "fall", f"{pet.name} should fall after release, is {pet.state}")

    # ------------------------------------------------------------------ script
    def start(self):
        m = self.m
        self.original_size = m.settings["size"]

        def spawn():
            for i, sid in enumerate(SPECIES_ORDER):
                l, t, r, b = m._screens[0]
                x = l + (r - l) * (i + 1) / (len(SPECIES_ORDER) + 2)
                m.add_pet(sid, at=(x, t + 10))
            self.check(len(m.pets) >= len(SPECIES_ORDER), "all species were added")
            if sys.platform == "darwin":
                from . import platform_setup

                for w in m.windows.values():
                    behavior = platform_setup.mac_collection_behavior(w)
                    self.check(behavior is not None and behavior & 1 == 1,
                               f"pet window is on all Spaces (collectionBehavior={behavior})")

        def interact():
            pets = m.pets
            pets[0].feed()
            self._click(pets[1])
            self.check(pets[1].state in ("happy", "fall", "land"), "clicking pets the pet")
            pets[2].go_to_sleep()
            pets[3].play()
            for p in pets:
                if p.species.can_climb:
                    p.start("climb")

        def drag():
            pet = m.pets[4]
            self._drag(pet, 60, -80)
            m.pets[5].release(900, -700)

        def menu_open():
            pet = m.pets[0]
            w = m.windows[pet.id]
            m.show_pet_menu(pet, w.mapToGlobal(w.rect().center()))
            self.check(m._menu is not None and pet.held, "menu opens and holds the pet")
            for p in m.pets:
                menu = m.build_pet_menu(p)
                self.check(len(menu.actions()) > 8, "pet menu has actions")
                menu.deleteLater()

        def menu_close():
            if m._menu is not None:
                m._menu.close()
            QTimer.singleShot(50, lambda: self.check(not m.pets[0].held, "closing the menu frees the pet"))

        def sizes():
            m.set_size("large")
            self.check(all(p.size == SIZES["large"] for p in m.pets), "resize to large")

        def sizes_back():
            m.set_size("small")
            m.set_size(self.original_size)

        def bubbles():
            m.set_bubbles(False)
            m.pets[0].say("quiet")
            QTimer.singleShot(200, lambda: m.set_bubbles(True))

        def rename():
            m.rename_pet(m.pets[1], "  Testy   McTest  ")
            self.check(m.pets[1].name == "Testy McTest", "rename cleans whitespace")
            pet = m.pets[2]
            m.set_variant(pet, pet.species.variants[-1].id)

        def hide():
            m.set_hidden(True)
            self.check(not any(w.isVisible() for w in m.windows.values()), "hide hides every pet")

        def show():
            m.set_hidden(False)
            self.check(all(w.isVisible() for w in m.windows.values()), "show shows every pet")

        def churn():
            m.remove_pet(m.pets[-1])
            m.add_pet("dog")
            m.handle_message("summon")
            m.handle_message("add:random")
            m.feed_all()
            if m.tray_menu is not None:
                m._do_rebuild_tray_menu()
                self.check(len(m.tray_menu.actions()) > 3, "tray menu built")

        def finish():
            expected = ["spawn", "interact", "drag", "menu_open", "menu_close", "sizes", "sizes_back",
                        "bubbles", "rename", "hide", "show", "churn"]
            self.check(self.done == expected, f"all steps ran in order: {self.done}")
            for pet in m.pets:
                l, t, r, b = m.screen_rect_at(pet.x + pet.size / 2, pet.y + pet.size / 2)
                inside = (l - 1 <= pet.x and pet.x + pet.size <= r + 1 and t - 1 <= pet.y
                          and pet.y + pet.size <= b + 1)
                self.check(inside, f"{pet.name} ({pet.species.id}, {pet.state}) stays on screen: "
                                   f"{pet.x:.0f},{pet.y:.0f} in {l:.0f},{t:.0f},{r:.0f},{b:.0f}")
                w = m.windows[pet.id]
                self.check(w._image is not None and not w._image.isNull(), f"{pet.name} was drawn")
            m.save()
            reloaded = m.store.load()
            self.check(len(reloaded["pets"]) == len(m.pets), "pets saved and reloaded")
            sys.excepthook = self._old_hook
            ok = not self.errors
            print(f"selftest {'OK' if ok else 'FAILED'}: platform={QApplication.platformName()} "
                  f"pets={len(m.pets)} steps={len(self.done)} errors={len(self.errors)}", flush=True)
            m._quitting = True
            self.app.exit(0 if ok else 1)

        self._at(0.2, "spawn", spawn)
        self._at(0.8, "interact", interact)
        self._at(1.3, "drag", drag)
        self._at(1.6, "menu_open", menu_open)
        self._at(2.0, "menu_close", menu_close)
        self._at(2.3, "sizes", sizes)
        self._at(2.6, "sizes_back", sizes_back)
        self._at(2.8, "bubbles", bubbles)
        self._at(3.1, "rename", rename)
        self._at(3.3, "hide", hide)
        self._at(3.6, "show", show)
        self._at(3.9, "churn", churn)
        self._at(self.seconds, "finish", finish)
