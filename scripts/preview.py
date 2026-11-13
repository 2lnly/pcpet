"""Render a contact sheet of every species, pose and color.

    python scripts/preview.py out.png            # all poses, default colors
    python scripts/preview.py out.png --variants # every color, standing
    python scripts/preview.py out.png --frames walk   # every frame of one pose

Runs without a display (uses Qt's offscreen platform).
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter  # noqa: E402

from pcpet.art import Pose  # noqa: E402
from pcpet.render import paint_sprite  # noqa: E402
from pcpet.species import ANIMS, SPECIES, SPECIES_ORDER  # noqa: E402

POSES = ["stand", "walk", "run", "sit", "sleep", "air", "drag", "happy", "eat", "land", "climb", "cling"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=120)
    ap.add_argument("--variants", action="store_true")
    ap.add_argument("--frames", metavar="POSE")
    ap.add_argument("--background", default="#E9EEF3")
    args = ap.parse_args()
    app = QGuiApplication(sys.argv[:1])  # noqa: F841 - needed for fonts

    rows = []  # (label, [(species, variant, pose, facing, rotation)])
    if args.variants:
        for sid in SPECIES_ORDER:
            sp = SPECIES[sid]
            rows.append((sp.name, [(sp, v.id, Pose("stand"), 1, 0, v.name) for v in sp.variants]))
    elif args.frames:
        count = ANIMS[args.frames][0]
        for sid in SPECIES_ORDER:
            sp = SPECIES[sid]
            rows.append((sp.name, [(sp, sp.variants[0].id, Pose(args.frames, i), 1, 0, f"{args.frames} {i}")
                                   for i in range(count)]))
    else:
        for sid in SPECIES_ORDER:
            sp = SPECIES[sid]
            cells = []
            for name in POSES:
                rot = -90 if name in ("climb", "cling") else 0
                cells.append((sp, sp.variants[0].id, Pose(name, 1 if ANIMS[name][0] > 1 else 0), 1, rot, name))
            rows.append((sp.name, cells))

    s = args.size
    label_w = 90
    cols = max(len(c) for _, c in rows)
    img = QImage(label_w + cols * (s + 8) + 8, len(rows) * (s + 26) + 8, QImage.Format.Format_ARGB32)
    img.fill(QColor(args.background))
    p = QPainter(img)
    font = QFont()
    font.setPixelSize(12)
    p.setFont(font)
    for r, (label, cells) in enumerate(rows):
        y = 8 + r * (s + 26)
        p.setPen(QColor("#333"))
        p.drawText(QRectF(4, y, label_w - 8, s), Qt.AlignmentFlag.AlignVCenter, label)
        for c, (sp, vid, pose, facing, rot, caption) in enumerate(cells):
            x = label_w + c * (s + 8)
            p.setPen(QColor("#C9D2DC"))
            p.drawRect(x, y, s, s)
            p.save()
            p.translate(x, y)
            paint_sprite(p, sp, vid, pose, float(s), facing, rot)
            p.restore()
            p.setPen(QColor("#555"))
            p.drawText(QRectF(x, y + s + 2, s, 18), Qt.AlignmentFlag.AlignHCenter, caption)
    p.end()
    img.save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
