"""The Jinja environment, its filters and the small page writers."""

import datetime
import functools
import hashlib
import os
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from prometheus.site import config as site_config
from prometheus.site.config import (
    NAV,
    PREDICTIONS,
    ROOT_DIR,
    SITE_URL,
    STATIC_SRC,
    SUNSET,
)
from prometheus.types import ALL_MAJOR_LEAGUES

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
env.filters["compact_series"] = lambda series: [
    [d["date"], round(d["elo"])] for d in series
]


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


@functools.cache
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
        dest_dir = Path(site_config.OUTPUT_DIR) / sub
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(Path(STATIC_SRC) / sub, dest_dir)
    shutil.copy2(
        Path(STATIC_SRC) / "favicon.svg", Path(site_config.OUTPUT_DIR) / "favicon.svg"
    )


def render_sunset():
    _write(
        os.path.join(site_config.OUTPUT_DIR, "sunset.html"),
        env.get_template("sunset.html.j2").render(
            page_key="sunset", root_path="", metrics=SUNSET
        ),
    )


def render_redirect(key, target, title):
    """A retired page that sends visitors (and search engines) to its replacement."""
    _write(
        os.path.join(site_config.OUTPUT_DIR, f"{key}.html"),
        env.get_template("redirect.html.j2").render(
            page_key=key, root_path="", target=target, title=title
        ),
    )


def render_404():
    # CloudFront serves 404.html for any missing path, so links must be root-absolute.
    _write(
        os.path.join(site_config.OUTPUT_DIR, "404.html"),
        env.get_template("404.html.j2").render(page_key="404", root_path="/"),
    )
