"""The site's metric registries, column configs, paths and limits."""

import os
from pathlib import Path

import pandas as pd

ROOT_DIR = str(Path(__file__).resolve().parents[2])
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
            "Rating: Elo plus Form, both in Elo points, on the team's league's own scale; the four majors share one. Form is how much better than its own league a team has played lately, from its recent gold and objective stats, each game adjusted for the opponent's Elo. Recent games count most: a game's weight halves every 20 games.",
            "Head to head turns two ratings into a chance to win one game. Between teams from different leagues it uses Elo alone, because Form only compares a team with its own league. It ignores side; blue side wins about 54% of games.",
            "Tested on every major-league game since 2014, using only earlier games each time: it picks the winner 64.8% of the time within a league, and its odds are more accurate than Elo's alone.",
            "The table opens on major-league teams that have played in the last six months. Pick a league to see its teams, or a season for ratings at the end of that year.",
        ],
        "caveats": "Ratings compare only within one league's scale. Regions meet only at international events, so a league that rarely plays abroad is measured loosely. Odds are for one game, not a series.",
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
SUNSET = [
    *FOLDED,
    *(m for m in [*METRICS.values(), *FORECASTS.values()] if m.get("sunset")),
]
NAV = [
    {
        "name": s["name"],
        "links": [
            {
                "key": m["key"],
                "name": m["name"],
                "title": m.get("title", m["name"]),
                "question": m["question"],
            }
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
        "Figures beside the bar: each team's chance of taking the series, in 100. It follows from the one-game chance, allowing for form that carries through a series: a favourite is a bigger favourite over five games than one, but less so than if games were independent.",
        "Same league: FORGE, with separate weights outside LCK, LPL, LEC and LCS. Different leagues: Elo, on a curve fit to international games.",
        "Calls refresh daily and freeze at the start. Matches played before the log began carry a call rebuilt from the day before; the weights saw those games, so trust saved calls more.",
        "Log loss: lower is better; a coin flip scores 0.693. Table II scores the one-game chance per game, Table III the series chance per series.",
        "Kalshi is a prediction market. Its figure is the market's series chance (mid of bid and offer), read hourly (before 6 Oct, from Kalshi's price history) and frozen at the start; the caret on the bar marks it. Over 2,300 past series it beat us; 12 hours out, FORGE tied it in the major leagues. Alerts flag major-league FORGE calls 5 points above Kalshi's price; closing line value is the last price minus the alerted one, above 0 when the market moved our way.",
    ],
    "caveats": "Schedule from Leaguepedia; teams Oracle's Elixir doesn't cover aren't shown. Calls ignore side selection, roster changes and new patches. Times are local.",
}
# The home page lists this many upcoming major-league and international matches,
# within this many days.
HOME_FIXTURES = 10
HOME_FIXTURE_DAYS = 4
# The Predictions page lists results from this many days back; older ones are on
# a page per month (results/YYYY-MM.html).
RECENT_RESULT_DAYS = 3
# The day's Kalshi alert (title and body of a GitHub issue), written only when
# there is one; the publish workflow posts it. Never published to the site.
KALSHI_ALERT = os.environ.get(
    "KALSHI_ALERT", os.path.join(ROOT_DIR, "data", "kalshi_alert.json")
)
# The prediction log; CI restores it from and saves it to the data backup bucket.
PREDICTIONS_LOG = os.environ.get(
    "PREDICTIONS_LOG", os.path.join(ROOT_DIR, "data", "predictions.json")
)
# Kalshi's last price before each settled series (scripts/export_market_prices.py);
# CI restores it from the data-backup bucket. Missing is fine: logs then show only
# the prices saved in the prediction log.
MARKET_PRICES = os.environ.get(
    "MARKET_PRICES", os.path.join(ROOT_DIR, "data", "market_prices.json")
)
# Team and player pages embed this many of their newest series; the rest load on request.
GAME_LOG_SERIES = 20

# Players get a page if they ever played in a major league or at an international
# event, or played anywhere within this window of the newest game.
PLAYER_PAGE_WINDOW = pd.Timedelta(days=730)
# The player register's past seasons: major-league player-seasons with this many games.
PLAYER_SEASON_GAMES = 10


# Rows in each of the home page's top-of-register tables.
HOME_TOP = 10


METRIC_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {
        "key": "score",
        "label": "Score",
        "type": "number",
        "digits": 2,
        "bar": True,
        "note": 1,
    },
    {
        "key": "era_score",
        "label": "Era Z",
        "type": "number",
        "digits": 2,
        "signed": True,
        "hint": "Standard deviations above the average major-league team that year",
        "phoneHide": True,
        "note": 2,
    },
    {
        "key": "league_score",
        "label": "League Z",
        "type": "number",
        "digits": 2,
        "signed": True,
        "hint": "Standard deviations above the average team in its league that year",
        "wideOnly": True,
        "note": 2,
    },
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]

RECORD_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {
        "key": "record",
        "label": "Record",
        "type": "number",
        "digits": 1,
        "bar": True,
        "note": 1,
        "hint": "Chance to beat the average major-league team that year",
    },
    {
        "key": "win_pct",
        "label": "Win %",
        "type": "number",
        "digits": 1,
        "phoneHide": True,
    },
    {
        "key": "games",
        "label": "Games",
        "type": "number",
        "digits": 0,
        "wideOnly": True,
        "note": 2,
    },
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]

LUCK_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {
        "key": "luck_wins",
        "label": "Luck",
        "type": "number",
        "digits": 1,
        "signed": True,
        "note": 1,
        "hint": "Wins above what the team's play earned",
    },
    {
        "key": "win_pct",
        "label": "Win %",
        "type": "number",
        "digits": 1,
        "phoneHide": True,
    },
    {
        "key": "expected",
        "label": "Earned",
        "type": "number",
        "digits": 1,
        "phoneHide": True,
        "note": 2,
        "hint": "The win % the team's stats were worth",
    },
    {"key": "games", "label": "Games", "type": "number", "digits": 0, "wideOnly": True},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]

FORGE_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {
        "key": "forge",
        "label": "Rating",
        "type": "number",
        "digits": 0,
        "bar": True,
        "note": 1,
    },
    {
        "key": "form",
        "label": "Form",
        "type": "number",
        "digits": 0,
        "signed": True,
        "phoneHide": True,
        "hint": "Elo points above or below its league's average, from recent play",
    },
    {
        "key": "elo",
        "label": "Elo",
        "type": "number",
        "digits": 0,
        "wideOnly": True,
        "hint": "Elo now, or at the end of the season shown",
    },
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 4},
]

FORM_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {
        "key": "form",
        "label": "Form",
        "type": "number",
        "digits": 0,
        "signed": True,
        "bar": True,
        "note": 1,
    },
    {"key": "league", "label": "League", "type": "league", "wideOnly": True, "note": 3},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 4},
    {"key": "latest_date", "label": "Last game", "type": "date", "wideOnly": True},
]

ELO_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {
        "key": "elo",
        "label": "Elo",
        "type": "number",
        "digits": 0,
        "bar": True,
        "note": 1,
    },
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 3},
    {"key": "latest_date", "label": "Last game", "type": "date", "wideOnly": True},
]


PLAYER_ELO_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "playername", "label": "Player", "type": "player"},
    {
        "key": "elo",
        "label": "Elo",
        "type": "number",
        "digits": 0,
        "bar": True,
        "note": 1,
    },
    {"key": "position", "label": "Role", "type": "role", "phoneHide": True},
    {"key": "teamname", "label": "Team", "type": "teamref", "wideOnly": True},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "year", "label": "Season", "type": "text", "wideOnly": True, "note": 4},
]


AURA_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "playername", "label": "Player", "type": "player"},
    {
        "key": "aura",
        "label": "AURA",
        "type": "number",
        "digits": 1,
        "signed": True,
        "bar": True,
        "note": 1,
        "hint": "Win-chance points per game, against an even lane",
    },
    {
        "key": "role_z",
        "label": "Role Z",
        "type": "number",
        "digits": 2,
        "signed": True,
        "phoneHide": True,
        "note": 2,
        "hint": "Standard deviations above the average player-season in the same role that year",
    },
    {"key": "position", "label": "Role", "type": "role", "phoneHide": True},
    # The team carries its league mark instead of a League column, so the register fits beside the margin.
    {
        "key": "teamname",
        "label": "Team",
        "type": "teamref",
        "mark": True,
        "wideOnly": True,
    },
    {
        "key": "games",
        "label": "Games",
        "type": "number",
        "digits": 0,
        "wideOnly": True,
        "note": 4,
    },
    {"key": "year", "label": "Year", "type": "text", "wideOnly": True},
]


ROLE_ORDER = ["top", "jng", "mid", "bot", "sup"]
# Past-roster cells list the main starter and at most this many others.
ROSTER_EXTRAS = 3
