import pytest

from pcpet.species import ANIMS, SPECIES, SPECIES_ORDER, Pose

POSES = list(ANIMS)


def alpha_bbox(img):
    """Bounding box (x0, y0, x1, y1) of visible pixels."""
    w, h = img.width(), img.height()
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() > 8:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("species_id", SPECIES_ORDER)
def test_every_pose_and_frame_draws_inside_its_box(qapp, species_id):
    from pcpet.render import render_image

    sp = SPECIES[species_id]
    size = 48  # small keeps the pixel scan quick
    for pose_name in POSES:
        rotation = -90 if pose_name in ("climb", "cling") else 0
        for frame in range(ANIMS[pose_name][0]):
            for facing in (1, -1):
                img = render_image(sp, sp.variants[0].id, Pose(pose_name, frame), size, 1.0, facing, rotation)
                box = alpha_bbox(img)
                assert box is not None, (pose_name, frame)
                x0, y0, x1, y1 = box
                # Nothing touches the edges (so nothing got cut off), except the
                # side the feet stand on: the bottom, or the wall when climbing.
                right_limit = size - 1 if rotation == -90 else size - 2
                bottom_limit = size - 2 if rotation == -90 else size - 1
                ok = x0 >= 1 and y0 >= 1 and x1 <= right_limit and y1 <= bottom_limit
                assert ok, (pose_name, frame, facing, box)
                # and the pet is a reasonable size
                assert (x1 - x0) > size * 0.3 and (y1 - y0) > size * 0.2, (pose_name, frame, box)


@pytest.mark.parametrize("species_id", SPECIES_ORDER)
def test_every_color_variant_draws(qapp, species_id):
    from pcpet.render import render_image

    sp = SPECIES[species_id]
    images = [render_image(sp, v.id, Pose("stand"), 40) for v in sp.variants]
    for img in images:
        assert alpha_bbox(img) is not None
    # colors differ between variants
    assert len({img.pixelColor(20, 30).rgba() for img in images}) == len(images) or len(images) == 1


def test_blink_changes_the_picture(qapp):
    from pcpet.render import render_image

    sp = SPECIES["cat"]
    a = render_image(sp, "orange", Pose("stand", 0, False), 64)
    b = render_image(sp, "orange", Pose("stand", 0, True), 64)
    assert a != b


def test_mask_covers_the_pet_but_not_the_corners(qapp):
    from PySide6.QtCore import QPoint

    from pcpet.render import SpriteRenderer

    r = SpriteRenderer()
    sp = SPECIES["dog"]
    img, mask = r.frame(sp, "golden", Pose("stand"), 96, 2.0, 1, 0, want_mask=True)
    assert img.width() == 192 and img.devicePixelRatio() == 2.0
    assert mask.contains(QPoint(48, 70))  # the body
    assert not mask.contains(QPoint(1, 1))
    assert not mask.contains(QPoint(94, 2))


def test_renderer_cache_respects_its_budget(qapp):
    from pcpet.render import SpriteRenderer

    r = SpriteRenderer(budget_bytes=64 * 64 * 4 * 3)
    sp = SPECIES["slime"]
    first, _ = r.frame(sp, "green", Pose("walk", 0), 64, 1.0, 1, 0)
    again, _ = r.frame(sp, "green", Pose("walk", 0), 64, 1.0, 1, 0)
    assert first is again
    for f in range(8):
        r.frame(sp, "green", Pose("walk", f), 64, 1.0, 1, 0)
    assert len(r) == 3 and r.cached_bytes <= r.budget


def test_icons(qapp):
    from pcpet.art import draw_icon
    from pcpet.icons import app_icon, icon_image
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt

    assert alpha_bbox(icon_image(32)) is not None
    assert not app_icon().isNull()
    for kind in ("heart", "food", "note", "sparkle", "!"):
        img = QImage(40, 40, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        draw_icon(p, kind, 20, 20, 24)
        p.end()
        assert alpha_bbox(img) is not None, kind
