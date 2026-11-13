import plistlib
import sys
from pathlib import Path

import pytest

from pcpet import autostart


def test_desktop_exec_quoting():
    assert autostart.desktop_exec(["/usr/bin/python3", "-m", "pcpet"]) == "/usr/bin/python3 -m pcpet"
    assert autostart.desktop_exec(["/opt/My Apps/pcpet"]) == '"/opt/My Apps/pcpet"'
    assert autostart.desktop_exec(["50%"]) == "50%%"
    assert autostart.desktop_exec(['a"b']) == '"a\\\\"b"'
    # a literal backslash becomes four backslashes inside quotes
    assert autostart.desktop_exec(["a\\b"]) == '"a\\\\\\\\b"'
    assert autostart.desktop_exec(["$HOME"]) == '"\\\\$HOME"'


def test_desktop_entry_has_exec_line():
    text = autostart.desktop_entry(["/x/pcpet"])
    assert "[Desktop Entry]" in text and "\nExec=/x/pcpet\n" in text and "Type=Application" in text


def test_mac_plist():
    data = plistlib.loads(autostart.mac_plist(["/usr/bin/open", "-a", "/Applications/PC Pet.app"]))
    assert data["ProgramArguments"] == ["/usr/bin/open", "-a", "/Applications/PC Pet.app"]
    assert data["RunAtLoad"] is True and data["Label"] == autostart.MAC_LABEL


def test_launch_command_from_source_points_at_main():
    cmd = autostart.launch_command()
    assert Path(cmd[-1]).name == "__main__.py" and Path(cmd[-1]).exists()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="XDG autostart is Linux only")
def test_linux_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not autostart.is_enabled()
    autostart.set_enabled(True, ["/opt/pc pet/pcpet"])
    path = tmp_path / "autostart" / "pcpet.desktop"
    assert path.exists() and autostart.is_enabled()
    assert 'Exec="/opt/pc pet/pcpet"' in path.read_text()
    autostart.set_enabled(False)
    assert not path.exists() and not autostart.is_enabled()
    autostart.set_enabled(False)  # turning off twice is fine


@pytest.mark.skipif(sys.platform != "darwin", reason="launchd is macOS only")
def test_mac_toggle(tmp_path, monkeypatch):
    target = tmp_path / "LaunchAgents" / "io.github.pcpet.plist"
    monkeypatch.setattr(autostart, "_mac_plist_path", lambda: target)
    autostart.set_enabled(True, ["/usr/bin/true"])
    assert autostart.is_enabled() and plistlib.loads(target.read_bytes())["ProgramArguments"] == ["/usr/bin/true"]
    autostart.set_enabled(False)
    assert not autostart.is_enabled()


@pytest.mark.skipif(sys.platform != "win32", reason="registry is Windows only")
def test_windows_toggle(monkeypatch):
    import winreg

    monkeypatch.setattr(autostart, "WINDOWS_VALUE", "PC Pet (test)")
    try:
        autostart.set_enabled(True, ["C:\\Program Files\\PC Pet\\pcpet.exe", "--x"])
        assert autostart.is_enabled()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.WINDOWS_RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "PC Pet (test)")
        assert value == '"C:\\Program Files\\PC Pet\\pcpet.exe" --x'
    finally:
        autostart.set_enabled(False)
    assert not autostart.is_enabled()
