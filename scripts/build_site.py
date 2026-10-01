"""
build_site.py: Generates static HTML site for Prometheus rankings.
- Computes GLORY/GLORB rankings and Elo snapshots from db/prometheus.db
- Renders index.html, one rankings page per metric, and one page per team
- Outputs to output/ folder
"""

import os
import re
import datetime
import shutil
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from prometheus.ranking import get_glory_ranking
from prometheus.elo import get_elo_history, get_latest_elos
from prometheus.types import ALL_MAJOR_LEAGUES

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
STATIC_SRC = os.path.join(ROOT_DIR, "site_static")
SITE_DOMAIN = "prometheus.thaiv.dev"
SITE_URL = f"https://{SITE_DOMAIN}"

METRICS = {
    "glory": {
        "key": "glory",
        "name": "GLORY",
        "full_name": "Global League Offensive Rankings Yield",
        "description": "Weights gold and objective rates by how much they won games in that season's meta, then scores every team-season on that scale.",
        "how_to_read": [
            "Score is the team-season's predicted win strength, scaled so most teams land between 0 and 100. Higher is better.",
            "Era Z compares a team with every major-league team that year. League Z compares it only with its own league that year. A Z of +2 is two standard deviations above average.",
            "Weights are refit every year, so a 2015 team is judged on what won in 2015.",
        ],
        "caveats": "Covers LCK, LPL, LEC and LCS. Teams with fewer than 5 games in a year are left out. Playoff runs face stronger opponents, which can pull a deep run's averages down.",
        "baseline": False,
        "lede_note": 3,
    },
    "glorb": {
        "key": "glorb",
        "name": "GLORB",
        "full_name": "Global League Offensive Rankings Baseline",
        "description": "The same stats as GLORY, all weighted equally. Use it to see how much GLORY's learned weights change the order.",
        "how_to_read": [
            "Score is the equal-weight sum of standardized stats, centred near 80. Higher is better.",
            "Era Z and League Z work as on GLORY.",
            "A team ranked far higher on GLORY than GLORB excels at the stats that mattered most that year.",
        ],
        "caveats": "Covers LCK, LPL, LEC and LCS. Teams with fewer than 5 games in a year are left out.",
        "baseline": True,
        "lede_note": 3,
    },
    "glory_plus": {
        "key": "glory_plus",
        "name": "GLORY+",
        "full_name": "GLORY, adjusted for opponent strength",
        "description": "GLORY with every game adjusted for how strong the opponent was, using their Elo going into the game. A big gold lead against a top team counts for more than the same lead against a weak one.",
        "how_to_read": [
            "Score: on the same scale as GLORY. Higher is better.",
            "GLORY+ minus GLORY shows how much a team's schedule helped or hurt it. Teams in weaker leagues usually drop.",
            "Era Z and League Z: same as on GLORY.",
        ],
        "caveats": "Only LCK, LPL, LEC and LCS. Team-seasons with fewer than 5 games are left out. Elo links regions only through international events like MSI and Worlds, so the gap between regions is probably understated.",
        "baseline": False,
        "opponent_adjusted": True,
        "lede_note": 3,
    },
}

ELO_METRICS = {
    "game_length_elo": {
        "key": "game_length_elo",
        "name": "Elo",
        "full_name": "Game-Length Adjusted Elo",
        "method": "game_length",
        "description": "A running rating for every team in every region. Beating stronger teams moves it more, and fast wins count more than long ones.",
        "how_to_read": [
            "Every team starts at 1500. Each game moves the winner up and the loser down by the same amount.",
            "Short, decisive wins move ratings most. A heavy favourite who scrapes a 50-minute win can lose a little rating.",
            "The table shows each team's rating after its most recent game.",
        ],
        "caveats": "Regions rarely play each other outside MSI and Worlds, so ratings compare best within a region. Team names come from the most recent game.",
        "lede_note": 2,
    }
}

NAV = [
    {"key": m["key"], "name": m["name"]} for m in [*METRICS.values(), *ELO_METRICS.values()]
]

env = Environment(
    loader=FileSystemLoader(os.path.join(ROOT_DIR, "templates")), autoescape=True
)
env.globals.update(
    nav=NAV,
    site_url=SITE_URL,
    major_leagues=[l.value for l in ALL_MAJOR_LEAGUES],
    edition=datetime.date.today().year,
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


def copy_static():
    if not os.path.isdir(STATIC_SRC):
        raise RuntimeError("Missing site_static directory.")
    for sub in ("css", "js", "fonts"):
        dest_dir = Path(OUTPUT_DIR) / sub
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(Path(STATIC_SRC) / sub, dest_dir)
    shutil.copy2(Path(STATIC_SRC) / "favicon.svg", Path(OUTPUT_DIR) / "favicon.svg")


def _rankings(baseline, minimum_matches, z_scores, opponent_adjusted=False):
    return get_glory_ranking(
        year=None,
        league=ALL_MAJOR_LEAGUES,
        baseline=baseline,
        z_scores=z_scores,
        minimum_matches=minimum_matches,
        opponent_adjusted=opponent_adjusted,
    )


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
            metrics=[*METRICS.values(), *ELO_METRICS.values()],
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

ELO_COLUMNS = [
    {"key": "rank", "label": "Rank", "type": "rank"},
    {"key": "teamname", "label": "Team", "type": "team"},
    {"key": "elo", "label": "Elo", "type": "number", "digits": 0, "bar": True, "note": 1},
    {"key": "league", "label": "League", "type": "league", "wideOnly": True},
    {"key": "latest_date", "label": "Last game", "type": "date", "wideOnly": True, "note": 3},
]


def _team_pages(glory_df, glorb_df, elo_history, latest_elos, glory_qualified):
    """Return {slug: context} for every team with GLORY data or Elo history."""

    # Rank of each qualified team-season within its year, for the franchise register.
    q = glory_qualified[["teamname", "year", "score"]].copy()
    q["year_rank"] = q.groupby("year")["score"].rank(ascending=False, method="min").astype(int)
    q["field"] = q.groupby("year")["score"].transform("size").astype(int)
    year_rank = {(t, int(y)): (int(r), int(f)) for t, y, r, f in q[["teamname", "year", "year_rank", "field"]].itertuples(index=False)}

    seasons = (
        glory_df[["teamname", "year", "league", "score"]]
        .rename(columns={"score": "glory"})
        .merge(
            glorb_df[["teamname", "year", "score"]].rename(columns={"score": "glorb"}),
            on=["teamname", "year"],
            how="outer",
        )
    )

    latest = latest_elos.set_index("teamname")
    pages = {}
    teams = sorted(set(seasons["teamname"]) | set(elo_history["teamname"]))
    seasons_by_team = dict(tuple(seasons.groupby("teamname")))
    elo_by_team = dict(tuple(elo_history.groupby("teamname")))

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
                        "glory": None if pd.isna(row.glory) else round(float(row.glory), 2),
                        "glorb": None if pd.isna(row.glorb) else round(float(row.glorb), 2),
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
            "current_league": None if current is None else current["league"],
            "leagues": leagues or ([current["league"]] if current is not None else []),
        }
    return pages


def render_404(last_update):
    # CloudFront serves 404.html for any missing path, so links must be root-absolute.
    _write(
        os.path.join(OUTPUT_DIR, "404.html"),
        env.get_template("404.html.j2").render(page_key="404", root_path="/", last_update=last_update),
    )


def render_team_pages(pages, last_update):
    template = env.get_template("team.html.j2")
    for page in pages.values():
        _write(
            os.path.join(OUTPUT_DIR, "teams", f"{page['slug']}.html"),
            template.render(page_key="team", root_path="../", last_update=last_update, **page),
        )


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    copy_static()
    last_update = datetime.datetime.now().strftime("%B %-d, %Y")

    # Each call refits one model per year, so compute each ranking once and reuse it.
    glory_df = _rankings(baseline=False, minimum_matches=5, z_scores=True)
    glorb_df = _rankings(baseline=True, minimum_matches=5, z_scores=True)
    glory_all = _rankings(baseline=False, minimum_matches=1, z_scores=False)
    glorb_all = _rankings(baseline=True, minimum_matches=1, z_scores=False)
    glory_plus_df = _rankings(baseline=False, minimum_matches=5, z_scores=True, opponent_adjusted=True)

    render_404(last_update)

    for metric, df in (
        (METRICS["glory"], glory_df),
        (METRICS["glorb"], glorb_df),
        (METRICS["glory_plus"], glory_plus_df),
    ):
        render_rankings_page(
            metric,
            _records(df),
            {"valueKey": "score", "columns": METRIC_COLUMNS, "defaultSort": "score"},
            {
                "years": sorted(int(y) for y in df["year"].unique()),
                "leagues": sorted(df["league"].unique()),
            },
            last_update,
        )

    latest_elos = {}
    for key, cfg in ELO_METRICS.items():
        latest = get_latest_elos(cfg["method"])
        latest_elos[key] = latest
        rows = _records(latest)
        for r in rows:
            r["latest_date"] = str(r["latest_date"])[:10]
            r["elo"] = round(float(r["elo"]), 1)
        majors = [l for l in env.globals["major_leagues"] if l in set(latest["league"])]
        others = sorted(set(latest["league"]) - set(majors))
        render_rankings_page(
            cfg,
            rows,
            {"valueKey": "elo", "columns": ELO_COLUMNS, "defaultSort": "elo"},
            {"years": sorted(int(y) for y in latest["year"].unique()), "leagues": majors + others},
            last_update,
        )

    elo_history = get_elo_history("game_length")
    pages = _team_pages(glory_all, glorb_all, elo_history, latest_elos["game_length_elo"], glory_df)
    render_index(
        glory_df,
        {"glory": len(glory_df), "glorb": len(glorb_df), "glory_plus": len(glory_plus_df), "game_length_elo": len(latest_elos["game_length_elo"])},
        len(latest_elos["game_length_elo"]),
        last_update,
    )
    render_team_pages(pages, last_update)

    print(f"Static site generated in {OUTPUT_DIR}/ ({len(pages)} team pages)")


if __name__ == "__main__":
    main()
