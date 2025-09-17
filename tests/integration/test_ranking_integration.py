import pytest
from unittest.mock import patch
from prometheus.ranking import get_lore_ranking


@patch("prometheus.matches._get_engine_and_tables")
def test_get_lore_ranking_integration(mock_get_engine_and_tables, inmemory_tables):
    engine, stat_table, match_raw_stats = inmemory_tables
    mock_get_engine_and_tables.return_value = (engine, stat_table, match_raw_stats)

    df = get_lore_ranking(year=2022)
    assert "teamname" in df.columns
    assert "score" in df.columns
    # Expected order: B, A, D, C
    expected_order = ["B", "A", "D", "C"]
    actual_order = df["teamname"].tolist()
    assert (
        actual_order == expected_order
    ), f"Expected {expected_order}, got {actual_order}"
