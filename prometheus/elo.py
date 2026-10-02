from collections import defaultdict
import datetime

import pandas as pd
from sqlalchemy import text

from prometheus.utils import get_engine
from prometheus.types import INTERNATIONAL_LEAGUES

ELO_METHODS = ("game_length",)
STARTING_ELO = 1500
# Share of a team's Elo change in a cross-league international game that also moves
# its home league's offset (and so every team in that league). Tuned in the backtest.
LEAGUE_SHARE = 0.5


def _elo_table(method: str) -> str:
    """Return the Elo table name for `method`, rejecting unknown methods.

    The table name is interpolated into SQL, so it must come from a fixed allowlist.
    """
    if method not in ELO_METHODS:
        raise ValueError(f"Unsupported Elo calculation method: {method}")
    return f"{method}_elo"


def _offsets_table(method: str) -> str:
    """Return the league-offset history table for `method` (see `_elo_table`)."""
    return f"{_elo_table(method)}_league_offsets"


def expected_score(elo: float, opponent_elo: float) -> float:
    """Standard Elo expected score for a team against an opponent."""
    return 1 / (1 + 10 ** ((opponent_elo - elo) / 400))


def winner_score(game_length, upper_bound=1.0, lower_bound=0.65, center=30 * 60, steepness=3):
    """The winner's "actual score" for a game of `game_length` seconds.

    Ranges from `lower_bound` (very long games) to `upper_bound` (very short games);
    the loser gets 1 minus it. Works on scalars and arrays.
    """
    return lower_bound + (upper_bound - lower_bound) / (1 + (game_length / center) ** steepness)


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
    score = winner_score(game_length, upper_bound, lower_bound, center, steepness)
    actual = score if result else 1 - score

    return K * (actual - expected_score(elo, opponent_elo))


def compute_elo_records(
    games: pd.DataFrame,
    elo_func,
    starting_elo: float = STARTING_ELO,
    league_share: float = LEAGUE_SHARE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replay games in order and return per-team Elo records.

    A team's rating is its own rating plus its home league's offset. Domestic games
    only move the teams' own ratings. Leagues are linked only by international events,
    so when teams from two leagues meet there, each league's offset also moves by
    `league_share` of the team's change: an upset at Worlds lifts the whole region,
    not only the team that travelled. A new team starts at `starting_elo` plus its
    league's offset, so it enters at its league's level.

    Args:
        games: One row per game with columns gameid, teamid, opponent_teamid,
            gamelength, result (from `teamid`'s perspective) and, optionally, league.
            Without a league column there are no offsets (plain Elo).
        elo_func: Function returning the Elo change for `teamid`.
        starting_elo: Own rating assigned to a team before its first game.
        league_share: Share of an international change applied to league offsets.
    Returns:
        (records, offsets). `records` has two rows per game (one per team): gameid,
        teamid, pre_match_elo, post_match_elo, elo_change, home_league (the last
        domestic league the team played in, None if it has only played international
        events) and league_offset (that league's offset after the game). `offsets` has
        gameid, date (when `games` has one), league and league_offset after every
        game that moved an offset.
    """
    has_league = "league" in games.columns
    leagues = games["league"] if has_league else [None] * len(games)
    own = {}
    home = {}
    league_offset = defaultdict(float)

    def rating(team):
        return own[team] + (league_offset[home[team]] if team in home else 0.0)

    elo_records = []
    offset_records = []
    for row, league in zip(games.itertuples(index=False), leagues):
        domestic = has_league and league not in INTERNATIONAL_LEAGUES
        for team in (row.teamid, row.opponent_teamid):
            if team not in own:
                own[team] = starting_elo
                if domestic:
                    home[team] = league
            elif domestic and home.get(team) != league:
                # Moving league (promotion, a cup) keeps the team's rating unchanged.
                current = rating(team)
                home[team] = league
                own[team] = current - league_offset[league]

        team_elo = rating(row.teamid)
        opponent_elo = rating(row.opponent_teamid)
        elo_change = elo_func(
            elo=team_elo,
            opponent_elo=opponent_elo,
            game_length=row.gamelength,
            result=row.result,
        )
        own[row.teamid] += elo_change
        own[row.opponent_teamid] -= elo_change

        team_league = home.get(row.teamid)
        opponent_league = home.get(row.opponent_teamid)
        if (
            has_league
            and not domestic
            and team_league is not None
            and opponent_league is not None
            and team_league != opponent_league
        ):
            league_offset[team_league] += league_share * elo_change
            league_offset[opponent_league] -= league_share * elo_change
            for moved in (team_league, opponent_league):
                offset_records.append(
                    {
                        "gameid": row.gameid,
                        "date": getattr(row, "date", None),
                        "league": moved,
                        "league_offset": league_offset[moved],
                    }
                )

        for team, pre in ((row.teamid, team_elo), (row.opponent_teamid, opponent_elo)):
            post = rating(team)
            elo_records.append(
                {
                    "gameid": row.gameid,
                    "teamid": team,
                    "pre_match_elo": pre,
                    "post_match_elo": post,
                    "elo_change": post - pre,
                    "home_league": home.get(team),
                    "league_offset": league_offset[home[team]] if team in home else 0.0,
                }
            )

    records = pd.DataFrame(
        elo_records,
        columns=[
            "gameid",
            "teamid",
            "pre_match_elo",
            "post_match_elo",
            "elo_change",
            "home_league",
            "league_offset",
        ],
    )
    offsets = pd.DataFrame(
        offset_records, columns=["gameid", "date", "league", "league_offset"]
    )
    return records, offsets


def bootstrap_elo(method: str, starting_elo: int = STARTING_ELO) -> None:
    """Recompute Elo ratings for all teams and overwrite the method's Elo tables.

    Args:
        method: The method to use for Elo calculation ('game_length' supported).
    """
    table = _elo_table(method)
    offsets_table = _offsets_table(method)
    match method:
        case "game_length":
            elo_func = calculate_game_length_elo_change

    stmt = """
    SELECT m1.gameid, m1.teamid AS teamid, m2.teamid AS opponent_teamid, m1.gamelength,
           m1.result, m1.league, m1.date
    FROM matches m1
        JOIN matches m2 ON m1.gameid = m2.gameid AND m1.teamid < m2.teamid
    ORDER BY m1.date ASC, m1.gameid ASC
    """

    engine = get_engine()
    games = pd.read_sql(stmt, engine)
    elo_df, offsets_df = compute_elo_records(games, elo_func, starting_elo=starting_elo)

    # Clear rather than drop so the schema from 001_create_tables.sql is preserved.
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
        conn.execute(text(f"DELETE FROM {offsets_table}"))
        elo_df.to_sql(table, conn, if_exists="append", index=False)
        offsets_df.to_sql(offsets_table, conn, if_exists="append", index=False)


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
        `league` is the team's most recent home league, so a team whose last game was
        at Worlds is still listed under its region. `elo` includes every change to the
        team's league offset since its last game (for example from an international
        event it did not attend).
    """
    table = _elo_table(method)
    offsets_table = _offsets_table(method)
    international = ", ".join(repr(l) for l in INTERNATIONAL_LEAGUES)
    stmt = f"""
    WITH ranked AS (
        SELECT e.teamid, m.teamname, m.league, CAST(strftime('%Y', m.date) AS INT) AS year,
               e.post_match_elo AS elo, e.home_league, e.league_offset,
               m.date AS latest_date,
               ROW_NUMBER() OVER (
                   PARTITION BY e.teamid ORDER BY m.date DESC, m.gameid DESC
               ) AS rn,
               ROW_NUMBER() OVER (
                   PARTITION BY e.teamid, m.league IN ({international})
                   ORDER BY m.date DESC, m.gameid DESC
               ) AS league_rn
        FROM {table} e
        JOIN matches m ON e.gameid = m.gameid AND e.teamid = m.teamid
        WHERE (:date IS NULL OR DATE(m.date) <= :date)
    ),
    home AS (
        SELECT teamid, league FROM ranked
        WHERE league_rn = 1 AND league NOT IN ({international})
    ),
    current_offset AS (
        SELECT league, league_offset FROM (
            SELECT league, league_offset,
                   ROW_NUMBER() OVER (PARTITION BY league ORDER BY rowid DESC) AS rn
            FROM {offsets_table}
            WHERE (:date IS NULL OR DATE(date) <= :date)
        )
        WHERE rn = 1
    )
    SELECT r.teamname, COALESCE(h.league, r.league) AS league, r.year,
           r.elo + COALESCE(c.league_offset - r.league_offset, 0) AS elo, r.latest_date
    FROM ranked r
    LEFT JOIN home h ON h.teamid = r.teamid
    LEFT JOIN current_offset c ON c.league = r.home_league
    WHERE r.rn = 1
    ORDER BY elo DESC
    """
    params = {"date": date.isoformat() if date else None}
    return pd.read_sql(text(stmt), get_engine(), params=params)


def get_season_elos(method: str) -> pd.DataFrame:
    """Return every team's rating at the end of each calendar year it played.

    A year's rating is the team's rating after its last game that year, plus any
    change to its league's offset through the end of that year (for example from
    Worlds, if the team did not attend). Years are calendar years of the game date,
    as in `get_latest_elos`, because Oracle's Elixir files some autumn games under
    the next season.

    Returns:
        DataFrame with columns: teamname, league, year, elo, latest_date. `league` is
        the domestic league the team played most that year (its home league if it
        only played international events); `teamname` is from its last game.
    """
    table = _elo_table(method)
    stmt = f"""
    SELECT e.teamid, m.teamname, m.league, CAST(strftime('%Y', m.date) AS INT) AS year,
           m.date AS latest_date, m.gameid,
           e.post_match_elo AS elo, e.home_league, e.league_offset
    FROM {table} e
    JOIN matches m ON e.gameid = m.gameid AND e.teamid = m.teamid
    ORDER BY m.date, m.gameid
    """
    games = pd.read_sql(stmt, get_engine())
    last = games.groupby(["teamid", "year"]).tail(1).copy()

    domestic = games[~games["league"].isin(INTERNATIONAL_LEAGUES)]
    # Most-played league, so a winter cup (KeSPA Cup, Demacia Cup) doesn't label the year.
    season_league = domestic.groupby(["teamid", "year"])["league"].agg(
        lambda leagues: leagues.value_counts().index[0]
    )
    last = last.join(season_league.rename("season_league"), on=["teamid", "year"])
    last["league"] = last["season_league"].fillna(last["home_league"]).fillna(last["league"])

    # Each league's offset at the end of each season: its last value up to then.
    offsets = pd.read_sql(
        f"SELECT date, league, league_offset FROM {_offsets_table(method)} ORDER BY rowid",
        get_engine(),
    )
    offsets["year"] = offsets["date"].str[:4].astype(int)
    by_season = offsets.groupby(["league", "year"])["league_offset"].last()
    years = sorted(last["year"].unique())
    season_end = (
        by_season.unstack("year").reindex(columns=years).ffill(axis=1).stack()
        .rename("season_end_offset")
    )
    last = last.join(season_end, on=["home_league", "year"])
    last["elo"] = last["elo"] + (
        last["season_end_offset"] - last["league_offset"]
    ).fillna(0)
    return (
        last[["teamname", "league", "year", "elo", "latest_date"]]
        .sort_values("elo", ascending=False)
        .reset_index(drop=True)
    )


def get_pregame_elos(method: str, years: list[int] | None = None) -> pd.DataFrame:
    """Return each team's and its opponent's Elo going into every game.

    Returns:
        DataFrame with columns: gameid, teamid, elo, opp_elo (two rows per game).
    """
    table = _elo_table(method)
    year_filter = ""
    if years is not None:
        year_filter = f"WHERE m.year IN ({', '.join(str(int(y)) for y in years)})"
    stmt = f"""
    SELECT e.gameid, e.teamid, e.pre_match_elo AS elo, o.pre_match_elo AS opp_elo
    FROM {table} e
    JOIN {table} o ON o.gameid = e.gameid AND o.teamid != e.teamid
    JOIN matches m ON m.gameid = e.gameid AND m.teamid = e.teamid
    {year_filter}
    """
    return pd.read_sql(stmt, get_engine())
