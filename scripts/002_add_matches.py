import pandas as pd
import sqlite3

from pathlib import Path

def insert_match_data(cursor, df):
    # Insert data into the matches table
    for index, row in df.iterrows():
        cursor.execute('''
            INSERT INTO matches (match_id, date, team1_id, team2_id, score1, score2)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (row['match_id'], row['date'], row['team1_id'], row['team2_id'], row['score1'], row['score2']))

def preprocess_match_raw_stats(df):
    # include only team stats (not player stats)
    df = df[df['position'] == 'team']
    df = df[df['datacompleteness'] == 'complete']
    
    columns = [
        'gameid', 'year', 'split', 'league', 'teamid', 'teamname', 'side', 'gamelength',
        'totalgold', 'opp_goldat10', 'towers', 'barons', 'dragons',
    ]
    df = df[columns]
    df = df.dropna(axis='index', how='any')
    
    return df

def main():
    project_dir = Path(__file__).resolve().parent.parent
    db_path = project_dir / 'db' / 'prometheus.db'
    csv_dir = project_dir / 'data' / 'raw'
    conn = sqlite3.connect(db_path)
    # each file is one year's worth of data from Oracle's Elixir
    for file in csv_dir.iterdir():
        if file.suffix != '.csv':
            print('Skipping non-CSV file:', file.name)
            continue
        
        df = pd.read_csv(file)
        df_sql = preprocess_match_raw_stats(df)
        df_sql.to_sql('match_raw_stats', conn, if_exists='append', index=False)
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()