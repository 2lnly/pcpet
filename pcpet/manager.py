"""Owns every pet: runs the animation clock, builds menus and saves state."""

from __future__ import annotations

import math
import random
import sys
import time

from PySide6.QtCore import QObject, QPoint, QTimer, Qt
from PySide6.QtGui import QActionGroup, QCursor, QFont, QGuiApplication
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox, QSystemTrayIcon

from . import autostart, platform_setup
from .icons import app_icon
from .model import Env, Pet, clamp
from .render import SpriteRenderer
from .species import PET_NAMES, SPECIES, SPECIES_ORDER
from .storage import MAX_PETS, SIZES, Store, clean_name
from .windows import PetWindow

FRAME_MS = 33  # ~30 frames per second
SAVE_EVERY_MS = 60_000
RAISE_EVERY_MS = 1_500
SIZE_LABELS = {"small": "Small", "medium": "Medium", "large": "Large", "huge": "Huge"}


class PetManager(QObject):
    def __init__(self, app, store: Store, *, use_tray: bool = True, time_scale: float = 1.0):
        super().__init__()
        self.app = app
        self.store = store
        data = store.load()
        self.settings = data["settings"]
        self._saved_pets = data["pets"]
        self.time_scale = time_scale
        self.renderer = SpriteRenderer()
        self.use_mask = platform_setup.needs_window_mask()
        self.pets: list[Pet] = []
        self.windows: dict[str, PetWindow] = {}
        self.hidden = False
        self.rng = random.Random()
        self._menu: QMenu | None = None
        self._screens: list[tuple] = []
        self._last = time.monotonic()
        self._quitting = False

        self._refresh_screens()
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(self._on_screens_changed)
        for screen in app.screens():
            self._watch_screen(screen)

        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)

        self.save_timer = QTimer(self)
        self.save_timer.setInterval(SAVE_EVERY_MS)
        self.save_timer.timeout.connect(self.save)

        self._save_soon = QTimer(self)
        self._save_soon.setSingleShot(True)
        self._save_soon.setInterval(1000)
        self._save_soon.timeout.connect(self.save)

        # Unmanaged X11 windows are not kept on top by the window manager.
        self.raise_timer = QTimer(self)
        self.raise_timer.setInterval(RAISE_EVERY_MS)
        self.raise_timer.timeout.connect(self._raise_all)

        self.tray: QSystemTrayIcon | None = None
        self.tray_menu: QMenu | None = None
        self._tray_rebuild = QTimer(self)
        self._tray_rebuild.setSingleShot(True)
        self._tray_rebuild.setInterval(0)
        self._tray_rebuild.timeout.connect(self._do_rebuild_tray_menu)
        if use_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self._make_tray()
        app.aboutToQuit.connect(self._on_about_to_quit)

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        for saved in self._saved_pets:
            self.add_pet(saved["species"], saved["variant"], saved["name"], at=(saved["x"], saved["y"]),
                         stats=saved, pet_id=saved["id"], save=False)
        self._saved_pets = []
        if not self.pets:
            pet = self.add_pet("cat", "orange", at=self._first_spawn_point(), save=False)
            if pet is not None and not self.settings.get("welcomed"):
                pet.say("Hi! Right-click me")
        self.settings["welcomed"] = True
        self._last = time.monotonic()
        self.timer.start()
        self.save_timer.start()
        if platform_setup.bypass_window_manager():
            self.raise_timer.start()
        self.save()

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        self.save()
        self.timer.stop()
        for w in self.windows.values():
            w.effects.hide()
            w.hide()
        if self.tray is not None:
            self.tray.hide()
        self.app.quit()

    def _on_about_to_quit(self):
        if not self._quitting:
            self._quitting = True
            self.save()

    # ------------------------------------------------------------------ screens
    def _watch_screen(self, screen):
        screen.availableGeometryChanged.connect(self._on_screens_changed)
        screen.geometryChanged.connect(self._on_screens_changed)

    def _on_screen_added(self, screen):
        self._watch_screen(screen)
        self._on_screens_changed()

    def _on_screens_changed(self, *_):
        self._refresh_screens()

    def _refresh_screens(self):
        rects = []
        for screen in QGuiApplication.screens():
            g = screen.availableGeometry()
            if g.width() > 0 and g.height() > 0:
                rects.append((float(g.x()), float(g.y()), float(g.x() + g.width()), float(g.y() + g.height())))
        self._screens = rects or [(0.0, 0.0, 1280.0, 800.0)]

    def screen_rect_at(self, x: float, y: float) -> tuple:
        best, best_d = self._screens[0], math.inf
        for rect in self._screens:
            l, t, r, b = rect
            if l <= x < r and t <= y < b:
                return rect
            dx = max(l - x, 0.0, x - r)
            dy = max(t - y, 0.0, y - b)
            d = dx * dx + dy * dy
            if d < best_d:
                best, best_d = rect, d
        return best

    def env_for(self, pet: Pet, cursor: tuple | None) -> Env:
        l, t, r, b = self.screen_rect_at(pet.x + pet.size / 2, pet.y + pet.size / 2)
        if cursor is not None and not (l <= cursor[0] < r and t <= cursor[1] < b):
            cursor = None
        return Env(l, t, r, b, cursor)

    def _first_spawn_point(self) -> tuple:
        primary = QGuiApplication.primaryScreen()
        size = self.pet_size
        if primary is not None:
            g = primary.availableGeometry()
            return (g.x() + g.width() * 0.5 - size / 2, g.y() + g.height() * 0.35)
        l, t, r, b = self._screens[0]
        return ((l + r) / 2 - size / 2, t + (b - t) * 0.35)

    def _cursor_spawn_point(self) -> tuple:
        c = QCursor.pos()
        l, t, r, b = self.screen_rect_at(c.x(), c.y())
        size = self.pet_size
        x = clamp(c.x() - size / 2, l, max(l, r - size))
        y = clamp(c.y() - size * 1.2, t, max(t, b - size))
        return x, y

    def _random_spawn_point(self) -> tuple:
        """Somewhere near the top of the screen the mouse is on, so the pet drops in."""
        c = QCursor.pos()
        l, t, r, b = self.screen_rect_at(c.x(), c.y())
        size = self.pet_size
        x = self.rng.uniform(l, max(l, r - size))
        y = t + (b - t) * self.rng.uniform(0.05, 0.3)
        return x, y

    # ------------------------------------------------------------------ pets
    @property
    def pet_size(self) -> int:
        return SIZES.get(self.settings.get("size"), SIZES["medium"])

    @property
    def show_bubbles(self) -> bool:
        return bool(self.settings.get("bubbles", True))

    def _fresh_name(self) -> str:
        used = {p.name for p in self.pets}
        free = [n for n in PET_NAMES if n not in used]
        if free:
            return self.rng.choice(free)
        n = len(self.pets) + 1
        while f"Pet {n}" in used:
            n += 1
        return f"Pet {n}"

    def add_pet(self, species_id: str | None = None, variant_id: str | None = None, name: str | None = None, *,
                at: tuple | str | None = None, stats: dict | None = None, pet_id: str | None = None,
                save: bool = True) -> Pet | None:
        if len(self.pets) >= MAX_PETS:
            return None
        species = SPECIES.get(species_id) if species_id else None
        if species is None:
            species = SPECIES[self.rng.choice(SPECIES_ORDER)]
        if variant_id is None:
            variant_id = self.rng.choice(species.variants).id
        if at == "random":
            x, y = self._random_spawn_point()
        elif at is None:
            x, y = self._cursor_spawn_point()
        else:
            x, y = at
        if pet_id is not None and pet_id in self.windows:
            pet_id = None
        pet = Pet(species, variant_id, clean_name(name, "") or self._fresh_name(), self.pet_size, x, y,
                  stats=stats, rng=random.Random(), pet_id=pet_id)
        pet.facing = self.rng.choice((-1, 1))
        # Make sure it starts somewhere visible.
        l, t, r, b = self.screen_rect_at(pet.x + pet.size / 2, pet.y + pet.size / 2)
        pet.x = clamp(pet.x, l, max(l, r - pet.size))
        pet.y = clamp(pet.y, t, max(t, b - pet.size))
        window = PetWindow(self, pet, self.renderer, self.use_mask)
        self.pets.append(pet)
        self.windows[pet.id] = window
        pet.update(1e-6, self.env_for(pet, None))
        window.sync(0.0, self.show_bubbles, self.hidden)
        if not self.hidden:
            window.show()
        self._rebuild_tray_menu()
        if save:
            self.schedule_save()
        return pet

    def remove_pet(self, pet: Pet):
        if pet not in self.pets:
            return
        self.pets.remove(pet)
        window = self.windows.pop(pet.id, None)
        if window is not None:
            window.close_all()
        self._rebuild_tray_menu()
        self.schedule_save()

    def rename_pet(self, pet: Pet, name: str):
        pet.name = clean_name(name, pet.name)
        window = self.windows.get(pet.id)
        if window is not None:
            window.setWindowTitle(pet.name)
        self.schedule_save()

    def set_variant(self, pet: Pet, variant_id: str):
        pet.variant_id = pet.species.variant(variant_id).id
        pet.emit("sparkle")
        self.schedule_save()

    def set_size(self, size_name: str):
        if size_name not in SIZES:
            return
        self.settings["size"] = size_name
        for pet in self.pets:
            pet.set_size(SIZES[size_name])
        self.renderer.clear()
        self._rebuild_tray_menu()
        self.schedule_save()

    def set_bubbles(self, enabled: bool):
        self.settings["bubbles"] = bool(enabled)
        self._rebuild_tray_menu()
        self.schedule_save()

    def set_autostart(self, enabled: bool):
        try:
            autostart.set_enabled(enabled)
        except OSError as exc:
            QMessageBox.warning(None, "PC Pet", f"Could not change the start-at-login setting:\n{exc}")
        self._rebuild_tray_menu()

    def feed_all(self):
        for pet in self.pets:
            pet.feed()

    def set_hidden(self, hidden: bool):
        self.hidden = hidden
        for pet in self.pets:
            pet.held = False
            w = self.windows[pet.id]
            if hidden:
                w.effects.effects.clear()
                w.effects.hide()
                w.hide()
            else:
                w._last_pos = None
                w.sync(0.0, self.show_bubbles, False)
                w.show()
        self._last = time.monotonic()
        self._rebuild_tray_menu()

    def summon(self):
        """Another launch of the app asked us to show ourselves."""
        if self.hidden:
            self.set_hidden(False)
        if not self.pets:
            self.add_pet(at="random")
            return
        for pet in self.pets:
            pet.say("hi!")

    def handle_message(self, message: str):
        message = message.strip()
        if message == "summon":
            self.summon()
        elif message.startswith("add:"):
            species = message[4:]
            if self.hidden:
                self.set_hidden(False)
            self.add_pet(None if species == "random" else species, at="random")

    # ------------------------------------------------------------------ interaction callbacks
    def on_pet_clicked(self, pet: Pet):
        pet.pet()

    def on_drag_started(self, pet: Pet):
        window = self.windows.get(pet.id)
        if window is not None:
            window.raise_()

    def on_drag_finished(self, pet: Pet):
        self.schedule_save()

    # ------------------------------------------------------------------ main loop
    def tick(self):
        now = time.monotonic()
        dt = clamp(now - self._last, 0.0, 0.1) * self.time_scale
        self._last = now
        if self.hidden or not self.pets:
            return
        if not (QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            for window in self.windows.values():
                if window.dragging:
                    window.cancel_drag()
        c = QCursor.pos()
        cursor = (float(c.x()), float(c.y()))
        for pet in self.pets:
            pet.update(dt, self.env_for(pet, cursor))
        self._social()
        show_bubbles = self.show_bubbles
        for pet in self.pets:
            self.windows[pet.id].sync(dt, show_bubbles)

    def _social(self):
        ready = [p for p in self.pets if p.can_greet()]
        for i, a in enumerate(ready):
            for b in ready[i + 1:]:
                if not (a.can_greet() and b.can_greet()):
                    continue
                if abs((a.y + a.size) - (b.y + b.size)) > 4:
                    continue  # not on the same floor
                gap = abs((a.x + a.size / 2) - (b.x + b.size / 2))
                if gap < min(a.size, b.size) * 0.7:
                    a.greet(b.x)
                    b.greet(a.x)

    def _raise_all(self):
        if self.hidden:
            return
        for w in self.windows.values():
            if w.isVisible():
                w.raise_()
            if w.effects.isVisible():
                w.effects.raise_()

    # ------------------------------------------------------------------ saving
    def snapshot(self) -> dict:
        pets = []
        for pet in self.pets:
            entry = {
                "id": pet.id,
                "species": pet.species.id,
                "variant": pet.variant_id,
                "name": pet.name,
                "x": round(pet.x, 1),
                "y": round(pet.y, 1),
            }
            entry.update(pet.stats())
            pets.append(entry)
        return {"version": 1, "settings": dict(self.settings), "pets": pets}

    def save(self):
        try:
            self.store.save(self.snapshot())
        except OSError as exc:
            print(f"pcpet: could not save to {self.store.path}: {exc}", file=sys.stderr)

    def schedule_save(self):
        self._save_soon.start()

    # ------------------------------------------------------------------ menus
    @staticmethod
    def _action(menu: QMenu, text: str, slot, enabled: bool = True, checked: bool | None = None):
        act = menu.addAction(text)
        if checked is not None:
            act.setCheckable(True)
            act.setChecked(checked)
        act.setEnabled(enabled)
        act.triggered.connect(slot)
        return act

    def status_text(self, pet: Pet) -> str:
        return (f"Food {round(pet.hunger)}%  ·  Energy {round(pet.energy)}%  ·  "
                f"Happy {round(pet.happiness)}%")

    def _fill_global(self, menu: QMenu, include_visibility: bool):
        add = menu.addMenu("Add a pet")
        can_add = len(self.pets) < MAX_PETS
        add.setEnabled(can_add)
        for sid in SPECIES_ORDER:
            self._action(add, SPECIES[sid].name, lambda checked=False, s=sid: self.add_pet(s))
        add.addSeparator()
        self._action(add, "Surprise me!", lambda checked=False: self.add_pet())
        self._action(menu, "Feed everyone", lambda checked=False: self.feed_all(), enabled=bool(self.pets))
        if include_visibility:
            if self.hidden:
                self._action(menu, "Show pets", lambda checked=False: self.set_hidden(False))
            else:
                self._action(menu, "Hide pets", lambda checked=False: self.set_hidden(True),
                             enabled=bool(self.pets))
        settings = menu.addMenu("Settings")
        size_menu = settings.addMenu("Pet size")
        group = QActionGroup(size_menu)
        for key, label in SIZE_LABELS.items():
            act = self._action(size_menu, label, lambda checked=False, k=key: self.set_size(k),
                               checked=self.settings.get("size") == key)
            group.addAction(act)
        self._action(settings, "Speech bubbles", lambda checked=False: self.set_bubbles(checked),
                     checked=self.show_bubbles)
        if autostart.is_supported():
            self._action(settings, "Start at login", lambda checked=False: self.set_autostart(checked),
                         checked=autostart.is_enabled())
        menu.addSeparator()
        self._action(menu, "Quit PC Pet", lambda checked=False: self.quit())

    def build_pet_menu(self, pet: Pet) -> QMenu:
        menu = QMenu()
        title = menu.addAction(f"{pet.name} the {pet.species.name}")
        font = QFont(title.font())
        font.setBold(True)
        title.setFont(font)
        title.setEnabled(False)
        menu.addAction(self.status_text(pet)).setEnabled(False)
        menu.addSeparator()
        self._action(menu, "Pet", lambda checked=False: self.on_pet_clicked(pet))
        self._action(menu, "Feed", lambda checked=False: pet.feed())
        self._action(menu, "Play", lambda checked=False: pet.play(), enabled=pet.grounded)
        if pet.state == "sleep":
            self._action(menu, "Wake up", lambda checked=False: pet.wake_up())
        else:
            self._action(menu, "Nap time", lambda checked=False: pet.go_to_sleep(), enabled=pet.grounded)
        menu.addSeparator()
        self._action(menu, "Rename…", lambda checked=False: self.ask_rename(pet))
        colors = menu.addMenu("Color")
        group = QActionGroup(colors)
        for v in pet.species.variants:
            act = self._action(colors, v.name, lambda checked=False, vid=v.id: self.set_variant(pet, vid),
                               checked=v.id == pet.variant_id)
            group.addAction(act)
        can_remove = self.tray is not None or len(self.pets) > 1
        self._action(menu, f"Say goodbye to {pet.name}", lambda checked=False: self.remove_pet(pet),
                     enabled=can_remove)
        menu.addSeparator()
        self._fill_global(menu, include_visibility=self.tray is not None)
        return menu

    def show_pet_menu(self, pet: Pet, pos: QPoint):
        if self._menu is not None:
            try:
                self._menu.close()
            except RuntimeError:  # already deleted
                pass
            self._menu = None
        menu = self.build_pet_menu(pet)
        pet.held = True

        def release():
            pet.held = False

        menu.aboutToHide.connect(release)
        menu.aboutToHide.connect(menu.deleteLater)
        self._menu = menu
        menu.destroyed.connect(lambda *_: self._forget_menu(menu))
        menu.popup(pos)

    def _forget_menu(self, menu):
        if self._menu is menu:
            self._menu = None

    def ask_rename(self, pet: Pet):
        dlg = QInputDialog()
        dlg.setWindowTitle("Rename")
        dlg.setLabelText(f"New name for {pet.name}:")
        dlg.setTextValue(pet.name)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.setWindowIcon(app_icon())
        QTimer.singleShot(0, lambda: (dlg.raise_(), dlg.activateWindow()))
        if dlg.exec() and pet in self.pets:
            self.rename_pet(pet, dlg.textValue())

    # ------------------------------------------------------------------ tray icon
    def _make_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("PC Pet")
        self.tray_menu = QMenu()
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self._do_rebuild_tray_menu()
        self.tray.show()

    def _rebuild_tray_menu(self):
        # Deferred: this often runs from inside one of the menu's own actions,
        # and clearing the menu deletes those actions.
        if self.tray_menu is not None:
            self._tray_rebuild.start()

    def _do_rebuild_tray_menu(self):
        if self.tray_menu is None:
            return
        self.tray_menu.clear()
        self._fill_global(self.tray_menu, include_visibility=True)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != "darwin":
            self.tray_menu.popup(QCursor.pos())
