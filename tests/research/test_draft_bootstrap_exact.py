import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "dw_fast", ROOT / "scripts/research/draft_walkforward.py"
)
dw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dw)


def test_aggregated_bootstrap_matches_original_draws_with_unequal_series(monkeypatch):
    monkeypatch.setattr(dw, "N_RESAMPLES", 100)
    f = pd.DataFrame(
        {
            "series": ["a", "b", "a", "c", "b", "b", "d"],
            "won": [1, 0, 0, 1, 1, 0, 1],
            "a": [0.7, 0.4, 0.6, 0.8, 0.5, 0.2, 0.6],
            "b": [0.6, 0.3, 0.4, 0.7, 0.4, 0.4, 0.5],
        }
    )
    la = dw.game_losses(f.a, f.won)["log_loss"].to_numpy()
    lb = dw.game_losses(f.b, f.won)["log_loss"].to_numpy()
    codes = pd.factorize(f.series)[0]
    groups = [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]
    draws = [(la - lb)[i].mean() for i in dw.resamples(groups, 100)]
    expected = (
        la.mean(),
        lb.mean(),
        (la - lb).mean(),
        *np.percentile(draws, [2.5, 97.5]),
    )
    assert np.allclose(dw.paired(f, "a", "b"), expected, atol=1e-14, rtol=0)
