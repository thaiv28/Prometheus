import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import elo_glicko as eg


def test_tuning_prefix_preserves_intervening_future_labelled_games():
    inputs = eg.ev.Inputs(
        games=pd.DataFrame({"year": [2020, 2022, 2021, 2022]}),
        rosters={},
        frame=pd.DataFrame(),
        form_games=pd.DataFrame(),
        db_pre_match=pd.Series(dtype=float),
        db_domestic=(),
    )
    prefix = eg.tuning_inputs(inputs, [2020, 2021])
    assert prefix.games["year"].tolist() == [2020, 2022, 2021]
    assert len(inputs.games) == 4


def test_roster_change_excludes_first_appearance_order_and_unknown_lineups():
    games = pd.DataFrame(
        {"gameid": list(range(6)), "teamid": ["a"] * 6, "opponent_teamid": ["b"] * 6}
    )
    rosters = {
        (0, "a"): (1, 2, 3, 4, 5),
        (1, "a"): (5, 4, 3, 2, 1),
        # Game 2 has no data: production retains game 1's lineup.
        (3, "a"): (1, 2, 3, 4, 6),
        (4, "a"): (1, 2),
        (5, "a"): (1, 2, 3, 4, 5),
        (1, "b"): (10, 11, 12, 13, 14),
        (2, "b"): (10, 11, 12, 13, 15),
    }
    assert eg.roster_changes(SimpleNamespace(games=games, rosters=rosters)) == {2, 3}


def test_comparison_checks_identity_before_pairing_and_slices_existing_losses():
    ids = np.array(["a", "b", "c"])
    base = {"slice": (ids, np.array([0.2, 0.4, 0.6]))}
    variant = {"slice": (ids, np.array([0.1, 0.4, 0.8]))}
    result = eg.comparison(base, variant, {"a", "c"})[0]
    assert result[1] == 2
    assert result[2] == pytest.approx(0.4)
    assert result[3] == pytest.approx(0.05)
    with pytest.raises(AssertionError):
        eg.comparison(base, {"slice": (ids[::-1], variant["slice"][1])})
