"""Carve the e2e fixture's Oracle's Elixir sample from the full CSVs in data/raw.

    uv run python tests/fixtures/make_oe_sample.py

Writes tests/fixtures/oe_sample/<file year>_sample.csv: the games of `YEARS`
(by Oracle's Elixir's year column; a file can hold games of the next year, such as
the 2016 file's LCS 2017 promotion games), every `STEP`-th game (by date) of each
major league and Worlds, plus a few named teams' games the e2e tests rely on. To keep the files small, only the
columns scripts/002_add_matches.py reads are kept, and values it never reads are
blanked: player stats on team rows, team-only stats on player rows, and the 20-
and 25-minute snapshots (allowed to be missing at ingest).
"""

from pathlib import Path

import pandas as pd

from prometheus.types import (
    MATCH_RAW_FEATURES,
    MATCHES_FEATURES,
    PLAYER_GAME_FEATURES,
    PLAYER_RAW_FEATURES,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent / "oe_sample"

YEARS = [2017, 2022]
FILES = [2016, 2017, 2022]  # the files holding YEARS' games
LEAGUES = ["LCK", "LPL", "EU LCS", "NA LCS", "LEC", "LCS", "WLDs", "Worlds"]
STEP = 24  # every 24th game of each league-year
KEEP_TEAMS = [
    "Cloud9 Challenger"
]  # under five games in LCS 2017 (minimum_matches test)

PLAYER_COLUMNS = ["position", "playerid", "playername", "champion", "earned gpm"]
COLUMNS = list(
    dict.fromkeys(
        MATCHES_FEATURES
        + PLAYER_COLUMNS
        + MATCH_RAW_FEATURES
        + PLAYER_RAW_FEATURES
        + [c for c in PLAYER_GAME_FEATURES if c != "earned_gpm"]
    )
)


def sample_file(file_year):
    df = pd.read_csv(
        RAW / f"{file_year}_LoL_esports_match_data_from_OraclesElixir.csv",
        low_memory=False,
    )
    df = df[df["league"].isin(LEAGUES) & df["year"].isin(YEARS)]
    games = df.drop_duplicates("gameid")[["gameid", "league", "date"]].sort_values(
        ["date", "gameid"]
    )
    picked = set(games.groupby("league").nth(slice(None, None, STEP))["gameid"])
    picked |= set(df.loc[df["teamname"].isin(KEEP_TEAMS), "gameid"])
    out = df[df["gameid"].isin(picked)][COLUMNS].copy()
    team = out["position"] == "team"
    player_only = PLAYER_RAW_FEATURES + [
        c for c in PLAYER_GAME_FEATURES if c != "earned_gpm"
    ]
    player_only += PLAYER_COLUMNS[1:]
    out.loc[team, [c for c in player_only if c != "kills"]] = None
    out.loc[~team, [c for c in MATCH_RAW_FEATURES if c != "kills"]] = None
    late = [c for c in PLAYER_RAW_FEATURES if c.endswith(("at20", "at25"))]
    out[late] = None
    for col in out.select_dtypes("float").columns:
        values = out[col].round(4)
        whole = values.dropna().mod(1).eq(0).all()
        out[col] = values.astype("Int64") if whole else values
    return out


def main():
    OUT.mkdir(exist_ok=True)
    for file_year in FILES:
        out = sample_file(file_year)
        path = OUT / f"{file_year}_sample.csv"
        out.to_csv(path, index=False)
        print(
            f"{path.name}: {out['gameid'].nunique()} games, {path.stat().st_size // 1024} KB"
        )


if __name__ == "__main__":
    main()
