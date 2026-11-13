"""Command-line entry point and Qt application set-up."""

from __future__ import annotations

import argparse
import signal
import sys
import tempfile
from pathlib import Path

from . import __version__, platform_setup
from .species import SPECIES_ORDER


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="pcpet",
        description="Little pets that wander around your screen. Right-click a pet for options.",
    )
    ap.add_argument("--add", metavar="SPECIES", action="append", choices=list(SPECIES_ORDER) + ["random"],
                    help="add a pet (%(choices)s); can be repeated. Works while PC Pet is already running.")
    ap.add_argument("--reset", action="store_true", help="forget all saved pets and settings")
    ap.add_argument("--config-dir", metavar="DIR", help="where to keep saved pets (default: your user config folder)")
    ap.add_argument("--no-tray", action="store_true", help="don't show a system tray / menu bar icon")
    ap.add_argument("--selftest", metavar="SECONDS", type=float, help=argparse.SUPPRESS)
    ap.add_argument("--version", action="version", version=f"PC Pet {__version__}")
    return ap.parse_args(argv)


def default_config_dir() -> Path:
    from PySide6.QtCore import QStandardPaths

    loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(loc) if loc else Path.home() / ".pcpet"


def main(argv=None) -> int:
    args = parse_args(argv)
    for note in platform_setup.prepare_environment():
        print(f"pcpet: {note}", file=sys.stderr)

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .icons import app_icon
    from .manager import PetManager
    from .single_instance import SingleInstance
    from .storage import Store

    app = QApplication(sys.argv[:1])
    app.setApplicationName("pcpet")
    app.setApplicationDisplayName("PC Pet")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    selftest = args.selftest is not None
    if args.config_dir:
        config_dir = Path(args.config_dir).expanduser()
    elif selftest:
        config_dir = Path(tempfile.mkdtemp(prefix="pcpet-selftest-"))
    else:
        config_dir = default_config_dir()

    instance = None
    if not selftest:
        instance = SingleInstance(config_dir)
        if not instance.acquire():
            messages = [f"add:{s}" for s in (args.add or [])] or ["summon"]
            delivered = all(instance.send(msg) for msg in messages)
            print("pcpet: already running" + ("" if delivered else " (could not reach it)"), file=sys.stderr)
            return 0

    store = Store(config_dir / "pcpet.json")
    if args.reset:
        store.reset()
    manager = PetManager(app, store, use_tray=not args.no_tray, time_scale=3.0 if selftest else 1.0)
    if instance is not None:
        instance.message_received.connect(manager.handle_message)
    manager.start()
    for species in args.add or []:
        manager.add_pet(None if species == "random" else species, at="random")

    # Let Ctrl+C in a terminal quit cleanly (Qt's event loop would swallow it).
    def on_signal(*_):
        QTimer.singleShot(0, manager.quit)

    signal.signal(signal.SIGINT, on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_signal)

    tester = None
    if selftest:
        from .selftest import SelfTest

        tester = SelfTest(app, manager, args.selftest)
        tester.start()

    code = app.exec()
    if instance is not None:
        instance.release()
    if selftest and not args.config_dir:
        import shutil

        shutil.rmtree(config_dir, ignore_errors=True)
    del tester
    return code
