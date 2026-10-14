import math

import numpy as np
import pandas as pd
import pytest

from prometheus import props, props_live


def test_chances_split_push_on_whole_lines():
    pmf = np.array([0.2, 0.3, 0.5])
    over, under, push = props_live.chances(pmf, 1)
    assert (over, under, push) == pytest.approx((0.5, 0.2, 0.3))
    assert props_live.chances(pmf, 1.5) == pytest.approx((0.5, 0.5, 0.0))


def test_maps_reads_spans():
    assert props_live._maps("1-3") == 3
    assert props_live._maps("1-2") == 2
    assert props_live._maps("2") is None
    assert props_live._maps(None) is None


def _index():
    return pd.DataFrame(
        {
            "playerid": ["p1", "p2", "p3"],
            "playername": ["Yike", "Yike", "Loki"],
            "teamid": ["t1", "t2", "t3"],
            "teamname": ["Karmine Corp", "Some Academy", "Cloud9"],
            "position": ["jng", "jng", "mid"],
            "date": pd.to_datetime(["2026-09-19", "2026-09-30", "2026-09-27"]),
            "key": ["yike", "yike", "loki"],
        }
    )


def test_resolve_player_prefers_the_team_label():
    index = _index()
    assert props_live.resolve_player("Yike", "KC", index)["playerid"] == "p1"
    assert props_live.resolve_player("Yike", "Karmine Corp", index)["playerid"] == "p1"
    # No label fits: the most recent player of that name.
    assert props_live.resolve_player("Yike", "XYZ", index)["playerid"] == "p2"
    assert props_live.resolve_player("Nobody", "KC", index) is None
    assert props_live.resolve_player("A + B", "KC", index) is None


def test_match_lines_finds_the_fixture_by_team_and_time():
    start = pd.Timestamp("2026-10-15 18:00", tz="UTC")
    fixtures = [
        {
            "match_id": "m1",
            "team1": "Cloud9",
            "team2": "Karmine Corp",
            "start": start,
            "best_of": 5,
        }
    ]
    lines = pd.DataFrame(
        {
            "player": ["Yike", "Loki", "Loki"],
            "team": ["KC", "C9", "C9"],
            "start": [
                start,
                start + pd.Timedelta(hours=1),
                start + pd.Timedelta(days=3),
            ],
        }
    )
    out = props_live.match_lines(lines, _index(), fixtures)
    assert list(out["match_id"]) == ["m1", "m1", None]
    assert list(out["playerid"]) == ["p1", "p3", "p3"]


class _Model:
    def alphas(self, frame, stat, result):
        return np.full(len(frame), 0.05)


def _projected():
    return pd.DataFrame(
        [
            {
                "match_id": "m1",
                "playerid": "p1",
                "p": 0.5,
                "kills_win": 3.0,
                "kills_loss": 2.0,
            }
        ]
    )


def test_price_lines_picks_only_offered_sides():
    fixtures = [
        {
            "match_id": "m1",
            "team1": "A",
            "team2": "B",
            "start": pd.Timestamp("2026-10-15", tz="UTC"),
            "best_of": 5,
        }
    ]
    lines = pd.DataFrame(
        [
            # Far above our projection (about 7.5 over three maps): the under is the pick...
            {
                "source": "underdog",
                "line_id": "1",
                "match_id": "m1",
                "playerid": "p1",
                "stat": "kills",
                "maps": "1-3",
                "line": 12.5,
                "over_mult": 1.0,
                "under_mult": 1.0,
                "over_prob": 0.5,
            },
            # ...unless only the over is offered.
            {
                "source": "underdog",
                "line_id": "2",
                "match_id": "m1",
                "playerid": "p1",
                "stat": "kills",
                "maps": "1-3",
                "line": 12.5,
                "over_mult": 1.0,
                "under_mult": None,
                "over_prob": None,
            },
        ]
    )
    priced = props_live.price_lines(_Model(), lines, _projected(), fixtures).set_index(
        "line_id"
    )
    assert priced.loc["1", "side"] == "under"
    assert priced.loc["1", "edge"] > 0
    assert priced.loc["1", "edge_market"] < 0
    assert priced.loc["2", "side"] == "over"
    assert priced.loc["2", "edge"] < 0
    assert priced.loc["1", "p_side"] == pytest.approx(1 - priced.loc["2", "p_side"])


def test_break_even_is_a_two_pick_entry_paying_three_times():
    assert props_live.BREAK_EVEN**2 * 3 == pytest.approx(1.0)
    assert math.isclose(props_live.BREAK_EVEN, 0.5774, abs_tol=1e-4)


def _games():
    """Two maps of C9 v KC: p1 (KC) scores 4 and 3 kills; a third series later."""
    base = pd.Timestamp("2026-10-15 18:00")
    rows = []
    for i, minutes in enumerate([0, 50]):
        for team, opp, pid, kills in (
            ("Karmine Corp", "Cloud9", "p1", 4 - i),
            ("Cloud9", "Karmine Corp", "p3", 2),
        ):
            rows.append(
                {
                    "gameid": f"g{i}",
                    "teamname": team,
                    "opp_teamname": opp,
                    "playerid": pid,
                    "date": base + pd.Timedelta(minutes=minutes),
                    "series": 1 if team == "Karmine Corp" else 2,
                    "map": i + 1,
                    "kills": kills,
                    "assists": 5,
                    "deaths": 1,
                    "cs": 200,
                }
            )
    return pd.DataFrame(rows)


def test_series_totals_sum_the_counted_maps():
    totals = props_live.series_totals(
        _games(),
        "Karmine Corp",
        "Cloud9",
        pd.Timestamp("2026-10-15 18:00", tz="UTC"),
        3,
    )
    assert totals["p1"]["kills"] == 7
    assert totals["p1"]["maps"] == 2
    assert totals["p1"]["fantasy"] == pytest.approx(3 * 7 + 2 * 10 - 2 + 0.02 * 400)
    assert (
        props_live.series_totals(
            _games(), "Karmine Corp", "G2", pd.Timestamp("2026-10-15", tz="UTC"), 3
        )
        == {}
    )


def test_calls_freeze_at_the_start_and_settle():
    start = pd.Timestamp("2026-10-15 18:00", tz="UTC")
    fixtures = [
        {
            "match_id": "m1",
            "team1": "Cloud9",
            "team2": "Karmine Corp",
            "start": start,
            "best_of": 5,
        }
    ]
    priced = pd.DataFrame(
        [
            {
                "source": "underdog",
                "line_id": "1",
                "match_id": "m1",
                "playerid": "p1",
                "player": "Yike",
                "teamname": "Karmine Corp",
                "start": start,
                "stat": "kills",
                "maps": "1-3",
                "line": 6.5,
                "over_mult": 1.0,
                "under_mult": 1.0,
                "over_prob": 0.5,
                "p_over": 0.4,
                "p_under": 0.6,
                "median": 6,
                "side": "under",
                "p_side": 0.6,
                "edge": 0.02,
            }
        ]
    )
    calls = props_live.update_calls({}, priced, fixtures, start - pd.Timedelta(hours=5))
    assert calls["underdog|1"]["opp"] == "Cloud9"
    first = calls["underdog|1"]["priced"]
    # After the start nothing changes.
    later = priced.assign(p_over=0.9, p_under=0.1)
    props_live.update_calls(calls, later, fixtures, start + pd.Timedelta(minutes=5))
    assert (
        calls["underdog|1"]["p_over"] == 0.4 and calls["underdog|1"]["priced"] == first
    )
    settled = props_live.settle_lines(calls, _games(), start + pd.Timedelta(days=1))
    assert settled.iloc[0]["actual"] == 7 and settled.iloc[0]["result"] == "over"
    card = props_live.scorecard(settled)
    assert card["n"] == 1 and card["hit_rate"] == 0.0
    assert card["market_n"] == 1 and card["market_log_loss_theirs"] == pytest.approx(
        math.log(2)
    )


def test_compact_cdf_prices_like_the_full_pmf():
    pmf = props.series_pmf(
        props.nb_pmf([3.5], [0.1], 40),
        props.nb_pmf([2.0], [0.1], 40),
        np.array([0.6]),
        5,
        3,
    )[0]
    spread = props_live.compact_cdf(pmf)
    for line in (4.5, 7.5, 8, 12.5, 30.5):
        assert props_live.cdf_chances(spread, line) == pytest.approx(
            props_live.chances(pmf, line), abs=2e-3
        )
    full = props_live.summary(pmf)
    assert props_live.cdf_summary(spread) == {
        k: full[k] for k in ("median", "p10", "p90")
    }


def _table():
    pmf = props.nb_pmf([9.0], [0.05], 60)[0]
    spread = props_live.compact_cdf(pmf)
    return {
        "at": "2026-10-14T10:00Z",
        "matches": [
            {
                "match_id": "m1",
                "start": "2026-10-15T18:00Z",
                "team1": "Cloud9",
                "team2": "Karmine Corp",
                "best_of": 5,
                "players": [
                    {
                        "playerid": "p1",
                        "name": "Yike",
                        "team": "Karmine Corp",
                        "spreads": {
                            s: {"2": spread, "3": spread}
                            for s in props_live.COUNT_STATS
                        },
                    },
                ],
            }
        ],
    }


def test_price_from_table_matches_and_prices_lines():
    start = pd.Timestamp("2026-10-15 18:00", tz="UTC")
    lines = pd.DataFrame(
        [
            {
                "source": "underdog",
                "line_id": "1",
                "player": "Yike",
                "team": "KC",
                "stat": "kills",
                "maps": "1-3",
                "line": 12.5,
                "over_mult": 1.0,
                "under_mult": 1.0,
                "over_prob": 0.5,
                "start": start,
            },
            {
                "source": "underdog",
                "line_id": "2",
                "player": "Nobody",
                "team": "KC",
                "stat": "kills",
                "maps": "1-3",
                "line": 5.5,
                "over_mult": 1.0,
                "under_mult": 1.0,
                "over_prob": 0.5,
                "start": start,
            },
        ]
    )
    priced, fixtures = props_live.price_from_table(lines, _table())
    assert [f["match_id"] for f in fixtures] == ["m1"]
    assert list(priced["line_id"]) == ["1"]
    row = priced.iloc[0]
    assert (
        row["playerid"] == "p1"
        and row["teamname"] == "Karmine Corp"
        and row["side"] == "under"
    )
    assert row["median"] == 9
    # Saving the call works from the table's fixtures alone.
    calls = props_live.update_calls({}, priced, fixtures, start - pd.Timedelta(hours=3))
    assert calls["underdog|1"]["opp"] == "Cloud9"
