import numpy as np
import pandas as pd
import pytest

from prometheus import season


def _games(rows):
    df = pd.DataFrame(rows, columns=["teamid", "opp_teamid", "result", "gamelength"])
    n = len(df)
    return df.assign(
        gameid=[f"g{i}" for i in range(n)],
        year=2024,
        date=pd.date_range("2024-01-01", periods=n).astype(str),
        league="LCK",
        teamname=df["teamid"],
        opp_teamname=df["opp_teamid"],
    )


def test_record_ranks_by_schedule_adjusted_results():
    # A beats B and C; B beats C; everyone plays everyone four times.
    rows = []
    for _ in range(4):
        rows += [("A", "B", 1, 1800), ("A", "C", 1, 1800), ("B", "C", 1, 1800)]
    rec = season.get_record(_games(rows)).set_index("teamid")
    assert rec.loc["A", "record"] > rec.loc["B", "record"] > rec.loc["C", "record"]
    # Centred on the average major-league team, so ratings sum to zero here.
    assert rec["rating"].mean() == pytest.approx(0, abs=1e-9)
    assert rec.loc["A", "games"] == 8 and rec.loc["A", "win_pct"] == 1


def test_record_counts_fast_wins_more_than_slow_ones():
    fast = season.fit_record(
        _games([("A", "B", 1, 900)] * 3 + [("B", "A", 1, 900)] * 3)
    )
    slow_wins_for_a = season.fit_record(
        _games([("A", "B", 1, 3000)] * 3 + [("B", "A", 1, 900)] * 3)
    )
    assert fast["A"] == pytest.approx(fast["B"], abs=1e-6)
    assert slow_wins_for_a["A"] < slow_wins_for_a["B"]


def test_luck_is_actual_minus_earned_win_pct():
    rng = np.random.default_rng(0)
    teams = [f"T{i}" for i in range(10)]
    n = 2000
    team = rng.choice(teams, n)
    skill = {t: rng.normal(0, 0.5) for t in teams}
    gpm = rng.normal(0, 1, n) + np.array([skill[t] for t in team])
    result = (gpm + rng.normal(0, 1, n) > 0).astype(int)
    games = pd.DataFrame(
        {"teamname": team, "year": 2024, "league": "LCK", "gpm": gpm, "result": result}
    )
    # "T0" also wins every game it was predicted to lose by a little.
    lucky = (games["teamname"] == "T0") & games["gpm"].between(-0.5, 0)
    games.loc[lucky, "result"] = 1

    luck = season.get_luck({2024: games}, features=["gpm"]).set_index("teamname")

    assert luck["luck"].idxmax() == "T0"
    row = luck.loc["T0"]
    assert row["luck"] == pytest.approx((row["win_pct"] - row["expected"]) * 100)
    assert row["luck_wins"] == pytest.approx(
        (row["win_pct"] - row["expected"]) * row["games"]
    )
    # Calibrated: across the league, luck averages out (weighted by games).
    assert np.average(luck["luck"], weights=luck["games"]) == pytest.approx(0, abs=1e-6)
