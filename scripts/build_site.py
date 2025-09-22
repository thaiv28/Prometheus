"""
build_site.py: Generates static HTML site for Prometheus rankings.
- Runs pipeline to fetch latest data and compute rankings
- Generates index.html and metric pages (glory.html, glorb.html)
- Outputs to output/ folder
"""

import os
import datetime
import shutil
from pathlib import Path

import pandas as pd
from prometheus.ranking import get_glory_ranking
from prometheus.types import GLORY_FEATURES, ALL_MAJOR_LEAGUES
from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
STATIC_SRC = os.path.join(ROOT_DIR, "site_static")


METRICS = {
    "glory": {
        "key": "glory",
        "name": "GLORY",
        "full_name": "Global League Offensive Rankings Yield",
        "description": "Weights gold/objectives by their importance in the meta, and calculates the best teams at securing those advantages across all regions.",
        "features": GLORY_FEATURES,
        "baseline": False,
    },
    "glorb": {
        "key": "glorb",
        "name": "GLORB",
        "full_name": "Global League Offensive Rankings Baseline",
        "description": "Baseline for GLORY. Weights all objective/gold equally.",
        "features": GLORY_FEATURES,
        "baseline": True,
    },
}

LATEST_YEAR = datetime.datetime.now().year


os.makedirs(OUTPUT_DIR, exist_ok=True)


# Copy static assets (css/js)
def copy_static():
    if not os.path.isdir(STATIC_SRC):
        raise RuntimeError("Missing site_static directory.")
    for sub in ("css", "js"):
        src_dir = Path(STATIC_SRC) / sub
        dest_dir = Path(OUTPUT_DIR) / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.glob("*.*"):
            shutil.copy2(f, dest_dir / f.name)


copy_static()


# Helper: HTML table from DataFrame
def df_to_html_table(df):
    return df.to_html(classes="rankings-table", index=False, border=0)


# Homepage

# Jinja2 setup
env = Environment(loader=FileSystemLoader(os.path.join(ROOT_DIR, "templates")))


# Render homepage
def render_index():
    # Use GLORY ranking (non-baseline) as representative dataset for global stats
    df = get_glory_ranking(
        year=None,
        league=ALL_MAJOR_LEAGUES,
        baseline=False,
        z_scores=True,
        minimum_matches=5,
    )
    total_teams = df["teamname"].nunique()
    years = sorted(df["year"].unique())
    leagues = sorted(df["league"].unique())
    template = env.get_template("index.html.j2")
    html = template.render(
        last_update=datetime.datetime.now().strftime("%B %d, %Y"),
        metrics=[v for v in METRICS.values()],
        total_teams=total_teams,
        total_years=len(years),
        total_leagues=len(leagues),
        years=years,
        leagues=leagues,
    )
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
        f.write(html)


# Metric pages
def render_metric_page(metric_key, metric):
    df = get_glory_ranking(
        year=None,
        league=ALL_MAJOR_LEAGUES,
        baseline=metric["baseline"],
        z_scores=True,
        minimum_matches=5,
    )
    years = sorted(df["year"].unique())
    leagues = sorted(df["league"].unique())
    rows = df.to_dict(orient="records")
    template = env.get_template("metric_dynamic.html.j2")
    html = template.render(
        metric=metric,
        metrics=[v for v in METRICS.values()],
        years=years,
        leagues=leagues,
        rows=rows,
    )
    with open(os.path.join(OUTPUT_DIR, f"{metric_key}.html"), "w") as f:
        f.write(html)


def main():
    render_index()
    for metric_key, metric in METRICS.items():
        render_metric_page(metric_key, metric)
    print(f"Static site generated in {OUTPUT_DIR}/")


if __name__ == "main" or __name__ == "__main__":
    main()
