from unittest.mock import patch

import pytest
from prometheus.ranking import get_glory_ranking


@patch("prometheus.utils.get_engine")
def test_get_glory_ranking_multiyear_integration(
    mock_get_engine, inmemory_engine
):
    mock_get_engine.return_value = inmemory_engine 

    years = [2022, 2023]
    df = get_glory_ranking(year=years, features=["gpm", "dragon_per_10"])

    # There should be one entry per (teamname, year)
    expected_combinations = set(
        [
            ("A", 2022),
            ("B", 2022),
            ("C", 2022),
            ("D", 2022),
            ("A", 2023),
            ("B", 2023),
            ("C", 2023),
            ("D", 2023),
        ]
    )
    actual_combinations = set(zip(df["teamname"], df["year"]))
    assert actual_combinations == expected_combinations

    # TODO: find a way to test that a higher performing team in 2023
    # has a higher score than a team in 2022, even if the overall stats are lower
    # in 2023 due to meta changes

    # Expected order for each year: B, A, D, C
    expected_order = [
        ("B", 2022),
        ("B", 2023),
        ("A", 2022),
        ("A", 2023),
        ("D", 2022),
        ("D", 2023),
        ("C", 2022),
        ("C", 2023),
    ]
    actual_order = list(zip(df["teamname"], df["year"]))
    assert (
        actual_order == expected_order
    ), f"Expected {expected_order}, got {actual_order}"


@patch("prometheus.utils.get_engine")
def test_get_glory_ranking_integration(mock_get_engine, inmemory_engine):
    mock_get_engine.return_value = inmemory_engine

    df = get_glory_ranking(year=2022, features=["gpm", "dragon_per_10"])

    assert "teamname" in df.columns
    assert "score" in df.columns

    expected_order = ["B", "A", "D", "C"]
    actual_order = df["teamname"].tolist()
    assert (
        actual_order == expected_order
    ), f"Expected {expected_order}, got {actual_order}"

    for score in df["score"]:
        assert 0 <= score <= 300, f"Score {score} out of expected range 0-300"


@patch("prometheus.utils.get_engine")
def test_get_glory_single_league_integration(
    mock_get_engine, inmemory_engine
):
    mock_get_engine.return_value = inmemory_engine

    df = get_glory_ranking(league="LPL", year=2022, features=["gpm", "dragon_per_10"])

    assert len(df) == 1
    # even though we just have one league, score should not be maxed out. the
    # model should still weight features based on ALL leagues
    assert df.iloc[0]["score"] != 100


@patch("prometheus.utils.get_engine")
def test_get_glory_minimum_matches_integration(
    mock_get_engine, inmemory_engine
):
    mock_get_engine.return_value = inmemory_engine

    with pytest.raises(ValueError):
        five_min_df = get_glory_ranking(
            league="LPL",
            year=2022,
            features=["gpm", "dragon_per_10"],
            minimum_matches=5,
            z_scores=True,
        )

    no_min_df = get_glory_ranking(
        league="LPL", year=2022, features=["gpm", "dragon_per_10"], minimum_matches=0
    )
    assert len(no_min_df) > 0


@patch("prometheus.utils.get_engine")
def test_get_glory_ranking_z_score_ranges(mock_get_engine, inmemory_engine):
    mock_get_engine.return_value = inmemory_engine

    df = get_glory_ranking(
        year=[2022, 2023], features=["gpm", "dragon_per_10"], z_scores=True
    )

    assert "era_score" in df.columns
    assert "league_score" in df.columns

    for score in df["era_score"]:
        # z-scores can be negative, but should generally be within a reasonable range
        assert -3 <= score <= 3, f"Era Score {score} out of expected range -3 to 3"

    for score in df["league_score"]:
        # z-scores can be negative, but should generally be within a reasonable range
        assert -3 <= score <= 3, f"League Score {score} out of expected range -3 to 3"


@patch("prometheus.utils.get_engine")
def test_get_glory_ranking_sort_by_league_score(
    mock_get_engine, inmemory_engine
):
    mock_get_engine.return_value = inmemory_engine

    df = get_glory_ranking(year=2022, features=["gpm", "dragon_per_10"], z_scores=True)

    # Sort by league_score descending
    df_sorted = df.sort_values("league_score", ascending=False)

    # Check that the first few entries are in descending order by league_score
    for i in range(len(df_sorted) - 1):
        assert (
            df_sorted.iloc[i]["league_score"] >= df_sorted.iloc[i + 1]["league_score"]
        ), f"League scores not in descending order: {df_sorted.iloc[i]['league_score']} < {df_sorted.iloc[i + 1]['league_score']}"


@patch("prometheus.utils.get_engine")
def test_get_glory_ranking_sort_by_era_score(
    mock_get_engine, inmemory_engine
):
    mock_get_engine.return_value = inmemory_engine

    df = get_glory_ranking(year=2022, features=["gpm", "dragon_per_10"], z_scores=True)

    # Sort by era_score descending
    df_sorted = df.sort_values("era_score", ascending=False)

    # Check that the first few entries are in descending order by era_score
    for i in range(len(df_sorted) - 1):
        assert (
            df_sorted.iloc[i]["era_score"] >= df_sorted.iloc[i + 1]["era_score"]
        ), f"Era scores not in descending order: {df_sorted.iloc[i]['era_score']} < {df_sorted.iloc[i + 1]['era_score']}"
