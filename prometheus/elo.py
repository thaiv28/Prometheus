import datetime
from collections import defaultdict

import pandas as pd
from sqlalchemy import text

from prometheus.player_tables import PlayerTables
from prometheus.types import INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine, insert_rows

ELO_METHODS = ("game_length",)
STARTING_ELO = 1500
# Share of a team's Elo change in a cross-league international game that also moves
# its home league's offset (and so every team in that league). Tuned in the backtest.
LEAGUE_SHARE = 0.5
# A new player starts at the average of players whose last game in the league was
# within this many days.
ACTIVE_DAYS = 365


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


def _players_table(method: str) -> str:
    """Return the per-player Elo table for `method` (see `_elo_table`)."""
    _elo_table(method)  # validates the method
    return f"{method}_player_elo"


def expected_score(elo: float, opponent_elo: float) -> float:
    """Standard Elo expected score for a team against an opponent."""
    return 1 / (1 + 10 ** ((opponent_elo - elo) / 400))


def winner_score(
    game_length, upper_bound=1.0, lower_bound=0.65, center=30 * 60, steepness=3
):
    """The winner's "actual score" for a game of `game_length` seconds.

    Ranges from `lower_bound` (very long games) to `upper_bound` (very short games);
    the loser gets 1 minus it. Works on scalars and arrays.
    """
    return lower_bound + (upper_bound - lower_bound) / (
        1 + (game_length / center) ** steepness
    )


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
    rosters: dict | None = None,
    active_days: int = ACTIVE_DAYS,
    player_records: bool = False,
) -> tuple[pd.DataFrame, ...]:
    """Replay games in order and return per-team Elo records built from player ratings.

    Every player has a rating. A team's rating is the average of its five starters'
    ratings plus its home league's offset, so a roster move carries ratings with the
    players. After a game every starter moves by the team's Elo change. Domestic games
    only move players. Leagues are linked only by international events, so when teams
    from two leagues meet there, each league's offset also moves by `league_share` of
    the team's change: an upset at Worlds lifts the whole region, not only the team
    that travelled. A new player starts at the average rating of the players active in
    the team's league (last game there within `active_days`), or `starting_elo` plus
    the offset when there are none.

    A team's home league is the non-international league it has played most this
    calendar year, with last year's home counting as one game, so a cup, promotion
    series or EMEA Masters doesn't relabel it. Its main roster is the starters of its
    last game in its home league or at an international event, so an academy lineup
    fielded under the team's name at a cup doesn't stand in for the team.

    Args:
        games: One row per game with columns gameid, teamid, opponent_teamid,
            gamelength, result (from `teamid`'s perspective) and, optionally, league
            and date. Without a league column there are no offsets (plain Elo).
        elo_func: Function returning the Elo change for `teamid`.
        starting_elo: Rating of a player entering a league with no active players.
        league_share: Share of an international change applied to league offsets.
        rosters: Maps (gameid, teamid) to that team's starters (player ids). A team
            with no roster for a game uses its last roster; one that never had a
            roster plays as a single "player", which is plain team Elo.
        active_days: How recent a player's last game must be to count toward the
            league average a new player starts at.
        player_records: Also return each rostered player's rating before and after
            every game (teams without a roster are left out).
    Returns:
        (records, offsets). `records` has two rows per game (one per team): gameid,
        teamid, pre_match_elo, post_match_elo, elo_change, home_league (see above;
        None if it has only played international events), league_offset (that
        league's offset after the game) and main_elo (the team's rating with its main
        roster after the game, the rating to forecast its next match with). `offsets` has
        gameid, date (when `games` has one), league and league_offset after every
        game that moved an offset. With `player_records`, a third frame has gameid,
        teamid, playerid, pre_match_elo, post_match_elo (offset included), home_league
        and league_offset.
    """
    has_league = "league" in games.columns
    leagues = games["league"] if has_league else [None] * len(games)
    dates = (
        pd.to_datetime(games["date"])
        if "date" in games.columns
        else [None] * len(games)
    )
    rosters = rosters or {}
    window = pd.Timedelta(days=active_days)
    own = {}  # player -> rating, relative to the offset of the league in `player_league`
    player_league = {}
    last_seen = {}  # player -> (date, league) of the last game
    members = defaultdict(set)  # league -> players whose last game was there
    home = {}
    season_counts = {}  # (team, year) -> {league: games}
    last_roster = {}
    main_roster = {}
    league_offset = defaultdict(float)

    def league_average(league, date):
        recent = [
            own[p]
            for p in members[league]
            if date is None
            or last_seen[p][0] is None
            or last_seen[p][0] >= date - window
        ]
        return sum(recent) / len(recent) if recent else starting_elo

    def seat(player, league, date):
        if player not in own:
            own[player] = (
                league_average(league, date) if league is not None else starting_elo
            )
            player_league[player] = league
        elif player_league[player] != league:
            # Moving league (a transfer, promotion, a cup) keeps the player's rating.
            own[player] += league_offset[player_league[player]] - league_offset[league]
            player_league[player] = league

    elo_records = []
    offset_records = []
    player_rows = []
    for row, league, date in zip(games.itertuples(index=False), leagues, dates):
        domestic = has_league and league not in INTERNATIONAL_LEAGUES
        sides = []
        for team in (row.teamid, row.opponent_teamid):
            if domestic:
                year = date.year if date is not None else None
                if (team, year) not in season_counts:
                    season_counts[(team, year)] = (
                        {home[team]: 1} if team in home else {}
                    )
                counts = season_counts[(team, year)]
                counts[league] = counts.get(league, 0) + 1
                # Strictly more games, so a tie keeps the current home.
                if counts[league] > counts.get(home.get(team), 0):
                    home[team] = league
            team_league = home.get(team)
            roster = (
                rosters.get((row.gameid, team))
                or last_roster.get(team)
                or (("team", team),)
            )
            last_roster[team] = roster
            for player in roster:
                seat(player, team_league, date)
            sides.append((team, team_league, roster))

        def rating(side):
            _, team_league, roster = side
            offset = league_offset[team_league] if team_league is not None else 0.0
            return sum(own[p] for p in roster) / len(roster) + offset

        pre = [rating(side) for side in sides]
        if player_records:
            player_pre = {
                p: own[p]
                + (league_offset[team_league] if team_league is not None else 0.0)
                for _, team_league, roster in sides
                for p in roster
            }
        elo_change = elo_func(
            elo=pre[0],
            opponent_elo=pre[1],
            game_length=row.gamelength,
            result=row.result,
        )
        for (_, _, roster), change in zip(sides, (elo_change, -elo_change)):
            for player in roster:
                own[player] += change

        team_league, opponent_league = sides[0][1], sides[1][1]
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

        for side, before in zip(sides, pre):
            team, team_league, roster = side
            if (
                not domestic
                or team_league is None
                or league == team_league
                or team not in main_roster
            ):
                main_roster[team] = roster
            for player in roster:
                if player in last_seen:
                    members[last_seen[player][1]].discard(player)
                last_seen[player] = (date, team_league)
                members[team_league].add(player)
            after = rating(side)
            offset_now = league_offset[team_league] if team_league is not None else 0.0
            if player_records and roster != (("team", team),):
                for player in roster:
                    player_rows.append(
                        (
                            row.gameid,
                            team,
                            player,
                            player_pre[player],
                            own[player] + offset_now,
                            team_league,
                            offset_now,
                        )
                    )
            main = main_roster[team]
            # Each player's own rating plus the offset of the league they sit in now.
            main_elo = sum(
                own[p]
                + (
                    league_offset[player_league[p]]
                    if player_league[p] is not None
                    else 0.0
                )
                for p in main
            ) / len(main)
            elo_records.append(
                {
                    "gameid": row.gameid,
                    "teamid": team,
                    "pre_match_elo": before,
                    "post_match_elo": after,
                    "elo_change": after - before,
                    "home_league": team_league,
                    "league_offset": league_offset[team_league]
                    if team_league is not None
                    else 0.0,
                    "main_elo": main_elo,
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
            "main_elo",
        ],
    )
    offsets = pd.DataFrame(
        offset_records, columns=["gameid", "date", "league", "league_offset"]
    )
    if player_records:
        players = pd.DataFrame(
            player_rows,
            columns=[
                "gameid",
                "teamid",
                "playerid",
                "pre_match_elo",
                "post_match_elo",
                "home_league",
                "league_offset",
            ],
        )
        return records, offsets, players
    return records, offsets


def load_elo_games() -> pd.DataFrame:
    """Every game once, oldest first, in the shape `compute_elo_records` takes."""
    stmt = """
    SELECT m1.gameid, m1.teamid AS teamid, m2.teamid AS opponent_teamid, m1.gamelength,
           m1.result, m1.league, m1.date
    FROM matches m1
        JOIN matches m2 ON m1.gameid = m2.gameid AND m1.teamid < m2.teamid
    ORDER BY m1.date ASC, m1.gameid ASC
    """
    return pd.read_sql(stmt, get_engine())


def load_rosters() -> dict:
    """Each team's starters in every game: {(gameid, teamid): (playerid, ...)}."""
    players = pd.read_sql(
        "SELECT gameid, teamid, playerid FROM match_players", get_engine()
    )
    rosters = {}
    for key in zip(players["gameid"], players["teamid"], players["playerid"]):
        rosters.setdefault(key[:2], []).append(key[2])
    return {key: tuple(ids) for key, ids in rosters.items()}


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

    engine = get_engine()
    games = load_elo_games()
    elo_df, offsets_df, players_df = compute_elo_records(
        games,
        elo_func,
        starting_elo=starting_elo,
        rosters=load_rosters(),
        player_records=True,
    )

    # Clear rather than drop so the schema from 001_create_tables.sql is preserved.
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
        conn.execute(text(f"DELETE FROM {offsets_table}"))
        conn.execute(text(f"DELETE FROM {_players_table(method)}"))
        insert_rows(conn, table, elo_df)
        insert_rows(conn, offsets_table, offsets_df)
        insert_rows(conn, _players_table(method), players_df)


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
        `league` is the team's home league after its last game (see
        `compute_elo_records`), so a team whose last game was at Worlds or a cup is
        still listed under its region. `elo` is its main roster's rating after that game
        (`main_elo`) plus every change to the league's offset since (for example from
        an international event it did not attend).
    """
    table = _elo_table(method)
    offsets_table = _offsets_table(method)
    stmt = f"""
    WITH ranked AS (
        SELECT e.teamid, m.teamname, m.league, CAST(strftime('%Y', m.date) AS INT) AS year,
               COALESCE(e.main_elo, e.post_match_elo) AS elo, e.home_league, e.league_offset,
               m.date AS latest_date,
               ROW_NUMBER() OVER (
                   PARTITION BY e.teamid ORDER BY m.date DESC, m.gameid DESC
               ) AS rn
        FROM {table} e
        JOIN matches m ON e.gameid = m.gameid AND e.teamid = m.teamid
        WHERE (:date IS NULL OR DATE(m.date) <= :date)
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
    SELECT r.teamname, COALESCE(r.home_league, r.league) AS league, r.year,
           r.elo + COALESCE(c.league_offset - r.league_offset, 0) AS elo, r.latest_date
    FROM ranked r
    LEFT JOIN current_offset c ON c.league = r.home_league
    WHERE r.rn = 1
    ORDER BY elo DESC
    """
    params = {"date": date.isoformat() if date else None}
    return pd.read_sql(text(stmt), get_engine(), params=params)


class LatestElos:
    """`get_latest_elos` for many cutoff dates from one read of the tables.

    `LatestElos(method)(date)` returns the same rows as `get_latest_elos(method,
    date)`. Each call to `get_latest_elos` scans every game again (about a second),
    so a caller that needs the ratings before each of hundreds of days (the market
    benchmark, the prediction log's rebuilt calls) uses this instead.
    """

    def __init__(self, method: str):
        table = _elo_table(method)
        offsets_table = _offsets_table(method)
        engine = get_engine()
        self.games = pd.read_sql(
            f"""
            SELECT e.teamid, m.teamname, m.league,
                   CAST(strftime('%Y', m.date) AS INT) AS year,
                   COALESCE(e.main_elo, e.post_match_elo) AS elo, e.home_league,
                   e.league_offset, m.date AS latest_date, DATE(m.date) AS day
            FROM {table} e
            JOIN matches m ON e.gameid = m.gameid AND e.teamid = m.teamid
            ORDER BY m.date, m.gameid
            """,
            engine,
        )
        self.offsets = pd.read_sql(
            f"SELECT league, league_offset, DATE(date) AS day FROM {offsets_table} ORDER BY rowid",
            engine,
        )

    def __call__(self, date: datetime.date | None = None) -> pd.DataFrame:
        games, offsets = self.games, self.offsets
        if date is not None:
            cutoff = date.isoformat()
            games = games[games["day"] <= cutoff]
            offsets = offsets[offsets["day"] <= cutoff]
        last = games.groupby("teamid").tail(1)
        current = offsets.groupby("league").tail(1).set_index("league")["league_offset"]
        moved = last["home_league"].map(current) - last["league_offset"]
        out = pd.DataFrame(
            {
                "teamname": last["teamname"],
                "league": last["home_league"].fillna(last["league"]),
                "year": last["year"],
                "elo": last["elo"] + moved.fillna(0),
                "latest_date": last["latest_date"],
            }
        )
        return out.sort_values("elo", ascending=False, kind="stable").reset_index(
            drop=True
        )


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
           COALESCE(e.main_elo, e.post_match_elo) AS elo, e.home_league, e.league_offset
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
    last["league"] = (
        last["season_league"].fillna(last["home_league"]).fillna(last["league"])
    )

    last = last.join(
        _season_end_offsets(method, sorted(last["year"].unique())),
        on=["home_league", "year"],
    )
    last["elo"] = last["elo"] + (
        last["season_end_offset"] - last["league_offset"]
    ).fillna(0)
    return (
        last[["teamname", "league", "year", "elo", "latest_date"]]
        .sort_values("elo", ascending=False)
        .reset_index(drop=True)
    )


def _season_end_offsets(method: str, years: list[int]) -> pd.Series:
    """Each league's offset at the end of each year: its last value up to then.

    Indexed by (league, year) and named `season_end_offset`.
    """
    offsets = pd.read_sql(
        f"SELECT date, league, league_offset FROM {_offsets_table(method)} ORDER BY rowid",
        get_engine(),
    )
    offsets["year"] = offsets["date"].str[:4].astype(int)
    by_season = offsets.groupby(["league", "year"])["league_offset"].last()
    return (
        by_season.unstack("year")
        .reindex(columns=years)
        .ffill(axis=1)
        .stack()
        .rename("season_end_offset")
    )


def _current_offsets(method: str) -> pd.Series:
    """Each league's latest offset, indexed by league."""
    offsets = pd.read_sql(
        f"SELECT league, league_offset FROM {_offsets_table(method)} ORDER BY rowid",
        get_engine(),
    )
    return offsets.groupby("league")["league_offset"].last()


def get_player_history(method: str, tables: PlayerTables | None = None) -> pd.DataFrame:
    """Every rostered player's Elo after each game, oldest first.

    `tables` is a `PlayerTables` for `method` (read when None).

    Returns:
        DataFrame with gameid, playerid, playername, position, teamid, teamname, league (of
        the game), home_league, date, year (calendar), elo (after the game) and
        league_offset (home league's offset after the game).
    """
    if tables is None:
        tables = PlayerTables(method)
    cols = [
        "gameid",
        "playerid",
        "playername",
        "position",
        "teamid",
        "teamname",
        "league",
        "home_league",
        "date",
        "elo",
        "league_offset",
    ]
    history = (
        # Roster order within a game, as the SQL join gave it.
        tables.roster.merge(
            tables.elo.drop(columns="elo_pre"), on=["gameid", "teamid", "playerid"]
        )
        .merge(
            tables.matches[["gameid", "teamid", "teamname", "league", "date"]],
            on=["gameid", "teamid"],
        )
        .sort_values(["date", "gameid"], kind="stable", ignore_index=True)[cols]
    )
    history["year"] = history["date"].str[:4].astype(int)
    return history


def _most_common(frame: pd.DataFrame, keys: list[str], col: str) -> pd.Series:
    """The most frequent `col` value per `keys` group (vectorised value_counts)."""
    counts = frame.groupby(keys + [col]).size().rename("n").reset_index()
    counts = counts.sort_values("n", ascending=False, kind="mergesort").drop_duplicates(
        keys
    )
    return counts.set_index(keys)[col]


def get_player_elos(
    method: str, history: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Players' current ratings and their ratings at the end of each calendar year.

    Like `get_latest_elos` and `get_season_elos` for teams: a rating is the player's
    rating after their last game (that year), plus every change to their home league's
    offset since then (through the end of that year).

    Returns:
        (latest, seasons). Both have playerid, playername (from the last game),
        position (most played), teamname and teamid (last team), league (home league,
        or the league of the last game), elo, latest_date and games; `seasons` also
        has year and is labelled with the domestic league played most that year.
    """
    if history is None:
        history = get_player_history(method)

    def summarise(group_cols):
        last = history.groupby(group_cols).tail(1).set_index(group_cols)
        out = last[
            [
                "playername",
                "teamname",
                "teamid",
                "home_league",
                "league",
                "elo",
                "league_offset",
            ]
        ].copy()
        out["latest_date"] = last["date"].str[:10]
        out["games"] = history.groupby(group_cols).size()
        out["position"] = _most_common(history, group_cols, "position")
        return out

    latest = summarise(["playerid"])
    moved = (
        latest["home_league"].map(_current_offsets(method)) - latest["league_offset"]
    )
    latest["elo"] = latest["elo"] + moved.fillna(0)
    latest["league"] = latest["home_league"].fillna(latest["league"])

    seasons = summarise(["playerid", "year"]).reset_index()
    domestic = history[~history["league"].isin(INTERNATIONAL_LEAGUES)]
    season_league = _most_common(domestic, ["playerid", "year"], "league")
    seasons = seasons.join(
        season_league.rename("season_league"), on=["playerid", "year"]
    )
    seasons = seasons.join(
        _season_end_offsets(method, sorted(seasons["year"].unique())),
        on=["home_league", "year"],
    )
    seasons["elo"] = seasons["elo"] + (
        seasons["season_end_offset"] - seasons["league_offset"]
    ).fillna(0)
    seasons["league"] = (
        seasons["season_league"]
        .fillna(seasons["home_league"])
        .fillna(seasons["league"])
    )

    cols = [
        "playerid",
        "playername",
        "position",
        "teamname",
        "teamid",
        "league",
        "elo",
        "latest_date",
        "games",
    ]
    return (
        latest.reset_index()[cols]
        .sort_values("elo", ascending=False)
        .reset_index(drop=True),
        seasons[cols[:1] + ["year"] + cols[1:]]
        .sort_values("elo", ascending=False)
        .reset_index(drop=True),
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
