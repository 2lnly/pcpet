"""App-level tests on Qt's offscreen platform: windows, mouse, menus, saving."""

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from pcpet.species import SPECIES_ORDER
from pcpet.storage import SIZES, Store


@pytest.fixture
def manager(qapp, tmp_path):
    from pcpet.manager import PetManager

    m = PetManager(qapp, Store(tmp_path / "pcpet.json"), use_tray=False)
    m.start()
    yield m
    m.timer.stop()
    m.save_timer.stop()
    m.raise_timer.stop()
    for pet in list(m.pets):
        m.remove_pet(pet)
    qapp.processEvents()


def tick(m, seconds=1.0, dt=1 / 30):
    for _ in range(int(seconds / dt)):
        m._last -= dt
        m.tick()


def calm(m, pet, limit=10.0):
    """Tick until the pet stands on the floor, then keep it idle (pets act randomly)."""
    for _ in range(int(limit * 30)):
        if pet.grounded and pet.state != "land":
            pet._enter("idle", 1000.0)
            pet.intent = None
            return
        tick(m, 1 / 30)
    raise AssertionError(f"pet never settled (state {pet.state})")


def send(widget, kind, global_pos, button, buttons):
    local = global_pos - QPointF(widget.pos())
    ev = QMouseEvent(kind, local, global_pos, button, buttons, Qt.KeyboardModifier.NoModifier)
    from PySide6.QtWidgets import QApplication

    QApplication.sendEvent(widget, ev)


def test_first_run_has_a_welcoming_cat(manager):
    assert len(manager.pets) == 1
    pet = manager.pets[0]
    assert pet.species.id == "cat"
    tick(manager, 0.1)
    window = manager.windows[pet.id]
    assert window.effects.effects.bubble is not None
    assert "Right-click" in window.effects.effects.bubble.content
    assert manager.settings["welcomed"] is True


def test_windows_follow_their_pets(manager):
    for sid in SPECIES_ORDER:
        manager.add_pet(sid, at="random")
    tick(manager, 3)
    for pet in manager.pets:
        w = manager.windows[pet.id]
        assert (w.x(), w.y()) == (round(pet.x), round(pet.y))
        assert w.width() == w.height() == SIZES["medium"]
        assert w._image is not None


def test_click_pets_and_drag_moves(manager):
    pet = manager.pets[0]
    calm(manager, pet)
    tick(manager, 0.1)
    w = manager.windows[pet.id]
    L, NO = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    grab = QPointF(w.pos()) + QPointF(w.width() / 2, w.height() * 0.7)
    send(w, QEvent.Type.MouseButtonPress, grab, L, L)
    send(w, QEvent.Type.MouseButtonRelease, grab, L, NO)
    assert pet.state == "happy"

    start = (pet.x, pet.y)
    send(w, QEvent.Type.MouseButtonPress, grab, L, L)
    send(w, QEvent.Type.MouseMove, grab + QPointF(3, 0), NO, L)
    assert pet.state != "drag"  # tiny wiggles are still a click
    send(w, QEvent.Type.MouseMove, grab + QPointF(-50, -120), NO, L)
    assert pet.state == "drag"
    assert (pet.x, pet.y) == pytest.approx((w.x(), w.y()), abs=1)
    assert pet.x == pytest.approx(start[0] - 50, abs=1) and pet.y == pytest.approx(start[1] - 120, abs=1)
    send(w, QEvent.Type.MouseButtonRelease, grab + QPointF(-50, -120), L, NO)
    assert pet.state == "fall"


def test_menus(manager, qapp):
    manager.add_pet("dog")
    pet = manager.pets[0]
    menu = manager.build_pet_menu(pet)
    texts = [a.text() for a in menu.actions()]
    assert texts[0] == f"{pet.name} the Cat"
    for wanted in ("Pet", "Feed", "Play", "Rename…", "Quit PC Pet"):
        assert wanted in texts
    goodbye = [a for a in menu.actions() if a.text().startswith("Say goodbye")][0]
    assert goodbye.isEnabled()  # two pets, so one can go
    menu.deleteLater()

    manager.show_pet_menu(pet, manager.windows[pet.id].pos())
    assert pet.held
    manager._menu.close()
    qapp.processEvents()
    assert not pet.held


def test_last_pet_cannot_be_removed_without_a_tray(manager):
    menu = manager.build_pet_menu(manager.pets[0])
    goodbye = [a for a in menu.actions() if a.text().startswith("Say goodbye")][0]
    assert not goodbye.isEnabled()
    menu.deleteLater()


def test_settings_and_persistence(manager, tmp_path):
    from pcpet.manager import PetManager

    dog = manager.add_pet("dog", "husky", "Rex", at=(100, 100))
    manager.rename_pet(dog, "  Sir  Rex ")
    manager.set_variant(dog, "black")
    manager.set_size("large")
    manager.set_bubbles(False)
    tick(manager, 0.5)
    assert all(p.size == SIZES["large"] for p in manager.pets)
    manager.save()

    again = PetManager(manager.app, Store(tmp_path / "pcpet.json"), use_tray=False)
    again.start()
    try:
        names = {p.name: p for p in again.pets}
        assert set(names) == {p.name for p in manager.pets}
        rex = names["Sir Rex"]
        assert rex.species.id == "dog" and rex.variant_id == "black" and rex.size == SIZES["large"]
        assert again.settings["size"] == "large" and again.settings["bubbles"] is False
    finally:
        again.timer.stop()
        for pet in list(again.pets):
            again.remove_pet(pet)


def test_bubbles_setting_hides_speech(manager):
    pet = manager.pets[0]
    tick(manager, 0.1)
    effects = manager.windows[pet.id].effects.effects
    assert effects.bubble is not None  # the welcome message
    manager.set_bubbles(False)
    assert effects.bubble is None  # switching off hides bubbles right away
    pet.say("hello")
    tick(manager, 0.1)
    assert effects.bubble is None
    manager.set_bubbles(True)
    pet.say("hello")
    tick(manager, 0.1)
    assert effects.bubble.content == "hello"


def test_hide_show_and_messages(manager):
    manager.set_hidden(True)
    assert not any(w.isVisible() for w in manager.windows.values())
    manager.handle_message("summon")
    assert not manager.hidden
    assert all(w.isVisible() for w in manager.windows.values())
    before = len(manager.pets)
    manager.handle_message("add:bunny")
    manager.handle_message("add:random")
    manager.handle_message("add:not-a-species")  # falls back to a random pet
    assert len(manager.pets) == before + 3
    assert manager.pets[before].species.id == "bunny"


def test_pet_limit(manager):
    from pcpet.storage import MAX_PETS

    while len(manager.pets) < MAX_PETS:
        assert manager.add_pet() is not None
    assert manager.add_pet() is None


def test_greeting_between_neighbours(manager):
    a = manager.pets[0]
    b = manager.add_pet("dog", at=(a.x + 20, a.y))
    tick(manager, 3)
    for p in (a, b):
        p._enter("idle", 10)
        p._greet_cooldown = 0
        p.intent = None
    b.x = a.x + 20
    b.y = a.y
    manager._social()
    assert a.state == b.state == "greet"


def test_screen_lookup(manager):
    l, t, r, b = manager._screens[0]
    assert manager.screen_rect_at((l + r) / 2, (t + b) / 2) == (l, t, r, b)
    assert manager.screen_rect_at(-10_000, -10_000) in manager._screens


def test_lost_mouse_release_does_not_leave_a_pet_floating(manager):
    pet = manager.pets[0]
    calm(manager, pet)
    tick(manager, 0.1)
    w = manager.windows[pet.id]
    L, NO = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    grab = QPointF(w.pos()) + QPointF(w.width() / 2, w.height() * 0.7)
    send(w, QEvent.Type.MouseButtonPress, grab, L, L)
    send(w, QEvent.Type.MouseMove, grab + QPointF(0, -100), NO, L)
    assert pet.state == "drag" and w.dragging
    # the release never arrives; the next frame notices no button is held
    tick(manager, 0.1)
    assert not w.dragging and pet.state in ("fall", "land")
    calm(manager, pet, limit=3.0)  # it lands instead of floating forever


def test_pets_live_on_the_screen_they_are_on(manager):
    # Two monitors side by side with different heights (taskbar on the second).
    left_screen, right_screen = (0.0, 0.0, 800.0, 600.0), (800.0, 100.0, 1440.0, 580.0)
    manager._screens = [left_screen, right_screen]
    a = manager.add_pet("cat", at=(100, 100))
    b = manager.add_pet("dog", at=(1000, 150))
    c = manager.add_pet("slime", at=(805, 40))  # in the gap above the right screen
    homes = ((a, left_screen), (b, right_screen), (c, right_screen))
    landed = set()
    for _ in range(60 * 30):
        tick(manager, 1 / 30)
        for pet, (l, t, r, bottom) in homes:
            assert l <= pet.x <= r - pet.size and t <= pet.y <= bottom - pet.size, pet.species.id
            if pet.y == bottom - pet.size:
                landed.add(pet.id)
    assert landed == {a.id, b.id, c.id}  # each one stood on its own screen's floor


def test_effects_layer_stays_on_screen_and_follows_the_pet(manager):
    pet = manager.pets[0]
    calm(manager, pet)
    l, t, r, b = manager._screens[0]
    effects = manager.windows[pet.id].effects
    for x, y in ((l, t), (r - pet.size, t), ((l + r) / 2, b - pet.size)):
        pet.x, pet.y = x, y
        pet.say("hi")
        tick(manager, 1 / 30)
        assert effects.isVisible()
        assert l <= effects.x() and t <= effects.y() and effects.x() + effects.width() <= r
        # the anchor is the pet's bottom centre, wherever the layer ended up
        assert effects.x() + effects._anchor.x() == pytest.approx(pet.x + pet.size / 2, abs=1)
        assert effects.y() + effects._anchor.y() == pytest.approx(pet.y + pet.size, abs=1)
        pet._enter("idle", 1000.0)
