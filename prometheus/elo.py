from collections import defaultdict
import datetime

import pandas as pd
from sqlalchemy import text

from prometheus.utils import get_engine

ELO_METHODS = ("game_length",)
STARTING_ELO = 1500


def _elo_table(method: str) -> str:
    """Return the Elo table name for `method`, rejecting unknown methods.

    The table name is interpolated into SQL, so it must come from a fixed allowlist.
    """
    if method not in ELO_METHODS:
        raise ValueError(f"Unsupported Elo calculation method: {method}")
    return f"{method}_elo"


def expected_score(elo: float, opponent_elo: float) -> float:
    """Standard Elo expected score for a team against an opponent."""
    return 1 / (1 + 10 ** ((opponent_elo - elo) / 400))


def calculate_game_length_elo_change(
    elo,
    opponent_elo,
    game_length,
    result,
    upper_bound=1.0,
    lower_bound=0.65,
    center=30 * 60,
    steepness=3,
    K=20,
):
    """Calculate the Elo change for a team based on game length.

    The winner's "actual score" ranges from `lower_bound` (very long games) to
    `upper_bound` (very short games); the loser receives 1 minus that. Shorter
    wins therefore move ratings more, and changes are zero-sum between teams.
    `lower_bound` sits well above 0.5 so even a long win counts for more than a draw.

    Args:
        elo: Current Elo rating of the team.
        opponent_elo: Current Elo rating of the opposing team.
        game_length: Length of the game in seconds.
        result: Match result for the team (1 = win, 0 = loss).
    Returns:
        Elo change for the team. The opponent's change is the negation.
    """
    winner_score = lower_bound + (upper_bound - lower_bound) / (
        1 + (game_length / center) ** steepness
    )
    actual = winner_score if result else 1 - winner_score

    return K * (actual - expected_score(elo, opponent_elo))


def compute_elo_records(
    games: pd.DataFrame, elo_func, starting_elo: float = STARTING_ELO
) -> pd.DataFrame:
    """Replay games in order and return per-team Elo records.

    Args:
        games: One row per game with columns gameid, teamid, opponent_teamid,
            gamelength, result (result is from `teamid`'s perspective).
        elo_func: Function returning the Elo change for `teamid`.
        starting_elo: Rating assigned to a team before its first game.
    Returns:
        DataFrame with two rows per game (one per team): gameid, teamid,
        pre_match_elo, post_match_elo, elo_change.
    """
    elo_ratings = defaultdict(lambda: starting_elo)
    elo_records = []
    for row in games.itertuples(index=False):
        team_elo = elo_ratings[row.teamid]
        opponent_elo = elo_ratings[row.opponent_teamid]

        elo_change = elo_func(
            elo=team_elo,
            opponent_elo=opponent_elo,
            game_length=row.gamelength,
            result=row.result,
        )

        elo_records.append(
            {
                "gameid": row.gameid,
                "teamid": row.teamid,
                "pre_match_elo": team_elo,
                "post_match_elo": team_elo + elo_change,
                "elo_change": elo_change,
            }
        )
        elo_records.append(
            {
                "gameid": row.gameid,
                "teamid": row.opponent_teamid,
                "pre_match_elo": opponent_elo,
                "post_match_elo": opponent_elo - elo_change,
                "elo_change": -elo_change,
            }
        )

        elo_ratings[row.teamid] = team_elo + elo_change
        elo_ratings[row.opponent_teamid] = opponent_elo - elo_change

    return pd.DataFrame(
        elo_records,
        columns=["gameid", "teamid", "pre_match_elo", "post_match_elo", "elo_change"],
    )


def bootstrap_elo(method: str, starting_elo: int = STARTING_ELO) -> None:
    """Recompute Elo ratings for all teams and overwrite the method's Elo table.

    Args:
        method: The method to use for Elo calculation ('game_length' supported).
    """
    table = _elo_table(method)
    match method:
        case "game_length":
            elo_func = calculate_game_length_elo_change

    stmt = """
    SELECT m1.gameid, m1.teamid AS teamid, m2.teamid AS opponent_teamid, m1.gamelength, m1.result
    FROM matches m1
        JOIN matches m2 ON m1.gameid = m2.gameid AND m1.teamid < m2.teamid
    ORDER BY m1.date ASC, m1.gameid ASC
    """

    engine = get_engine()
    games = pd.read_sql(stmt, engine)
    elo_df = compute_elo_records(games, elo_func, starting_elo=starting_elo)

    # Clear rather than drop so the schema from 001_create_tables.sql is preserved.
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
        elo_df.to_sql(table, conn, if_exists="append", index=False)


def get_elo_history(
    method: str, team: str | None = None, date: datetime.date | None = None
) -> pd.DataFrame:
    """Return Elo after each game, for one team or (team=None) every team.

    Optionally limited to games on or before `date` (inclusive).
    """
    table = _elo_table(method)
    stmt = f"""
    SELECT m.teamname, m.league, m.date, e.pre_match_elo, e.post_match_elo, e.elo_change
    FROM {table} e
    JOIN matches m
        ON e.gameid = m.gameid AND e.teamid = m.teamid
    WHERE (:team IS NULL OR m.teamname = :team)
      AND (:date IS NULL OR DATE(m.date) <= :date)
    ORDER BY m.date ASC, m.gameid ASC
    """
    params = {"team": team, "date": date.isoformat() if date else None}
    return pd.read_sql(text(stmt), get_engine(), params=params)


def get_latest_elos(method: str, date: datetime.date | None = None) -> pd.DataFrame:
    """Return latest Elo snapshot per team for the given method.

    Args:
        method: Elo method/table prefix, e.g. 'game_length'.
        date: Optional cutoff date (inclusive). If provided, only matches on or before
              this date are considered when computing latest Elo.
    Returns:
        DataFrame with columns: teamname, league, year, elo, latest_date.
    """
    table = _elo_table(method)
    stmt = f"""
    WITH ranked AS (
        SELECT m.teamname, m.league, CAST(strftime('%Y', m.date) AS INT) AS year,
               e.post_match_elo AS elo, m.date AS latest_date,
               ROW_NUMBER() OVER (
                   PARTITION BY e.teamid ORDER BY m.date DESC, m.gameid DESC
               ) AS rn
        FROM {table} e
        JOIN matches m ON e.gameid = m.gameid AND e.teamid = m.teamid
        WHERE (:date IS NULL OR DATE(m.date) <= :date)
    )
    SELECT teamname, league, year, elo, latest_date
    FROM ranked
    WHERE rn = 1
    ORDER BY elo DESC
    """
    params = {"date": date.isoformat() if date else None}
    return pd.read_sql(text(stmt), get_engine(), params=params)
