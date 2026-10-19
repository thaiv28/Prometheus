"""Research share redistribution: conservation, orientation and causal scaling."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prometheus import elo

RESEARCH = Path(__file__).resolve().parents[1] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
spec = importlib.util.spec_from_file_location(
    "elo_win_share", RESEARCH / "elo_win_share.py"
)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


def fixture():
    games = pd.DataFrame(
        [("g1", "a", "b", 1800, 1), ("g2", "a", "b", 1800, 0)],
        columns=["gameid", "teamid", "opponent_teamid", "gamelength", "result"],
    )
    rosters = {
        (g, t): tuple(t + str(i) for i in range(5))
        for g in ("g1", "g2")
        for t in ("a", "b")
    }
    return games, rosters


def run(shares=None, **kw):
    games, rosters = fixture()
    return elo.compute_elo_records(
        games,
        lambda **kw: 10 if kw["result"] else -10,
        rosters=rosters,
        player_records=True,
        win_share=shares,
        rookie_penalty=0,
        away_factor=0,
        **kw,
    )


def test_equal_weights_and_default_are_exact():
    _, rosters = fixture()
    equal = {key: dict.fromkeys(ids, 0.2) for key, ids in rosters.items()}
    for baseline, variant in zip(run(), run(equal)):
        pd.testing.assert_frame_equal(baseline, variant, check_exact=True)


def test_hand_made_shares_preserve_team_move_and_never_reverse():
    _, rosters = fixture()
    shares = {
        key: dict(zip(ids, [0, 0.1, 0.2, 0.3, 0.4])) for key, ids in rosters.items()
    }
    teams, _, players = run(shares, provisional_games=0)
    for key, group in players.groupby(["gameid", "teamid"], sort=False):
        step = group.post_match_elo.to_numpy() - group.pre_match_elo.to_numpy()
        sign = 1 if key in [("g1", "a"), ("g2", "b")] else -1
        np.testing.assert_allclose(step, sign * np.array([0, 5, 10, 15, 20]))
    np.testing.assert_allclose(teams.elo_change, [10, -10, -10, 10])


def test_missing_invalid_or_zero_weights_use_equal_moves():
    _, rosters = fixture()
    for value in (0, -1, np.nan):
        shares = {key: dict.fromkeys(ids, value) for key, ids in rosters.items()}
        for b, v in zip(run(), run(shares)):
            pd.testing.assert_frame_equal(b, v, check_exact=True)
    for b, v in zip(run(), run({("g1", "a"): {"a0": 1}})):
        pd.testing.assert_frame_equal(b, v, check_exact=True)


def test_conservation_with_mixed_provisional_multipliers():
    games, rosters = fixture()
    rosters[("g2", "a")] = ("new", "a1", "a2", "a3", "a4")
    shares = {("g2", "a"): dict(zip(rosters[("g2", "a")], [0, 0.1, 0.2, 0.3, 0.4]))}
    results = []
    for weights in (None, shares):
        teams, _ = elo.compute_elo_records(
            games,
            lambda **kw: 10,
            rosters=rosters,
            rookie_penalty=0,
            provisional_games=1,
            provisional_factor=2,
            away_factor=0,
            win_share=weights,
        )
        results.append(teams)
    np.testing.assert_allclose(results[0].elo_change, results[1].elo_change)


def test_signal_orientation_clipping_and_whole_game_fallback():
    players = pd.DataFrame(
        [
            (g, t, t + str(i), r, int(t == "a"))
            for g in ("g1", "g2")
            for t in ("a", "b")
            for i, r in enumerate(research.aura.ROLES)
        ],
        columns=["gameid", "teamid", "playerid", "position", "result"],
    )
    z = pd.Series(np.tile([-10, -1, 0, 1, 10], 4), dtype=float)
    shares, eligible = research.make_shares(players, z, 0.1)
    assert eligible == {"g1", "g2"}
    assert shares[("g1", "a")]["a4"] > shares[("g1", "a")]["a0"] == 0
    assert shares[("g1", "b")]["b0"] > shares[("g1", "b")]["b4"] == 0
    for w in shares.values():
        assert sum(w.values()) == pytest.approx(1)
        assert min(w.values()) >= 0
    z.iloc[0] = np.nan
    shares, eligible = research.make_shares(players, z, 0.1)
    assert eligible == {"g2"}
    assert ("g1", "b") not in shares


def test_role_scaling_never_reads_current_or_future_year():
    players = pd.DataFrame(
        {"year": [2020] * 100 + [2021] * 100 + [2022] * 100, "position": ["jng"] * 300}
    )
    values = pd.Series(np.tile(np.arange(100), 3), dtype=float)
    b = research.standardize_prior(players, values)
    values.iloc[100:] += 10000
    v = research.standardize_prior(players, values)
    assert b.iloc[:100].isna().all()
    # Current year's changed values change its z, but cannot change its scaler.
    np.testing.assert_allclose(
        v.iloc[100:200] - b.iloc[100:200], 10000 / np.std(np.arange(100), ddof=1)
    )
    values.iloc[200:] += 1e6
    w = research.standardize_prior(players, values)
    np.testing.assert_array_equal(v.iloc[:200], w.iloc[:200])
