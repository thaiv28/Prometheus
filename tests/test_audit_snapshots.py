"""Protect raw-data coverage accounting and chronological evaluation boundaries."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_snapshots.py"
spec = importlib.util.spec_from_file_location("audit_snapshots", PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def raw_game(gameid="g", date="2026-01-01", length=1800):
    rows = []
    for side, result, base in (("Blue", 1, 200), ("Red", 0, 100)):
        for role in audit.ROLES:
            row = {
                "gameid": gameid,
                "date": date,
                "year": 2025,
                "league": "LTA N",
                "gamelength": length,
                "side": side,
                "teamname": side,
                "position": role,
                "result": result,
                "champion": "champ",
                "playerid": f"{side}/{role}",
                "playername": role,
            }
            row.update({f"{s}at{m}": base for s in audit.STATS for m in audit.MINUTES})
            rows.append(row)
    return pd.DataFrame(rows)


def test_calendar_year_and_gaps_use_actual_rows():
    frames, missing = audit.game_frames(raw_game())
    row = frames[10].loc["g"]
    assert missing == 0
    assert row.year == 2026  # season label deliberately says 2025
    assert row.league == "LCS"
    assert row.total_gold == 500
    assert row.mid_xp == 100
    assert row.won == 1
    assert row.blue_mid_champion == "champ"
    assert row.red_mid_champion == "champ"


def test_missing_xp_keeps_gold_cohort_and_short_games_are_not_missing():
    raw = pd.concat([raw_game("missing"), raw_game("short", length=1199)])
    raw.loc[(raw.gameid == "missing") & (raw.position == "mid"), "xpat20"] = np.nan
    coverage = audit.audit(audit.game_frames(raw)[0]).set_index("minute")
    assert coverage.loc[20, "games"] == 2
    assert coverage.loc[20, "ended_by_minute"] == 1
    assert coverage.loc[20, "reached_minute"] == 1
    assert coverage.loc[20, "gold"] == 1
    assert coverage.loc[20, "aura_features"] == 0
    assert coverage.loc[10, "aura_features"] == 2


@pytest.mark.parametrize(
    "problem",
    [
        "duplicate_role",
        "two_winners",
        "conflicting_date",
        "missing_team",
        "missing_result",
    ],
)
def test_malformed_games_are_counted_but_not_modeled(problem):
    raw = raw_game()
    if problem == "duplicate_role":
        raw.loc[0, "position"] = "mid"
    elif problem == "two_winners":
        raw["result"] = 1
    elif problem == "conflicting_date":
        raw.loc[0, "date"] = "2027-01-01"
    elif problem == "missing_team":
        raw.loc[0, "teamname"] = np.nan
    else:
        raw.loc[0, "result"] = np.nan
    frames, _ = audit.game_frames(pd.concat([raw, raw_game("good")]))
    assert not frames[10].loc["g", "valid_roster"]
    coverage = audit.audit(frames).groupby("minute").sum(numeric_only=True)
    assert coverage.loc[10, "games"] == 2
    assert coverage.loc[10, "invalid_roster_or_metadata"] == 1
    assert coverage.loc[10, "gold"] == 1


def test_nonfinite_negative_and_missing_identifiers():
    raw = raw_game()
    raw["goldat10"] = raw["goldat10"].astype(float)
    raw.loc[0, "goldat10"] = np.inf
    raw.loc[1, "goldat15"] = -1
    raw.loc[0, "playerid"] = np.nan
    raw = pd.concat([raw, raw_game(None)])
    frames, missing = audit.game_frames(raw)
    assert missing == 10
    coverage = audit.audit(frames).set_index("minute")
    assert coverage.loc[10, "gold"] == 0
    assert coverage.loc[15, "gold"] == 0
    assert coverage.loc[20, "gold"] == 1
    assert coverage.loc[20, "complete_player_ids"] == 0


def test_repeated_games_across_files_are_excluded(tmp_path):
    raw_game().to_csv(
        tmp_path / "2025_LoL_esports_match_data_from_OraclesElixir.csv", index=False
    )
    pd.concat([raw_game(), raw_game("new")]).to_csv(
        tmp_path / "2026_LoL_esports_match_data_from_OraclesElixir.csv", index=False
    )
    frames, manifest = audit.load_raw(tmp_path)
    assert manifest["duplicate_gameids_excluded"] == 1
    assert frames[10].index.tolist() == ["new"]


def test_training_and_calibration_cannot_see_future_outcomes_or_features():
    rng = np.random.default_rng(7)
    rows = []
    for year in range(2021, 2028):
        for i in range(110):
            row = {
                "gameid": f"{year}/{i}",
                "date": pd.Timestamp(f"{year}-06-01", tz="UTC"),
                "year": year,
                "league": "LCK",
                "valid_roster": True,
                "gamelength": 1800,
                "won": i % 2,
            }
            row.update({c: rng.normal() for c in audit.FEATURES["aura_features"]})
            row["total_gold"] = row["mid_gold"]
            row["total_kills"] = row["mid_kills"]
            rows.append(row)
    games = pd.DataFrame(rows).set_index("gameid")
    train, cal, test = audit.temporal_split(games, 2026)
    assert set(train.year) == {2022, 2023, 2024}
    assert set(cal.year) == {2025}
    assert set(test.year) == {2026}
    first = audit.benchmark({10: games}, years=(2026,))
    changed = games.copy()
    future = changed.year.ge(2026)
    changed.loc[future, "won"] = 1 - changed.loc[future, "won"]
    changed.loc[future, audit.FEATURES["aura_features"]] *= 1000
    second = audit.benchmark({10: changed}, years=(2026,))
    assert first[2] == second[2]  # includes scaler, model and calibration coefficients
    assert first[1].gameid.nunique() == 110
    assert first[0].n.eq(110).all()
