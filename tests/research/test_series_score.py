import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "series_score",
    Path(__file__).resolve().parents[2] / "scripts/research/series_score.py",
)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)


def test_posterior_zero_limit_updates_and_side_symmetry():
    assert np.isclose(ss.posterior(0.6, 0.0, 1, 0), 0.6)
    assert np.isclose(ss.posterior(0.6, 0.1, 1, 0), 0.6 + 0.1 * 0.4)
    assert np.isclose(ss.posterior(0.6, 0.1, 2, 1), 1 - ss.posterior(0.4, 0.1, 1, 2))


def test_histories_count_missing_drafts_and_never_read_current_or_later_result():
    rows = [
        {
            "gameid": f"g{i}",
            "teamname": team,
            "opp": opp,
            "when": pd.Timestamp("2025-01-01") + pd.Timedelta(hours=i),
            "result": win if team == "A" else 1 - win,
        }
        for i, win in enumerate([1, 0, 1])
        for team, opp in [("A", "B"), ("B", "A")]
    ]
    frame = pd.DataFrame(rows)
    picks = {
        (f"g{i}", team): tuple(f"{team}{i}{j}" for j in range(5))
        for i in [0, 2]
        for team in ["A", "B"]
    }
    before = ss.histories(frame, picks)
    assert before.wins.tolist() == [0, 1, 1]
    assert before.losses.tolist() == [0, 0, 1]
    assert before.previous.tolist() == [(), ("g0",), ("g0", "g1")]
    assert not before.iloc[2].prefix_complete
    frame.loc[frame.gameid.isin(["g1", "g2"]), "result"] = (
        1 - frame.loc[frame.gameid.isin(["g1", "g2"]), "result"]
    )
    after = ss.histories(frame, picks)
    pd.testing.assert_frame_equal(before.iloc[:2], after.iloc[:2])


def test_walkforward_coefficients_do_not_see_test_results(monkeypatch):
    rng = np.random.default_rng(11)
    games = []
    history = []
    for year in range(2019, 2023):
        for i in range(24):
            gid = f"{year}-{i}"
            games.append(
                dict(
                    gameid=gid,
                    year=year,
                    league="LCK",
                    blue="A" if i % 2 == 0 else "B",
                    red="B" if i % 2 == 0 else "A",
                    won=i % 2 == 0,
                    p_forge=0.55,
                    forge_logit=0.2,
                    series=f"{year}-{i // 3}",
                    **{f: rng.normal() for f in ss.dw.FEATURES},
                )
            )
            history.append(
                {
                    "gameid": gid,
                    "first": f"{year}-{i - i % 3}",
                    "canonical": "A",
                    "wins": i % 3,
                    "losses": 0,
                    "previous": tuple(f"{year}-{j}" for j in range(i - i % 3, i)),
                    "reuse": 0.0,
                    "repeat_free": True,
                    "prefix_complete": True,
                }
            )
    games = pd.DataFrame(games)
    history = pd.DataFrame(history)
    monkeypatch.setattr(ss.dw, "TEST_YEARS", [2022])
    before, rhos = ss.evaluate(games, history)
    changed = games.copy()
    changed.loc[changed.year == 2022, "won"] = ~changed.loc[changed.year == 2022, "won"]
    after, later = ss.evaluate(changed, history)
    assert rhos == later
    for col in ["posterior", "draft", "draft_score", "adapt"]:
        assert np.allclose(before[col], after[col])
    assert set(before["series"]) == set(
        games.loc[(games.year == 2022) & (games.index % 3 > 0), "series"]
    )
