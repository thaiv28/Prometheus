from unittest.mock import patch

from prometheus.matches import get_matches_frame 


@patch("prometheus.utils.get_engine")
def test_retrieve_dataframe_from_table_inmemory(
    mock_get_engine, inmemory_engine
):
    mock_get_engine.return_value = inmemory_engine

    filters = {"league": "LCK", "year": 2022}
    df = get_matches_frame("match_glory_stats", filters)

    assert not df.empty
    assert df["teamname"].iloc[0] == "A"
    assert df["gpm"].iloc[0] == 100
