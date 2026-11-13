# PyInstaller recipe for PC Pet. Builds for the OS it runs on:
#
#   pip install pyinstaller pillow
#   pyinstaller --noconfirm packaging/pcpet.spec
#
# Output: dist/pcpet (Linux), dist/pcpet.exe (Windows), dist/PC Pet.app (macOS).
# Pillow lets PyInstaller turn assets/icon.png into .ico / .icns.
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "assets" / "icon.png")
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "pcpet" / "__init__.py").read_text()).group(1)

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="pcpet", console=False, icon=ICON)
    coll = COLLECT(exe, a.binaries, a.datas, name="pcpet")
    app = BUNDLE(
        coll,
        name="PC Pet.app",
        icon=ICON,
        bundle_identifier="io.github.pcpet",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "PC Pet",
            "CFBundleShortVersionString": VERSION,
            "LSUIElement": True,  # no Dock icon: the pets and the menu bar icon are the UI
            "NSHighResolutionCapable": True,
        },
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="pcpet", console=False, icon=ICON, upx=False)
