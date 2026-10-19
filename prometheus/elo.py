import datetime
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import text

from prometheus.player_tables import PlayerTables
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine, insert_rows

ELO_METHODS = ("game_length",)
STARTING_ELO = 1500
# Share of a team's Elo change in a cross-league international game that also moves
# its home league's offset (and so every team in that league). Tuned in the backtest.
LEAGUE_SHARE = 0.5
# A new player starts at the average of players whose last game in the league was
# within this many days.
ACTIVE_DAYS = 365
# Rookie discount fades logarithmically over these many games; never stored.
ROOKIE_PENALTY = 250
ROOKIE_GAMES = 200
# Stored bonus when moving from a major to another league, after offset conversion.
MOVE_DOWN_BONUS = 25.0
MAJOR_LEAGUES = frozenset(league.value for league in ALL_MAJOR_LEAGUES)

# New, floor and growth per sqrt(day); tuned through 2021.
PLAYER_RD = (280.0, 140.0, 10.0)
# Per-game information multiplier controls RD shrinkage.
PLAYER_RD_INFORMATION = 0.125
# Non-major domestic expected-score log-odds per point; K stays 20 everywhere.
OTHER_LEAGUE_SLOPE = 0.0065


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


EXPECTED_SLOPE = math.log(10) / 400


def expected_score(
    elo: float, opponent_elo: float, slope: float = EXPECTED_SLOPE
) -> float:
    """Expected score; slope is log-odds per point.

    Keep the original arithmetic on the default path for exact replay parity.
    """
    if slope == EXPECTED_SLOPE:
        return 1 / (1 + 10 ** ((opponent_elo - elo) / 400))
    return 1 / (1 + math.exp(slope * (opponent_elo - elo)))


def power_winner_score(
    game_length, upper_bound=1.0, lower_bound=0.65, center=30 * 60, steepness=3
):
    """Original duration curve, retained for Record and historical experiments."""
    return lower_bound + (upper_bound - lower_bound) / (
        1 + (game_length / center) ** steepness
    )


def winner_score(
    game_length,
    upper_bound=1.0,
    lower_bound=0.65,
    center=30 * 60,
    steepness=None,
    transition=5 * 60,
):
    """Elo's duration evidence: a steep transition around 30 minutes.

    Very short wins approach 1; very long wins approach .65. The loser receives
    the complement. Scalars and arrays are supported. An explicit `steepness`
    retains the historical power curve for existing research configurations.
    Record calls `power_winner_score` directly to preserve its season definition.
    """
    if steepness is not None:
        return power_winner_score(
            game_length, upper_bound, lower_bound, center, steepness
        )
    if transition <= 0:
        raise ValueError("Duration transition must be positive")
    midpoint = (upper_bound + lower_bound) / 2
    amplitude = (upper_bound - lower_bound) / 2
    squash = math.tanh if np.isscalar(game_length) else np.tanh
    return midpoint + amplitude * squash((center - game_length) / transition)


def calculate_game_length_elo_change(
    elo,
    opponent_elo,
    game_length,
    result,
    upper_bound=1.0,
    lower_bound=0.65,
    center=30 * 60,
    steepness=None,
    K=20,
    transition=5 * 60,
    expected_slope=EXPECTED_SLOPE,
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
    score = winner_score(
        game_length, upper_bound, lower_bound, center, steepness, transition
    )
    actual = score if result else 1 - score

    return K * (actual - expected_score(elo, opponent_elo, slope=expected_slope))


class EloState:
    """Mutable Elo replay state, resumable without changing replay arithmetic."""

    def __init__(
        self,
        elo_func,
        starting_elo=STARTING_ELO,
        league_share=LEAGUE_SHARE,
        rosters=None,
        active_days=ACTIVE_DAYS,
        player_records=False,
        rookie_penalty=ROOKIE_PENALTY,
        rookie_games=ROOKIE_GAMES,
        move_down_bonus=MOVE_DOWN_BONUS,
        player_rd=PLAYER_RD,
        player_rd_information=PLAYER_RD_INFORMATION,
        other_league_slope=OTHER_LEAGUE_SLOPE,
        has_league=True,
    ):
        if player_rd is not None:
            rd_new, rd_min, rd_growth = player_rd
            if not all(math.isfinite(x) for x in player_rd) or not (
                0 < rd_min <= rd_new and rd_growth >= 0
            ):
                raise ValueError(
                    "player_rd requires finite new >= floor > 0, growth >= 0"
                )
            if not math.isfinite(player_rd_information) or player_rd_information <= 0:
                raise ValueError("player_rd_information must be finite and positive")
        self.elo_func = elo_func
        self.rosters = rosters or {}
        self.team_last = {}
        self.starting_elo = starting_elo
        self.league_share = league_share
        self.active_days = active_days
        self.rookie_penalty = rookie_penalty
        self.rookie_games = rookie_games
        self.move_down_bonus = move_down_bonus
        self.player_rd = player_rd
        self.player_rd_information = player_rd_information
        self.other_league_slope = other_league_slope
        self.has_league = has_league
        self.own = {}
        self.player_league = {}
        self.last_seen = {}
        self.members = defaultdict(set)
        self.home = {}
        self.season_counts = {}
        self.last_roster = {}
        self.main_roster = {}
        self.league_offset = defaultdict(float)
        self.played = defaultdict(int)
        self.rd_variance = {}

    def play(self, row, league, date, player_records=False):
        """Apply one game and return team, offset and optional player records."""
        starting_elo = self.starting_elo
        league_share = self.league_share
        active_days = self.active_days
        rookie_penalty = self.rookie_penalty
        rookie_games = self.rookie_games
        move_down_bonus = self.move_down_bonus
        player_rd = self.player_rd
        player_rd_information = self.player_rd_information
        other_league_slope = self.other_league_slope
        has_league = self.has_league
        own = self.own
        player_league = self.player_league
        last_seen = self.last_seen
        members = self.members
        home = self.home
        season_counts = self.season_counts
        last_roster = self.last_roster
        main_roster = self.main_roster
        league_offset = self.league_offset
        played = self.played
        rd_variance = self.rd_variance
        elo_func = self.elo_func
        rosters = self.rosters
        window = pd.Timedelta(days=active_days)
        if player_rd is not None:
            rd_new, rd_min, rd_growth = player_rd

        def league_average(league, date):
            recent = [
                own[p]
                for p in members[league]
                if date is None
                or last_seen[p][0] is None
                or last_seen[p][0] >= date - window
            ]
            return sum(recent) / len(recent) if recent else starting_elo

        def eff(player):
            """Rating counted toward the team, after the logarithmic rookie discount."""
            games = played[player]
            discount = (
                rookie_penalty * (1 - math.log1p(games) / math.log1p(rookie_games))
                if rookie_games and games < rookie_games
                else 0.0
            )
            return own[player] - discount

        def seat(player, league, date):
            if player not in own:
                own[player] = (
                    league_average(league, date) if league is not None else starting_elo
                )
                player_league[player] = league
            elif player_league[player] != league:
                # Moving league (a transfer, promotion, a cup) keeps the player's rating.
                own[player] += (
                    league_offset[player_league[player]] - league_offset[league]
                )
                own[player] += _move_adjustment(
                    player_league[player], league, move_down_bonus
                )
                player_league[player] = league

        elo_records, offset_records, player_rows = [], [], []
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
            return sum(eff(p) for p in roster) / len(roster) + offset

        pre = [rating(side) for side in sides]
        if player_records:
            player_pre = {
                p: eff(p)
                + (league_offset[team_league] if team_league is not None else 0.0)
                for _, team_league, roster in sides
                for p in roster
            }
        slope_args = (
            {"expected_slope": other_league_slope}
            if domestic
            and league not in MAJOR_LEAGUES
            and other_league_slope is not None
            else {}
        )
        elo_change = elo_func(
            elo=pre[0],
            opponent_elo=pre[1],
            game_length=row.gamelength,
            result=row.result,
            **slope_args,
        )
        if player_rd is not None:
            weights = []
            # Information on the same expected-score slope the update used.
            slope = slope_args.get("expected_slope", EXPECTED_SLOPE)
            expectation = expected_score(pre[0], pre[1], slope=slope)
            information = (
                player_rd_information * slope**2 * expectation * (1 - expectation)
            )
            for _, _, roster in sides:
                side_weights = {}
                for player in roster:
                    variance = rd_variance.get(player, rd_new**2)
                    days = 0
                    if date is not None and player in last_seen:
                        seen = last_seen[player][0]
                        if seen is not None:
                            days = max(0, (date - seen).days)
                    variance = min(rd_new**2, variance + rd_growth**2 * days)
                    weight = variance / rd_min**2
                    side_weights[player] = weight
                    rd_variance[player] = max(
                        rd_min**2, 1 / (1 / variance + information)
                    )
                weights.append(side_weights)
            for (_, _, roster), change, side_weights in zip(
                sides, (elo_change, -elo_change), weights
            ):
                for player in roster:
                    own[player] += change * side_weights[player]
                    played[player] += 1
        else:
            for (_, _, roster), change in zip(sides, (elo_change, -elo_change)):
                for player in roster:
                    own[player] += change
                    played[player] += 1

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
                            eff(player) + offset_now,
                            team_league,
                            offset_now,
                        )
                    )
            main = main_roster[team]
            # Each player's own rating plus the offset of the league they sit in now.
            main_elo = sum(
                eff(p)
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

        for team in (row.teamid, row.opponent_teamid):
            self.team_last[team] = date
        return elo_records, offset_records, player_rows

    def player_rating(self, player):
        """Effective player rating with the offset of their current league."""
        if player not in self.own:
            return None
        games = self.played[player]
        discount = (
            self.rookie_penalty
            * (1 - math.log1p(games) / math.log1p(self.rookie_games))
            if self.rookie_games and games < self.rookie_games
            else 0.0
        )
        league = self.player_league[player]
        return (
            self.own[player]
            - discount
            + (self.league_offset[league] if league is not None else 0.0)
        )

    def team_rating(self, team):
        """Current effective main-roster rating, including current league offsets."""
        roster = self.main_roster.get(team)
        if roster is None:
            return None

        def eff(p):
            games = self.played[p]
            discount = (
                self.rookie_penalty
                * (1 - math.log1p(games) / math.log1p(self.rookie_games))
                if self.rookie_games and games < self.rookie_games
                else 0.0
            )
            return self.own[p] - discount

        return sum(
            eff(p)
            + (
                self.league_offset[self.player_league[p]]
                if self.player_league[p] is not None
                else 0.0
            )
            for p in roster
        ) / len(roster)

    def to_dict(self):
        """JSON-safe snapshot. Caller-supplied per-game rosters are excluded."""

        def encode(value):
            if isinstance(value, pd.Timestamp):
                return {"timestamp": value.isoformat()}
            if isinstance(value, (datetime.datetime, datetime.date)):
                return {"timestamp": value.isoformat()}
            if isinstance(value, tuple):
                return {"tuple": [encode(v) for v in value]}
            if isinstance(value, set):
                return {"set": [encode(v) for v in value]}
            if isinstance(value, dict):
                return {"dict": [[encode(k), encode(v)] for k, v in value.items()]}
            return value

        names = (
            "starting_elo",
            "league_share",
            "active_days",
            "rookie_penalty",
            "rookie_games",
            "move_down_bonus",
            "player_rd",
            "player_rd_information",
            "other_league_slope",
            "has_league",
        )
        mutable = (
            "own",
            "player_league",
            "last_seen",
            "members",
            "home",
            "season_counts",
            "last_roster",
            "main_roster",
            "league_offset",
            "played",
            "rd_variance",
            "team_last",
        )
        return {
            "schema": 1,
            "parameters": {k: encode(getattr(self, k)) for k in names},
            "state": {k: encode(getattr(self, k)) for k in mutable},
        }

    @classmethod
    def from_dict(cls, d, elo_func):
        """Restore a snapshot; attach input rosters separately before continuing."""
        if d["schema"] != 1:
            raise ValueError("Unsupported Elo state schema")

        def decode(value):
            if not isinstance(value, dict):
                return value
            if "timestamp" in value:
                return pd.Timestamp(value["timestamp"])
            if "tuple" in value:
                return tuple(decode(v) for v in value["tuple"])
            if "set" in value:
                return {decode(v) for v in value["set"]}
            return {decode(k): decode(v) for k, v in value["dict"]}

        obj = cls(elo_func, **{k: decode(v) for k, v in d["parameters"].items()})
        for k, v in d["state"].items():
            setattr(obj, k, decode(v))
        obj.members = defaultdict(set, obj.members)
        obj.league_offset = defaultdict(float, obj.league_offset)
        obj.played = defaultdict(int, obj.played)
        return obj


def compute_elo_records(
    games: pd.DataFrame,
    elo_func,
    starting_elo: float = STARTING_ELO,
    league_share: float = LEAGUE_SHARE,
    rosters: dict | None = None,
    active_days: int = ACTIVE_DAYS,
    player_records: bool = False,
    rookie_penalty: float = ROOKIE_PENALTY,
    rookie_games: int = ROOKIE_GAMES,
    move_down_bonus: float = MOVE_DOWN_BONUS,
    player_rd: tuple[float, float, float] | None = PLAYER_RD,
    player_rd_information: float = PLAYER_RD_INFORMATION,
    other_league_slope: float | None = OTHER_LEAGUE_SLOPE,
) -> tuple[pd.DataFrame, ...]:
    """Replay ordered games into team and league-offset frames, plus optional players.

    Team ratings average their starters plus the home-league offset. Home is the
    most-played domestic league this calendar year, with last year's home counting
    as one game and ties keeping the current home. Missing rosters reuse the last
    lineup or treat the team as one player. Main-roster ratings use the last lineup
    in the home league or an international event.

    New players start at the league's active-player average (last seen within
    active_days), or starting_elo when empty. Transfers preserve ratings through
    offset conversion; moving down from a major adds a stored move_down_bonus.
    The rookie_penalty counts only toward effective ratings, fading with
    log(1 + games) to zero at rookie_games; it never lowers the stored rating.

    player_rd is (new, floor, growth per sqrt(day)), or None to disable RD.
    Moves scale by RD²/floor². Variance grows by growth² × days away, capped at
    new², then shrinks to max(floor², 1/(1/RD² + player_rd_information ×
    s² × E × (1−E))), with s and E on the game's update slope. Information must be
    finite and positive.
    other_league_slope overrides the callback's expected-score slope only in
    non-major domestic events; None disables it. Cross-home international games
    also move both league offsets by league_share of the unscaled team change.

    games contains gameid, teamid, opponent_teamid, gamelength (seconds), result,
    and optional league/date. rosters maps (gameid, teamid) to starter IDs.
    Team records contain pre/post ratings, elo_change, home_league, league_offset
    and main_elo. Offset records contain gameid, date, league and league_offset.
    player_records adds starter pre/post ratings with home_league and offset;
    teams with no roster are omitted from that frame.
    """
    state = EloState(
        elo_func,
        starting_elo=starting_elo,
        league_share=league_share,
        rosters=rosters,
        active_days=active_days,
        rookie_penalty=rookie_penalty,
        rookie_games=rookie_games,
        move_down_bonus=move_down_bonus,
        player_rd=player_rd,
        player_rd_information=player_rd_information,
        other_league_slope=other_league_slope,
        has_league="league" in games.columns,
    )
    leagues = games["league"] if state.has_league else [None] * len(games)
    dates = (
        pd.to_datetime(games["date"])
        if "date" in games.columns
        else [None] * len(games)
    )
    elo_records, offset_records, player_rows = [], [], []
    for row, league, date in zip(games.itertuples(index=False), leagues, dates):
        teams, offsets, players = state.play(row, league, date, player_records)
        elo_records.extend(teams)
        offset_records.extend(offsets)
        player_rows.extend(players)

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


def _move_adjustment(old, new, down_bonus):
    """Stored bonus for a player moving from a major down to another league."""
    if old is not None and new is not None:
        if old in MAJOR_LEAGUES and new not in MAJOR_LEAGUES:
            return down_bonus
    return 0.0


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


def replay_state(
    games=None, rosters=None, elo_func=calculate_game_length_elo_change, **kwargs
):
    """Replay ordered inputs and retain their final resumable state."""
    games = load_elo_games() if games is None else games
    rosters = load_rosters() if rosters is None else rosters
    state = EloState(
        elo_func, rosters=rosters, has_league="league" in games.columns, **kwargs
    )
    for row in games.itertuples(index=False):
        state.play(
            row,
            getattr(row, "league", None),
            pd.Timestamp(row.date) if hasattr(row, "date") else None,
        )
    return state


def bootstrap_elo(method: str, starting_elo: int = STARTING_ELO, **overrides) -> None:
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
        **overrides,
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
