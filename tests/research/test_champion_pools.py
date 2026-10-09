"""Rolling champion pools in champion_pools.py."""

import importlib.util
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DIR = Path(__file__).resolve().parents[2] / "scripts" / "research"
spec = importlib.util.spec_from_file_location(
    "champion_pools", DIR / "champion_pools.py"
)
cp = importlib.util.module_from_spec(spec)
sys.modules["champion_pools"] = cp
spec.loader.exec_module(cp)


def _picks(rows):
    df = pd.DataFrame(
        rows, columns=["gameid", "teamid", "playerid", "champion", "when"]
    )
    df["when"] = pd.to_datetime(df["when"])
    return df.sort_values("when", kind="mergesort").reset_index(drop=True)


def test_depth_is_effective_champions_before_the_game():
    picks = _picks(
        [
            ("g1", "t", "p", "Ahri", "2026-01-01"),
            ("g2", "t", "p", "Ahri", "2026-01-02"),
            ("g3", "t", "p", "Syndra", "2026-01-03"),
            ("g4", "t", "p", "Orianna", "2026-01-04"),
            ("g5", "t", "p", "Azir", "2026-09-01"),  # first three out of the window
        ]
    )
    pools = cp.player_pools(picks, window_days=180)
    assert np.isnan(pools.loc[0, "depth"]) and pools.loc[0, "games"] == 0
    assert pools.loc[1, "depth"] == pytest.approx(1.0)
    assert pools.loc[2, "depth"] == pytest.approx(1.0)  # two Ahri games
    q = np.array([2, 1]) / 3
    assert pools.loc[3, "depth"] == pytest.approx(math.exp(-(q * np.log(q)).sum()))
    # Sep 1 is 240 days after Jan 4: nothing left in the window
    assert pools.loc[4, "games"] == 0


def test_matches_a_brute_force_count():
    rng = np.random.default_rng(0)
    champs = ["A", "B", "C", "D", "E"]
    start = pd.Timestamp("2025-01-01")
    rows = [
        (
            f"g{i}",
            "t",
            f"p{i % 3}",
            rng.choice(champs),
            start + pd.Timedelta(days=int(d)),
        )
        for i, d in enumerate(np.sort(rng.integers(0, 400, 300)))
    ]
    picks = _picks(rows)
    pools = cp.player_pools(picks, window_days=60)
    for i in range(len(picks)):
        r = picks.iloc[i]
        h = picks[
            (picks["playerid"] == r["playerid"])
            & (picks["when"] < r["when"])
            & (picks["when"] >= r["when"] - pd.Timedelta(days=60))
        ]
        assert pools.loc[i, "games"] == len(h)
        if len(h):
            q = np.array(list(Counter(h["champion"]).values())) / len(h)
            assert pools.loc[i, "depth"] == pytest.approx(
                math.exp(-(q * np.log(q)).sum())
            )
