"""Champion encoding, rarity fallback and future-data isolation."""

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "evaluate_champions", ROOT / "scripts" / "evaluate_champions.py"
)
champions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(champions)


def games(n=30):
    rows = []
    for i in range(n):
        row = {"won": i % 2, "total_gold": (i % 2) * 500 - 250}
        for role in champions.snapshots.ROLES:
            row[f"blue_{role}_champion"] = f"{role}_A"
            row[f"red_{role}_champion"] = f"{role}_B"
        rows.append(row)
    return pd.DataFrame(rows)


def test_swapping_drafts_negates_features_and_mirrors_cancel():
    original = games()
    swapped = original.copy()
    for role in champions.snapshots.ROLES:
        swapped[f"blue_{role}_champion"] = original[f"red_{role}_champion"]
        swapped[f"red_{role}_champion"] = original[f"blue_{role}_champion"]
    encoder = champions.DraftEncoder(matchups=True).fit(original)
    np.testing.assert_array_equal(
        encoder.transform(original).toarray(), -encoder.transform(swapped).toarray()
    )
    mirrored = original.copy()
    for role in champions.snapshots.ROLES:
        mirrored[f"red_{role}_champion"] = mirrored[f"blue_{role}_champion"]
    assert encoder.transform(mirrored).nnz == 0


def test_rare_matchup_falls_back_to_main_effects_and_unknowns_do_not_expand_vocabulary():
    train = games(15)  # Main effects reach 10; matchups do not reach 20.
    encoder = champions.DraftEncoder(matchups=True).fit(train)
    assert any(key.startswith("champion/") for key in encoder.allowed)
    assert not any(key.startswith("matchup/") for key in encoder.allowed)
    assert encoder.transform(train).nnz > 0
    vocabulary = encoder.vectorizer.get_feature_names_out().tolist()
    unknown = train.copy()
    unknown[champions.DRAFT_COLS] = "unseen"
    assert encoder.transform(unknown).nnz == 0
    assert encoder.vectorizer.get_feature_names_out().tolist() == vocabulary
    sparse_train = games(9)
    assert champions.DraftEncoder(matchups=True).fit(sparse_train).transform(
        sparse_train
    ).shape == (9, 0)


def test_future_champions_outcomes_and_numeric_values_do_not_change_parameters():
    train, calibration, test = games(60), games(30), games(30)
    _, _, first = champions.fit_predict(
        train, calibration, test, ["total_gold"], "matchups"
    )
    changed = test.copy()
    changed[champions.DRAFT_COLS] = "new_champion"
    changed["won"] = 1 - changed.won
    changed["total_gold"] *= 100
    _, _, second = champions.fit_predict(
        train, calibration, changed, ["total_gold"], "matchups"
    )
    assert first == second
    assert not any("new_champion" in col for col in first["draft_columns"])


def test_2026_cannot_enter_experiment_or_coverage():
    # Too few earlier games means there is nothing to score, even though 2026
    # alone has enough examples. No accidental fallback to the viewed holdout.
    frame = games(150)
    frame["year"] = 2026
    frame["valid_roster"] = True
    frame["league"] = "LCK"
    frame["gamelength"] = 1800
    for col in champions.snapshots.FEATURES["aura_features"]:
        frame[col] = 0
    import pytest

    with pytest.raises(ValueError, match="Insufficient"):
        champions.evaluate({10: frame})
