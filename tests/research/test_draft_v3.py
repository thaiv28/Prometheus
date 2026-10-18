import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
spec = importlib.util.spec_from_file_location(
    "draft_v3", ROOT / "scripts/research/draft_v3.py"
)
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)


def specs(tmp_path):
    rows = pd.DataFrame(
        {
            "gameid": ["a", "b"],
            "date": pd.to_datetime(["2019-01-01", "2021-01-01"]),
            "year": [2019, 2021],
            "league": ["LCK", "LPL"],
            "blue": ["A", "A"],
            "red": ["B", "B"],
            "won": [1, 0],
            "series": ["s1", "s2"],
            "forge_logit": [0.1, 0.2],
            **{f: [0.1, 0.2] for f in v3.dw.FEATURES},
        }
    )
    out = []
    for name in sorted(v3.EXPECTED):
        path = tmp_path / f"{name}.pkl"
        rows.assign(**{f"{name}_x": [0.1, 0.2]}).to_pickle(path)
        out.append([name, str(path), f"{name}_x"])
    return out


def test_combination_preserves_full_training_cohort_and_all_declared_blocks(tmp_path):
    choices = specs(tmp_path)
    games, blocks, manifest = v3.merge_blocks(choices)
    assert games.year.tolist() == [2019, 2021]
    assert set(blocks) == v3.EXPECTED
    assert len(manifest) == 4
    with pytest.raises(ValueError, match="four declared blocks"):
        v3.merge_blocks(choices[:-1])


@pytest.mark.parametrize("mutation", ["target", "missing", "duplicate"])
def test_refuse_misaligned_targets_or_cohorts(tmp_path, mutation):
    choices = specs(tmp_path)
    path = Path(choices[-1][1])
    frame = pd.read_pickle(path)
    if mutation == "target":
        frame.loc[0, "won"] = 0
    elif mutation == "missing":
        frame = frame.iloc[1:]
    else:
        frame = pd.concat([frame, frame.iloc[:1]])
    frame.to_pickle(path)
    with pytest.raises(ValueError, match=r"mismatch|duplicate game"):
        v3.merge_blocks(choices)


def test_pooled_gain_cannot_override_a_significantly_worse_guarded_slice(monkeypatch):
    # Homogeneous per-slice losses make the guard deterministic; avoid 2,000 Monte Carlo draws in a unit test.
    monkeypatch.setattr(v3.dw, "N_RESAMPLES", 20)
    intl = next(iter(v3.dw.INTERNATIONAL_LEAGUES))
    rows = []
    for league in ["LCK", "LPL", "TEST", intl]:
        for i in range(20):
            rows.append(
                {
                    "league": league,
                    "year": 2021,
                    "series": f"{league}-{i}",
                    "won": 1,
                    "candidate": 0.6 if league != intl else 0.49,
                    "v2": 0.5,
                }
            )
    frame = pd.DataFrame(rows)
    qualifies, _ = v3.gate(frame)
    assert not qualifies
    qualifies, _ = v3.gate(frame.assign(candidate=0.6))
    assert qualifies
