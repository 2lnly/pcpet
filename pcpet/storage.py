"""Saving and loading pets and settings as a small JSON file."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

from .species import SPECIES

SCHEMA_VERSION = 1
MAX_PETS = 20
MAX_NAME = 24

SIZES = {"small": 64, "medium": 96, "large": 128, "huge": 176}
DEFAULT_SETTINGS = {
    "size": "medium",
    "bubbles": True,
    "welcomed": False,
}


def clean_name(name, fallback: str = "Pet") -> str:
    text = " ".join(str(name).split())[:MAX_NAME] if name is not None else ""
    return text or fallback


def _finite(value, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _clean_settings(raw) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        if raw.get("size") in SIZES:
            settings["size"] = raw["size"]
        for key in ("bubbles", "welcomed"):
            if isinstance(raw.get(key), bool):
                settings[key] = raw[key]
    return settings


def _clean_pet(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    species = SPECIES.get(raw.get("species"))
    if species is None:
        return None
    pet = {
        "id": str(raw.get("id") or "")[:32] or None,
        "species": species.id,
        "variant": species.variant(raw.get("variant")).id,
        "name": clean_name(raw.get("name"), species.name),
        "x": _finite(raw.get("x"), 0.0),
        "y": _finite(raw.get("y"), 0.0),
    }
    for stat in ("hunger", "energy", "happiness"):
        pet[stat] = min(100.0, max(0.0, _finite(raw.get(stat), 75.0)))
    return pet


def clean_data(raw) -> dict:
    """Validate loaded data, dropping anything malformed instead of crashing."""
    data = {"version": SCHEMA_VERSION, "settings": dict(DEFAULT_SETTINGS), "pets": []}
    if not isinstance(raw, dict):
        return data
    data["settings"] = _clean_settings(raw.get("settings"))
    pets = raw.get("pets")
    if isinstance(pets, list):
        seen = set()
        for item in pets:
            pet = _clean_pet(item)
            if pet is None:
                continue
            if pet["id"] in seen:
                pet["id"] = None
            seen.add(pet["id"])
            data["pets"].append(pet)
            if len(data["pets"]) >= MAX_PETS:
                break
    return data


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            raw = None
        except (OSError, ValueError):
            # Keep a copy of the unreadable file for the curious, then start fresh.
            try:
                os.replace(self.path, self.path.with_suffix(".corrupt.json"))
            except OSError:
                pass
            raw = None
        return clean_data(raw)

    def save(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pcpet-", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def reset(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
