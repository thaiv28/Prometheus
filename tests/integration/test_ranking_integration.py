import pytest
from unittest.mock import patch
from prometheus.ranking import get_glory_ranking


@patch("prometheus.matches._get_engine_and_tables")
def test_get_glory_ranking_integration(mock_get_engine_and_tables, inmemory_tables):
    mock_get_engine_and_tables.return_value = inmemory_tables

    df = get_glory_ranking(year=2022, features=["gpm", "dragon_per_10"])

    assert "teamname" in df.columns
    assert "score" in df.columns

    expected_order = ["B", "A", "D", "C"]
    actual_order = df["teamname"].tolist()
    assert (
        actual_order == expected_order
    ), f"Expected {expected_order}, got {actual_order}"
