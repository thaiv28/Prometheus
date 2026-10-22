"""Local raw-feed extraction and alignment checks for the fixed role study."""

import gzip
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
study = importlib.import_module("live_role_leads")


def stamp(seconds):
    return f"2024-01-01T00:{seconds // 60:02d}:{seconds % 60:02d}Z"


def joined(times=(0,)):
    team = {
        "gold": 2500,
        "towers": 0,
        "dragons": 0,
        "barons": 0,
        "inhibitors": 0,
        "kills": 0,
    }
    return [
        {
            "game_id": "riot",
            "oe_gameid": "oe",
            "start": stamp(0),
            "samples": [
                {
                    "at": stamp(t),
                    "state": "in_game",
                    "flat": False,
                    "blue": team.copy(),
                    "red": team.copy(),
                }
                for t in times
            ],
        }
    ]


def write_raw(tmp_path, seconds=0, metadata_in_first=False, duplicate=False):
    metadata, frame = {}, {"rfc460Timestamp": stamp(seconds)}
    for side, offset in (("blue", 0), ("red", 5)):
        people, values = [], []
        for i, role in enumerate(study.ROLES, 1):
            pid = i + offset
            people.append({"participantId": pid, "role": role})
            gap = i if side == "blue" else 0
            values.append(
                {
                    "participantId": pid,
                    "totalGold": 1000 + gap * 100,
                    "level": 2 + gap,
                    "creepScore": 10 + gap * 2,
                }
            )
        if duplicate:
            people.append(people[0].copy())
        metadata[f"{side}TeamMetadata"] = {"participantMetadata": people}
        frame[f"{side}Team"] = {"participants": values}
    window = {"frames": [frame]}
    raw = {"samples": [{"window": None}, {"window": window}]}
    if metadata_in_first:
        raw["first"] = {"gameMetadata": metadata}
    else:
        window["gameMetadata"] = metadata
    games = tmp_path / "games"
    games.mkdir(exist_ok=True)
    with gzip.open(games / "riot.json.gz", "wt") as stream:
        json.dump(raw, stream)


def assert_unknown(rows):
    assert not rows.role_known.any()
    assert (rows[study.GAPS].to_numpy() == 0).all()


@pytest.mark.parametrize("metadata_in_first", [False, True])
def test_exact_gaps_and_scaling(tmp_path, metadata_in_first):
    write_raw(tmp_path, metadata_in_first=metadata_in_first)
    rows = study.role_rows(joined(), tmp_path)
    assert rows.role_known.tolist() == [True]
    for i, role in enumerate(study.ROLES, 1):
        assert rows.iloc[0][f"gold_{role}"] == pytest.approx(i / 10)
        assert rows.iloc[0][f"level_{role}"] == i
        assert rows.iloc[0][f"cs_{role}"] == pytest.approx(i / 5)
    assert rows.attrs["coverage"]["exact"] == 1


def test_nearest_and_outside_tolerance(tmp_path):
    write_raw(tmp_path, seconds=10)
    rows = study.role_rows(joined((0, 21)), tmp_path)
    assert rows.role_known.tolist() == [True, False]
    assert rows.iloc[0].gold_top == pytest.approx(0.1)
    assert_unknown(rows.iloc[1:])
    assert rows.attrs["coverage"]["nearest"] == 1


def test_missing_raw(tmp_path):
    assert_unknown(study.role_rows(joined(), tmp_path))


def test_duplicate_role(tmp_path):
    write_raw(tmp_path, duplicate=True)
    assert_unknown(study.role_rows(joined(), tmp_path))


def test_row_count_order_and_filters(tmp_path):
    data = joined((0, 60, 120, 180, 240, 300))
    data[0]["samples"][1]["state"] = "paused"
    data[0]["samples"][2]["flat"] = True
    data[0]["samples"][4]["blue"]["gold"] = 0
    write_raw(tmp_path)
    expected = study.objective_rows(data)
    actual = study.role_rows(data, tmp_path)
    assert len(actual) == len(expected) == 3
    assert actual.game_id.tolist() == expected.game_id.tolist()
    np.testing.assert_array_equal(actual.seconds, expected.seconds)
    assert actual.seconds.tolist() == [0, 60, 180]


def test_first_frame_only_and_missing_role(tmp_path):
    write_raw(tmp_path, seconds=11)
    path = tmp_path / "games" / "riot.json.gz"
    with gzip.open(path, "rt") as stream:
        raw = json.load(stream)
    window = raw["samples"][1]["window"]
    second = window["frames"][0].copy()
    second["rfc460Timestamp"] = stamp(0)
    window["frames"].append(second)
    with gzip.open(path, "wt") as stream:
        json.dump(raw, stream)
    assert_unknown(study.role_rows(joined(), tmp_path))
    window["gameMetadata"]["redTeamMetadata"]["participantMetadata"].pop()
    with gzip.open(path, "wt") as stream:
        json.dump(raw, stream)
    assert_unknown(study.role_rows(joined((11,)), tmp_path))
