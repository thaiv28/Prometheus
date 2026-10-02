"""
build_site.py: Generates static HTML site for Prometheus rankings.
- Computes season stats (GLORY, Record, Luck, and the sunset GLORB and unadjusted
  GLORY) and forecasts (GlorELO+, Form, Elo) from db/prometheus.db
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

from prometheus.elo import get_elo_history, get_latest_elos, get_season_elos
from prometheus.form import form_states, load_form_games, opponent_adjust
from prometheus.glorelo import (
    CROSS_REGION_ELO_WEIGHT,
    ELO_WEIGHT,
    FORM_POINTS,
    glorelo_ratings,
    team_forms,
)
from prometheus.ranking import get_glory_ranking, load_glory_games
from prometheus.season import get_luck, get_record, load_season_games
from prometheus.types import ALL_MAJOR_LEAGUES

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
        "description": "How well a team played: each team-season's gold and objective stats, weighted by how much each stat decided wins that year, with every game adjusted for how strong the opponent was.",
        "how_to_read": [
            "Score: roughly 0 to 100. Higher is better.",
            "Era Z: how far a team is above the average major-league team that year, in standard deviations. League Z: the same, compared only with its own league. +2 means two standard deviations above average.",
            "Weights are recalculated each year, so a 2015 team is judged by what won games in 2015. Opponent strength is each opponent's Record for the whole season, so a big gold lead against a top team counts for more.",
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
        "full_name": "Game-Length Adjusted Elo",
        "method": "game_length",
        "description": "A rating for every team in every region, updated after each game. Wins over stronger teams and faster wins raise it more.",
        "how_to_read": [
            "Every team starts at 1500. Each game moves the winner up and the loser down by the same amount.",
            "Short games move ratings most. A heavy favourite that needs 50 minutes to win can still lose a little rating.",
            "The table opens on teams that have played in the last six months, at today's rating. Pick a season to rank every team by its rating at the end of that year, or several seasons to compare across years.",
            "International results also move a shared rating for each league, so when a region's teams win abroad, every team in that region rises, even those that stayed home.",
        ],
        "caveats": "Regions meet only at international events, so a league that rarely plays abroad is measured loosely. Team names are taken from each team's last game in the period shown.",
        "lede_note": 2,
    }
}

FORECASTS = {
    "glorelo_plus": {
        "key": "glorelo_plus",
        "name": "GlorELO+",
        "full_name": "Elo and Form, blended into a forecast",
        "description": "Who would win a game today. Each team's Elo plus its Form, the recent play that Elo misses, weighted by what best predicted past games.",
        "how_to_read": [
            "Rating: Elo plus Form, both in Elo points. Form says how much better than its own league a team has played lately.",
            "Head to head turns two ratings into a chance to win one game. Between teams from different leagues it uses Elo alone, because Form only compares a team with its own league. It ignores side; blue side wins about 54% of games.",
            "Tested on every major-league game since 2014, using only earlier games each time: it picks the winner 64.6% of the time within a league, and its odds are more accurate than Elo's alone.",
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
            "Form compares a team only with its own league; to compare regions, use Elo or GlorELO+.",
            "The table opens on teams that have played in the last six months. Pick a season to see Form at the end of that year.",
        ],
        "caveats": "Form is relative to each league, so a +100 in a weak league is not a +100 in a strong one. Teams with few games are pulled toward their league's average.",
        "lede_note": 1,
        "value_word": "Form",
        "value_plural": "Form",
    },
}

# The header and contents split what happened (season stats) from what's likely
# to happen next (forecasts). Retired metrics keep their pages but leave the header:
# one "Sunset stats" link leads to a page listing them.
SECTIONS = [
    {"name": "Season stats", "metrics": [m for m in METRICS.values() if not m.get("sunset")]},
    {"name": "Forecasts", "metrics": [*FORECASTS.values(), *ELO_METRICS.values()]},
]
SUNSET = [*FOLDED, *(m for m in METRICS.values() if m.get("sunset"))]
NAV = [
    {"name": s["name"], "links": [{"key": m["key"], "name": m["name"]} for m in s["metrics"]]}
    for s in SECTIONS
]

env = Environment(
    loader=FileSystemLoader(os.path.join(ROOT_DIR, "templates")), autoescape=True
)
env.globals.update(
    nav=NAV,
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


def _slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "team"


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


def render_index(glory_df, entry_counts, total_elo_teams, last_update):
    top = glory_df.sort_values("score", ascending=False).head(15)
    # The best qualified GLORY team-season in each year, newest first.
    leaders = glory_df.loc[glory_df.groupby("year")["score"].idxmax()].sort_values("year", ascending=False)
    year_sizes = glory_df.groupby("year").size().to_dict()
    annual = _records(leaders)
    for r in annual:
        r["field"] = int(year_sizes[r["year"]])
    _write(
        os.path.join(OUTPUT_DIR, "index.html"),
        env.get_template("index.html.j2").render(
            page_key="index",
            root_path="",
            last_update=last_update,
            sections=SECTIONS,
            entry_counts=entry_counts,
            all_time=_records(top),
            annual=annual,
            total_team_seasons=len(glory_df),
            total_elo_teams=total_elo_teams,
            first_year=int(glory_df["year"].min()),
            last_year=int(glory_df["year"].max()),
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

GLORELO_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "glorelo", "label": "Rating", "type": "number", "digits": 0, "bar": True, "note": 1},
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


def _team_pages(glory_df, record_df, luck_df, glorelo_seasons, glorelo_now, elo_history, latest_elos, glory_qualified):
    """Return {slug: context} for every team with GLORY data or Elo history.

    Each season carries GLORY (every team-season with a game), Record and Luck, and
    GlorELO+ at the end of that year. `glorelo_now` gives the current GlorELO+.
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
        .merge(record_df[key + ["record"]].drop_duplicates(key), on=key, how="left")
        .merge(luck_df[key + ["luck_wins"]].drop_duplicates(key), on=key, how="left")
        .merge(glorelo_seasons[key + ["glorelo"]].drop_duplicates(key), on=key, how="left")
    )
    glorelo_current = glorelo_now.drop_duplicates("teamname").set_index("teamname")["glorelo"]

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
                        "record": value(row.record, 1),
                        "luck_wins": value(row.luck_wins, 1),
                        "glorelo": None if pd.isna(row.glorelo) else round(float(row.glorelo)),
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
            "current_glorelo": round(float(glorelo_current[team])) if team in glorelo_current.index else None,
            "current_league": None if current is None else current["league"],
            "leagues": leagues or ([current["league"]] if current is not None else []),
        }
    return pages


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
    render_rankings_page(
        cfg,
        _forecast_records(latest_elos.assign(active=_active(latest_elos)), season_elos, ("elo",)),
        {"valueKey": "elo", "columns": ELO_COLUMNS, "defaultSort": "elo", "kind": "rating"},
        {"years": sorted(int(y) for y in season_elos["year"].unique()), "leagues": league_order},
        last_update,
    )

    # Form for every team in every league, as of now and at the end of each season.
    states = form_states(opponent_adjust(load_form_games()))
    forms_now, forms_seasons = team_forms(states)
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

    # GlorELO+ for major-league teams: now (active teams, current Elo) and at the end
    # of each season (that year's season-end Elo).
    glorelo = glorelo_ratings(forms_now[forms_now["home"].isin(majors)], latest_elos)
    glorelo = glorelo[_active(glorelo)].reset_index(drop=True)
    glorelo_seasons = glorelo_ratings(forms_seasons[forms_seasons["home"].isin(majors)], season_elos)
    render_rankings_page(
        FORECASTS["glorelo_plus"],
        _forecast_records(glorelo, glorelo_seasons, ("glorelo", "elo", "form")),
        {"valueKey": "glorelo", "columns": GLORELO_COLUMNS, "defaultSort": "glorelo", "kind": "rating",
         "weights": {"elo": ELO_WEIGHT, "crossRegionElo": CROSS_REGION_ELO_WEIGHT}},
        {"years": sorted(int(y) for y in glorelo_seasons["year"].unique()), "leagues": sorted(glorelo_seasons["league"].unique())},
        last_update,
    )

    # ---- Index and team pages -----------------------------------------------
    elo_history = get_elo_history("game_length")
    pages = _team_pages(glory_all, record_df, luck_df, glorelo_seasons, glorelo, elo_history, latest_elos, glory_df)
    render_index(
        glory_df,
        {"glory": len(glory_df), "record": len(record_df), "luck": len(luck_df),
         "glorelo_plus": len(glorelo), "form": int(_active(form_now).sum()),
         "game_length_elo": len(latest_elos)},
        len(latest_elos),
        last_update,
    )
    render_team_pages(pages, last_update)
    write_team_index(pages)

    print(f"Static site generated in {OUTPUT_DIR}/ ({len(pages)} team pages)")


if __name__ == "__main__":
    main()
