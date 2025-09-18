import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path


def preprocess_match_raw_stats(df):
    # include only team stats (not player stats)
    df = df[df["position"] == "team"]
    df = df[df["datacompleteness"] == "complete"]

    columns = [
        "gameid",
        "year",
        "split",
        "league",
        "teamid",
        "teamname",
        "side",
        "gamelength",
        "result",
        "totalgold",
        "golddiffat15",
        "towers",
        "barons",
        "dragons",
    ]
    df = df[columns]
    df = df.dropna(axis="index", how="any")

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
