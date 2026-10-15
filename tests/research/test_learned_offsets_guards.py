import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import learned_offsets_guards as guards


def test_roster_slices_partition_losses_by_known_moves_and_prior_appearances():
    players = pd.DataFrame(
        {
            "gameid": [f"g{i}" for i in range(50)],
            "playerid": ["p"] * 50,
            "home": ["A"] * 35 + ["B"] * 15,
        }
    )
    key = ("Within other leagues", "Elo")
    ids = np.array(["g0", "g30", "g35"])
    losses = {
        "baseline": {key: (ids, np.ones(3))},
        "recalibrated_fixed": {key: (ids, np.array([1.1, 1.2, 1.3]))},
    }
    with mock.patch.object(guards.pd, "read_sql", return_value=players):
        report = "\n".join(guards.transfer_attribution(losses))
    assert "| Recent home-league move | 1 | +0.300000 | +0.300 |" in report
    assert "| Rookie, no recent move | 1 | +0.100000 | +0.100 |" in report
    assert "| Neither | 1 | +0.200000 | +0.200 |" in report
