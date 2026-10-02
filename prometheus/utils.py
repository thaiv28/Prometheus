from enum import Enum
from rich.table import Table
from rich.console import Console
from sqlalchemy import create_engine

from . import DB_PATH
from prometheus.types import League
from prometheus import types


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}")


def filter_leagues(league_list, years=None):
    filtered_leagues = set(league_list).copy()

    if League.MAJOR in league_list:
        filtered_leagues.update(types.ALL_MAJOR_LEAGUES)
        filtered_leagues.remove(League.MAJOR)

    return list(filtered_leagues)


def parse_years(values):
    """Expand CLI year values: "2024" and ranges like "2021-2023" (inclusive).

    Returns a sorted list of distinct years, or None when no years were given.
    """
    if not values:
        return None
    years = set()
    for value in values:
        start, sep, end = str(value).strip().partition("-")
        try:
            first = int(start)
            last = int(end) if sep else first
        except ValueError:
            raise ValueError(f"{value!r} is not a year or a range like 2021-2023")
        if last < first:
            raise ValueError(f"{value!r} ends before it starts")
        years.update(range(first, last + 1))
    return sorted(years)


def print_rankings_table(df, metric, league, year, n, console=None):
    df = df.head(n)
    title = f"{metric.upper()} Rankings"
    filter_strs = []
    if league:
        filter_strs.append(", ".join(l.value for l in league))
    if year:
        filter_strs.append(", ".join(str(y) for y in year))
    title += " (" + " | ".join(filter_strs) + ")"
    table = Table(title)
    table.add_row(df.to_string(float_format=lambda _: "{:.2f}".format(_)))
    if console is None:
        console = Console()
    console.print(table)
