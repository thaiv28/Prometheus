import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import international_markets as im


def fixture(**changes):
    row = {
        "event_ticker": "x",
        "event": "MSI 2026",
        "ours1": "A",
        "ours2": "B",
        "start": dt.datetime(2026, 5, 3, 8, tzinfo=dt.UTC),
        "won1": True,
        "best_of": 3,
    }
    return pd.DataFrame([{**row, **changes}])


def games():
    return pd.DataFrame(
        [
            {
                "gameid": f"g{i}",
                "date": f"2026-05-03 0{i}:00:00",
                "league": "MSI",
                "team": "A",
                "opponent": "B",
                "result": int(i != 1),
                "day": dt.date(2026, 5, 3),
            }
            for i in range(3)
        ]
    )


def test_international_classification_excludes_regional_qualifier():
    a, rejected = im.attach_games(fixture(), games(), True)
    assert a.international.all() and rejected.empty
    b, _ = im.attach_games(fixture(event="MSI EMEA Qualifier 2026"), games(), True)
    assert b.qualifier.all() and not b.international.any()
    c, _ = im.attach_games(
        fixture(event="LPL Regional Finals 2026"), games().assign(league="Worlds"), True
    )
    assert not c.international.any()


def test_join_rejects_outcome_conflict_and_multiple_dates():
    f = fixture()
    f["won1"] = False
    matched, rejected = im.attach_games(f, games(), True)
    assert matched.empty and rejected.iloc[0].reason == "outcome mismatch"
    g = games()
    g.loc[2, "day"] = dt.date(2026, 5, 4)
    matched, rejected = im.attach_games(fixture(), g, True)
    assert matched.empty and rejected.iloc[0].reason == "multiple game dates"


def test_rebuild_discards_cached_probabilities_and_uses_each_cutoff():
    cutoffs = []

    def before(day):
        cutoffs.append(day)
        return pd.DataFrame(
            {
                "league": ["LCK", "LPL"],
                "elo": [1600.0, 1400.0],
                "forge": [1700.0, 1500.0],
                "has_form": [True, True],
            },
            index=["A", "B"],
        )

    f = fixture()
    f["p_game"], f["p_series"], f["major"] = 0.99, 0.99, False
    result = im.rebuild(f, before, True)
    assert cutoffs == [dt.date(2026, 5, 3), dt.date(2026, 5, 2)]
    expected = im.schedule.series_probability(
        float(im.expit(im.schedule.CROSS_REGION_ELO_WEIGHT * 200)),
        3,
        im.schedule.SERIES_RHO[True],
    )
    assert result.iloc[0].ours_close == expected
    assert result.iloc[0].elo_close == expected
    assert result.iloc[0].pair == "LCK / LPL"


def test_phase_counts_unpriced_prior_games_but_not_same_day():
    f = fixture().assign(game_date="2026-05-03", league="MSI")
    first = f.copy().assign(game_date="2026-05-01", ours1="C", ours2="D")
    all_f = pd.concat([first, f], ignore_index=True)
    g = games()
    g = pd.concat([g, g.assign(team="B", opponent="A")], ignore_index=True)
    g["day"] = dt.date(2026, 5, 2)
    assert im.phase_labels(all_f, g).iloc[1].phase == "later appearances"
    g["day"] = dt.date(2026, 5, 3)
    assert im.phase_labels(all_f, g).iloc[1].phase == "either team's first appearance"


def test_cluster_interval_keeps_events_together():
    # Two tournament shocks; row-level resampling would imply much more precision.
    values = np.repeat([-1.0, 1.0], 100)
    assert im.interval(values, np.repeat(["a", "b"], 100)) == (-1.0, 1.0)
    lo, hi = im.interval(values)
    assert lo > -0.3 and hi < 0.3
    assert all(np.isnan(im.interval(values, ["one"] * 200)))
