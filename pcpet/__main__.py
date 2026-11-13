"""Entry point: ``python -m pcpet`` (or run this file directly)."""

import os
import sys

if __package__ in (None, ""):
    # Started as a plain script (e.g. by the start-at-login entry).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcpet.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
