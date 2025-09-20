import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

from prometheus.types import RAW_FEATURES


def preprocess_match_raw_stats(df):
    # include only team stats (not player stats)
    df = df[df["position"] == "team"]

    required_columns = [
        "gameid",
        "year",
        "split",
        "league",
        "teamid",
        "teamname",
        "side",
        "gamelength",
        "result",
    ]
    columns = required_columns + RAW_FEATURES
    df = df[columns]

    # fill missing raw features with mean of that feature. drop any that don't have required features
    df[RAW_FEATURES] = df[RAW_FEATURES].fillna(df[RAW_FEATURES].mean())
    df = df.dropna(axis="index", how="any")

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
        df_sql = preprocess_match_raw_stats(df)
        df_sql = df_sql.drop_duplicates(subset=["gameid", "teamid"])
        df_sql.to_sql("match_raw_stats", engine, if_exists="append", index=False)


if __name__ == "__main__":
    main()
