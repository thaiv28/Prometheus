from enum import Enum
from rich.table import Table
from rich.console import Console
from prometheus.types import League

from prometheus import types


def match_major_leagues(league_list, year=None):
    if year is None:
        major_leagues = types.ALL_MAJOR_LEAGUES
    elif year < 2019:
        major_leagues = types.PRE_2019_MAJOR_LEAGUES
    elif year < 2025:
        major_leagues = types.PRE_2025_MAJOR_LEAGUES
    else:
        major_leagues = types.CURRENT_MAJOR_LEAGUES

    return major_leagues


def filter_leagues(league_list, year=None):
    filtered_leagues = league_list.copy()

    if League.MAJOR in league_list:
        filtered_leagues.remove(League.MAJOR)
        filtered_leagues += match_major_leagues(league_list, year)

    return filtered_leagues


def print_rankings_table(df, metric, league, year, n, console=None):
    df = df.head(n)
    title = f"{metric.upper()} Rankings"
    filter_strs = []
    if league:
        filter_strs.append(", ".join(l.value for l in league))
    if year:
        filter_strs.append(str(year))
    title += " (" + " | ".join(filter_strs) + ")"
    table = Table(title)
    table.add_row(df.to_string(float_format=lambda _: "{:.2f}".format(_)))
    if console is None:
        console = Console()
    console.print(table)
