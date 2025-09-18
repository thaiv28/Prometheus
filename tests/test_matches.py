import pytest
import pandas as pd
from unittest.mock import patch
from sqlalchemy import Table, MetaData, Column, String, Float

from prometheus.matches import get_team_averages_frame


@patch("prometheus.matches._retrieve_dataframe_from_table")
def test_get_team_averages_frame_team_averages(mock_retrieve):
    # Create a mock DataFrame to be returned by _retrieve_dataframe_from_table
    data = {
        "gameid": ["g1", "g2", "g3", "g4"],
        "teamid": ["t1", "t1", "t2", "t2"],
        "teamname": ["A", "A", "B", "B"],
        "feature1": [1.0, 2.0, 3.0, 4.0],
        "feature2": [10.0, 20.0, 30.0, 40.0],
    }
    df = pd.DataFrame(data)
    # stat_table.columns.keys() must match df columns
    metadata = MetaData()
    stat_table = Table(
        "match_glory_stats",
        metadata,
        Column("gameid", String, primary_key=True),
        Column("teamid", String),
        Column("teamname", String),
        Column("feature1", Float),
        Column("feature2", Float),
    )
    mock_retrieve.return_value = (df, stat_table)
    result = get_team_averages_frame("match_glory_stats")
    # Should average feature1 and feature2 by teamname
    assert set(result["teamname"]) == {"A", "B"}
    assert result.loc[result["teamname"] == "A", "feature1"].iloc[0] == pytest.approx(
        1.5
    )
    assert result.loc[result["teamname"] == "B", "feature2"].iloc[0] == pytest.approx(
        35.0
    )
