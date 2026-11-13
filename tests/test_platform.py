from pcpet import platform_setup


def test_wayland_uses_xwayland_when_available():
    env = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
    notes = platform_setup.prepare_environment(env)
    assert env["QT_QPA_PLATFORM"] == "xcb" and notes


def test_explicit_wayland_platform_is_redirected_too():
    env = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":1", "QT_QPA_PLATFORM": "wayland;xcb"}
    platform_setup.prepare_environment(env)
    assert env["QT_QPA_PLATFORM"] == "xcb"


def test_wayland_without_xwayland_is_left_alone_with_a_note():
    env = {"WAYLAND_DISPLAY": "wayland-0"}
    notes = platform_setup.prepare_environment(env)
    assert "QT_QPA_PLATFORM" not in env and notes


def test_other_choices_are_respected():
    for value in ("offscreen", "xcb"):
        env = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0", "QT_QPA_PLATFORM": value}
        assert platform_setup.prepare_environment(env) == []
        assert env["QT_QPA_PLATFORM"] == value
    env = {"DISPLAY": ":0"}  # plain X11
    assert platform_setup.prepare_environment(env) == [] and "QT_QPA_PLATFORM" not in env


def test_mac_helpers_do_nothing_without_the_native_mac_backend(qapp):
    # The tests run on Qt's "offscreen" backend, where window ids are not
    # Cocoa views; touching them through the Objective-C runtime would crash.
    from PySide6.QtWidgets import QWidget

    w = QWidget()
    w.show()
    assert platform_setup.mac_join_all_spaces(w) is False
    assert platform_setup.mac_collection_behavior(w) is None
    w.close()
