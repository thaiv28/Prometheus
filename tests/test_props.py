import numpy as np
import pandas as pd
import pytest

from prometheus import props


def test_result_sequences_cover_every_bo3_outcome():
    seqs = props.result_sequences(3, 3)
    # WW, LL, WLW, WLL, LWW, LWL
    assert len(seqs) == 6
    p = 0.6
    total = sum(p**w * (1 - p) ** l_ for w, l_, _, _ in seqs)
    assert total == pytest.approx(1.0)
    # Every Bo3 has at least two counted maps, at most three.
    assert {cw + cl for _, _, cw, cl in seqs} == {2, 3}


def test_result_sequences_cap_counted_maps():
    seqs = props.result_sequences(5, 3)
    assert all(cw + cl == 3 for _, _, cw, cl in seqs)
    assert sum(0.5 ** (w + l_) for w, l_, _, _ in seqs) == pytest.approx(1.0)


def test_series_pmf_sums_and_mean():
    win = props.nb_pmf([5.0], [0.1], 40)
    loss = props.nb_pmf([2.0], [0.1], 40)
    p = np.array([0.7])
    pmf = props.series_pmf(win, loss, p, best_of=5, maps=2)
    assert pmf.sum() == pytest.approx(1.0, abs=1e-6)
    mean = (pmf[0] * np.arange(pmf.shape[1])).sum()
    # Maps 1-2 are always played in a Bo5: two independent maps.
    assert mean == pytest.approx(2 * (0.7 * 5 + 0.3 * 2), rel=1e-3)


def test_series_pmf_bo3_as_played_weights_third_map():
    one = props.nb_pmf([3.0], [0.05], 30)
    p = np.array([0.5])
    pmf = props.series_pmf(one, one, p, best_of=3, maps=3)
    mean = (pmf[0] * np.arange(pmf.shape[1])).sum()
    # A coin-flip Bo3 goes to three maps half the time: 2.5 maps on average.
    assert mean == pytest.approx(2.5 * 3.0, rel=1e-3)


def test_ew_mean_uses_earlier_rows_only():
    mean, weight = props._ew_mean(
        np.array([1.0, 3.0, 5.0, 10.0]), pd.Series(["a", "a", "b", "a"]), 1
    )
    assert np.isnan(mean[0]) and np.isnan(mean[2])
    assert mean[1] == pytest.approx(1.0)
    # Half-life 1: the newer game counts twice the older one.
    assert mean[3] == pytest.approx((1 * 0.5 + 3 * 1) / 1.5)
    assert list(weight) == pytest.approx([0, 1, 0, 1.5])


def test_shrunk_falls_back_to_prior():
    out = props._shrunk(
        np.array([np.nan, 4.0]), np.array([0.0, 2.0]), np.array([2.0, 2.0]), 2
    )
    assert list(out) == pytest.approx([2.0, 3.0])


def test_add_series_groups_consecutive_games():
    t = pd.Timestamp("2026-01-01 10:00")
    rows = []
    for i, (opp, hours, won) in enumerate(
        [("B", 0, 1), ("B", 1, 0), ("B", 2, 1), ("C", 30, 1)]
    ):
        rows.append(
            {
                "gameid": f"g{i}",
                "teamid": "A",
                "opp_teamid": opp,
                "date": t + pd.Timedelta(hours=hours),
                "result": won,
            }
        )
    g = props.add_series(pd.DataFrame(rows))
    assert list(g["map"]) == [1, 2, 3, 1]
    assert g["series"].nunique() == 2
    assert list(g["series_wins"]) == [2, 2, 2, 1]
    assert list(g["series_losses"]) == [1, 1, 1, 0]


def test_log_score_and_rps_reward_the_right_count():
    sharp = np.zeros((1, 10))
    sharp[0, 3] = 1.0
    flat = np.full((1, 10), 0.1)
    assert props.log_score(sharp, [3])[0] == pytest.approx(0.0, abs=1e-9)
    assert props.rps(sharp, [3])[0] == pytest.approx(0.0)
    assert props.rps(flat, [3])[0] > 0
    assert props.prob_over(flat, [3.5])[0] == pytest.approx(0.6)


def _synthetic_games(n_games=300, seed=0):
    """Two leagues of four teams with fixed rosters, random totals."""
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2024-01-01")
    for i in range(n_games):
        league = "LCK" if i % 2 else "LEC"
        a, b = rng.choice(4, 2, replace=False)
        teams = [f"{league}{a}", f"{league}{b}"]
        won = rng.integers(0, 2)
        for side, (team, opp) in enumerate(
            [(teams[0], teams[1]), (teams[1], teams[0])]
        ):
            result = int(won == side)
            for role in props.ROLES:
                rows.append(
                    {
                        "gameid": f"g{i}",
                        "teamid": team,
                        "position": role,
                        "playerid": f"{team}-{role}",
                        "playername": f"{team}-{role}",
                        "kills": rng.poisson(3 + result),
                        "assists": rng.poisson(6 + 2 * result),
                        "deaths": rng.poisson(3 - result),
                        "cs": rng.poisson(200),
                        "date": start + pd.Timedelta(hours=i),
                        "year": 2024,
                        "league": league,
                        "teamname": team,
                        "gamelength": 1800,
                        "result": result,
                        "opp_teamid": opp,
                        "opp_teamname": opp,
                        "elo": 1500.0,
                        "opp_elo": 1500.0,
                    }
                )
    return props.prepare(pd.DataFrame(rows))


def test_stat_states_take_each_stats_own_half_life():
    g = _synthetic_games(120)
    settings = {"kills": (2, 3), "assists": (16, 3), "deaths": (2, 3), "cs": (16, 3)}
    mixed = props.add_stat_states(g, settings)
    short, long_ = props.add_states(g, 2, 3), props.add_states(g, 16, 3)
    assert np.allclose(mixed["p_kills"], short["p_kills"])
    assert np.allclose(mixed["p_assists"], long_["p_assists"])
    assert np.allclose(mixed["t_cs"], long_["t_cs"]) and np.allclose(
        mixed["o_deaths"], short["o_deaths"]
    )


def test_saved_model_gives_the_same_projections(tmp_path):
    g = props.series_start_states(
        props.add_stat_states(_synthetic_games(), props.uniform(8, 3))
    )
    model = props.fit(g, props.uniform(8, 3))
    path = tmp_path / "w.json"
    path.write_text(__import__("json").dumps(model.to_dict()))
    again = props.load_model(path)
    for stat in props.STATS:
        assert np.allclose(model.means(g, stat), again.means(g, stat))
        assert model.alphas(g, stat, 1).tolist() == again.alphas(g, stat, 1).tolist()
    assert np.allclose(model.win_chance(g), again.win_chance(g))
    assert again.settings == model.settings


def test_published_weights_load():
    model = props.load_model()
    assert set(model.settings) == set(props.STATS)
    assert set(model.models) == set(props.STATS)
