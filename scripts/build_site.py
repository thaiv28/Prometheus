"""
build_site.py: Generates static HTML site for Prometheus rankings.
- Runs pipeline to fetch latest data and compute rankings
- Generates index.html and metric pages (glory.html, glorb.html)
- Outputs to output/ folder
"""

import os
import datetime

import pandas as pd
from prometheus.ranking import get_glory_ranking
from prometheus.types import GLORY_FEATURES, ALL_MAJOR_LEAGUES
from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "sites")
CSS_FILE = "style.css"

METRICS = {
    "glory": {
        "key": "glory",
        "name": "GLORY",
        "description": "Global League Offensive Rankings Yield (GLORY): Weights gold/objectives by their importance in the meta, and calculates the best teams at securing those advantages across all regions.",
        "features": GLORY_FEATURES,
        "baseline": False,
    },
    "glorb": {
        "key": "glorb",
        "name": "GLORB",
        "description": "Global League Offensive Rankings Baseline (GLORB): Baseline for GLORY. Weights all objective/gold equally.",
        "features": GLORY_FEATURES,
        "baseline": True,
    },
}

LATEST_YEAR = datetime.datetime.now().year


os.makedirs(OUTPUT_DIR, exist_ok=True)

# Copy CSS file

if not os.path.exists(os.path.join(OUTPUT_DIR, CSS_FILE)):
    import shutil

    css_src = os.path.join(OUTPUT_DIR, CSS_FILE)
    shutil.copyfile(css_src, os.path.join(OUTPUT_DIR, CSS_FILE))


# Helper: HTML table from DataFrame
def df_to_html_table(df):
    return df.to_html(classes="rankings-table", index=False, border=0)


# Homepage

# Jinja2 setup
env = Environment(loader=FileSystemLoader(os.path.join(ROOT_DIR, "templates")))

# Render homepage
template = env.get_template("index.html.j2")
index_html = template.render(
    css_file=CSS_FILE,
    last_update=datetime.datetime.now().strftime("%B %d, %Y"),
    metrics=[v for v in METRICS.values()],
)
with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
    f.write(index_html)


# Metric pages
def render_metric_page(metric_key, metric):
    # Get all years and all leagues from the database
    # If you want to restrict to a specific set, you can change the arguments below
    df = get_glory_ranking(
        year=None,
        league=ALL_MAJOR_LEAGUES,
        baseline=metric["baseline"],
        minimum_matches=5,
    )
    years = sorted(df["year"].unique())
    leagues = sorted(df["league"].unique())
    columns = df.columns.tolist()
    rows = df.to_dict(orient="records")
    template = env.get_template("metric_filter.html.j2")
    html = template.render(
        css_file=CSS_FILE,
        metric=metric,
        years=years,
        leagues=leagues,
        columns=columns,
        rows=rows,
    )
    with open(os.path.join(OUTPUT_DIR, f"{metric_key}.html"), "w") as f:
        f.write(html)


for metric_key, metric in METRICS.items():
    render_metric_page(metric_key, metric)

print(f"Static site generated in {OUTPUT_DIR}/")
