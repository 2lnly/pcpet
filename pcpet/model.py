"""Pet behaviour: a small state machine with simple physics.

No Qt in here, so the behaviour is easy to unit-test.  Positions are in
logical screen pixels; ``x``/``y`` is the top-left corner of the pet's
square sprite box and ``size`` is its edge length.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass

from .species import ANIMS, BLINKABLE, Pose, Species

GRAVITY = 2200.0  # px/s^2
TERMINAL_VY = 3200.0
MAX_THROW_SPEED = 2600.0
BOUNCE_MIN_VY = 650.0  # landing faster than this bounces
WALK_SPEED = 0.55  # body lengths per second
RUN_SPEED = 2.1
CLIMB_SPEED = 0.6

HUNGER_RATE = 0.04  # points per second: full -> hungry in roughly half an hour
SLEEP_RECOVERY = 1.0
HAPPY_DECAY = 0.015

AIR_STATES = frozenset({"fall", "drag"})
WALL_STATES = frozenset({"climb", "cling"})
GROUND_STATES = frozenset({
    "idle", "walk", "run", "sit", "sleep", "land", "happy", "eat", "chase", "greet", "talk", "beg",
})

POSE_OF = {
    "idle": "stand", "walk": "walk", "run": "run", "sit": "sit", "sleep": "sleep", "fall": "air",
    "land": "land", "drag": "drag", "happy": "happy", "eat": "eat", "climb": "climb", "cling": "cling",
    "greet": "stand", "talk": "stand", "beg": "stand", "chase": "walk",
}


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class Env:
    """The part of the world a pet can see this frame."""

    left: float
    top: float
    right: float
    bottom: float  # the floor
    cursor: tuple | None = None  # mouse position, only when it is on the pet's screen


class Pet:
    def __init__(self, species: Species, variant_id: str | None = None, name: str = "Pet",
                 size: float = 96, x: float = 0.0, y: float = 0.0, stats: dict | None = None,
                 rng: random.Random | None = None, pet_id: str | None = None):
        self.id = pet_id or uuid.uuid4().hex[:12]
        self.species = species
        self.variant_id = species.variant(variant_id).id
        self.name = name
        self.size = float(size)
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.rotation = 0
        self.wall: str | None = None
        self.rng = rng or random.Random()
        stats = stats or {}
        self.hunger = clamp(float(stats.get("hunger", 80.0)), 0.0, 100.0)  # 100 = full
        self.energy = clamp(float(stats.get("energy", 90.0)), 0.0, 100.0)
        self.happiness = clamp(float(stats.get("happiness", 70.0)), 0.0, 100.0)
        self.state = "idle"
        self.state_time = 0.0
        self.anim_time = 0.0
        self.duration = self.rng.uniform(0.5, 2.0)
        self.target_x = self.x
        self.target_y = self.y
        self.intent: str | None = None
        self.pending: str | None = None
        self.held = False  # frozen in place, e.g. while its menu is open
        self.events: list = []
        self._env: Env | None = None
        self._blink_timer = self.rng.uniform(1.5, 5.0)
        self._blinking = 0.0
        self._zzz_timer = 0.0
        self._greet_cooldown = self.rng.uniform(8.0, 25.0)
        self._chase_pose = "walk"
        self._caught = 0.0
        self._run_legs = 0

    # ------------------------------------------------------------------ helpers
    def _bounds(self, env: Env):
        lo = env.left
        hi = max(lo, env.right - self.size)
        return lo, hi

    def _ground_y(self, env: Env) -> float:
        return env.bottom - self.size

    def _enter(self, state: str, duration: float = 0.0):
        self.state = state
        self.state_time = 0.0
        self.anim_time = 0.0
        self.duration = duration
        if state not in WALL_STATES:
            self.rotation = 0
            self.wall = None

    def _keep_grounded(self, env: Env) -> bool:
        """Keep a pet standing on the floor; returns False if it started to fall."""
        lo, hi = self._bounds(env)
        self.x = clamp(self.x, lo, hi)
        gy = self._ground_y(env)
        if self.y < gy - 2.0:
            self._enter("fall")
            self.vx = 0.0
            self.vy = 0.0
            return False
        self.y = gy
        return True

    def _move_toward(self, tx: float, step: float) -> bool:
        dx = tx - self.x
        if abs(dx) <= step:
            self.x = tx
            return True
        self.facing = 1 if dx > 0 else -1
        self.x += self.facing * step
        return False

    @property
    def env(self) -> Env | None:
        """The surroundings seen on the most recent update."""
        return self._env

    @property
    def grounded(self) -> bool:
        return self.state in GROUND_STATES

    def emit(self, kind: str, *data):
        self.events.append((kind, *data))

    def drain_events(self) -> list:
        out, self.events = self.events, []
        return out

    # ------------------------------------------------------------------ main loop
    def update(self, dt: float, env: Env):
        if dt <= 0:
            return
        self._env = env
        self.anim_time += dt
        self.state_time += dt
        self._tick_stats(dt)
        self._tick_blink(dt)
        self._greet_cooldown = max(0.0, self._greet_cooldown - dt)
        if self.state == "drag" or self.held:
            return
        getattr(self, "_u_" + self.state)(dt, env)

    def _tick_stats(self, dt: float):
        self.hunger = clamp(self.hunger - HUNGER_RATE * dt, 0.0, 100.0)
        if self.state == "sleep":
            self.energy += SLEEP_RECOVERY * dt
        else:
            drain = 0.02
            if self.state in ("run", "chase"):
                drain += 0.12
            elif self.state in ("walk", "climb", "cling"):
                drain += 0.04
            self.energy -= drain * dt
        self.energy = clamp(self.energy, 0.0, 100.0)
        decay = HAPPY_DECAY + (0.03 if self.hunger < 20 else 0.0)
        self.happiness = clamp(self.happiness - decay * dt, 0.0, 100.0)

    def _tick_blink(self, dt: float):
        if self._blinking > 0:
            self._blinking -= dt
            return
        self._blink_timer -= dt
        if self._blink_timer <= 0:
            self._blinking = 0.13
            self._blink_timer = self.rng.uniform(2.0, 6.0)

    # ------------------------------------------------------------------ decisions
    def _choose_next(self):
        env = self._env
        r = self.rng
        weights = {
            "idle": 3.0,
            "walk": 4.0,
            "sit": 2.0,
            "run": 0.8 if self.energy > 40 else 0.1,
            "jump": 0.5 if self.energy > 30 else 0.0,
            "sleep": 0.15 + (2.5 if self.energy < 35 else 0.0) + (10.0 if self.energy < 15 else 0.0),
            "chase": 0.35 if env is not None and env.cursor is not None and self.energy > 25 else 0.0,
            "climb": 0.7 if self.species.can_climb and self.energy > 30 else 0.0,
            "talk": 0.7,
            "beg": 3.0 if self.hunger < 30 else 0.0,
        }
        total = sum(weights.values())
        pick = r.uniform(0.0, total)
        choice = "idle"
        for name, w in weights.items():
            if w <= 0:
                continue
            pick -= w
            if pick <= 0:
                choice = name
                break
        self.start(choice)

    def start(self, action: str):
        """Begin an autonomous action by name (also used by tests)."""
        r = self.rng
        env = self._env
        self.intent = None
        if action == "walk" and env is not None:
            lo, hi = self._bounds(env)
            span = hi - lo
            if span < self.size * 0.5:
                self._enter("idle", r.uniform(1.5, 4.0))
                return
            for _ in range(6):
                tx = r.uniform(lo, hi)
                if abs(tx - self.x) >= self.size * 0.5:
                    break
            self.target_x = tx
            self._enter("walk", 40.0)
        elif action == "run" and env is not None:
            self._run_legs = r.randint(1, 3)
            self._pick_run_target(env)
            self._enter("run", 30.0)
        elif action == "sit":
            self._enter("sit", r.uniform(3.0, 9.0))
        elif action == "sleep":
            self.go_to_sleep(r.uniform(15.0, 35.0))
        elif action == "jump":
            self._jump()
        elif action == "chase" and env is not None and env.cursor is not None:
            self._caught = 0.0
            self._enter("chase", r.uniform(6.0, 10.0))
        elif action == "climb" and env is not None and self.species.can_climb:
            lo, hi = self._bounds(env)
            self.intent = "climb"
            self.target_x = lo if (self.x - lo) <= (hi - self.x) else hi
            self._enter("walk", 60.0)
        elif action == "talk":
            sounds = self.species.sounds
            self.emit("bubble", "note" if r.random() < 0.2 else r.choice(sounds))
            self._enter("talk", 2.5)
        elif action == "beg":
            self.emit("bubble", "food")
            self._enter("beg", 3.0)
        else:
            self._enter("idle", r.uniform(1.5, 4.0))

    def _pick_run_target(self, env: Env):
        lo, hi = self._bounds(env)
        mid = (lo + hi) / 2
        if self.x < mid:
            self.target_x = self.rng.uniform(mid, hi)
        else:
            self.target_x = self.rng.uniform(lo, mid)

    def _jump(self):
        h = self.rng.uniform(0.5, 1.0) * self.size
        self._enter("fall")
        self.vy = -math.sqrt(2 * GRAVITY * h)
        self.vx = self.facing * self.rng.uniform(0.3, 1.2) * self.size

    # ------------------------------------------------------------------ state handlers
    def _u_idle(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        if self.state_time >= self.duration:
            self._choose_next()

    _u_sit = _u_idle
    _u_talk = _u_idle
    _u_greet = _u_idle
    _u_happy = _u_idle

    def _u_beg(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        if env.cursor is not None:
            self.facing = 1 if env.cursor[0] >= self.x + self.size / 2 else -1
        if self.state_time >= self.duration:
            self._choose_next()

    def _u_walk(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        running = self.state == "run"
        speed = (RUN_SPEED if running else WALK_SPEED) * self.size * self.species.speed
        lo, hi = self._bounds(env)
        self.target_x = clamp(self.target_x, lo, hi)
        if self._move_toward(self.target_x, speed * dt):
            if self.intent == "climb" and self.species.can_climb:
                if self.x <= lo + 0.5:
                    self._start_climb("left")
                    return
                if self.x >= hi - 0.5:
                    self._start_climb("right")
                    return
            self.intent = None
            if running and self._run_legs > 1:
                self._run_legs -= 1
                self._pick_run_target(env)
                return
            if self.rng.random() < 0.5:
                self._enter("idle", self.rng.uniform(1.0, 3.0))
            else:
                self._choose_next()
        elif self.state_time >= self.duration:
            self._choose_next()

    _u_run = _u_walk

    def _u_sleep(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        self._zzz_timer -= dt
        if self._zzz_timer <= 0:
            self._zzz_timer = 1.4
            self.emit("zzz")
        if self.state_time >= self.duration:
            self._enter("idle", self.rng.uniform(1.0, 2.5))

    def _u_eat(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        self.hunger = clamp(self.hunger + 45.0 * dt / 4.0, 0.0, 100.0)
        if self.state_time >= self.duration:
            self.happiness = clamp(self.happiness + 8.0, 0.0, 100.0)
            self.emit("hearts", 2)
            self._enter("idle", self.rng.uniform(1.0, 2.0))

    def _u_land(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        if self.state_time >= self.duration:
            if self.pending == "eat":
                self.pending = None
                self._start_eat()
            else:
                self._enter("idle", self.rng.uniform(0.8, 2.0))

    def _u_fall(self, dt: float, env: Env):
        self.vy = min(self.vy + GRAVITY * dt, TERMINAL_VY)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= max(0.0, 1.0 - 0.35 * dt)
        if abs(self.vx) > 30:
            self.facing = 1 if self.vx > 0 else -1
        lo, hi = self._bounds(env)
        if self.x < lo:
            self.x = lo
            self.vx = abs(self.vx) * 0.45
        elif self.x > hi:
            self.x = hi
            self.vx = -abs(self.vx) * 0.45
        if self.y < env.top:
            self.y = env.top
            if self.vy < 0:
                self.vy = -self.vy * 0.3
        gy = self._ground_y(env)
        if self.y >= gy:
            self.y = gy
            impact = self.vy
            if impact > BOUNCE_MIN_VY:
                self.vy = -impact * 0.38
                self.vx *= 0.7
                self.emit("dust")
            else:
                self.vx = 0.0
                self.vy = 0.0
                if impact > 250:
                    self.emit("dust")
                self._enter("land", 0.22)

    def _u_chase(self, dt: float, env: Env):
        if not self._keep_grounded(env):
            return
        if env.cursor is None or self.state_time >= self.duration:
            self._chase_pose = "walk"
            self._enter("sit", self.rng.uniform(2.0, 5.0))
            return
        lo, hi = self._bounds(env)
        tx = clamp(env.cursor[0] - self.size / 2, lo, hi)
        dx = tx - self.x
        if abs(dx) < self.size * 0.12:
            self._chase_pose = "stand"
            self.facing = 1 if env.cursor[0] >= self.x + self.size / 2 else -1
            self._caught += dt
            if self._caught > 1.2:
                self.happiness = clamp(self.happiness + 4.0, 0.0, 100.0)
                self.emit("hearts", 2)
                self._enter("happy", 1.5)
            return
        self._caught = 0.0
        far = abs(dx) > self.size * 1.2
        speed = (RUN_SPEED if far else WALK_SPEED * 1.4) * self.size * self.species.speed
        self._chase_pose = "run" if far else "walk"
        self._move_toward(tx, speed * dt)

    def _start_climb(self, side: str):
        env = self._env
        self._enter("climb")
        self.wall = side
        self.rotation = 90 if side == "left" else -90
        self.facing = -1 if side == "left" else 1
        top = env.top if env else self.y - self.size * 3
        lowest = (self._ground_y(env) if env else self.y) - self.size * 0.75
        self.target_y = self.rng.uniform(top, max(top, lowest))

    def _stick_to_wall(self, env: Env):
        lo, hi = self._bounds(env)
        self.x = lo if self.wall == "left" else hi
        self.y = clamp(self.y, env.top, self._ground_y(env))

    def _u_climb(self, dt: float, env: Env):
        self._stick_to_wall(env)
        self.y -= CLIMB_SPEED * self.size * dt
        if self.y <= self.target_y or self.y <= env.top:
            self.y = max(self.y, env.top)
            self._enter("cling", self.rng.uniform(2.0, 6.0))

    def _u_cling(self, dt: float, env: Env):
        self._stick_to_wall(env)
        if self.state_time >= self.duration:
            self._let_go()

    def _let_go(self):
        away = 1 if self.wall == "left" else -1
        self._enter("fall")
        self.facing = away
        self.vx = away * self.size * 1.2
        self.vy = -self.size * 2.0

    # ------------------------------------------------------------------ commands from the UI
    def start_drag(self):
        self._enter("drag")
        self.vx = self.vy = 0.0
        self.emit("bubble", "!")

    def drag_to(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)

    def release(self, vx: float = 0.0, vy: float = 0.0):
        speed = math.hypot(vx, vy)
        if speed > MAX_THROW_SPEED:
            vx *= MAX_THROW_SPEED / speed
            vy *= MAX_THROW_SPEED / speed
        self._enter("fall")
        self.vx = float(vx)
        self.vy = float(vy)

    def pet(self):
        """The user petted (clicked) this pet."""
        self.happiness = clamp(self.happiness + 12.0, 0.0, 100.0)
        self.emit("hearts", 3)
        if self.state in AIR_STATES or self.state in WALL_STATES:
            return
        if self.state == "sleep":
            self.emit("bubble", "!")
        self._enter("happy", 1.5)

    def feed(self):
        if self.state in WALL_STATES:
            self.pending = "eat"
            self._let_go()
            return
        if self.state in AIR_STATES:
            self.pending = "eat"
            return
        self._start_eat()

    def _start_eat(self):
        self._enter("eat", 4.0)
        self.emit("bowl", 4.0)

    def go_to_sleep(self, duration: float | None = None):
        if not self.grounded:
            return
        if duration is None:
            duration = self.rng.uniform(45.0, 90.0)
        if self.energy < 35:
            duration = max(duration, min(120.0, (95.0 - self.energy) / SLEEP_RECOVERY))
        self._zzz_timer = 0.6
        self._enter("sleep", duration)

    def wake_up(self):
        if self.state == "sleep":
            self.emit("bubble", "!")
            self._enter("idle", 1.5)

    def play(self):
        if not self.grounded or self._env is None:
            return
        self.happiness = clamp(self.happiness + 3.0, 0.0, 100.0)
        if self._env.cursor is not None:
            self._caught = 0.0
            self._enter("chase", 10.0)
        else:
            self.start("run")

    def can_greet(self) -> bool:
        return (self.state in ("idle", "walk", "sit") and self._greet_cooldown <= 0
                and not self.held and self.intent is None)

    def greet(self, other_x: float):
        self._greet_cooldown = self.rng.uniform(40.0, 90.0)
        self.facing = 1 if other_x > self.x else -1
        self.happiness = clamp(self.happiness + 5.0, 0.0, 100.0)
        self._enter("greet", 2.5)
        self.emit("bubble", "heart")

    def say(self, text: str):
        self.emit("bubble", text)

    def set_size(self, size: float):
        cx = self.x + self.size / 2
        bottom = self.y + self.size
        self.size = float(size)
        self.x = cx - self.size / 2
        self.y = bottom - self.size

    # ------------------------------------------------------------------ view helpers
    def pose(self) -> Pose:
        if self.state == "chase":
            name = self._chase_pose
        else:
            name = POSE_OF[self.state]
        if self.held and name in ("walk", "run"):
            name = "stand"
        frames, fps = ANIMS[name]
        frame = int(self.anim_time * fps) % frames
        blink = self._blinking > 0 and name in BLINKABLE
        return Pose(name, frame, blink)

    def visible_height(self) -> float:
        """How tall the pet currently looks, in pixels (for placing speech bubbles)."""
        if self.rotation:
            return self.size * 0.95
        if self.state == "sleep":
            return self.size * self.species.sleep_height
        if self.state == "drag":
            return self.size * (self.species.height + 0.04)
        return self.size * self.species.height

    def stats(self) -> dict:
        return {
            "hunger": round(self.hunger, 2),
            "energy": round(self.energy, 2),
            "happiness": round(self.happiness, 2),
        }
