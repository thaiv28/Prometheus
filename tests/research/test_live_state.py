"""Synthetic offline checks for the fixed live-state study."""

import gzip
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
study = importlib.import_module("live_state")
roles = importlib.import_module("test_live_role_leads")


def item(**overrides):
    return {
        "gold": {"total": 3000, "purchasable": True},
        "maps": {"11": True},
        **overrides,
    }


def write_items(tmp_path):
    directory = tmp_path / "items"
    directory.mkdir()
    data = {
        "1": item(),
        "2": item(into=["1"]),
        "3": item(gold={"total": 1100, "purchasable": True}),
        "4": item(tags=["Consumable"]),
        "5": item(requiredChampion="Viktor"),
        "6": item(requiredAlly="Ornn"),
        "7": item(inStore=False),
        "8": item(gold={"total": 3000, "purchasable": False}),
        "9": item(maps={"11": False}),
        "10": item(into=[]),
    }
    (directory / "14.1.json").write_text(json.dumps({"data": data}))
    (directory / "14.3.json").write_text(json.dumps({"data": {"11": item()}}))
    return directory


def raw_sample(sec, dead=(), dragons=None, details=True):
    frame = {"rfc460Timestamp": roles.stamp(sec)}
    participants = []
    for side, offset in (("blue", 0), ("red", 5)):
        people = []
        for pid in range(1 + offset, 6 + offset):
            people.append(
                {
                    "participantId": pid,
                    "currentHealth": 0 if pid in dead else 100,
                    "maxHealth": 100,
                    "level": 18,
                    "deaths": int(pid in dead),
                }
            )
            participants.append(
                {"participantId": pid, "items": [1, 2, 3, 4, 5] if pid == 1 else []}
            )
        frame[f"{side}Team"] = {
            "participants": people,
            "dragons": list((dragons or {}).get(side, [])),
        }
    sample = {
        "window": {"gameMetadata": {"patchVersion": "14.2.123.456"}, "frames": [frame]}
    }
    if details:
        sample["details"] = {
            "frames": [
                {"rfc460Timestamp": roles.stamp(sec), "participants": participants}
            ]
        }
    return sample


def extract(tmp_path, samples, times=None):
    games = tmp_path / "games"
    games.mkdir(parents=True, exist_ok=True)
    with gzip.open(games / "riot.json.gz", "wt") as stream:
        json.dump({"samples": samples}, stream)
    times = times if times is not None else [i * 30 for i in range(len(samples))]
    return study.state_rows(roles.joined(times), tmp_path, write_items(tmp_path))


def test_alive_from_health_and_balanced_deaths(tmp_path):
    rows = extract(tmp_path, [raw_sample(0, (1, 6, 7)), raw_sample(30, (1, 6))])
    assert rows.alive.tolist() == [1, 0]
    assert rows.any_dead.tolist() == [True, True]
    assert rows.state_known.all()
    assert rows.iloc[0].respawn == pytest.approx(52.5 / 60)


def test_respawn_decreases_and_clears(tmp_path):
    rows = extract(
        tmp_path, [raw_sample(0, (6,)), raw_sample(30, (6,)), raw_sample(60)]
    )
    assert rows.respawn.tolist() == pytest.approx([52.5 / 60, 22.5 / 60, 0])


def test_new_death_resets_estimate(tmp_path):
    samples = [raw_sample(0, (6,)), raw_sample(30, (6,))]
    samples[1]["window"]["frames"][0]["redTeam"]["participants"][0]["deaths"] = 2
    rows = extract(tmp_path, samples)
    assert rows.respawn.tolist() == pytest.approx([52.5 / 60, 52.5 / 60])


def test_elder_recent_causal_and_expires_soul_ignores_elder(tmp_path):
    times = (0, 60, 240, 241, 300)
    dragons = {"blue": ["infernal", "ocean", "cloud", "elder"]}
    samples = [raw_sample(t, dragons=dragons if t >= 60 else {}) for t in times]
    samples[-1]["window"]["frames"][0]["blueTeam"]["dragons"].append("mountain")
    rows = extract(tmp_path, samples, times)
    assert rows.elder_recent.tolist() == [0, 1, 1, 0, 0]
    assert rows.elder.tolist() == [0, 1, 1, 1, 1]
    assert rows.soul_true.tolist() == [0, 0, 0, 0, 1]
    assert rows.elder_taken.tolist() == [False, True, True, True, True]


def test_completed_item_rule_and_patch_fallback(tmp_path):
    sets = study.completed_sets(write_items(tmp_path))
    assert sets[(14, 1)] == {1, 10}
    assert study.patch_items("14.2.123", sets) == {1, 10}
    assert study.patch_items("14.3.123", sets) == {11}
    assert study.patch_items("13.24", sets) is None
    assert study.patch_items(None, sets) is None


def test_items_gap_and_unknown_details_patch(tmp_path):
    samples = [raw_sample(0), raw_sample(30, details=False), raw_sample(60)]
    samples[2]["window"]["gameMetadata"]["patchVersion"] = "13.24"
    rows = extract(tmp_path, samples)
    assert rows.items_known.tolist() == [True, False, False]
    assert rows["items"].tolist() == [1, 0, 0]
    assert rows.state_known.all()


@pytest.mark.parametrize("offset, known", [(0, True), (10, True), (11, False)])
def test_details_timestamp_match(tmp_path, offset, known):
    sample = raw_sample(0)
    sample["details"]["frames"][0]["rfc460Timestamp"] = roles.stamp(offset)
    rows = extract(tmp_path, [sample])
    assert bool(rows.iloc[0].items_known) == known


def test_details_exact_preferred(tmp_path):
    sample = raw_sample(0)
    near = {"rfc460Timestamp": roles.stamp(1), "participants": []}
    sample["details"]["frames"].insert(0, near)
    assert extract(tmp_path, [sample]).iloc[0].items_known


def test_row_count_order_equals_objectives(tmp_path):
    data = roles.joined((0, 60, 120, 180, 240, 300))
    data[0]["samples"][1]["state"] = "paused"
    data[0]["samples"][2]["flat"] = True
    data[0]["samples"][4]["blue"]["gold"] = 0
    expected = roles.study.objective_rows(data)
    actual = study.state_rows(data, tmp_path, tmp_path)
    assert len(actual) == len(expected) == 3
    assert actual.game_id.tolist() == expected.game_id.tolist()
    np.testing.assert_array_equal(actual.seconds, expected.seconds)
    assert not actual.state_known.any()
    assert not actual.items_known.any()
    assert (actual[study.VALUES].to_numpy() == 0).all()


def test_death_timer_steps_and_cap():
    assert study.death_timer(1, 899) == 6
    assert study.death_timer(18, 900) == 52.5
    assert study.death_timer(18, 930) == pytest.approx(52.5 * 1.00425)
    assert study.death_timer(18, 1800) == pytest.approx(52.5 * 1.1275)
    assert study.death_timer(18, 2700) == pytest.approx(52.5 * 1.2175)
    assert study.death_timer(18, 3300) == pytest.approx(52.5 * 1.5)


def test_fixed_candidate_columns():
    assert len(study.STATE_FEATURES) == len(study.candidate_columns("soul_true")) == 20
    assert "obj_soul" not in study.candidate_columns("combined")
    assert "soul_true_time" in study.candidate_columns("combined")


def test_level_outside_fixed_table_marks_state_unknown(tmp_path):
    sample = raw_sample(0)
    sample["window"]["frames"][0]["blueTeam"]["participants"][0]["level"] = 20
    assert extract(tmp_path / "cap", [sample]).iloc[0].state_known
    sample["window"]["frames"][0]["blueTeam"]["participants"][0]["level"] = 21
    rows = extract(tmp_path, [sample])
    assert not rows.iloc[0].state_known
    assert rows.iloc[0].items_known
    assert (rows[[c for c in study.VALUES if c != "items"]].to_numpy() == 0).all()


def test_raised_level_cap_uses_level_18_timer():
    assert study.death_timer(20, 900) == study.death_timer(18, 900)
    assert study.death_timer(19, 1800) == study.death_timer(18, 1800)
