"""Game-agnostic calls and results from versioned JSON feeds."""

import datetime
import json
import logging
import os
import re
from pathlib import Path

from prometheus.site import config as site_config
from prometheus.site.config import RECENT_RESULT_DAYS
from prometheus.site.predictions import _by_day, _pct_pair
from prometheus.site.render import env, write

FEED_DIR = os.environ.get("PROMETHEUS_GAME_FEEDS", "data/games")
logger = logging.getLogger(__name__)


def load_feeds(folder=FEED_DIR) -> list[dict]:
    """Skip unreadable or invalid exports without interrupting the site build."""
    folder = Path(folder)
    if not folder.is_dir():
        logger.warning("Game feeds: missing folder %s", folder)
        return []
    feeds = []
    for path in sorted(folder.glob("*.json")):
        try:
            feed = json.loads(path.read_text(encoding="utf-8"))
            if feed["version"] != 1:
                raise ValueError("unsupported version")
            if not re.fullmatch(r"[a-z0-9-]+", feed["game"]):
                raise ValueError("invalid game slug")
            for key in ("name", "model", "generated", "data_through"):
                if not isinstance(feed[key], str):
                    raise ValueError(f"invalid {key}")
            for key in ("name", "url", "license"):
                feed["source"][key]
            for section in feed["sections"]:
                section["label"], section["major"]
            # Validate rows through the same path that will render them.
            game_view(feed, datetime.datetime.now(datetime.UTC))
            feeds.append(feed)
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
            logger.warning(
                "Game feeds: skipped %s (%s)", path, str(exc).splitlines()[0]
            )
    return sorted(feeds, key=lambda feed: feed["name"])


def game_row(entry, model):
    """Adapt a feed match to the shared fixture register."""
    if entry["best_of"] not in (None, 1, 3, 5):
        raise ValueError("invalid best_of")
    start = datetime.datetime.strptime(entry["start"], "%Y-%m-%dT%H:%MZ")
    pct1, pct2 = _pct_pair(entry["p_series"])
    game1, game2 = _pct_pair(entry["p_game"])
    fav = 1 if entry["p_series"] > 0.5 else 2 if entry["p_series"] < 0.5 else 0
    winner = entry["winner"]
    s1, s2 = entry["score1"], entry["score2"]
    row = {
        "id": entry["match_id"],
        "start": entry["start"],
        "day": start.strftime("%Y-%m-%d"),
        "time": start.strftime("%H:%M"),
        "league": entry["section"],
        "event": entry["event"],
        "best_of": entry["best_of"] or 1,
        "bo_known": entry["best_of"] is not None,
        "pct1": pct1,
        "pct2": pct2,
        "game1": game1,
        "game2": game2,
        "fav": fav,
        "method": model,
        "cross": False,
        "calibrated": False,
        "reconstructed": entry["reconstructed"],
        "winner": winner,
        "name1": entry["name1"],
        "name2": entry["name2"],
        "slug1": None,
        "slug2": None,
        "href": entry["url"],
        "score": f"{s1}–{s2}" if s1 is not None and s2 is not None else None,
        "call": ("even" if not fav else "right" if fav == winner else "missed")
        if winner in (1, 2)
        else None,
        "mkt1": None,
        "mkt2": None,
        "mkt_at": None,
        "mkt_url": None,
    }
    if market := entry["market"]:
        row["mkt1"], row["mkt2"] = _pct_pair(market["p"])
        at = datetime.datetime.strptime(market["at"], "%Y-%m-%dT%H:%MZ")
        row["mkt_at"] = f"{at.day} {at.strftime('%b %H:%M')} UTC"
        row["mkt_url"] = market["url"]
    return row


def game_view(feed, now):
    """Group feed calls by status and UTC day, preserving the feed's tiers."""
    groups = {status: [] for status in ("live", "upcoming", "final")}
    for entry in feed["matches"]:
        groups[entry["status"]].append(game_row(entry, feed["model"]))
    for status, rows in groups.items():
        rows.sort(key=lambda r: (r["start"], r["id"]), reverse=status == "final")
    cutoff = (now - datetime.timedelta(days=RECENT_RESULT_DAYS)).strftime(
        "%Y-%m-%dT%H:%MZ"
    )
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    months = {}
    for row in groups["final"]:
        months.setdefault(row["start"][:7], []).append(row)
    return {
        **{
            key: feed[key]
            for key in ("data_through", "model", "source", "name", "game")
        },
        "live": _by_day(groups["live"]),
        "upcoming": _by_day(groups["upcoming"]),
        "past": _by_day([r for r in groups["final"] if cutoff <= r["start"] <= now_s]),
        "months": [
            {
                "key": key,
                "label": datetime.date.fromisoformat(key + "-01").strftime("%B %Y"),
                "count": len(rows),
                "days": _by_day(rows),
            }
            for key, rows in months.items()
        ],
        "upcoming_count": len(groups["upcoming"]),
        "recent_days": RECENT_RESULT_DAYS,
        "leagues": [s["key"] for s in feed["sections"]],
        "major_set": [s["key"] for s in feed["sections"] if s["major"]],
        "filter_noun": "tiers",
        "major_label": "Majors",
        "all_label": "All tiers",
    }


def render_game_pages(feeds, now):
    """Write each game's predictions, monthly results and downloadable feed."""
    folder = Path(site_config.OUTPUT_DIR) / "other"
    for feed in feeds:
        view = game_view(feed, now)
        game = feed["game"]
        context = {"page_key": f"other/{game}", "view": view}
        write(
            folder / f"{game}.html",
            env.get_template("game.html.j2").render(root_path="../", **context),
        )
        write(folder / f"{game}.json", json.dumps(feed, ensure_ascii=False))
        months = view["months"]
        for i, month in enumerate(months):
            write(
                folder / game / f"{month['key']}.html",
                env.get_template("game_results.html.j2").render(
                    root_path="../../",
                    month=month,
                    newer=months[i - 1] if i else None,
                    older=months[i + 1] if i + 1 < len(months) else None,
                    **context,
                ),
            )


def nav_group(feeds):
    return {
        "name": "Other games",
        "links": [
            {
                "key": f"other/{f['game']}",
                "name": f["name"],
                "title": f["name"],
                "question": "Series calls and results",
            }
            for f in feeds
        ],
    }
