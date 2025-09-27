import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

from prometheus.types import GLORY_FEATURES


def compute_glory_stats(df):
    # Derived stats for match_glory_stats
    gamelength_mins = df["gamelength"] / 60
    df["gpm"] = df["totalgold"] / gamelength_mins
    df["turrets_per_10"] = df["towers"] / (gamelength_mins / 10)
    df["baron_per_10"] = df["barons"] / (gamelength_mins / 10)
    df["dragon_per_10"] = df["dragons"] / (gamelength_mins / 10)
    df["kills_per_10"] = df["kills"] / (gamelength_mins / 10)
    df["heralds_per_10"] = df["heralds"] / (gamelength_mins / 10)
    df["visionscore_per_10"] = df["visionscore"] / (gamelength_mins / 10)

    return df[
        [
            "gameid",
            "teamid",
        ]
        + GLORY_FEATURES
    ]


def main():
    project_dir = Path(__file__).resolve().parent.parent
    db_path = project_dir / "db" / "prometheus.db"
    engine = create_engine(f"sqlite:///{db_path}")

    # Read raw stats
    df_raw = pd.read_sql("SELECT * FROM match_raw_stats", engine)
    df_glory = compute_glory_stats(df_raw)

    # Write glory stats to DB
    df_glory.to_sql("match_glory_stats", engine, if_exists="append", index=False)


if __name__ == "__main__":
    main()
