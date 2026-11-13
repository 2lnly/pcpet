"""Start PC Pet when the user logs in (Linux, macOS and Windows)."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

APP_NAME = "PC Pet"
LINUX_FILE = "pcpet.desktop"
MAC_LABEL = "io.github.pcpet"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_VALUE = "PC Pet"


def launch_command() -> list[str]:
    """The command line that starts this copy of PC Pet."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if sys.platform == "darwin":
            for parent in exe.parents:
                if parent.suffix == ".app":
                    return ["/usr/bin/open", "-a", str(parent)]
        return [str(exe)]
    python = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = python.with_name("pythonw.exe")
        if pythonw.exists():
            python = pythonw  # no console window
    main_file = Path(__file__).resolve().parent / "__main__.py"
    return [str(python), str(main_file)]


# ---------------------------------------------------------------- Linux (XDG)

def _xdg_autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "autostart"


def desktop_exec(args: list[str]) -> str:
    """Quote a command line for the Exec= key of a .desktop file."""
    out = []
    for arg in args:
        needs_quotes = any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`') or arg == ""
        if needs_quotes:
            escaped = arg
            for ch in ("\\", '"', "`", "$"):
                escaped = escaped.replace(ch, "\\" + ch)
            arg = f'"{escaped}"'
        # The value is also a desktop-entry "string": backslashes are escaped
        # once more, and a literal percent sign is written as %%.
        arg = arg.replace("\\", "\\\\").replace("%", "%%")
        out.append(arg)
    return " ".join(out)


def desktop_entry(args: list[str]) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Little pets that wander around your screen\n"
        f"Exec={desktop_exec(args)}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


# ---------------------------------------------------------------- macOS (launchd)

def _mac_plist_path() -> Path:
    return Path(os.path.expanduser("~")) / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def mac_plist(args: list[str]) -> bytes:
    return plistlib.dumps({
        "Label": MAC_LABEL,
        "ProgramArguments": list(args),
        "RunAtLoad": True,
        "ProcessType": "Interactive",
    })


# ---------------------------------------------------------------- Windows (registry)

def _win_command(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


# ---------------------------------------------------------------- public API

def is_supported() -> bool:
    return sys.platform in ("win32", "darwin") or sys.platform.startswith("linux")


def is_enabled() -> bool:
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
                winreg.QueryValueEx(key, WINDOWS_VALUE)
            return True
        if sys.platform == "darwin":
            return _mac_plist_path().exists()
        return (_xdg_autostart_dir() / LINUX_FILE).exists()
    except OSError:
        return False


def set_enabled(enabled: bool, args: list[str] | None = None):
    """Turn start-at-login on or off. Raises OSError if that fails."""
    args = args or launch_command()
    if sys.platform == "win32":
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, WINDOWS_VALUE, 0, winreg.REG_SZ, _win_command(args))
            else:
                try:
                    winreg.DeleteValue(key, WINDOWS_VALUE)
                except FileNotFoundError:
                    pass
        return
    if sys.platform == "darwin":
        path = _mac_plist_path()
        content = mac_plist(args)
    else:
        path = _xdg_autostart_dir() / LINUX_FILE
        content = desktop_entry(args).encode("utf-8")
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
