import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

from prometheus.types import MATCH_RAW_FEATURES, MATCHES_FEATURES, PLAYER_GAME_FEATURES, PLAYER_RAW_FEATURES


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
        df["playerid"].notna(), "name:" + df["playername"] + "|" + df["teamid"].astype(str)
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
        df["playerid"].notna(), "name:" + df["playername"] + "|" + df["teamid"].astype(str)
    )
    df = df.drop_duplicates(subset=["gameid", "teamid", "position"])
    # A handful of games list one player id twice (two roles, or both teams). The
    # first row keeps the id; the others become one-off players.
    repeat = df.duplicated(subset=["gameid", "playerid"])
    df.loc[repeat, "playerid"] = (
        "dup:" + df.loc[repeat, "gameid"].astype(str) + "|" + df.loc[repeat, "teamid"].astype(str)
        + "|" + df.loc[repeat, "position"]
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


def main():
    project_dir = Path(__file__).resolve().parent.parent
    db_path = project_dir / "db" / "prometheus.db"
    csv_dir = project_dir / "data" / "raw"
    engine = create_engine(f"sqlite:///{db_path}")

    # each file is one year's worth of data from Oracle's Elixir
    for file in csv_dir.iterdir():
        if file.suffix != ".csv":
            print("Skipping non-CSV file:", file.name)
            continue

        df = pd.read_csv(file)
        df_matches = preprocess_matches(df)
        matches = df_matches[MATCHES_FEATURES]
        match_stats = df_matches[["gameid", "teamid"] + MATCH_RAW_FEATURES]

        matches.to_sql("matches", engine, if_exists="append", index=False)
        match_stats.to_sql("match_stats", engine, if_exists="append", index=False)
        preprocess_match_players(df, matches).to_sql(
            "match_players", engine, if_exists="append", index=False
        )

        df_player_sql = preprocess_player_raw_stats(df)
        df_player_sql = df_player_sql.drop_duplicates(subset=["gameid", "playerid"])
        df_player_sql.to_sql("player_stats", engine, if_exists="append", index=False)


if __name__ == "__main__":
    main()
