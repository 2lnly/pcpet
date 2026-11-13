"""Species, color variants and animation tables.

This module is pure Python (no Qt) so that the behaviour model and the
save-file code can use it without a GUI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Animation table shared by every species: pose -> (frame count, frames/sec).
ANIMS: dict[str, tuple[int, float]] = {
    "stand": (4, 3.0),
    "walk": (8, 10.0),
    "run": (6, 14.0),
    "sit": (4, 3.0),
    "sleep": (4, 1.5),
    "air": (2, 8.0),
    "drag": (4, 7.0),
    "happy": (4, 8.0),
    "eat": (4, 6.0),
    "land": (1, 1.0),
    "climb": (8, 10.0),
    "cling": (4, 3.0),
}

# Poses in which the eyes are open and a blink may be shown.
BLINKABLE = frozenset({"stand", "walk", "sit", "cling", "climb"})


@dataclass(frozen=True)
class Pose:
    """What to draw: a pose name, an animation frame and whether the eyes blink."""

    name: str
    frame: int = 0
    blink: bool = False


@dataclass(frozen=True)
class Variant:
    id: str
    name: str
    colors: dict = field(hash=False, compare=False)


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    variants: tuple
    sounds: tuple
    can_climb: bool = False
    speed: float = 1.0  # multiplier on walking/running speed
    height: float = 0.75  # visible height when standing, as a fraction of the sprite box
    sleep_height: float = 0.4  # visible height when lying down

    def variant(self, variant_id: str | None) -> Variant:
        for v in self.variants:
            if v.id == variant_id:
                return v
        return self.variants[0]


def _v(vid: str, name: str, **colors) -> Variant:
    return Variant(vid, name, colors)


_CAT = Species(
    "cat",
    "Cat",
    (
        _v("orange", "Orange tabby", body="#F6A55B", belly="#FFE6C7", outline="#5B3A29",
           accent="#DE8240", inner_ear="#F7B2AE", eye="#2B1D1A", nose="#EE8A8A", stripes=True),
        _v("gray", "Gray tabby", body="#AEB4C2", belly="#EEF0F5", outline="#3E4352",
           accent="#878EA0", inner_ear="#F2B8C0", eye="#2A2D36", nose="#E59AA6", stripes=True),
        _v("black", "Black", body="#45424F", belly="#45424F", outline="#19181E",
           accent="#33313B", inner_ear="#A8818E", eye="#F2D25C", pupil="#19181E", nose="#C77D8E"),
        _v("tuxedo", "Tuxedo", body="#3F3D49", belly="#F6F3EE", outline="#19181E",
           accent="#302E38", inner_ear="#A8818E", eye="#9BD36A", pupil="#19181E", nose="#E59AA6",
           socks="#F6F3EE"),
        _v("snow", "Snow white", body="#FCF9F4", belly="#FFFFFF", outline="#6B6170",
           accent="#E9E1DA", inner_ear="#F7B7C5", eye="#5AA9E6", pupil="#22303A", nose="#F29BB0"),
    ),
    ("meow!", "mrrp?", "purr~", "mew", "nya~"),
    can_climb=True,
    height=0.76,
)

_DOG = Species(
    "dog",
    "Dog",
    (
        _v("golden", "Golden", body="#EBB866", belly="#FFF1D6", outline="#5E3C1E",
           accent="#C98B3A", eye="#2B1D1A", nose="#2B1D1A"),
        _v("chocolate", "Chocolate", body="#8F5E40", belly="#DDB993", outline="#3A2416",
           accent="#6B4029", eye="#1E130D", nose="#1E130D"),
        _v("husky", "Husky", body="#8E99A8", belly="#F5F7FA", outline="#333A45",
           accent="#66717F", eye="#6EC1F0", pupil="#1D2530", nose="#1D2530", socks="#F5F7FA"),
        _v("cream", "Cream", body="#F3E3C7", belly="#FFFFFF", outline="#6A5440",
           accent="#D9BC8E", eye="#2B1D1A", nose="#2B1D1A"),
        _v("black", "Black", body="#4A4245", belly="#6A5F62", outline="#171314",
           accent="#332C2E", eye="#120E0F", nose="#0E0B0C"),
    ),
    ("woof!", "arf!", "bork", "awoo~", "ruff"),
    speed=1.1,
    height=0.7,
)

_FOX = Species(
    "fox",
    "Fox",
    (
        _v("red", "Red", body="#F07F3A", belly="#FFF6EC", outline="#5A2A12",
           accent="#4A2C22", inner_ear="#4A2C22", eye="#2B1712", nose="#2B1712",
           socks="#4A2C22", tail_tip="#FFF6EC"),
        _v("arctic", "Arctic", body="#F2F4F8", belly="#FFFFFF", outline="#5D6878",
           accent="#C9D0DB", inner_ear="#C9D0DB", eye="#2C3440", nose="#2C3440",
           tail_tip="#FFFFFF"),
        _v("silver", "Silver", body="#7D8796", belly="#E8EBF0", outline="#2E3440",
           accent="#3B4250", inner_ear="#3B4250", eye="#1E232B", nose="#1E232B",
           socks="#3B4250", tail_tip="#F4F6F8"),
    ),
    ("yip!", "ack!", "hehe", "yap?"),
    speed=1.15,
    height=0.8,
)

_BUNNY = Species(
    "bunny",
    "Bunny",
    (
        _v("white", "White", body="#FCFAF8", belly="#FFFFFF", outline="#6E6168",
           accent="#ECE4E6", inner_ear="#F6B5C8", eye="#3B2B33", nose="#F29BB0"),
        _v("brown", "Brown", body="#B98C66", belly="#F1E2D0", outline="#4E3524",
           accent="#9C7350", inner_ear="#F0B9AE", eye="#2B1D1A", nose="#E59AA6"),
        _v("gray", "Gray", body="#A9A4A8", belly="#EFECEE", outline="#45404A",
           accent="#8C878C", inner_ear="#F2B8C0", eye="#2A2630", nose="#E59AA6"),
        _v("black", "Black", body="#4D474B", belly="#6D6569", outline="#1E1A1D",
           accent="#3A3538", inner_ear="#C99AA8", eye="#16131A", nose="#C77D8E"),
    ),
    ("*thump*", "nom?", "squeak", "!"),
    speed=0.95,
    height=0.88,
)

_CHICK = Species(
    "chick",
    "Chick",
    (
        _v("yellow", "Yellow", body="#FFD84D", wing="#F5C42C", outline="#8A5A12",
           beak="#F59A23", eye="#2B1D1A"),
        _v("peach", "Peach", body="#FFC7A8", wing="#F7A985", outline="#8A4A2E",
           beak="#F2884B", eye="#2B1D1A"),
        _v("sky", "Sky", body="#BFE3FF", wing="#97CDF5", outline="#2F5B80",
           beak="#F5A623", eye="#1D2A36"),
    ),
    ("peep!", "cheep!", "pip", "peep peep"),
    speed=0.8,
    height=0.6,
    sleep_height=0.48,
)

_SLIME = Species(
    "slime",
    "Slime",
    (
        _v("green", "Green", body="#7ED957", light="#C9F6AC", outline="#2F6B2A", eye="#173516"),
        _v("blue", "Blue", body="#5FB4F5", light="#C6E7FF", outline="#1F4E79", eye="#10263B"),
        _v("pink", "Pink", body="#F58FC0", light="#FFD3E9", outline="#8A2F5C", eye="#3D1027"),
        _v("purple", "Purple", body="#A98BF0", light="#DED2FF", outline="#4B3591", eye="#1F1440"),
        _v("honey", "Honey", body="#F7C04A", light="#FFE8AC", outline="#8A5A12", eye="#3A2606"),
    ),
    ("blub", "bloop!", "squish", "~"),
    can_climb=True,
    speed=0.85,
    height=0.47,
    sleep_height=0.37,
)

SPECIES: dict[str, Species] = {s.id: s for s in (_CAT, _DOG, _FOX, _BUNNY, _CHICK, _SLIME)}
SPECIES_ORDER: tuple[str, ...] = tuple(SPECIES)

PET_NAMES = (
    "Mochi", "Biscuit", "Pudding", "Noodle", "Pickle", "Bean", "Tofu", "Waffles",
    "Pepper", "Maple", "Cocoa", "Sprout", "Dumpling", "Nugget", "Pebble", "Clover",
    "Muffin", "Sesame", "Toast", "Ziggy", "Boba", "Kiwi", "Olive", "Peanut",
)


def get_species(species_id: str) -> Species | None:
    return SPECIES.get(species_id)
