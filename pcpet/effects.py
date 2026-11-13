"""Particles and speech bubbles that float around a pet (no Qt here).

Coordinates are relative to the pet's *anchor*: the bottom centre of its
sprite box, with y pointing down (so things above the pet are negative).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

ICON_BUBBLES = frozenset({"heart", "food", "note", "sparkle"})


@dataclass
class Particle:
    kind: str  # heart | zzz | dust | sparkle
    x: float
    y: float
    vx: float
    vy: float
    life: float
    size: float
    age: float = 0.0

    @property
    def alpha(self) -> float:
        """0..1 opacity: quick fade in, slow fade out."""
        t = self.age / self.life
        if t <= 0:
            return 0.0
        if t < 0.12:
            return t / 0.12
        return max(0.0, 1.0 - (t - 0.12) / 0.88) ** 0.8


@dataclass
class Bubble:
    content: str
    duration: float
    age: float = 0.0

    @property
    def is_icon(self) -> bool:
        return self.content in ICON_BUBBLES

    @property
    def scale(self) -> float:
        t = min(1.0, self.age / 0.14)
        # ease-out-back for a little "pop"
        c = 1.7
        return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

    @property
    def alpha(self) -> float:
        remaining = self.duration - self.age
        return max(0.0, min(1.0, remaining / 0.3))


@dataclass
class Bowl:
    duration: float
    age: float = 0.0

    @property
    def remaining(self) -> float:
        return max(0.0, 1.0 - self.age / self.duration)


class Effects:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.particles: list[Particle] = []
        self.bubble: Bubble | None = None
        self.bowl: Bowl | None = None

    @property
    def active(self) -> bool:
        return bool(self.particles) or self.bubble is not None or self.bowl is not None

    def clear(self):
        self.particles.clear()
        self.bubble = None
        self.bowl = None

    def add(self, event: tuple, size: float, facing: int, height: float, show_bubbles: bool = True):
        """React to an event emitted by the pet model."""
        kind = event[0]
        r = self.rng
        if kind == "hearts":
            count = event[1] if len(event) > 1 else 3
            for i in range(count):
                self.particles.append(Particle(
                    "heart",
                    x=facing * size * 0.12 + r.uniform(-0.18, 0.18) * size,
                    y=-height * 0.85 + r.uniform(-0.05, 0.08) * size,
                    vx=r.uniform(-18.0, 18.0),
                    vy=-r.uniform(38.0, 62.0),
                    life=r.uniform(1.1, 1.6) + i * 0.08,
                    size=size * r.uniform(0.14, 0.2),
                    age=-i * 0.12,  # stagger
                ))
        elif kind == "zzz":
            self.particles.append(Particle(
                "zzz",
                x=facing * size * 0.28,
                y=-height * 0.95,
                vx=facing * r.uniform(10.0, 18.0),
                vy=-r.uniform(18.0, 26.0),
                life=2.4,
                size=size * 0.17,
            ))
        elif kind == "dust":
            for side in (-1, 1):
                for _ in range(2):
                    self.particles.append(Particle(
                        "dust",
                        x=side * size * r.uniform(0.12, 0.3),
                        y=-2.0,
                        vx=side * r.uniform(25.0, 60.0),
                        vy=-r.uniform(8.0, 22.0),
                        life=r.uniform(0.35, 0.55),
                        size=size * r.uniform(0.05, 0.08),
                    ))
        elif kind == "bubble":
            if not show_bubbles and event[1] not in ("!",):
                return
            content = str(event[1])
            duration = 2.6 if len(content) < 12 else 4.0
            self.bubble = Bubble(content, duration)
        elif kind == "bowl":
            self.bowl = Bowl(float(event[1]) if len(event) > 1 else 4.0)
        elif kind == "sparkle":
            for _ in range(5):
                self.particles.append(Particle(
                    "sparkle",
                    x=r.uniform(-0.4, 0.4) * size,
                    y=-r.uniform(0.2, 0.9) * height,
                    vx=0.0,
                    vy=-r.uniform(5.0, 15.0),
                    life=r.uniform(0.6, 1.0),
                    size=size * r.uniform(0.08, 0.13),
                ))

    def step(self, dt: float, bowl_allowed: bool = True):
        alive = []
        for p in self.particles:
            p.age += dt
            if p.age < 0:
                alive.append(p)
                continue
            if p.age >= p.life:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.kind == "dust":
                p.vx *= max(0.0, 1.0 - 4.0 * dt)
                p.vy *= max(0.0, 1.0 - 3.0 * dt)
                p.size *= 1.0 + 0.8 * dt
            elif p.kind == "zzz":
                p.size *= 1.0 + 0.25 * dt
            alive.append(p)
        self.particles = alive
        if self.bubble is not None:
            self.bubble.age += dt
            if self.bubble.age >= self.bubble.duration:
                self.bubble = None
        if self.bowl is not None:
            self.bowl.age += dt
            if self.bowl.age >= self.bowl.duration or not bowl_allowed:
                self.bowl = None
