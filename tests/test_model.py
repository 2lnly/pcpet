import math
import random

import pytest

from pcpet.model import MAX_THROW_SPEED, Env, Pet
from pcpet.species import ANIMS, SPECIES, SPECIES_ORDER

DT = 1 / 30
ENV = Env(0.0, 0.0, 1200.0, 700.0)


def make(species="cat", x=500.0, y=0.0, size=96, seed=1, **kw):
    return Pet(SPECIES[species], None, "Test", size, x, y, rng=random.Random(seed), **kw)


def run(pet, seconds, env=ENV, check=None):
    events = []
    for _ in range(int(seconds / DT)):
        pet.update(DT, env)
        events.extend(pet.drain_events())
        if check:
            check(pet)
    return events


def settle(pet, env=ENV):
    for _ in range(300):
        pet.update(DT, env)
        if pet.state not in ("fall", "land"):
            return
    raise AssertionError("pet never landed")


def ground_y(pet, env=ENV):
    return env.bottom - pet.size


def test_falls_and_lands_on_floor():
    pet = make(y=50)
    pet.update(DT, ENV)
    assert pet.state == "fall"
    settle(pet)
    assert pet.y == ground_y(pet)
    assert pet.grounded


def test_high_drop_bounces_and_makes_dust():
    pet = make(y=0)
    saw_upward = False
    events = []
    for _ in range(200):
        pet.update(DT, ENV)
        events.extend(pet.drain_events())
        if pet.state == "fall" and pet.vy < 0:
            saw_upward = True
        if pet.state not in ("fall",):
            break
    assert saw_upward, "a long drop should bounce"
    assert ("dust",) in events


@pytest.mark.parametrize("species", SPECIES_ORDER)
@pytest.mark.parametrize("with_cursor", [False, True])
def test_long_simulation_stays_on_screen(species, with_cursor):
    env = Env(100.0, 50.0, 1000.0, 650.0, cursor=(700.0, 640.0) if with_cursor else None)
    pet = make(species, x=400, y=60, seed=hash((species, with_cursor)) & 0xFFFF)
    seen = set()

    def check(p):
        assert math.isfinite(p.x) and math.isfinite(p.y)
        assert env.left - 1e-6 <= p.x <= env.right - p.size + 1e-6
        assert env.top - 1e-6 <= p.y <= env.bottom - p.size + 1e-6
        pose = p.pose()
        assert pose.name in ANIMS
        assert 0 <= pose.frame < ANIMS[pose.name][0]
        seen.add(p.state)

    run(pet, 15 * 60, env, check)
    assert {"idle", "walk", "sit"} <= seen
    assert 0 <= pet.hunger <= 100 and 0 <= pet.energy <= 100 and 0 <= pet.happiness <= 100


def test_climbing_cat_goes_up_the_wall_then_lets_go():
    pet = make("cat", x=300, y=ground_y(make()))
    pet.update(DT, ENV)
    pet.start("climb")
    states = []

    def check(p):
        states.append(p.state)
        if p.state in ("climb", "cling"):
            assert p.x == ENV.left
            assert p.rotation == 90
            assert p.wall == "left"
        else:
            assert p.rotation == 0

    run(pet, 120, ENV, check)
    assert "climb" in states and "cling" in states
    first_fall = states.index("fall", states.index("cling"))
    assert first_fall > 0


def test_climbing_right_wall_rotates_the_other_way():
    pet = make("slime", x=1000, y=ground_y(make("slime")))
    pet.update(DT, ENV)
    pet._start_climb("right")
    pet.update(DT, ENV)
    assert pet.state == "climb" and pet.rotation == -90 and pet.facing == 1
    assert pet.x == ENV.right - pet.size
    y0 = pet.y
    pet.update(DT, ENV)
    assert pet.y < y0


def test_non_climbers_do_not_climb():
    pet = make("dog", y=ground_y(make("dog")))
    pet.update(DT, ENV)
    pet.start("climb")
    assert pet.state == "idle" and pet.intent is None


def test_drag_and_throw_is_capped_and_bounces_off_walls():
    pet = make(y=ground_y(make()))
    pet.update(DT, ENV)
    pet.start_drag()
    assert pet.state == "drag"
    assert ("bubble", "!") in pet.drain_events()
    pet.drag_to(900, 200)
    pet.update(DT, ENV)
    assert (pet.x, pet.y) == (900, 200)  # no physics while held
    pet.release(10_000, 0)
    assert math.hypot(pet.vx, pet.vy) == pytest.approx(MAX_THROW_SPEED)
    hit_wall = False
    for _ in range(300):
        pet.update(DT, ENV)
        if pet.vx < 0:
            hit_wall = True
        if pet.state != "fall":
            break
    assert hit_wall
    assert pet.x <= ENV.right - pet.size


def test_feed_eats_and_fills_up():
    pet = make(y=ground_y(make()), stats={"hunger": 20})
    pet.update(DT, ENV)
    pet.feed()
    assert pet.state == "eat"
    assert ("bowl", 4.0) in pet.drain_events()
    events = run(pet, 4.2)
    assert pet.hunger > 60
    assert ("hearts", 2) in events
    assert pet.state != "eat"


def test_feed_while_falling_eats_after_landing():
    pet = make(y=0)
    pet.update(DT, ENV)
    assert pet.state == "fall"
    pet.feed()
    assert pet.pending == "eat"
    states = set()
    run(pet, 3, ENV, lambda p: states.add(p.state))
    assert "eat" in states and pet.pending is None


def test_petting_makes_happy_and_wakes_sleepers():
    pet = make(y=ground_y(make()), stats={"happiness": 10})
    pet.update(DT, ENV)
    pet.go_to_sleep()
    assert pet.state == "sleep"
    pet.drain_events()
    pet.pet()
    events = pet.drain_events()
    assert pet.state == "happy"
    assert ("hearts", 3) in events and ("bubble", "!") in events
    assert pet.happiness == pytest.approx(22, abs=0.1)


def test_sleep_restores_energy_and_snores():
    pet = make(y=ground_y(make()), stats={"energy": 10})
    pet.update(DT, ENV)
    pet.go_to_sleep(20)
    assert pet.duration >= 80  # tired pets sleep until rested
    events = run(pet, 10)
    assert pet.state == "sleep"
    assert pet.energy > 18
    assert events.count(("zzz",)) >= 5


def test_stats_drift_over_time():
    pet = make(y=ground_y(make()), stats={"hunger": 50, "energy": 50, "happiness": 50})
    run(pet, 60)
    assert pet.hunger < 50
    assert pet.happiness < 50


def test_chasing_reaches_the_cursor_and_gets_happy():
    env = Env(0.0, 0.0, 1200.0, 700.0, cursor=(1000.0, 650.0))
    pet = make(x=100, y=ground_y(make()))
    pet.update(DT, env)
    pet.play()
    assert pet.state == "chase"
    for _ in range(int(8 / DT)):
        pet.update(DT, env)
        if pet.state != "chase":
            break
    assert pet.state == "happy"
    assert abs(pet.x + pet.size / 2 - 1000) < pet.size * 0.15


def test_play_without_cursor_does_zoomies():
    pet = make(y=ground_y(make()))
    pet.update(DT, ENV)
    pet.play()
    assert pet.state == "run"


def test_greeting():
    a = make(x=400, y=ground_y(make()))
    a.update(DT, ENV)
    a._greet_cooldown = 0
    assert a.can_greet()
    a.greet(600)
    assert a.state == "greet" and a.facing == 1
    assert ("bubble", "heart") in a.drain_events()
    assert not a.can_greet()


def test_floor_moving_down_makes_pet_fall_and_up_snaps():
    pet = make(y=ground_y(make()))
    pet.update(DT, ENV)
    assert pet.grounded
    lower = Env(0.0, 0.0, 1200.0, 800.0)
    pet.update(DT, lower)
    assert pet.state == "fall"
    settle(pet, lower)
    higher = Env(0.0, 0.0, 1200.0, 750.0)
    pet.update(DT, higher)
    assert pet.y == ground_y(pet, higher)


def test_screen_shrinking_pulls_pet_back_inside():
    pet = make(x=1100, y=ground_y(make()))
    pet.update(DT, ENV)
    small = Env(0.0, 0.0, 800.0, 700.0)
    pet.update(DT, small)
    assert pet.x <= 800 - pet.size


def test_set_size_keeps_feet_in_place():
    pet = make(x=500, y=ground_y(make()))
    bottom, center = pet.y + pet.size, pet.x + pet.size / 2
    pet.set_size(176)
    assert pet.y + pet.size == bottom and pet.x + pet.size / 2 == center


def test_held_pets_freeze():
    pet = make(x=500, y=ground_y(make()))
    pet.update(DT, ENV)
    pet.start("walk")
    pet.held = True
    x = pet.x
    run(pet, 2)
    assert pet.x == x
    assert pet.pose().name == "stand"


def test_jump_reaches_expected_height():
    pet = make(x=500, y=ground_y(make()))
    pet.update(DT, ENV)
    start_y = pet.y
    pet._jump()
    peak = start_y
    for _ in range(100):
        pet.update(1 / 240, ENV)
        peak = min(peak, pet.y)
    rise = start_y - peak
    # the jump height is chosen between 0.5 and 1.0 body sizes
    assert 0.45 * pet.size <= rise <= 1.05 * pet.size


def test_bubbles_for_talking_use_species_sounds():
    pet = make("dog", y=ground_y(make("dog")), seed=3)
    pet.update(DT, ENV)
    texts = set()
    for _ in range(40):
        pet.start("talk")
        for ev in pet.drain_events():
            texts.add(ev[1])
    assert texts <= set(SPECIES["dog"].sounds) | {"note"}
    assert len(texts) > 2
