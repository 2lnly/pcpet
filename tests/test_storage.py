import json

from pcpet.storage import DEFAULT_SETTINGS, MAX_PETS, Store, clean_data, clean_name


def test_round_trip(tmp_path):
    store = Store(tmp_path / "sub" / "pcpet.json")
    data = {
        "version": 1,
        "settings": {"size": "large", "bubbles": False, "welcomed": True},
        "pets": [{"id": "abc", "species": "fox", "variant": "arctic", "name": "Snowy", "x": 10.5, "y": 20.0,
                  "hunger": 50.0, "energy": 60.0, "happiness": 70.0}],
    }
    store.save(data)
    assert store.load() == data
    assert not list(store.path.parent.glob(".pcpet-*"))  # no temp files left behind


def test_missing_file_gives_defaults(tmp_path):
    data = Store(tmp_path / "none.json").load()
    assert data["pets"] == [] and data["settings"] == DEFAULT_SETTINGS


def test_corrupt_file_is_moved_aside(tmp_path):
    path = tmp_path / "pcpet.json"
    path.write_text("{not json", encoding="utf-8")
    data = Store(path).load()
    assert data["pets"] == []
    assert (tmp_path / "pcpet.corrupt.json").exists()
    assert not path.exists()


def test_bad_entries_are_dropped_or_repaired():
    raw = {
        "settings": {"size": "gigantic", "bubbles": "yes", "welcomed": True},
        "pets": [
            {"species": "dragon"},
            "nonsense",
            {"species": "cat", "variant": "plaid", "name": "   ", "x": float("nan"), "y": "12",
             "hunger": 500, "energy": -3, "happiness": None},
            {"id": "same", "species": "dog"},
            {"id": "same", "species": "dog"},
        ],
    }
    data = clean_data(raw)
    assert data["settings"] == {"size": "medium", "bubbles": True, "welcomed": True}
    cat, dog1, dog2 = data["pets"]
    assert cat["variant"] == "orange" and cat["name"] == "Cat"
    assert cat["x"] == 0.0 and cat["y"] == 12.0
    assert (cat["hunger"], cat["energy"], cat["happiness"]) == (100.0, 0.0, 75.0)
    assert dog1["id"] == "same" and dog2["id"] is None


def test_pet_count_is_capped():
    raw = {"pets": [{"species": "chick"}] * (MAX_PETS + 5)}
    assert len(clean_data(raw)["pets"]) == MAX_PETS


def test_clean_name():
    assert clean_name("  Sir   Fluff  ") == "Sir Fluff"
    assert clean_name("x" * 100) == "x" * 24
    assert clean_name("", "Fallback") == "Fallback"
    assert clean_name(None, "F") == "F"


def test_saved_file_is_plain_json(tmp_path):
    store = Store(tmp_path / "p.json")
    store.save(clean_data(None))
    assert json.loads(store.path.read_text(encoding="utf-8"))["version"] == 1
