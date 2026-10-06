"""
build_site.py: Generates static HTML site for Prometheus rankings.
- Computes season stats (GLORY, and the sunset Record, Luck, GLORB and unadjusted
  GLORY) and forecasts (FORGE, Elo, and the sunset Form) from db/prometheus.db
- Computes player stats (Player Elo, and AURA per player-season)
- Fetches upcoming and recent matches from Leaguepedia, predicts them, and keeps
  a prediction log (prometheus.schedule); renders predictions.html
- Renders index.html, one rankings page per metric, and one page per team
- Outputs to output/ folder
"""

import json
import os
import re
import datetime
import hashlib
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from prometheus import alerts, aura, markets, schedule
from prometheus.evaluation import paired_bootstrap
from prometheus.elo import (
    get_elo_history,
    get_latest_elos,
    get_player_elos,
    get_player_history,
    get_season_elos,
)
from prometheus.form import form_states, load_form_games, opponent_adjust
from prometheus.forge import (
    CROSS_REGION_ELO_WEIGHT,
    ELO_WEIGHT,
    FORM_POINTS,
    forge_ratings,
    team_forms,
)
from prometheus.ranking import get_glory_ranking, load_glory_games
from prometheus.season import get_luck, get_record, load_season_games
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
STATIC_SRC = os.path.join(ROOT_DIR, "site_static")
SITE_DOMAIN = "prometheus.thaiv.dev"
SITE_URL = f"https://{SITE_DOMAIN}"
# Forecast pages open on teams that played within this window of the newest game.
ACTIVE_WINDOW = pd.Timedelta(days=183)

METRICS = {
    "glory": {
        "key": "glory",
        "name": "GLORY",
        "full_name": "Global League Offensive Rankings Yield",
        "question": "How well did a team play this season?",
        "description": "How well a team played: each team-season's gold and objective stats, weighted by how much each stat decided wins that year, with every game adjusted for how strong the opponent was.",
        "how_to_read": [
            "Score: roughly 0 to 100. Higher is better.",
            "Era Z: how far a team is above the average major-league team that year, in standard deviations. League Z: the same, compared only with its own league. +2 means two standard deviations above average.",
            "Weights are recalculated each year, so a 2015 team is judged by what won games in 2015. Opponent strength comes from each opponent's schedule-adjusted results over the whole season, so a big gold lead against a top team counts for more.",
            "GLORY needs about 8 games before a score is more signal than noise.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS. Team-seasons with fewer than 5 games are left out. Regions meet only at international events, so the gap between regions is measured loosely.",
        "lede_note": 3,
    },
    "record": {
        "key": "record",
        "name": "Record",
        "full_name": "Results, adjusted for schedule",
        "description": "What a team achieved: its wins and losses over the whole season, adjusted for who it played, with fast wins counting for more than slow ones.",
        "how_to_read": [
            "Record: the chance this team-season would beat the average major-league team of the same year in one game. 50 is average.",
            "Every game of the season counts, including international events, which is how regions are compared.",
            "A 15-minute stomp counts as nearly a full win, a 50-minute win as about two-thirds of one, as in Elo.",
        ],
        "caveats": "Shown for LCK, LPL, LEC and LCS teams with 5 or more games. Teams with few games are pulled slightly toward average. Regions meet only at international events.",
        "lede_note": 1,
        "value_word": "Record",
        "value_plural": "Records",
        "sunset_why": "Most of what it says is already in win % and Elo. GLORY still uses it behind the scenes to measure each opponent's strength.",
        "sunset": "Record is no longer developed. Win % and Elo already show most of what it shows, and the site now focuses on GLORY and the forecasts. GLORY still uses Record behind the scenes to adjust each game for the opponent's strength. This page and its numbers stay up so old links keep working.",
    },
    "luck": {
        "key": "luck",
        "name": "Luck",
        "full_name": "Wins above what a team's play earned",
        "description": "Who won more, or fewer, games than their play deserved. Earned wins come from GLORY's model of each game's stats, so a team that keeps winning games it was behind in shows up as lucky.",
        "how_to_read": [
            "Luck: wins above (or below) what the team's gold and objective stats earned, over the season. +3 means three more wins than its play earned.",
            "Earned: the win % a team's stats were worth, after correcting the per-game model, which pulls everyone toward 50%.",
            "Luck repeats only a little from one half of a season to the other, so most of it is luck. The part that repeats may be real skill the stats miss, such as closing out games.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS team-seasons with 5 or more games. Not adjusted for schedule.",
        "lede_note": 1,
        "value_word": "luck",
        "value_plural": "luck",
        "sunset_why": "Mostly noise: it barely repeats from one half of a season to the other.",
        "sunset": "Luck is no longer developed. It barely repeats from one half of a season to the other (reliability 0.34), so it says little about a team. This page and its numbers stay up so old links keep working.",
    },
    "glory_unadjusted": {
        "key": "glory_unadjusted",
        "name": "GLORY (unadjusted)",
        "full_name": "GLORY before the opponent adjustment",
        "description": "GLORY as it was first published: the same stats and yearly weights, with no adjustment for opponent strength.",
        "how_to_read": [
            "Score: roughly 0 to 100. Higher is better.",
            "Era Z and League Z: same as on GLORY.",
            "Teams in weaker leagues score higher here than on GLORY, because their stats came against weaker opponents.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS. Team-seasons with fewer than 5 games are left out.",
        "lede_note": 3,
        "sunset_why": "Replaced by GLORY, which now adjusts every game for the opponent's strength. The adjusted score is more stable from one half of a season to the other.",
        "sunset": "This is GLORY without the opponent adjustment. GLORY now adjusts every game for the opponent's strength, which makes it more stable and fairer to teams with hard schedules. Use GLORY instead. This page stays up for comparison and old links.",
    },
    "glorb": {
        "key": "glorb",
        "name": "GLORB",
        "full_name": "Global League Offensive Rankings Baseline",
        "description": "The same stats as GLORY, all weighted equally. Compare it with GLORY to see how much the yearly weights change the order.",
        "how_to_read": [
            "Score: the equal-weight sum of standardized stats, centred near 80. Higher is better.",
            "Era Z and League Z: same as on GLORY.",
            "A team ranked much higher on GLORY than on GLORB was strong in the stats that mattered most that year.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS. Team-seasons with fewer than 5 games are left out.",
        "baseline": True,
        "lede_note": 3,
        "sunset_why": "Built as a yardstick for GLORY. On its own it predicts winners no better than a team's win % so far.",
        "sunset": "GLORB is no longer developed. It was built as a yardstick for GLORY, and on its own it adds little: tested on every major-league game since 2014, it predicts winners no better than a team's win % so far. Use GLORY instead. This page and its numbers stay up so old links keep working.",
    },
}

# Retired pages that now point somewhere else; listed on the Sunset stats page.
FOLDED = [
    {
        "key": "glory_plus",
        "name": "GLORY+",
        "full_name": "GLORY, adjusted for opponent strength",
        "href": "glory.html",
        "link_text": "Now part of GLORY",
        "sunset_why": "Folded into GLORY, which is now always opponent-adjusted. GLORY+ measured opponents by their Elo going into each game, a forecast; GLORY uses each opponent's Record for the whole season, so a season stat depends only on that season.",
    },
]

ELO_METRICS = {
    "game_length_elo": {
        "key": "game_length_elo",
        "name": "Elo",
        "title": "Team Elo",
        "full_name": "Game-Length Adjusted Elo",
        "question": "How strong is a team now, judged by its results?",
        "method": "game_length",
        "description": "A rating for every team in every region, updated after each game and built from its players: a team's Elo is the average of its five starters' ratings. Wins over stronger teams and faster wins raise it more.",
        "how_to_read": [
            "Every player has a rating, and a team's Elo is the average of its five starters. Each game moves the winning starters up and the losing starters down by the same amount, so players keep their ratings when they change teams. A new player starts at the average of the league's active players.",
            "Short games move ratings most. A heavy favourite that needs 50 minutes to win can still lose a little rating.",
            "The table opens on teams that have played in the last six months, at today's rating. Pick a season to rank every team by its rating at the end of that year, or several seasons to compare across years.",
            "International results also move a shared rating for each league, so when a region's teams win abroad, every team in that region rises, even those that stayed home.",
        ],
        "caveats": "Regions meet only at international events, so a league that rarely plays abroad is measured loosely. Team names are taken from each team's last game in the period shown.",
        "lede_note": 2,
    }
}

FORECASTS = {
    "forge": {
        "key": "forge",
        "name": "FORGE",
        "full_name": "Form and Elo, forged into a forecast",
        "question": "Who wins if two teams play today?",
        "description": "Who would win a game today. Each team's Elo plus its Form, the recent play that Elo misses, weighted by what best predicted past games.",
        "how_to_read": [
            "Rating: Elo plus Form, both in Elo points. Form is how much better than its own league a team has played lately, from its recent gold and objective stats, each game adjusted for the opponent's Elo. Recent games count most: a game's weight halves every 20 games.",
            "Head to head turns two ratings into a chance to win one game. Between teams from different leagues it uses Elo alone, because Form only compares a team with its own league. It ignores side; blue side wins about 54% of games.",
            "Tested on every major-league game since 2014, using only earlier games each time: it picks the winner 64.7% of the time within a league, and its odds are more accurate than Elo's alone.",
            "The table opens on current ratings for teams that have played in the last six months. Pick a season to see ratings at the end of that year.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS teams. Regions meet only at international events, so a league that rarely plays abroad is measured loosely. Odds are for one game, not a series.",
        "lede_note": 3,
        "matchup": True,
    },
    "form": {
        "key": "form",
        "name": "Form",
        "full_name": "Predictive GLORY: recent play against the league",
        "description": "How well a team has been playing lately compared with the rest of its league, from its recent gold and objective stats. Built to predict the next game, not to describe a season.",
        "how_to_read": [
            "Form: in Elo points above or below the team's league average. +100 means it has played like a team about 100 Elo points better than its league's average.",
            "Recent games count most: a game's weight halves every 20 games, and a new season starts from half of last season's weight. Each game's stats are adjusted for the opponent's Elo going into it.",
            "Form compares a team only with its own league; to compare regions, use Elo or FORGE.",
            "The table opens on teams that have played in the last six months. Pick a season to see Form at the end of that year.",
        ],
        "caveats": "Form is relative to each league, so a +100 in a weak league is not a +100 in a strong one. Teams with few games are pulled toward their league's average.",
        "sunset": "Form is no longer shown as a stat of its own. Alone it predicts winners no better than Elo within a league, and clearly worse between leagues. Added to Elo it does help, so it lives on inside FORGE, whose register shows each team's Form as a column. This page stays up so old links keep working.",
        "sunset_why": "Folded into FORGE. Tested on every major-league game since 2014, Form alone predicts no better than Elo within a league and worse between leagues; added to Elo, it makes FORGE's odds more accurate than Elo's alone.",
        "lede_note": 1,
        "value_word": "Form",
        "value_plural": "Form",
    },
}

PLAYER_METRICS = {
    "player_elo": {
        "key": "player_elo",
        "name": "Elo",
        "title": "Player Elo",
        "full_name": "Game-length Elo for every player",
        "question": "How have a player's teams done, across a career?",
        "entity": "player",
        "description": "The rating behind team Elo, for each player: every game moves the five starters together, and the rating follows a player from team to team.",
        "how_to_read": [
            "A team's Elo is the average of its five starters. After each game every starter moves by the team's change, so a player's rating is a record of how the teams they played on did, carried with them through transfers.",
            "Teammates move together, so five players who have only played together share one rating. Ratings differ because of where each player played before. It does not split credit within a team.",
            "A new player starts at the average of the league's active players. Short games move ratings most, and international results move a shared rating for each league, as for team Elo.",
            "The table opens on players who have played in the last six months, at today's rating. Pick a season to rank LCK, LPL, LEC and LCS players with 10 or more games that year by their rating at the end of it.",
        ],
        "caveats": "Listed: players who have played in the LCK, LPL, LEC or LCS or at an international event, or anywhere in the last two years. Names, roles and teams are from each player's last game in the period shown. Players without an Oracle's Elixir id are tracked by name and team, so their careers split at each transfer.",
        "lede_note": 2,
        "value_word": "Elo",
        "value_plural": "ratings",
    },
    "aura": {
        "key": "aura",
        "name": "AURA",
        "full_name": "Attributable Utility via Role Analytics",
        "question": "How much did a player's own play swing their team's chances?",
        "entity": "player",
        "description": "How much each player moved their team's chance of winning, from their own lane: how far ahead of their lane opponent they were at 15 minutes, plus how much more than their teammates they gained after that.",
        "how_to_read": [
            "AURA is in win-chance points per game. +4 means the player's play was worth about 4 percentage points of their team's chance to win each game, compared with an even lane. The two players in a lane always get opposite scores, so 0 is even with the lane opponent.",
            "Role Z: how far a player-season is above the average one in the same role that year, in standard deviations. Lanes swing games by different amounts (bot laners' scores spread about twice as wide as supports'), so compare across roles with Role Z.",
            "Each year a win-probability model reads every game at 15 minutes from the five lanes: gold, XP, CS, kills, deaths and assists against the lane opponent. A player's share is their lane's part of that chance, plus a quarter of how much more their own part grew than their teammates' between 15 and 25 minutes.",
            "A season needs about 22 games before AURA is more signal than noise, so the register lists player-seasons with 20 or more games. Tested on players who changed teams, it follows the player better than lane gold or win %.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS games. Oracle's Elixir has no minute-by-minute data for most LPL games in 2016–2017 and 2021–2025, so LPL players are missing in those years. AURA credits a player's lane: it doesn't see objectives or fights after 25 minutes, and a jungler or support is measured against the opposing jungler or support.",
        "lede_note": 1,
        "value_word": "AURA",
        "value_plural": "AURA scores",
    },
}

# The header has one menu per entity, Teams and Players, each listing its stats by
# name with the question it answers; the home contents follow the same split.
# Retired metrics keep their pages but leave the menus: the Teams menu ends with
# a "Sunset stats" link to a page listing them.
SECTIONS = [
    {
        "name": "Teams",
        "metrics": [
            *(m for m in METRICS.values() if not m.get("sunset")),
            *(m for m in FORECASTS.values() if not m.get("sunset")),
            *ELO_METRICS.values(),
        ],
    },
    {"name": "Players", "metrics": list(PLAYER_METRICS.values())},
]
SUNSET = [*FOLDED, *(m for m in [*METRICS.values(), *FORECASTS.values()] if m.get("sunset"))]
NAV = [
    {
        "name": s["name"],
        "links": [
            {"key": m["key"], "name": m["name"], "title": m.get("title", m["name"]), "question": m["question"]}
            for m in s["metrics"]
        ],
    }
    for s in SECTIONS
]
PREDICTIONS = {
    "key": "predictions",
    "name": "Predictions",
    "full_name": "Every match we rate, called before it's played",
    "question": "Who wins the matches coming up?",
    "description": "Each team's chance of winning every scheduled pro match between teams we rate, and how past calls did.",
    "how_to_read": [
        "Figures beside the bar: each team's chance of taking the series, in 100. It follows from the one-game chance, so a favourite is a bigger favourite over five games than one.",
        "Same major league (LCK, LPL, LEC, LCS): FORGE. Any other pairing: Elo, across leagues on a curve fit to international games.",
        "Calls refresh daily and freeze at the start. Matches played before the log began carry a call rebuilt from the day before; the weights saw those games, so trust saved calls more.",
        "Log loss: lower is better; a coin flip scores 0.693. Table II scores the one-game chance per game, Table III the series chance per series.",
        "Kalshi is a prediction market. Its figure is the market's series chance (mid of bid and offer), read hourly (before 6 Oct, from Kalshi's price history) and frozen at the start; the caret on the bar marks it. Over 2,180 past series it beat us; 12 hours out, FORGE tied it in the major leagues. Alerts flag FORGE calls 5 points above Kalshi's price; closing line value is the last price minus the alerted one, above 0 when the market moved our way.",
    ],
    "caveats": "Schedule from Leaguepedia; teams Oracle's Elixir doesn't cover aren't shown. Calls ignore side selection, roster changes and new patches. Times are local.",
}
# The home page lists this many upcoming major-league and international matches,
# within this many days.
HOME_FIXTURES = 10
HOME_FIXTURE_DAYS = 4
# The day's Kalshi alert (title and body of a GitHub issue), written only when
# there is one; the publish workflow posts it. Never published to the site.
KALSHI_ALERT = os.environ.get("KALSHI_ALERT", os.path.join(ROOT_DIR, "data", "kalshi_alert.json"))
# The market backtest's paper bets by edge (written by evaluate_markets.py), shown
# beside the log's on the Predictions page.
MARKET_BETS = os.path.join(ROOT_DIR, "docs", "market_bets.json")
# The prediction log; CI restores it from and saves it to the data backup bucket.
PREDICTIONS_LOG = os.environ.get("PREDICTIONS_LOG", os.path.join(ROOT_DIR, "data", "predictions.json"))

# Players get a page if they ever played in a major league or at an international
# event, or played anywhere within this window of the newest game.
PLAYER_PAGE_WINDOW = pd.Timedelta(days=730)
# The player register's past seasons: major-league player-seasons with this many games.
PLAYER_SEASON_GAMES = 10

env = Environment(
    loader=FileSystemLoader(os.path.join(ROOT_DIR, "templates")), autoescape=True
)
env.globals.update(
    nav=NAV,
    predictions_nav=PREDICTIONS,
    sunset_keys=[m["key"] for m in SUNSET],
    site_url=SITE_URL,
    major_leagues=[l.value for l in ALL_MAJOR_LEAGUES],
)


def _longdate(value: str) -> str:
    """'2024-09-08' -> '8 Sep 2024' for dates set in running prose."""
    try:
        d = datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return str(value)
    return f"{d.day} {d.strftime('%b')} {d.year}"


env.filters["longdate"] = _longdate
env.filters["shortdate"] = lambda v: _longdate(v).rsplit(" ", 1)[0]  # '2 Sep'
# Elo series embedded in team and player pages as [date, elo] pairs, about half the
# size of {date, elo} objects across ~7,000 pages.
env.filters["compact_series"] = lambda series: [[d["date"], round(d["elo"])] for d in series]


def _slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "team"


env.filters["slugify"] = _slugify


def _write(path, html):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(html)


def _asset_url(path: str) -> str:
    """'css/base.css' -> 'css/base.css?v=<content hash>'.

    A changed file gets a new URL, so browsers never pair new HTML with a cached
    old stylesheet or script.
    """
    digest = hashlib.sha256((Path(STATIC_SRC) / path).read_bytes()).hexdigest()[:10]
    return f"{path}?v={digest}"


env.globals["asset"] = _asset_url


def copy_static():
    if not os.path.isdir(STATIC_SRC):
        raise RuntimeError("Missing site_static directory.")
    for sub in ("css", "js", "fonts"):
        dest_dir = Path(OUTPUT_DIR) / sub
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(Path(STATIC_SRC) / sub, dest_dir)
    shutil.copy2(Path(STATIC_SRC) / "favicon.svg", Path(OUTPUT_DIR) / "favicon.svg")


def _rankings(games, minimum_matches, z_scores, baseline=False, opponent_adjusted=False, record=None):
    return get_glory_ranking(
        year=sorted(games),
        league=ALL_MAJOR_LEAGUES,
        games=games,
        baseline=baseline,
        z_scores=z_scores,
        minimum_matches=minimum_matches,
        opponent_adjusted=opponent_adjusted,
        record=record,
    )


def _forecast_records(now, seasons, rating_cols):
    """Rows for a forecast page: `now` rows (current ratings) then team-season rows.

    A `now` row is shown by default when it is `active` (missing means active).
    """
    rows = []
    for df, is_now in ((now, True), (seasons, False)):
        for r in _records(df):
            r["now"] = is_now
            r["active"] = bool(r.get("active", True))
            r["latest_date"] = str(r["latest_date"])[:10]
            for col in rating_cols:
                r[col] = round(float(r[col]), 1)
            rows.append(r)
    return rows


def _records(df):
    df = df.copy()
    df["slug"] = df["teamname"].apply(_slugify)
    df["year"] = df["year"].astype(int)
    return df.to_dict(orient="records")


# Rows in each of the home page's top-of-register tables.
HOME_TOP = 10


def _rating_bar(values):
    """Bar lengths (0-100) on the scale the metric's own page uses: whole hundreds
    of Elo points around every value in its register."""
    lo = np.floor(values.min() / 100) * 100
    hi = np.ceil(values.max() / 100) * 100
    return lambda v: round(float((v - lo) / (hi - lo) * 100), 1)


def render_index(forge_rows, team_elo_rows, player_rows, entry_counts, forge_config, last_update, fixtures=None):
    """Home: FORGE's head to head and top teams, then the top of team and player Elo.

    Each `*_rows` argument holds the register's "now" rows (every current team or
    player); the active ones lead the tables, scaled like their own pages.
    """

    def top(rows, value_key):
        df = pd.DataFrame(rows)
        bar = _rating_bar(df[value_key])
        df = df[df["active"]].sort_values(value_key, ascending=False).head(HOME_TOP)
        return [{**r, "bar": bar(r[value_key])} for r in df.to_dict(orient="records")]

    forge_now = [r for r in forge_rows if r["now"]]
    _write(
        os.path.join(OUTPUT_DIR, "index.html"),
        env.get_template("index.html.j2").render(
            page_key="index",
            root_path="",
            last_update=last_update,
            sections=SECTIONS,
            entry_counts=entry_counts,
            forge=FORECASTS["forge"],
            forge_top=top(forge_now, "forge"),
            forge_rows=sorted(forge_now, key=lambda r: -r["forge"]),
            forge_config=forge_config,
            fixtures=fixtures or [],
            team_elo=ELO_METRICS["game_length_elo"],
            team_elo_top=top([r for r in team_elo_rows if r["now"]], "elo"),
            player_elo=PLAYER_METRICS["player_elo"],
            player_elo_top=top([r for r in player_rows if r["now"]], "elo"),
        ),
    )


def render_rankings_page(metric, rows, config, filters, last_update):
    _write(
        os.path.join(OUTPUT_DIR, f"{metric['key']}.html"),
        env.get_template("rankings.html.j2").render(
            page_key=metric["key"],
            root_path="",
            metric=metric,
            rows=rows,
            config=config,
            filters=filters,
            last_update=last_update,
        ),
    )


METRIC_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "score", "label": "Score", "type": "number", "digits": 2, "bar": True, "note": 1},
    {"key": "era_score", "label": "Era Z", "type": "number", "digits": 2, "signed": True,
     "hint": "Standard deviations above the average major-league team that year", "phoneHide": True, "note": 2},
    {"key": "league_score", "label": "League Z", "type": "number", "digits": 2, "signed": True,
     "hint": "Standard deviations above the average team in its league that year", "wideOnly": True, "note": 2},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]

RECORD_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "record", "label": "Record", "type": "number", "digits": 1, "bar": True, "note": 1,
     "hint": "Chance to beat the average major-league team that year"},
    {"key": "win_pct", "label": "Win %", "type": "number", "digits": 1, "phoneHide": True},
    {"key": "games", "label": "Games", "type": "number", "digits": 0, "wideOnly": True, "note": 2},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]

LUCK_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "luck_wins", "label": "Luck", "type": "number", "digits": 1, "signed": True, "note": 1,
     "hint": "Wins above what the team's play earned"},
    {"key": "win_pct", "label": "Win %", "type": "number", "digits": 1, "phoneHide": True},
    {"key": "expected", "label": "Earned", "type": "number", "digits": 1, "phoneHide": True, "note": 2,
     "hint": "The win % the team's stats were worth"},
    {"key": "games", "label": "Games", "type": "number", "digits": 0, "wideOnly": True},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]

FORGE_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "forge", "label": "Rating", "type": "number", "digits": 0, "bar": True, "note": 1},
    {"key": "form", "label": "Form", "type": "number", "digits": 0, "signed": True, "phoneHide": True,
     "hint": "Elo points above or below its league's average, from recent play"},
    {"key": "elo", "label": "Elo", "type": "number", "digits": 0, "wideOnly": True,
     "hint": "Elo now, or at the end of the season shown"},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 4},
]

FORM_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "form", "label": "Form", "type": "number", "digits": 0, "signed": True, "bar": True, "note": 1},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True, "note": 3},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 4},
    {"key": "latest_date", "label": "Last game", "type": "date", "wideOnly": True},
]

ELO_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "elo", "label": "Elo", "type": "number", "digits": 0, "bar": True, "note": 1},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 3},
    {"key": "latest_date", "label": "Last game", "type": "date", "wideOnly": True},
]


PLAYER_ELO_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "playername", "label": "Player", "type": "player"},
    {"key": "elo", "label": "Elo", "type": "number", "digits": 0, "bar": True, "note": 1},
    {"key": "position", "label": "Role", "type": "role", "phoneHide": True},
    {"key": "teamname", "label": "Team", "type": "teamref", "wideOnly": True},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 4},
]


AURA_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "playername", "label": "Player", "type": "player"},
    {"key": "aura", "label": "AURA", "type": "number", "digits": 1, "signed": True, "bar": True, "note": 1,
     "hint": "Win-chance points per game, against an even lane"},
    {"key": "role_z", "label": "Role Z", "type": "number", "digits": 2, "signed": True, "phoneHide": True, "note": 2,
     "hint": "Standard deviations above the average player-season in the same role that year"},
    {"key": "position", "label": "Role", "type": "role", "phoneHide": True},
    # The team carries its league mark instead of a League column, so the register fits beside the margin.
    {"key": "teamname", "label": "Team", "type": "teamref", "mark": True, "wideOnly": True},
    {"key": "games", "label": "Games", "type": "number", "digits": 0, "wideOnly": True, "note": 4},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]


def aura_rows_and_seasons(seasons, slugs):
    """AURA register rows (qualified player-seasons of listed players) and each listed player's seasons.

    `seasons` is `aura.season_aura` output; `slugs` maps playerid to page slug.
    Returns (rows, {slug: [season, ...] newest first}).
    """
    listed = seasons[seasons["playerid"].isin(slugs.index)].assign(slug=lambda d: d["playerid"].map(slugs))
    listed = listed.assign(aura=listed["aura"].round(2), role_z=listed["role_z"].round(2))
    qualified = listed[listed["qualified"]]
    cols = ["slug", "playername", "position", "teamname", "league", "year", "games", "aura", "role_z"]
    rows = qualified[cols].to_dict(orient="records")
    by_player = {}
    for r in listed.sort_values(["year", "games"], ascending=[False, False]).itertuples():
        by_player.setdefault(r.slug, []).append(
            {
                "year": int(r.year),
                "teamname": r.teamname,
                "team_slug": _slugify(r.teamname),
                "league": r.league,
                "position": r.position,
                "games": int(r.games),
                "aura": float(r.aura),
                "role_rank": int(r.role_rank) if r.qualified else None,
                "role_count": int(r.role_count) if r.qualified else None,
            }
        )
    return rows, by_player


def _team_pages(glory_df, forge_seasons, forge_now, elo_history, latest_elos, glory_qualified, rosters=None):
    """Return {slug: context} for every team with GLORY data or Elo history.

    Each season carries GLORY (every team-season with a game) and FORGE at the
    end of that year. `forge_now` gives the current FORGE.
    """

    # Rank of each qualified team-season within its year, for team pages.
    q = glory_qualified[["teamname", "year", "score"]].copy()
    q["year_rank"] = q.groupby("year")["score"].rank(ascending=False, method="min").astype(int)
    q["field"] = q.groupby("year")["score"].transform("size").astype(int)
    year_rank = {(t, int(y)): (int(r), int(f)) for t, y, r, f in q[["teamname", "year", "year_rank", "field"]].itertuples(index=False)}

    key = ["teamname", "year"]
    seasons = (
        glory_df[["teamname", "year", "league", "score"]]
        .rename(columns={"score": "glory"})
        .merge(forge_seasons[key + ["forge"]].drop_duplicates(key), on=key, how="left")
    )
    forge_current = forge_now.drop_duplicates("teamname").set_index("teamname")["forge"]

    latest = latest_elos.set_index("teamname")
    pages = {}
    teams = sorted(set(seasons["teamname"]) | set(elo_history["teamname"]))
    seasons_by_team = dict(tuple(seasons.groupby("teamname")))
    elo_by_team = dict(tuple(elo_history.groupby("teamname")))
    value = lambda v, digits: None if pd.isna(v) else round(float(v), digits)

    for team in teams:
        slug = _slugify(team)
        series = []
        if team in seasons_by_team:
            for row in seasons_by_team[team].sort_values("year").itertuples():
                year = int(row.year)
                series.append(
                    {
                        "year": year,
                        "league": row.league,
                        "glory": value(row.glory, 2),
                        "forge": None if pd.isna(row.forge) else round(float(row.forge)),
                        "year_rank": year_rank.get((team, year), (None, None))[0],
                        "field": year_rank.get((team, year), (None, None))[1],
                    }
                )
        elo_series = []
        if team in elo_by_team:
            elo_series = [
                {"date": str(d)[:10], "elo": round(float(v), 1)}
                for d, v in zip(elo_by_team[team]["date"], elo_by_team[team]["post_match_elo"])
            ]
        current = latest.loc[team] if team in latest.index else None
        if isinstance(current, pd.DataFrame):  # duplicate team names across ids
            current = current.iloc[0]
        elo_summary = None
        if elo_series:
            peak = max(elo_series, key=lambda d: d["elo"])
            low = min(elo_series, key=lambda d: d["elo"])
            elo_summary = {"games": len(elo_series), "peak": peak, "low": low,
                           "first": elo_series[0], "last": elo_series[-1]}
        ranked = [s for s in series if s["glory"] is not None]
        best = max(ranked, key=lambda s: s["glory"]) if ranked else None
        leagues = sorted({s["league"] for s in series})
        pages[slug] = {
            "teamname": team,
            "slug": slug,
            "series": series,
            "elo_series": elo_series,
            "elo_summary": elo_summary,
            "best": best,
            "current_elo": None if current is None else round(float(current["elo"])),
            "current_forge": round(float(forge_current[team])) if team in forge_current.index else None,
            "current_league": None if current is None else current["league"],
            "leagues": leagues or ([current["league"]] if current is not None else []),
            "roster": (rosters or {}).get(team),
        }
    return pages


def _pct_pair(p):
    """A chance as two whole numbers that add to 100, never 0 or 100."""
    a = min(99, max(1, round(p * 100)))
    return a, 100 - a


def fixture_row(entry, team_slugs):
    """One match as the fixture register shows it.

    `team_slugs` holds the slugs of teams that have a page, so names link only
    when there is somewhere to go.
    """
    start = datetime.datetime.strptime(entry["start"], "%Y-%m-%dT%H:%MZ")
    pct1, pct2 = _pct_pair(entry["p_series"])
    game1, game2 = _pct_pair(entry["p_game"])
    row = {
        "id": entry["match_id"],
        "start": entry["start"],
        "day": start.strftime("%Y-%m-%d"),
        "time": start.strftime("%H:%M"),
        "league": entry["league"],
        "event": entry.get("event") or "",
        "best_of": entry["best_of"],
        "pct1": pct1,
        "pct2": pct2,
        "game1": game1,
        "game2": game2,
        "fav": 1 if entry["p_series"] > 0.5 else 2 if entry["p_series"] < 0.5 else 0,
        "method": "FORGE" if entry["method"] == "forge" else "Elo",
        "cross": entry["method"] == "elo-cross",
        "reconstructed": bool(entry.get("reconstructed")),
        "winner": entry.get("winner"),
    }
    market = entry.get("market")
    if market:
        row["mkt1"], row["mkt2"] = _pct_pair(market["p"])
        at = datetime.datetime.strptime(market["at"], "%Y-%m-%dT%H:%MZ")
        row["mkt_at"] = f"{at.day} {at.strftime('%b')} {at.strftime('%H:%M')} UTC"
        row["mkt_url"] = markets.event_url(market["ticker"]) if market.get("ticker") else None
    for side in (1, 2):
        name = schedule.display_name(entry, side)
        slug = _slugify(entry[f"ours{side}"]) if entry.get(f"ours{side}") else None
        row[f"name{side}"] = name
        row[f"slug{side}"] = slug if slug in team_slugs else None
    if row["winner"] in (1, 2):
        s1, s2 = entry.get("score1"), entry.get("score2")
        row["score"] = f"{s1}–{s2}" if s1 is not None and s2 is not None else ("W–L" if row["winner"] == 1 else "L–W")
        row["call"] = "even" if row["fav"] == 0 else ("right" if row["fav"] == row["winner"] else "missed")
    return row


def _by_day(rows):
    """[(day ISO, label, rows)] in the order the rows come."""
    days = []
    for r in rows:
        if not days or days[-1][0] != r["day"]:
            d = datetime.date.fromisoformat(r["day"])
            days.append((r["day"], f"{d.strftime('%A')} {d.day} {d.strftime('%B')}", []))
        days[-1][2].append(r)
    return [{"day": d, "label": label, "rows": rs} for d, label, rs in days]


def predictions_view(log, team_slugs, now):
    """Upcoming and past fixture rows, the scorecard, and the home page's fixtures.

    Only matches between two teams we rate are shown. Upcoming: not started,
    soonest first. Past: started, newest first (a started match without a result
    yet shows as awaiting one).
    """
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    entries = [e for e in log.values() if e.get("matched")]
    upcoming = sorted((e for e in entries if e["start"] > now_s), key=lambda e: (e["start"], e["match_id"]))
    past = sorted((e for e in entries if e["start"] <= now_s), key=lambda e: (e["start"], e["match_id"]), reverse=True)
    up_rows = [fixture_row(e, team_slugs) for e in upcoming]
    horizon = (now + datetime.timedelta(days=HOME_FIXTURE_DAYS)).strftime("%Y-%m-%dT%H:%MZ")
    home = [fixture_row(e, team_slugs) for e in upcoming if schedule.is_major(e) and e["start"] <= horizon][:HOME_FIXTURES]
    leagues = {e["league"] for e in entries}
    majors = env.globals["major_leagues"]
    return {
        "upcoming": _by_day(up_rows),
        "past": _by_day([fixture_row(e, team_slugs) for e in past]),
        "upcoming_count": len(up_rows),
        "past_count": len(past),
        "scorecard": schedule.scorecard(entries),
        "vs_market": schedule.market_scorecard(entries),
        "edges": edge_groups(schedule.edge_record(entries), entries),
        "alerts": alert_record(entries),
        "market_min": schedule.MARKET_MIN_SERIES,
        "home": _by_day(home),
        "home_count": len(home),
        "leagues": [l for l in majors if l in leagues]
        + [l for l in INTERNATIONAL_LEAGUES if l in leagues]
        + sorted(leagues - set(majors) - set(INTERNATIONAL_LEAGUES)),
        "major_set": [l for l in [*majors, *INTERNATIONAL_LEAGUES] if l in leagues or l in majors],
        "since": min((e["start"][:10] for e in entries), default=None),
        "saved_since": min((e["start"][:10] for e in entries if not e.get("reconstructed")), default=None),
    }


def edge_groups(rows, entries, path=None):
    """Table IV's row groups: for FORGE and then Elo, the log's paper bets since
    its first priced match and the backtest's (`MARKET_BETS`, when present)."""
    path = path or MARKET_BETS
    backtest = json.loads(open(path).read()) if os.path.exists(path) else None
    priced = [e["start"][:10] for e in entries if e.get("market_12h") and e.get("winner") in (1, 2)]
    since = min(priced, default=None)
    groups = []
    for label in ("FORGE", "Elo"):
        sources = [{"name": "since", "since": since, "rows": [r for r in rows if r["label"] == label]}]
        if backtest:
            sources.append(
                {
                    "name": "backtest",
                    "from": backtest["from"],
                    "to": backtest["to"],
                    "rows": [r for r in backtest["rows"] if r["label"] == label],
                }
            )
        groups.append({"label": label, "sources": sources})
    return groups


def alert_record(entries):
    """The paper record of the Kalshi alerts for the Predictions page: settled,
    won, mean CLV and share beating the close, and ROI after the 7% taker fee,
    with a 95% bootstrap interval once there are enough bets."""
    bets = alerts.settled_alerts({e["match_id"]: e for e in entries})
    clv, beat = alerts.clv_summary(bets)
    profits = [b["profit"] for b in bets]
    roi = interval = None
    if profits:
        roi = sum(profits) / len(profits)
        if len(profits) >= schedule.MARKET_MIN_SERIES:
            _, lo, hi = paired_bootstrap(profits, [0.0] * len(profits))
            interval = (float(lo), float(hi))
    return {
        "settled": len(bets),
        "won": sum(b["won"] for b in bets),
        "clv": clv,
        "beat": beat,
        "roi": roi,
        "interval": interval,
    }


def render_predictions(view, coverage, last_update):
    _write(
        os.path.join(OUTPUT_DIR, "predictions.html"),
        env.get_template("predictions.html.j2").render(
            page_key="predictions",
            root_path="",
            metric=PREDICTIONS,
            view=view,
            coverage=coverage,
            last_update=last_update,
        ),
    )


def update_predictions(states):
    """Fetch the schedule and update the prediction log; on any failure keep the
    log as it was, so the site still builds (with yesterday's calls).

    Set PREDICTIONS_FETCH=0 to skip the fetch. Returns (log, coverage) where
    coverage counts this fetch's matched and unmatched matches (None if skipped).
    """
    if os.environ.get("PREDICTIONS_FETCH", "1") == "0":
        return schedule.load_log(PREDICTIONS_LOG), None
    try:
        log, coverage = schedule.build_predictions(states, PREDICTIONS_LOG)
        print(f"Predictions: {coverage['matched']} of {coverage['matches']} scheduled matches rated; "
              f"{len(coverage['unmatched'])} team names not matched; "
              f"{coverage.get('priced') if coverage.get('priced') is not None else 'no'} priced by Kalshi")
        return log, coverage
    except Exception as e:  # network, rate limit, schema change: never block the build
        print(f"Predictions: schedule not updated ({e}); using the saved log.")
        return schedule.load_log(PREDICTIONS_LOG), None


def write_kalshi_alert(log, coverage, team_slugs, path=None):
    """Record this build's alerts in the log and write the day's issue to `path`
    (`alerts.update`). Runs only on fresh prices (this build's fetch worked) and
    unless KALSHI_ALERTS=0. A stale file from an earlier run is always removed,
    so a day without alerts posts nothing. Returns the issue dict or None."""
    path = path or KALSHI_ALERT
    if os.path.exists(path):
        os.remove(path)
    if os.environ.get("KALSHI_ALERTS", "1") == "0" or not coverage or not coverage.get("priced"):
        return None
    now = datetime.datetime.strptime(coverage["at"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)
    alert = alerts.update(log, now, coverage.get("data_through"), _slugify, team_slugs)
    schedule.save_log(log, PREDICTIONS_LOG)
    if alert is None:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(alert, f, ensure_ascii=False)
    print(f"Kalshi alert: {alert['new']} new match(es); issue written to {path}")
    return alert


def render_sunset(last_update):
    _write(
        os.path.join(OUTPUT_DIR, "sunset.html"),
        env.get_template("sunset.html.j2").render(
            page_key="sunset", root_path="", metrics=SUNSET, last_update=last_update
        ),
    )


def render_redirect(key, target, title, last_update):
    """A retired page that sends visitors (and search engines) to its replacement."""
    _write(
        os.path.join(OUTPUT_DIR, f"{key}.html"),
        env.get_template("redirect.html.j2").render(
            page_key=key, root_path="", target=target, title=title, last_update=last_update
        ),
    )


def render_404(last_update):
    # CloudFront serves 404.html for any missing path, so links must be root-absolute.
    _write(
        os.path.join(OUTPUT_DIR, "404.html"),
        env.get_template("404.html.j2").render(page_key="404", root_path="/", last_update=last_update),
    )


def _player_slugs(players):
    """Unique page slugs: the name, then name and last team, then a number."""
    base = players["playername"].map(_slugify)
    shared = base.duplicated(keep=False)
    slug = base.where(~shared, base + "-" + players["teamname"].map(_slugify))
    order = players.assign(slug=slug).sort_values("playerid")
    order["n"] = order.groupby("slug").cumcount()
    order.loc[order["n"] > 0, "slug"] = order["slug"] + "-" + (order["n"] + 1).astype(str)
    return order["slug"].reindex(players.index)


def player_pages_and_rows(history, latest, seasons):
    """Player Elo register rows and one page context per listed player.

    Listed players: ever in a major league or at an international event, or active
    within PLAYER_PAGE_WINDOW. The register has their current ratings ("now" rows,
    active within ACTIVE_WINDOW, every league) and, to keep the page light, their
    major-league seasons with PLAYER_SEASON_GAMES or more games.
    """
    newest = pd.to_datetime(latest["latest_date"]).max()
    big_stage = set(env.globals["major_leagues"]) | set(INTERNATIONAL_LEAGUES)
    on_big_stage = set(history.loc[history["league"].isin(big_stage), "playerid"])
    latest = latest[~latest["playerid"].str.startswith("dup:")]
    listed = latest[
        latest["playerid"].isin(on_big_stage)
        | (pd.to_datetime(latest["latest_date"]) >= newest - PLAYER_PAGE_WINDOW)
    ].copy()
    listed["slug"] = _player_slugs(listed)
    slugs = listed.set_index("playerid")["slug"]

    def rows(df, is_now):
        df = df.assign(
            slug=df["playerid"].map(slugs),
            elo=df["elo"].round(),
            now=is_now,
            active=True,
        )
        if is_now:
            df["active"] = pd.to_datetime(df["latest_date"]) >= newest - ACTIVE_WINDOW
            df["year"] = pd.to_datetime(df["latest_date"]).dt.year
        cols = ["slug", "playername", "position", "teamname", "league", "elo", "year",
                "latest_date", "now", "active"]
        return df[cols].to_dict(orient="records")

    season_rows = seasons[
        seasons["playerid"].isin(slugs.index)
        & (seasons["games"] >= PLAYER_SEASON_GAMES)
        & seasons["league"].isin(env.globals["major_leagues"])
    ]
    register = rows(listed, True) + rows(season_rows, False)

    pages = {}
    listed_history = history[history["playerid"].isin(slugs.index)]
    for pid, games in listed_history.groupby("playerid", sort=False):
        info = listed.loc[listed["playerid"] == pid].iloc[0]
        series = [{"date": d[:10], "elo": round(float(e), 1)} for d, e in zip(games["date"], games["elo"])]
        peak = max(series, key=lambda d: d["elo"])
        low = min(series, key=lambda d: d["elo"])
        # A stint is a run of consecutive games for one team.
        stint_id = (games["teamid"] != games["teamid"].shift()).cumsum()
        stints = []
        for _, stint in games.groupby(stint_id, sort=False):
            last = stint.iloc[-1]
            stints.append(
                {
                    "teamname": last["teamname"],
                    "team_slug": _slugify(last["teamname"]),
                    "league": last["home_league"] or last["league"],
                    "position": stint["position"].mode().iloc[0],
                    "first": stint["date"].iloc[0][:10],
                    "last": last["date"][:10],
                    "games": len(stint),
                    "elo": round(float(last["elo"])),
                }
            )
        names = [n for n in dict.fromkeys(games["playername"][::-1]) if n != info["playername"]]
        pages[info["slug"]] = {
            "playername": info["playername"],
            "slug": info["slug"],
            "position": info["position"],
            "teamname": info["teamname"],
            "team_slug": _slugify(info["teamname"]),
            "home_league": info["league"],
            "current_elo": round(float(info["elo"])),
            "active": bool(pd.to_datetime(info["latest_date"]) >= newest - ACTIVE_WINDOW),
            "aliases": names,
            "elo_series": series,
            "elo_summary": {"games": len(series), "peak": peak, "low": low, "first": series[0], "last": series[-1]},
            "stints": stints[::-1],
        }
    return register, pages, listed


ROLE_ORDER = ["top", "jng", "mid", "bot", "sup"]
# Past-roster cells list the main starter and at most this many others.
ROSTER_EXTRAS = 3


def team_rosters(history, player_slugs, player_elos):
    """Each team's last lineup and its starters by season and role, keyed by team name.

    Args:
        history: `elo.get_player_history` rows (gameid, date, year, teamname,
            position, playerid, playername).
        player_slugs: playerid -> page slug, for players with a page.
        player_elos: playerid -> current player Elo.
    Returns:
        {teamname: {"last": {"date", "active", "players": [...]}, "seasons": [{"year", "roles": [...]}]}}.
        A player entry has name, slug (or None), role and games; in "last" also elo.
        Seasons are newest first; each role lists players by games for the team that
        year, the main starter first.
    """
    role_rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    newest = pd.to_datetime(history["date"]).max()
    rosters = {}

    last_game = history.drop_duplicates("teamname", keep="last")[["teamname", "gameid", "date"]]
    last = history.merge(last_game, on=["teamname", "gameid", "date"])
    for team, rows in last.groupby("teamname", sort=False):
        rows = rows.sort_values("position", key=lambda p: p.map(role_rank))
        rosters[team] = {
            "last": {
                "date": rows["date"].iloc[0][:10],
                "active": bool(pd.to_datetime(rows["date"].iloc[0]) >= newest - ACTIVE_WINDOW),
                "players": [
                    {"name": r.playername, "slug": player_slugs.get(r.playerid), "role": r.position,
                     "elo": None if pd.isna(player_elos.get(r.playerid)) else round(float(player_elos.get(r.playerid)))}
                    for r in rows.itertuples()
                ],
            },
            "seasons": [],
        }

    counts = (
        history.groupby(["teamname", "year", "position", "playerid"])
        .agg(games=("gameid", "size"), name=("playername", "last"))
        .reset_index()
        .sort_values(["teamname", "year", "position", "games"], ascending=[True, False, True, False], kind="mergesort")
    )
    for (team, year), season in counts.groupby(["teamname", "year"], sort=False):
        roles = []
        for role in ROLE_ORDER:
            players = season[season["position"] == role]
            listed = [
                {"name": r.name, "slug": player_slugs.get(r.playerid), "games": int(r.games)}
                for r in players.itertuples()
            ]
            roles.append({"role": role, "players": listed[: 1 + ROSTER_EXTRAS], "more": max(0, len(listed) - 1 - ROSTER_EXTRAS)})
        rosters[team]["seasons"].append({"year": int(year), "roles": roles})
    for roster in rosters.values():
        roster["seasons"].sort(key=lambda s: s["year"], reverse=True)
    return rosters


def render_player_pages(pages, last_update):
    template = env.get_template("player.html.j2")
    for page in pages.values():
        _write(
            os.path.join(OUTPUT_DIR, "players", f"{page['slug']}.html"),
            template.render(page_key="player", root_path="../", last_update=last_update, **page),
        )


def write_player_index(listed):
    """players.json for the header search: name, slug, role, team, league, last game."""
    majors = set(env.globals["major_leagues"])
    players = [
        {"n": r.playername, "s": r.slug, "r": r.position, "t": r.teamname, "l": r.league, "d": r.latest_date}
        for r in listed.sort_values("latest_date", ascending=False).itertuples()
    ]
    players.sort(key=lambda p: p["l"] not in majors)
    with open(os.path.join(OUTPUT_DIR, "players.json"), "w") as f:
        json.dump(players, f, ensure_ascii=False, separators=(",", ":"))


def write_team_index(pages):
    """teams.json for the header search: name, slug, league and last game.

    Ordered major-league teams first, then by last game, newest first; the search
    keeps this order among equally good matches.
    """
    teams = [
        {
            "n": p["teamname"],
            "s": p["slug"],
            "l": p["current_league"] or (p["leagues"][-1] if p["leagues"] else ""),
            "d": p["elo_summary"]["last"]["date"] if p["elo_summary"] else str(p["series"][-1]["year"]),
        }
        for p in pages.values()
    ]
    majors = set(env.globals["major_leagues"])
    teams.sort(key=lambda t: t["d"], reverse=True)
    teams.sort(key=lambda t: t["l"] not in majors)
    with open(os.path.join(OUTPUT_DIR, "teams.json"), "w") as f:
        json.dump(teams, f, ensure_ascii=False, separators=(",", ":"))


def render_team_pages(pages, last_update):
    template = env.get_template("team.html.j2")
    for page in pages.values():
        _write(
            os.path.join(OUTPUT_DIR, "teams", f"{page['slug']}.html"),
            template.render(page_key="team", root_path="../", last_update=last_update, **page),
        )


def _season_page(key, df, columns, value_key, last_update, domain=None):
    config = {"valueKey": value_key, "columns": columns, "defaultSort": value_key, "kind": "season"}
    if domain is not None:
        config["domain"] = domain
    render_rankings_page(
        METRICS[key],
        _records(df),
        config,
        {"years": sorted(int(y) for y in df["year"].unique()), "leagues": sorted(df["league"].unique())},
        last_update,
    )


def _active(df):
    """True for rows whose last game is within ACTIVE_WINDOW of the newest game."""
    played = pd.to_datetime(df["latest_date"])
    return played >= played.max() - ACTIVE_WINDOW


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    copy_static()
    last_update = datetime.datetime.now().strftime("%B %-d, %Y")
    majors = env.globals["major_leagues"]

    # ---- Season stats ----------------------------------------------------
    # Read each year's games once and share them across every GLORY variant.
    games = load_glory_games()
    record_all = get_record(load_season_games())
    glory_df = _rankings(games, 5, True, opponent_adjusted="record", record=record_all)
    glory_all = _rankings(games, 1, False, opponent_adjusted="record", record=record_all)
    glory_unadjusted_df = _rankings(games, 5, True)
    glorb_df = _rankings(games, 5, True, baseline=True)

    # Record covers the same team-seasons as GLORY (5+ major-league games), with
    # GLORY's league; its win % and games count every game of the season.
    record_df = glory_df[["teamname", "year", "league"]].merge(
        record_all.sort_values("games").drop_duplicates(["teamname", "year"], keep="last")[
            ["teamname", "year", "record", "win_pct", "games"]
        ],
        on=["teamname", "year"],
    ).assign(win_pct=lambda d: (d["win_pct"] * 100).round(1), record=lambda d: d["record"].round(1))
    luck_df = get_luck(games, minimum_matches=5).assign(
        win_pct=lambda d: (d["win_pct"] * 100).round(1),
        expected=lambda d: (d["expected"] * 100).round(1),
        luck_wins=lambda d: d["luck_wins"].round(1),
    )[["teamname", "year", "league", "luck_wins", "win_pct", "expected", "games"]]

    render_404(last_update)
    render_sunset(last_update)
    render_redirect("glory_plus", "glory.html", "GLORY+ is now part of GLORY", last_update)
    # GlorELO+ was renamed FORGE; keep its old address working.
    render_redirect("glorelo_plus", "forge.html", "GlorELO+ is now FORGE", last_update)

    _season_page("glory", glory_df, METRIC_COLUMNS, "score", last_update)
    _season_page("record", record_df, RECORD_COLUMNS, "record", last_update)
    reach = float(np.ceil(luck_df["luck_wins"].abs().max() / 5) * 5)
    _season_page("luck", luck_df, LUCK_COLUMNS, "luck_wins", last_update, domain=[-reach, reach])
    _season_page("glory_unadjusted", glory_unadjusted_df, METRIC_COLUMNS, "score", last_update)
    _season_page("glorb", glorb_df, METRIC_COLUMNS, "score", last_update)

    # ---- Forecasts -------------------------------------------------------
    # Forecast pages open on "now" rows (current ratings) and also carry one row per
    # team-season (rating at the end of that year) for the season picker.
    cfg = ELO_METRICS["game_length_elo"]
    latest_elos = get_latest_elos(cfg["method"])
    season_elos = get_season_elos(cfg["method"])
    # Every team's current rating is a "now" row, so search finds retired teams;
    # the default view shows only the active ones.
    leagues = set(latest_elos["league"]) | set(season_elos["league"])
    league_order = [l for l in majors if l in leagues] + sorted(leagues - set(majors))
    team_elo_rows = _forecast_records(latest_elos.assign(active=_active(latest_elos)), season_elos, ("elo",))
    render_rankings_page(
        cfg,
        team_elo_rows,
        {"valueKey": "elo", "columns": ELO_COLUMNS, "defaultSort": "elo", "kind": "rating"},
        {"years": sorted(int(y) for y in season_elos["year"].unique()), "leagues": league_order},
        last_update,
    )

    # Form for every team in every league, as of now and at the end of each season.
    states = form_states(opponent_adjust(load_form_games()))
    forms_now, forms_seasons = team_forms(states)
    prediction_log, coverage = update_predictions(states)
    form_now = forms_now.rename(columns={"home": "league"}).assign(form=lambda d: FORM_POINTS * d["form"])
    form_seasons = forms_seasons.rename(columns={"home": "league"}).assign(form=lambda d: FORM_POINTS * d["form"])
    form_leagues = set(form_now["league"]) | set(form_seasons["league"])
    render_rankings_page(
        FORECASTS["form"],
        _forecast_records(form_now.assign(active=_active(form_now)), form_seasons, ("form",)),
        {"valueKey": "form", "columns": FORM_COLUMNS, "defaultSort": "form", "kind": "rating"},
        {"years": sorted(int(y) for y in form_seasons["year"].unique()),
         "leagues": [l for l in majors if l in form_leagues] + sorted(form_leagues - set(majors))},
        last_update,
    )

    # FORGE for major-league teams: now (active teams, current Elo) and at the end
    # of each season (that year's season-end Elo).
    forge = forge_ratings(forms_now[forms_now["home"].isin(majors)], latest_elos)
    forge = forge[_active(forge)].reset_index(drop=True)
    forge_seasons = forge_ratings(forms_seasons[forms_seasons["home"].isin(majors)], season_elos)
    forge_rows = _forecast_records(forge, forge_seasons, ("forge", "elo", "form"))
    forge_config = {"valueKey": "forge", "columns": FORGE_COLUMNS, "defaultSort": "forge", "kind": "rating",
                    "weights": {"elo": ELO_WEIGHT, "crossRegionElo": CROSS_REGION_ELO_WEIGHT}}
    render_rankings_page(
        FORECASTS["forge"],
        forge_rows,
        forge_config,
        {"years": sorted(int(y) for y in forge_seasons["year"].unique()), "leagues": sorted(forge_seasons["league"].unique())},
        last_update,
    )

    # ---- Players ---------------------------------------------------------
    player_history = get_player_history(cfg["method"])
    player_latest, player_seasons = get_player_elos(cfg["method"], player_history)
    player_rows, player_pages, listed_players = player_pages_and_rows(player_history, player_latest, player_seasons)
    player_leagues = {r["league"] for r in player_rows}
    render_rankings_page(
        PLAYER_METRICS["player_elo"],
        player_rows,
        {"valueKey": "elo", "columns": PLAYER_ELO_COLUMNS, "defaultSort": "elo", "kind": "rating", "entity": "player"},
        {"years": sorted({int(r["year"]) for r in player_rows if not r["now"]}),
         "leagues": [l for l in majors if l in player_leagues] + sorted(player_leagues - set(majors))},
        last_update,
    )

    # AURA per player-season (major leagues), on its own page and on player pages.
    aura_seasons = aura.season_aura(aura.get_aura(), majors)
    aura_rows, aura_by_player = aura_rows_and_seasons(aura_seasons, listed_players.set_index("playerid")["slug"])
    for slug, page in player_pages.items():
        page["aura_seasons"] = aura_by_player.get(slug, [])
    reach = float(np.ceil(max(abs(r["aura"]) for r in aura_rows) / 5) * 5)
    render_rankings_page(
        PLAYER_METRICS["aura"],
        aura_rows,
        {"valueKey": "aura", "columns": AURA_COLUMNS, "defaultSort": "aura", "kind": "season", "entity": "player",
         "domain": [-reach, reach]},
        {"years": sorted({int(r["year"]) for r in aura_rows}),
         "leagues": [l for l in majors if any(r["league"] == l for r in aura_rows)],
         "roles": ROLE_ORDER},
        last_update,
    )

    # ---- Index and team pages -----------------------------------------------
    elo_history = get_elo_history("game_length")
    rosters = team_rosters(
        player_history,
        listed_players.set_index("playerid")["slug"].to_dict(),
        player_latest.set_index("playerid")["elo"].to_dict(),
    )
    pages = _team_pages(glory_all, forge_seasons, forge, elo_history, latest_elos, glory_df, rosters)
    write_kalshi_alert(prediction_log, coverage, set(pages))
    predictions = predictions_view(prediction_log, set(pages), datetime.datetime.now(datetime.timezone.utc))
    render_predictions(predictions, coverage, last_update)
    with open(os.path.join(OUTPUT_DIR, "predictions.json"), "w") as f:
        json.dump(markets.published_log(prediction_log), f, ensure_ascii=False, separators=(",", ":"))
    # The hourly price job (scripts/update_prices.py) replaces this between builds.
    with open(os.path.join(OUTPUT_DIR, "kalshi.json"), "w") as f:
        json.dump(markets.prices_file(prediction_log, datetime.datetime.now(datetime.timezone.utc)), f, separators=(",", ":"))
    render_index(
        forge_rows,
        team_elo_rows,
        player_rows,
        {"glory": len(glory_df), "forge": len(forge),
         "game_length_elo": len(latest_elos), "player_elo": sum(r["now"] and r["active"] for r in player_rows),
         "aura": len(aura_rows)},
        forge_config,
        last_update,
        fixtures=predictions["home"],
    )
    render_team_pages(pages, last_update)
    write_team_index(pages)

    render_player_pages(player_pages, last_update)
    write_player_index(listed_players)

    print(f"Static site generated in {OUTPUT_DIR}/ ({len(pages)} team pages, {len(player_pages)} player pages)")


if __name__ == "__main__":
    main()
