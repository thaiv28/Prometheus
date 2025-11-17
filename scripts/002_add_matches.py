import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

from prometheus.types import MATCH_RAW_FEATURES, PLAYER_RAW_FEATURES, MATCHES_FEATURES


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
    columns = required_columns + PLAYER_RAW_FEATURES
    df = df[columns]
    df = df.dropna(how="any")

    return df

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

    df = df.dropna(how="any")

    # Remap league names to standard values
    league_mapping = {
        "LCS": ["LCS", "NA LCS", "LTA N"],
        "LEC": ["LEC", "EU LCS"],
        "Worlds": ["Wlds"],
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
        match_stats = df_matches[['gameid', 'teamid'] + MATCH_RAW_FEATURES]
        
        matches.to_sql("matches", engine, if_exists="append", index=False)
        match_stats.to_sql("match_stats", engine, if_exists="append", index=False)

        df_player_sql = preprocess_player_raw_stats(df)
        df_player_sql = df_player_sql.drop_duplicates(subset=["gameid", "playerid"])
        df_player_sql.to_sql(
            "player_stats", engine, if_exists="append", index=False
        )


if __name__ == "__main__":
    main()
