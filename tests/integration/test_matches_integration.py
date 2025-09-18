from unittest.mock import patch

from prometheus.matches import _retrieve_dataframe_from_table


@patch("prometheus.matches._get_engine_and_tables")
def test_retrieve_dataframe_from_table_inmemory(
    mock_get_engine_and_tables, inmemory_tables
):
    engine, stat_table, match_raw_stats = inmemory_tables
    mock_get_engine_and_tables.return_value = (engine, stat_table, match_raw_stats)

    filters = {"league": "LCK", "year": 2022}
    df, _ = _retrieve_dataframe_from_table("match_glory_stats", filters)

    assert not df.empty
    assert df["teamname"].iloc[0] == "A"
    assert df["gpm"].iloc[0] == 1800
