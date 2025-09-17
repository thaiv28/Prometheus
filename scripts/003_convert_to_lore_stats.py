import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

def compute_lore_stats(df):
    # Derived stats for match_lore_stats
    gamelength_mins = df['gamelength'] / 60
    df['gpm'] = df['totalgold'] / gamelength_mins
    df['turrets_per_10'] = df['towers'] / (gamelength_mins / 10)
    df['baron_per_10'] = df['barons'] / (gamelength_mins / 10)
    df['dragon_per_10'] = df['dragons'] / (gamelength_mins / 10)
    return df[['gameid', 'teamid', 'gpm', 'golddiffat15', 'turrets_per_10', 'baron_per_10', 'dragon_per_10']]

def main():
    project_dir = Path(__file__).resolve().parent.parent
    db_path = project_dir / 'db' / 'prometheus.db'
    engine = create_engine(f'sqlite:///{db_path}')

    # Read raw stats
    df_raw = pd.read_sql('SELECT * FROM match_raw_stats', engine)
    df_lore = compute_lore_stats(df_raw)

    # Write lore stats to DB
    df_lore.to_sql('match_lore_stats', engine, if_exists='replace', index=False)

if __name__ == "__main__":
    main()
