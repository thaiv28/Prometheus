import numpy as np
import pandas as pd
import pytest

from prometheus import aura
from prometheus.evaluation import half_of, paired_correlation_bootstrap


def _players(n_games=400, seed=0, short_every=None):
    """Synthetic starters: blue wins more often when its lanes are ahead in gold."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        gaps = {r: rng.normal(0, 1000, size=len(aura.STATS)) for r in aura.ROLES}
        lead = sum(gaps[r][0] for r in aura.ROLES) / 2000
        blue_won = int(rng.random() < 1 / (1 + np.exp(-lead)))
        for side, sign, won in (("Blue", 1, blue_won), ("Red", -1, 1 - blue_won)):
            for r in aura.ROLES:
                row = {
                    "gameid": f"g{g}",
                    "teamid": f"{side}{g % 7}",
                    "position": r,
                    "playerid": f"{side}{g % 7}{r}",
                    "year": 2024,
                    "side": side,
                    "result": won,
                }
                for m in aura.MINUTES:
                    ended = short_every and g % short_every == 0 and m == 25
                    for s, v in zip(aura.STATS, gaps[r]):
                        row[f"{s}_{m}"] = np.nan if ended else sign * v
                rows.append(row)
    return pd.DataFrame(rows)


def test_game_frame_is_one_blue_row_per_game():
    players = _players(20, short_every=5)
    games = aura.game_frame(players, 15)
    assert len(games) == 20
    assert list(games.columns[2:]) == aura.lane_columns()
    blue_top = players[
        (players["side"] == "Blue") & (players["position"] == "top")
    ].set_index("gameid")
    assert games["top_gold"].to_numpy() == pytest.approx(
        blue_top.loc[games.index, "gold_15"].to_numpy()
    )
    # Games that ended before 25 minutes drop out of that snapshot only.
    assert len(aura.game_frame(players, 25)) == 16


def test_player_shares_add_up_to_the_team_and_cancel_by_lane():
    players = _players()
    games = aura.game_frame(players)
    intercept, weights = aura.fit_aura_weights(games)
    players["aura"] = aura.player_scores(players, weights)
    blue = players[players["side"] == "Blue"].groupby("gameid")["aura"].sum()
    logit = np.log(
        aura.win_probability(games, intercept, weights)
        / (1 - aura.win_probability(games, intercept, weights))
    )
    assert (blue.loc[games.index] + intercept).to_numpy() == pytest.approx(
        logit, abs=1e-9
    )
    # Each lane is zero-sum: a player's AURA is minus their lane opponent's.
    assert players.groupby(["gameid", "position"])[
        "aura"
    ].sum().abs().max() == pytest.approx(0, abs=1e-9)


def test_weights_find_the_stat_that_wins():
    _, weights = aura.fit_aura_weights(aura.game_frame(_players(2000)))
    gold = [weights[r][0] for r in aura.ROLES]
    assert all(w > 0 for w in gold)
    # Only gold drives the synthetic result: per unit, the others stay near 0.
    assert all(abs(weights[r][1:]).max() < min(gold) / 3 for r in aura.ROLES)


def _two_years():
    players = pd.concat(
        [_players(300, seed=1).assign(year=2023), _players(300, seed=2, short_every=10)]
    )
    return players.assign(
        gameid=players["gameid"] + players["year"].astype(str)
    ).reset_index(drop=True)


def test_snapshot_scores_fit_each_year_and_leave_short_games_blank():
    players = _two_years()
    scored = aura.snapshot_scores(players, minute=25)
    assert scored[players["year"] == 2023].notna().all()
    assert scored.isna().sum() == 30 * len(aura.ROLES) * 2


def test_earlier_only_skips_years_without_enough_history(monkeypatch):
    monkeypatch.setattr(aura, "MIN_TRAIN_GAMES", 100)
    scored = aura.snapshot_scores(_two_years(), earlier_only=True)
    years = _two_years()["year"]
    assert scored[years == 2023].isna().all()  # nothing earlier to fit on
    assert scored[years == 2024].notna().all()


def test_team_centred_change_sums_to_zero_and_keeps_the_team_total():
    players = _two_years()
    scored = aura.get_aura(players)
    by_team = scored.groupby(["gameid", "teamid"])
    assert by_team["aura_late"].sum().abs().max() == pytest.approx(0, abs=1e-9)
    early = (
        aura.snapshot_scores(players)
        .groupby([players["gameid"], players["teamid"]])
        .sum()
    )
    assert by_team["aura"].sum().to_numpy() == pytest.approx(early.to_numpy())
    # Games that ended before 25 minutes still get a change from the 20-minute snapshot.
    assert scored["aura"].notna().all()


def test_team_centred():
    players = pd.DataFrame({"gameid": ["g"] * 5, "teamid": ["A"] * 5})
    out = aura.team_centred(pd.Series([4.0, 0, 0, 0, 0]), players)
    assert out.tolist() == pytest.approx([4.0, -1.0, -1.0, -1.0, -1.0])


def test_half_of_is_stable_and_splits():
    ids = pd.Series([f"g{i}" for i in range(1000)])
    halves = half_of(ids)
    assert halves.equals(half_of(ids))
    assert 0.4 < halves.mean() < 0.6


def test_paired_correlation_bootstrap():
    rng = np.random.default_rng(0)
    x = rng.normal(size=500)
    strong, weak = (
        x + rng.normal(scale=0.3, size=500),
        x + rng.normal(scale=3, size=500),
    )
    diff, lo, hi = paired_correlation_bootstrap((x, strong), (x, weak))
    assert diff > 0 and lo > 0 and hi > lo


def test_season_aura_points_ranks_and_minimum():
    rows = []
    for pid, team, n, value in (
        ("a", "T1", 25, 0.2),
        ("b", "GEN", 25, -0.1),
        ("c", "DK", 5, 0.4),
    ):
        for g in range(n):
            rows.append(
                {
                    "playerid": pid,
                    "playername": pid.upper(),
                    "year": 2025,
                    "position": "mid",
                    "teamname": team,
                    "league": "LCK",
                    "gameid": f"{pid}{g}",
                    "aura": value,
                }
            )
    rows.append(
        {
            "playerid": "a",
            "playername": "A",
            "year": 2025,
            "position": "mid",
            "teamname": "T1",
            "league": "LDL",
            "gameid": "x",
            "aura": 9.0,
        }
    )  # not a listed league
    seasons = aura.season_aura(pd.DataFrame(rows), ["LCK"], min_games=20).set_index(
        "playerid"
    )
    assert seasons.loc["a", "games"] == 25
    assert seasons.loc["a", "aura"] == pytest.approx(0.2 * aura.POINTS)
    assert seasons.loc["a", "role_rank"] == 1 and seasons.loc["a", "role_count"] == 2
    assert seasons.loc["a", "role_z"] == pytest.approx(-seasons.loc["b", "role_z"])
    assert not seasons.loc["c", "qualified"] and np.isnan(seasons.loc["c", "role_rank"])
