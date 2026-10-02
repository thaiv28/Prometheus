import pytest

from prometheus.utils import parse_years


def test_parse_years_expands_ranges_and_merges():
    assert parse_years(["2021-2023", "2025", "2022"]) == [2021, 2022, 2023, 2025]


def test_parse_years_none_when_empty():
    assert parse_years(None) is None
    assert parse_years([]) is None


@pytest.mark.parametrize("bad", ["20x1", "2023-2021", "2021-"])
def test_parse_years_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        parse_years([bad])
