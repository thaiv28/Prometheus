from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from prometheus.types import (
    MATCH_RAW_FEATURES,
    MATCHES_FEATURES,
    PLAYER_GAME_FEATURES,
    PLAYER_RAW_FEATURES,
)
from prometheus.utils import insert_rows


def fill_team_ids(df):
    """Give rows with no teamid (OE leaves it blank for some smaller teams, about
    500 team rows in 2026) the id the same team name has elsewhere in the file,
    or "name:<teamname>". Without one, the game kept only its other team and
    dropped out of Elo and FORGE."""
    known = df[df["teamid"].notna() & df["teamname"].notna()]
    ids = known.groupby("teamname")["teamid"].agg(
        lambda s: s.iloc[0] if s.nunique() == 1 else None
    )
    fallback = df["teamname"].map(ids.dropna()).fillna("name:" + df["teamname"])
    df = df.copy()
    df["teamid"] = df["teamid"].fillna(fallback)
    return df


def preprocess_player_raw_stats(df):
    # include only player stats (not team stats)
    df = df[df["position"] != "team"]

    required_columns = [
        "gameid",
        "playerid",
        "playername",
        "teamid",
        "position",
        "champion",
    ]
    df = df.rename(columns={"earned gpm": "earned_gpm"})
    columns = required_columns + PLAYER_RAW_FEATURES + PLAYER_GAME_FEATURES
    df = df[columns].copy()
    # Same fallback id as match_players, so short of a snapshot no starter is lost.
    df["playername"] = df["playername"].fillna("unknown").astype(str)
    df["playerid"] = df["playerid"].where(
        df["playerid"].notna(),
        "name:" + df["playername"] + "|" + df["teamid"].astype(str),
    )
    # Games without snapshots ("partial" data) are dropped. The 20- and 25-minute
    # snapshots are missing when the game ended first; keep those games, or the
    # table loses most stomps.
    early = [c for c in PLAYER_RAW_FEATURES if not c.endswith(("at20", "at25"))]
    df = df.dropna(subset=required_columns + early)

    return df


def preprocess_match_players(df, matches):
    """Each team's starters in every kept game, with a fallback id when OE has none."""
    df = df[df["position"] != "team"]
    df = df[["gameid", "teamid", "position", "playerid", "playername"]].copy()
    df["playername"] = df["playername"].fillna("unknown").astype(str)
    df["playerid"] = df["playerid"].where(
        df["playerid"].notna(),
        "name:" + df["playername"] + "|" + df["teamid"].astype(str),
    )
    df = df.drop_duplicates(subset=["gameid", "teamid", "position"])
    # A handful of games list one player id twice (two roles, or both teams). The
    # first row keeps the id; the others become one-off players.
    repeat = df.duplicated(subset=["gameid", "playerid"])
    df.loc[repeat, "playerid"] = (
        "dup:"
        + df.loc[repeat, "gameid"].astype(str)
        + "|"
        + df.loc[repeat, "teamid"].astype(str)
        + "|"
        + df.loc[repeat, "position"]
    )
    return df.merge(matches[["gameid", "teamid"]], on=["gameid", "teamid"])


def preprocess_matches(df):
    # include only team stats (not player stats)
    df = df[df["position"] == "team"]

    columns = MATCHES_FEATURES + MATCH_RAW_FEATURES
    df = df[columns].drop_duplicates(subset=["gameid", "teamid"])

    # fill missing raw features with mean of that feature. for years without means (e.g. atakhans pre 2025), fill with 0
    df[MATCH_RAW_FEATURES] = df[MATCH_RAW_FEATURES].fillna(
        df[MATCH_RAW_FEATURES].mean()
    )
    df[MATCH_RAW_FEATURES] = df[MATCH_RAW_FEATURES].fillna(0)
    # Oracle's Elixir leaves split empty for international events (Worlds, MSI, ...)
    # and some regional leagues. Keep those games: internationals are the only
    # games that connect regions for Elo.
    df["split"] = df["split"].fillna("")
    # OE labels promotion and qualifier games with the season they qualify for
    # (PRM, LFL, CBLOL games in Aug-Sep 2026 carry 2027), so a team's season label
    # would jump back and forth. The calendar year of the game is its season, as in
    # Elo's home leagues.
    df["year"] = pd.to_datetime(df["date"]).dt.year

    df = df.dropna(how="any")

    # Remap league names to standard values
    league_mapping = {
        "LCS": ["LCS", "NA LCS", "LTA N"],
        "LEC": ["LEC", "EU LCS"],
        "Worlds": ["WLDs"],
    }
    reverse_league_mapping = {v: k for k, vals in league_mapping.items() for v in vals}
    df["league"] = df["league"].map(reverse_league_mapping).fillna(df["league"])

    return df


# The CSV columns this script reads (of about 165); reading only these halves the
# parse time.
COLUMNS = set(
    MATCHES_FEATURES
    + MATCH_RAW_FEATURES
    + PLAYER_RAW_FEATURES
    + PLAYER_GAME_FEATURES
    + ["position", "playerid", "playername", "champion", "earned gpm"]
)


def main():
    project_dir = Path(__file__).resolve().parent.parent
    db_path = project_dir / "db" / "prometheus.db"
    csv_dir = project_dir / "data" / "raw"
    engine = create_engine(f"sqlite:///{db_path}")

    # each file is one year's worth of data from Oracle's Elixir
    for file in sorted(csv_dir.iterdir()):
        if file.suffix != ".csv":
            print("Skipping non-CSV file:", file.name)
            continue

        df = fill_team_ids(pd.read_csv(file, usecols=lambda c: c in COLUMNS))
        df_matches = preprocess_matches(df)
        matches = df_matches[MATCHES_FEATURES]
        match_stats = df_matches[["gameid", "teamid"] + MATCH_RAW_FEATURES]

        df_player_sql = preprocess_player_raw_stats(df)
        df_player_sql = df_player_sql.drop_duplicates(subset=["gameid", "playerid"])
        with engine.begin() as conn:
            insert_rows(conn, "matches", matches)
            insert_rows(conn, "match_stats", match_stats)
            insert_rows(conn, "match_players", preprocess_match_players(df, matches))
            insert_rows(conn, "player_stats", df_player_sql)


if __name__ == "__main__":
    main()
