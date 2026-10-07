"""Interaction direction, support thresholds and chronological isolation."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import evaluate_champion_interactions as experiment
import evaluate_champions as champions


def games(n=80):
    rng = np.random.default_rng(9)
    rows = []
    for i in range(n):
        row = {"total_gold": 300 if i % 2 else -300, "won": i % 2}
        for role in champions.snapshots.ROLES:
            row[f"blue_{role}_champion"] = f"{role}_A"
            row[f"red_{role}_champion"] = f"{role}_B"
            for stat in champions.snapshots.STATS:
                row[f"{role}_{stat}"] = rng.normal()
        rows.append(row)
    return pd.DataFrame(rows)


def test_interactions_reverse_with_teams_and_gaps_and_vanish_at_even_state():
    original = games()
    encoder = champions.InteractionEncoder(lane_stats=True).fit(original)
    swapped = original.copy()
    for role in champions.snapshots.ROLES:
        swapped[f"blue_{role}_champion"] = original[f"red_{role}_champion"]
        swapped[f"red_{role}_champion"] = original[f"blue_{role}_champion"]
    for col in encoder.scales:
        swapped[col] = -original[col]
    np.testing.assert_array_equal(
        encoder.transform(original).toarray(), -encoder.transform(swapped).toarray()
    )
    tied = original.copy()
    tied[list(encoder.scales)] = 0
    rows = encoder.rows(tied)
    assert all(not any(key.startswith("interaction/") for key in row) for row in rows)
    assert any(key.startswith("interaction/") for key in encoder.allowed)
    assert not any(key.startswith("matchup/") for key in encoder.allowed)


def test_ahead_and_behind_are_separate_and_unknown_or_rare_slopes_fall_back():
    train = games()
    encoder = champions.InteractionEncoder().fit(train)
    positive, negative = encoder.rows(train.iloc[[1, 0]])
    assert positive["interaction/top/top_A/total_gold/ahead"] > 0
    assert positive["interaction/top/top_B/total_gold/behind"] > 0
    assert negative["interaction/top/top_A/total_gold/behind"] < 0
    assert negative["interaction/top/top_B/total_gold/ahead"] < 0
    sparse = champions.InteractionEncoder().fit(games(30))  # 15 observations per branch
    assert not any(key.startswith("interaction/") for key in sparse.allowed)
    assert sparse.transform(games(1)).nnz > 0  # Main effects still available.
    unknown = train.copy()
    unknown[champions.DRAFT_COLS] = "unseen"
    assert encoder.transform(unknown).nnz == 0
    assert encoder.scales == {"total_gold": 300.0}


def test_future_state_and_drafts_do_not_change_fitted_scales_or_parameters():
    train, calibration, test = games(100), games(60), games(60)
    columns = champions.snapshots.FEATURES["aura_features"]
    _, _, first = champions.fit_predict(
        train, calibration, test, columns, "state_interactions"
    )
    changed = test.copy()
    changed[champions.DRAFT_COLS] = "future"
    changed[columns] *= 1000
    changed["total_gold"] *= 1000
    changed["won"] = 1 - changed.won
    _, _, second = champions.fit_predict(
        train, calibration, changed, columns, "state_interactions"
    )
    assert first == second
    assert not any("future" in name for name in first["draft_columns"])


def test_interaction_protocol_excludes_exact_matchups_and_uses_champion_control():
    assert "matchups" not in experiment.VARIANTS
    assert champions.control_for("gold_interactions") == "champions"
    assert champions.control_for("state_interactions") == "champions"
    assert champions.YEARS == (2023, 2024, 2025)
