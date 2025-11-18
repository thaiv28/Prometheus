import pytest
import pandas as pd
from unittest.mock import patch
from sqlalchemy import Table, MetaData, Column, String, Float

from prometheus.matches import get_team_averages_frame


@patch("prometheus.matches.get_matches_frame")
def test_get_team_averages_frame_team_averages(mock_retrieve):
    # Create a mock DataFrame to be returned by _retrieve_dataframe_from_table
    data = {
        "gameid": [
            "g1",
            "g1",
            "g2",
            "g2",
            "g3",
            "g3",
            "g4",
            "g4",
            "g5",
            "g5",
            "g6",
            "g6",
            "g7",
            "g7",
            "g8",
            "g8",
        ],
        "teamid": [
            "t1",
            "t2",
            "t1",
            "t2",
            "t1",
            "t2",
            "t1",
            "t2",
            "t1",
            "t2",
            "t1",
            "t2",
            "t1",
            "t2",
            "t1",
            "t2",
        ],
        "teamname": [
            "A",
            "B",
            "A",
            "B",
            "A",
            "B",
            "A",
            "B",
            "A",
            "B",
            "A",
            "B",
            "A",
            "B",
            "A",
            "B",
        ],
        "feature1": [
            1.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            5.0,
            2.5,
            3.5,
            4.5,
            5.5,
            3.0,
            4.0,
            5.0,
            6.0,
        ],
        "feature2": [
            10.0,
            20.0,
            30.0,
            40.0,
            15.0,
            25.0,
            35.0,
            45.0,
            12.0,
            22.0,
            32.0,
            42.0,
            17.0,
            27.0,
            37.0,
            47.0,
        ],
        "year": [
            2022,
            2022,
            2022,
            2022,
            2023,
            2023,
            2023,
            2023,
            2022,
            2022,
            2022,
            2022,
            2023,
            2023,
            2023,
            2023,
        ],
        "league": [
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
            "LCS",
        ],
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
    mock_retrieve.return_value = df 
    result = get_team_averages_frame("match_glory_stats")
    # Should average feature1 and feature2 by teamname and year
    # For 2022: A: (1.0+3.0+2.5+1.0)/4=1.625, (10.0+30.0+12.0+10.0)/4=15.5
    #           B: (2.0+4.0+3.5+2.0)/4=2.875, (20.0+40.0+22.0+20.0)/4=25.5
    # For 2023: A: (2.0+4.0+3.0+5.0)/4=3.5, (15.0+35.0+17.0+37.0)/4=26.0
    #           B: (3.0+5.0+4.0+6.0)/4=4.5, (25.0+45.0+27.0+47.0)/4=36.0
    expected = {
        ("A", 2022): {"feature1": 2.75, "feature2": 21.0},
        ("B", 2022): {"feature1": 3.75, "feature2": 31.0},
        ("A", 2023): {"feature1": 3.5, "feature2": 26.0},
        ("B", 2023): {"feature1": 4.5, "feature2": 36.0},
    }
    for (team, year), vals in expected.items():
        row = result[(result["teamname"] == team) & (result["year"] == year)]
        assert row["feature1"].iloc[0] == pytest.approx(vals["feature1"])
        assert row["feature2"].iloc[0] == pytest.approx(vals["feature2"])
