import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import learned_offsets as lo

from prometheus import elo


def inputs():
    games = pd.DataFrame(
        [
            ("g0", "a", "aa", 1800, 1, "LCK", "2020-01-01 12:00:00"),
            ("g1", "b", "bb", 1800, 1, "LPL", "2020-01-02 12:00:00"),
            ("g2", "a", "b", 1500, 1, "Worlds", "2020-01-03 12:00:00"),
            ("g3", "a", "b", 1600, 1, "Worlds", "2020-01-04 12:00:00"),
            ("g4", "a", "aa", 1800, 0, "LCK", "2020-01-05 12:00:00"),
        ],
        columns=[
            "gameid",
            "teamid",
            "opponent_teamid",
            "gamelength",
            "result",
            "league",
            "date",
        ],
    )
    rosters = {
        (r.gameid, t): (t,)
        for r in games.itertuples()
        for t in (r.teamid, r.opponent_teamid)
    }
    events = pd.DataFrame(
        {
            "gameid": ["g2", "g3"],
            "event_id": ["e", "e"],
            "day": pd.to_datetime(["2020-01-03", "2020-01-04"]),
        }
    )
    return games, rosters, events


def test_baseline_wrapper_matches_production_records_and_offsets_exactly():
    games, rosters, events = inputs()
    expected, offsets = elo.compute_elo_records(
        games, elo.calculate_game_length_elo_change, rosters=rosters
    )
    actual, learned, _ = lo.replay(games, rosters, events, "baseline")
    pd.testing.assert_frame_equal(actual, expected)
    pd.testing.assert_frame_equal(learned, offsets)


def test_replacement_disables_original_offset_updates_and_no_history_is_neutral():
    games, rosters, events = inputs()
    records, offsets, policy = lo.replay(games, rosters, events, "replacement_fixed")
    assert not policy.audit
    assert (offsets.league_offset == 0).all()
    assert (records.league_offset == 0).all()


def test_new_offsets_only_become_available_after_event_completion():
    games, rosters, events = inputs()
    with mock.patch.object(lo.rc, "MIN_TRAIN", 1):
        records, _, policy = lo.replay(games, rosters, events, "replacement_fixed")
    assert policy.audit[0]["available_from"] == "2020-01-05"
    assert policy.audit[0]["trained_through"] == "2020-01-04"
    assert (records[records.gameid.isin(["g2", "g3"])].league_offset == 0).all()
    assert policy.audit[0]["offsets"]["LCK"] > 0
    assert policy.audit[0]["offsets"]["LPL"] < 0
    assert records[records.gameid == "g4"].league_offset.abs().max() > 0
    assert lo.alpha_at(policy, pd.Timestamp("2020-01-04")) == 1.0


def test_transfer_uses_learned_offsets_and_preserves_player_global_rating():
    games, rosters, events = inputs()
    # Player b transfers from LPL to team a in LCK after the offset fit.
    rosters[("g4", "a")] = ("b",)
    with mock.patch.object(lo.rc, "MIN_TRAIN", 1):
        records, _, policy = lo.replay(games, rosters, events, "replacement_fixed")
    old = records[(records.gameid == "g3") & (records.teamid == "b")].iloc[0]
    new = records[(records.gameid == "g4") & (records.teamid == "a")].iloc[0]
    expected = (
        old.post_match_elo + policy.audit[0]["offsets"]["LPL"] - old.league_offset
    )
    assert abs(new.pre_match_elo - expected) < 1e-9


def test_future_results_cannot_change_past_ratings_or_first_offset_fit():
    games, rosters, events = inputs()
    # Subsequent domestic result must not change ratings/fit available before it.
    changed = games.copy()
    changed.loc[4, "result"] = 1
    with mock.patch.object(lo.rc, "MIN_TRAIN", 1):
        a, _, pa = lo.replay(games, rosters, events, "replacement_fixed")
        b, _, pb = lo.replay(changed, rosters, events, "replacement_fixed")
    pd.testing.assert_frame_equal(a[a.gameid != "g4"], b[b.gameid != "g4"])
    assert pa.audit == pb.audit
    np.testing.assert_array_equal(
        a[a.gameid == "g4"].pre_match_elo, b[b.gameid == "g4"].pre_match_elo
    )


def test_fixed_scale_fit_is_symmetric_and_has_one_zero_sum_offset():
    g = pd.DataFrame(
        {
            "gameid": ["x", "y", "z"],
            "home1": ["A"] * 3,
            "home2": ["B"] * 3,
            "base_logit": [0.0, 0.3, -0.3],
            "won": [1, 1, 0],
            "cluster": ["a", "b", "c"],
        }
    )
    swapped = g.copy()
    swapped[["home1", "home2"]] = swapped[["home2", "home1"]].to_numpy()
    swapped["base_logit"] = -swapped.base_logit
    swapped["won"] = 1 - swapped.won
    with mock.patch.object(lo.rc, "MIN_TRAIN", 1):
        alpha, a = lo.fit_offsets(g, False)
        beta, b = lo.fit_offsets(swapped, False)
    assert alpha == beta == 1.0
    assert abs(sum(a.values())) < 1e-10
    np.testing.assert_allclose([a["A"], a["B"]], [b["A"], b["B"]], atol=1e-8)


def test_scaled_correction_can_be_folded_into_one_effective_offset_exactly():
    n = 60
    history = pd.DataFrame(
        {
            "gameid": [f"g{i}" for i in range(n)],
            "day": pd.to_datetime(["2020-01-01"] * n),
            "home1": ["A"] * n,
            "home2": ["B"] * n,
            "base_logit": np.tile([-0.5, 0.0, 0.5], 20),
            "won": np.tile([0, 1, 1], 20),
            "cluster": [f"c{i}" for i in range(n)],
            "weight": np.ones(n),
        }
    )
    alpha, shifts = lo.fit_offsets(history, True)
    original = lo.rc.fit(history, "2020-01-02", penalty=lo.PENALTY)
    folded = (
        lo.schedule.CROSS_REGION_ELO_WEIGHT
        * alpha
        * (
            history.base_logit.to_numpy() / lo.schedule.CROSS_REGION_ELO_WEIGHT
            + shifts["A"]
            - shifts["B"]
        )
    )
    expected = original.logit(history.base_logit, history.home1, history.home2)
    np.testing.assert_allclose(folded, expected, atol=1e-8, rtol=0)


def test_absolute_refit_shrinks_toward_current_single_offset_values():
    history = pd.DataFrame(
        {
            "gameid": ["x", "y", "z"],
            "home1": ["A"] * 3,
            "home2": ["B"] * 3,
            "base_logit": [0.0, 0.3, -0.3],
            "won": [1, 1, 0],
            "cluster": ["a", "b", "c"],
        }
    )
    with mock.patch.object(lo.rc, "MIN_TRAIN", 1):
        _, neutral = lo.fit_offsets(history, False)
        alpha, prior = lo.fit_offsets(history, False, {"A": 100.0, "B": -100.0})
    assert alpha == 1.0
    assert prior["A"] > neutral["A"] and prior["B"] < neutral["B"]
    assert abs(sum(prior.values())) < 1e-10


def test_recalibration_keeps_one_offset_table_and_preserves_transfers():
    games, rosters, events = inputs()
    rosters[("g4", "a")] = ("b",)
    with mock.patch.object(lo.rc, "MIN_TRAIN", 1):
        records, _, policy = lo.replay(games, rosters, events, "recalibrated_fixed")
    assert all(fit["alpha"] == 1.0 for fit in policy.audit)
    old = records[(records.gameid == "g3") & (records.teamid == "b")].iloc[0]
    new = records[(records.gameid == "g4") & (records.teamid == "a")].iloc[0]
    expected = (
        old.post_match_elo + policy.audit[0]["offsets"]["LPL"] - old.league_offset
    )
    assert abs(new.pre_match_elo - expected) < 1e-9
