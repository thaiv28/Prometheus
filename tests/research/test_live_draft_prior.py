import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "live_draft_prior",
    Path(__file__).resolve().parents[2] / "scripts/research/live_draft_prior.py",
)
ld = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ld)


def test_partitions_are_chronological_feed_only_and_common_support():
    rows = []
    for date, source, prefix, high in (
        ("2024-12-31", "gol", "a", 25),
        ("2025-01-01", "feed", "b", 23),
        ("2025-07-01", "feed", "c", 21),
        ("2025-04-01", "gol", "excluded", 40),
    ):
        rows.extend(
            {
                "date": date,
                "source": source,
                "game_id": f"{prefix}{i}",
                "minute": m,
                "seconds": m * 60,
            }
            for i in range(2)
            for m in range(high + 1)
        )
    parts = ld.partitions(pd.DataFrame(rows), min_maps=2)
    assert [set(p.game_id.str[0]) for p in parts] == [{"a"}, {"b"}, {"c"}]
    assert [p.seconds.max() for p in parts] == [1260] * 3


def test_unmatched_shift_maps_drop_before_all_comparisons():
    frame = pd.DataFrame({"game_id": ["a", "a", "b"], "time": [0.0, 1.0, 2.0]})
    got = ld.attach(frame, pd.Series({"a": 0.4}))
    assert got.game_id.tolist() == ["a", "a"]
    assert got.draft_time.tolist() == [0.0, 0.4]


def test_draft_weights_never_fit_live_training_or_test_targets():
    rng = np.random.default_rng(7)
    games = pd.DataFrame(
        [
            dict(
                gameid=f"{year}-{i}",
                year=year,
                won=i % 2,
                forge_logit=rng.normal(),
                **{f: rng.normal() for f in ld.dw.FEATURES},
            )
            for year in range(2019, 2027)
            for i in range(20)
        ]
    )
    original = ld.draft_shifts(games)
    changed = games.copy()
    changed.loc[changed.year >= 2025, "won"] = (
        1 - changed.loc[changed.year >= 2025, "won"]
    )
    assert np.allclose(original, ld.draft_shifts(changed))
    # Live training weights freeze through 2021, despite available 2022-24 targets.
    changed = games.copy()
    changed.loc[changed.year.between(2022, 2024), "won"] = (
        1 - changed.loc[changed.year.between(2022, 2024), "won"]
    )
    later = ld.draft_shifts(changed)
    ids = games.loc[games.year.between(2022, 2024), "gameid"]
    assert np.allclose(original.loc[ids], later.loc[ids])
