import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "draft_walkforward", ROOT / "scripts" / "research" / "draft_walkforward.py"
)
dw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dw)


def _frame(days, values):
    return pd.DataFrame(
        {
            "key": ["a"] * len(days),
            "day": pd.to_datetime(days),
            "v": values,
        }
    )


def test_prior_days_never_reads_the_same_day_or_later():
    frame = _frame(
        ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-05"], [1.0, 2.0, 4.0, 8.0]
    )
    got = dw.prior_days(frame, ["key"], ["v"])[:, 0]
    # Both games on the first day see nothing; later days see all earlier days.
    assert list(got) == [0.0, 0.0, 3.0, 7.0]


def test_prior_days_ignores_future_changes():
    frame = _frame(["2025-01-01", "2025-01-02", "2025-01-03"], [1.0, 1.0, 1.0])
    before = dw.prior_days(frame, ["key"], ["v"])[:, 0]
    frame.loc[2, "v"] = 100.0  # a later result changes
    after = dw.prior_days(frame, ["key"], ["v"])[:, 0]
    assert np.array_equal(before[:2], after[:2])


def _rows():
    """Two games on two days, blue v red, each player one champion."""
    out = []
    for game, day, blue_won in (("g1", "2025-01-01", 1), ("g2", "2025-01-02", 0)):
        for team, side, won in (("t1", "Blue", blue_won), ("t2", "Red", 1 - blue_won)):
            for i, pos in enumerate(["top", "jng", "mid", "bot", "sup"]):
                out.append(
                    {
                        "gameid": game,
                        "teamid": team,
                        "teamname": team.upper(),
                        "date": pd.Timestamp(day),
                        "day": pd.Timestamp(day),
                        "league": "LCK",
                        "side": side,
                        "result": won,
                        "position": pos,
                        "playerid": f"{team}{i}",
                        "champion": f"{team}c{i}",
                        "p": 0.5,
                        "wae": won - 0.5,
                        "one": 1.0,
                    }
                )
    return pd.DataFrame(out)


def test_first_game_has_no_history_and_the_second_sees_the_first():
    rows = dw.player_features(_rows())
    games = dw.game_table(rows, dw.synergy(rows)).set_index("gameid")
    assert (games.loc["g1", dw.FEATURES] == 0).all()
    # The same champions again: blue (t1) has experience, matchups and pairs
    # that won on day one; red the opposite.
    g2 = games.loc["g2"]
    assert g2["exp"] == 0  # both sides have played once: equal experience
    assert g2["matchup"] > 0 and g2["synergy"] > 0 and g2["meta"] > 0
