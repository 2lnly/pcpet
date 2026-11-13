"""Per-OS tweaks: environment set-up before Qt starts and window flags."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt

IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"


def is_wayland_session(environ=None) -> bool:
    env = os.environ if environ is None else environ
    return bool(env.get("WAYLAND_DISPLAY")) or env.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def prepare_environment(environ=None) -> list[str]:
    """Adjust environment variables before QApplication is created.

    Returns human-readable notes about anything that was changed.
    """
    env = os.environ if environ is None else environ
    notes = []
    if IS_LINUX or environ is not None:
        # Native Wayland does not let apps place their own windows, which a
        # desktop pet needs.  Run through XWayland instead when possible.
        requested = env.get("QT_QPA_PLATFORM", "")
        wants_wayland = requested.startswith("wayland") or (not requested and is_wayland_session(env))
        if wants_wayland:
            if env.get("DISPLAY"):
                env["QT_QPA_PLATFORM"] = "xcb"
                notes.append("Wayland session detected: using XWayland so pets can move freely.")
            else:
                notes.append("Wayland session without XWayland: pets may not be able to move around.")
    return notes


def using_x11() -> bool:
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.platformName() == "xcb"


def needs_window_mask() -> bool:
    """X11 has no per-pixel click-through, so pets get a shaped window instead.

    Windows and macOS already let clicks pass through fully transparent
    pixels of a translucent window.
    """
    return using_x11()


def bypass_window_manager() -> bool:
    """On X11, unmanaged windows avoid taskbar entries and follow you to every workspace."""
    return using_x11() and os.environ.get("PCPET_X11_MANAGED", "") in ("", "0")


def window_flags(click_through: bool = False) -> Qt.WindowType:
    flags = (
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.NoDropShadowWindowHint
        | Qt.WindowType.WindowDoesNotAcceptFocus
    )
    if bypass_window_manager():
        flags |= Qt.WindowType.X11BypassWindowManagerHint
    if click_through:
        flags |= Qt.WindowType.WindowTransparentForInput
    return flags


def setup_overlay_widget(widget, click_through: bool = False):
    """Common attributes for transparent, always-on-top pet windows."""
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
    # Without this, macOS hides tool windows whenever the app is not active.
    widget.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
    if click_through:
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)


# --------------------------------------------------------------------------
# macOS: show pets on every Space (virtual desktop), including full-screen ones.
# Qt has no API for this, so call the Objective-C runtime directly.
# --------------------------------------------------------------------------

_NS_CAN_JOIN_ALL_SPACES = 1 << 0
_NS_FULL_SCREEN_AUXILIARY = 1 << 8
# Flags AppKit refuses to combine with the two above (it would throw).
_NS_CONFLICTING = (1 << 1) | (1 << 7) | (1 << 9)  # MoveToActiveSpace, FullScreenPrimary, FullScreenNone
_objc_cache = None


def _objc():
    global _objc_cache
    if _objc_cache is None:
        import ctypes
        import ctypes.util

        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        addr = ctypes.cast(lib.objc_msgSend, ctypes.c_void_p).value
        # objc_msgSend must be called through a prototype that matches each
        # method exactly (this matters on Apple Silicon).
        get_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(addr)
        get_ulong = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(addr)
        set_ulong = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(addr)
        _objc_cache = (lib.sel_registerName, get_ptr, get_ulong, set_ulong)
    return _objc_cache


def _on_cocoa() -> bool:
    """True only with Qt's native macOS backend; winId() is an NSView* only there."""
    from PySide6.QtGui import QGuiApplication

    return IS_MAC and QGuiApplication.platformName() == "cocoa"


def _ns_window(widget):
    if not _on_cocoa():
        return None
    sel, get_ptr, _, _ = _objc()
    view = int(widget.winId())  # an NSView* with the cocoa backend
    if not view:
        return None
    return get_ptr(view, sel(b"window")) or None


def mac_collection_behavior(widget) -> int | None:
    if not _on_cocoa():
        return None
    try:
        window = _ns_window(widget)
        if window is None:
            return None
        sel, _, get_ulong, _ = _objc()
        return int(get_ulong(window, sel(b"collectionBehavior")))
    except Exception:  # noqa: BLE001 - purely cosmetic, never fatal
        return None


def mac_join_all_spaces(widget) -> bool:
    """Make a window visible on every Space. Returns True on success."""
    if not _on_cocoa():
        return False
    try:
        window = _ns_window(widget)
        if window is None:
            return False
        sel, _, get_ulong, set_ulong = _objc()
        behavior = int(get_ulong(window, sel(b"collectionBehavior")))
        wanted = (behavior & ~_NS_CONFLICTING) | _NS_CAN_JOIN_ALL_SPACES | _NS_FULL_SCREEN_AUXILIARY
        if wanted != behavior:
            set_ulong(window, sel(b"setCollectionBehavior:"), wanted)
        return True
    except Exception:  # noqa: BLE001 - purely cosmetic, never fatal
        return False
