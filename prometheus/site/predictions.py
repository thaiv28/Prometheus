"""The Predictions page, the prediction log update and the Kalshi alert."""

import datetime
import json
import os

from prometheus import alerts, markets, schedule
from prometheus.evaluation import paired_bootstrap
from prometheus.site import config as site_config
from prometheus.site.config import (
    HOME_FIXTURE_DAYS,
    HOME_FIXTURES,
    PREDICTIONS,
    RECENT_RESULT_DAYS,
)
from prometheus.site.render import _slugify, _write, env
from prometheus.types import INTERNATIONAL_LEAGUES


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
        row["mkt_url"] = (
            markets.event_url(market["ticker"]) if market.get("ticker") else None
        )
    for side in (1, 2):
        name = schedule.display_name(entry, side)
        slug = _slugify(entry[f"ours{side}"]) if entry.get(f"ours{side}") else None
        row[f"name{side}"] = name
        row[f"slug{side}"] = slug if slug in team_slugs else None
    if row["winner"] in (1, 2):
        s1, s2 = entry.get("score1"), entry.get("score2")
        row["score"] = (
            f"{s1}–{s2}"
            if s1 is not None and s2 is not None
            else ("W–L" if row["winner"] == 1 else "L–W")
        )
        row["call"] = (
            "even"
            if row["fav"] == 0
            else ("right" if row["fav"] == row["winner"] else "missed")
        )
    return row


def _by_day(rows):
    """[(day ISO, label, rows)] in the order the rows come."""
    days = []
    for r in rows:
        if not days or days[-1][0] != r["day"]:
            d = datetime.date.fromisoformat(r["day"])
            days.append(
                (r["day"], f"{d.strftime('%A')} {d.day} {d.strftime('%B')}", [])
            )
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
    upcoming = sorted(
        (e for e in entries if e["start"] > now_s),
        key=lambda e: (e["start"], e["match_id"]),
    )
    past = sorted(
        (e for e in entries if e["start"] <= now_s),
        key=lambda e: (e["start"], e["match_id"]),
        reverse=True,
    )
    up_rows = [fixture_row(e, team_slugs) for e in upcoming]
    recent_from = (now - datetime.timedelta(days=RECENT_RESULT_DAYS)).strftime(
        "%Y-%m-%dT%H:%MZ"
    )
    recent = [e for e in past if e["start"] >= recent_from]
    horizon = (now + datetime.timedelta(days=HOME_FIXTURE_DAYS)).strftime(
        "%Y-%m-%dT%H:%MZ"
    )
    home = [
        fixture_row(e, team_slugs)
        for e in upcoming
        if schedule.is_major(e) and e["start"] <= horizon
    ][:HOME_FIXTURES]
    leagues = {e["league"] for e in entries}
    majors = env.globals["major_leagues"]
    return {
        "upcoming": _by_day(up_rows),
        "past": _by_day([fixture_row(e, team_slugs) for e in recent]),
        "upcoming_count": len(up_rows),
        "past_count": len(past),
        "recent_days": RECENT_RESULT_DAYS,
        "months": result_months(past, team_slugs),
        "scorecard": schedule.scorecard(entries),
        "vs_market": method_groups(schedule.market_scorecard(entries)),
        "edges": method_groups(schedule.edge_record(entries)),
        "backtest_span": backtest_span(entries),
        "alerts": alert_record(entries),
        "market_min": schedule.MARKET_MIN_SERIES,
        "home": _by_day(home),
        "home_count": len(home),
        "leagues": [l for l in majors if l in leagues]
        + [l for l in INTERNATIONAL_LEAGUES if l in leagues]
        + sorted(leagues - set(majors) - set(INTERNATIONAL_LEAGUES)),
        "major_set": [
            l for l in [*majors, *INTERNATIONAL_LEAGUES] if l in leagues or l in majors
        ],
        "since": min((e["start"][:10] for e in entries), default=None),
        "saved_since": min(
            (e["start"][:10] for e in entries if not e.get("reconstructed")),
            default=None,
        ),
    }


def result_months(past, team_slugs):
    """The results pages, newest month first: key ('2026-09'), label
    ('September 2026'), count and the fixture rows by day (team links from
    `results/`)."""
    months = {}
    for e in past:  # newest first
        months.setdefault(e["start"][:7], []).append(e)
    out = []
    for key, entries in months.items():
        first = datetime.date.fromisoformat(key + "-01")
        out.append(
            {
                "key": key,
                "label": f"{first.strftime('%B')} {first.year}",
                "count": len(entries),
                "days": _by_day([fixture_row(e, team_slugs) for e in entries]),
            }
        )
    return out


def render_results(view):
    """One results page per month, with links to the months either side."""
    folder = os.path.join(site_config.OUTPUT_DIR, "results")
    os.makedirs(folder, exist_ok=True)
    months = view["months"]
    template = env.get_template("results.html.j2")
    for i, month in enumerate(months):
        _write(
            os.path.join(folder, f"{month['key']}.html"),
            template.render(
                page_key="predictions",
                root_path="../",
                view=view,
                month=month,
                newer=months[i - 1] if i > 0 else None,
                older=months[i + 1] if i + 1 < len(months) else None,
            ),
        )


def method_groups(rows):
    """Tables III and IV's row groups: FORGE then Other, each with its saved calls
    and its backtest (`schedule.BET_GROUPS`), from rows carrying label and source."""
    groups = []
    for label in ("FORGE", "Other"):
        sources = [
            {
                "name": source,
                "rows": [
                    r for r in rows if r["label"] == label and r["source"] == source
                ],
            }
            for name, source in schedule.BET_GROUPS
            if name == label
        ]
        groups.append({"label": label, "sources": sources})
    return groups


def backtest_span(entries):
    """(first, last) start day of the settled rebuilt calls with a 12-hour price:
    the backtest rows' dates."""
    days = [
        e["start"][:10]
        for e in entries
        if e.get("reconstructed") and e.get("market_12h") and e.get("winner") in (1, 2)
    ]
    return (min(days), max(days)) if days else None


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


def render_predictions(view, coverage):
    _write(
        os.path.join(site_config.OUTPUT_DIR, "predictions.html"),
        env.get_template("predictions.html.j2").render(
            page_key="predictions",
            root_path="",
            metric=PREDICTIONS,
            view=view,
            coverage=coverage,
        ),
    )


def update_predictions(states):
    """Fetch the schedule and update the prediction log; on any failure keep the
    log as it was, so the site still builds (with yesterday's calls).

    Set PREDICTIONS_FETCH=0 to skip the fetch. Returns (log, coverage) where
    coverage counts this fetch's matched and unmatched matches (None if skipped).
    """
    if os.environ.get("PREDICTIONS_FETCH", "1") == "0":
        return schedule.load_log(site_config.PREDICTIONS_LOG), None
    try:
        log, coverage = schedule.build_predictions(states, site_config.PREDICTIONS_LOG)
        print(
            f"Predictions: {coverage['matched']} of {coverage['matches']} scheduled matches rated; "
            f"{len(coverage['unmatched'])} team names not matched; "
            f"{coverage.get('priced') if coverage.get('priced') is not None else 'no'} priced by Kalshi"
        )
        return log, coverage
    except Exception as e:  # network, rate limit, schema change: never block the build
        print(f"Predictions: schedule not updated ({e}); using the saved log.")
        return schedule.load_log(site_config.PREDICTIONS_LOG), None


def warn_missing_results(log, data_through, now=None):
    """Print a GitHub Actions warning when the log has settled matches the data
    should hold but doesn't (the CSV download has failed for days). Returns them."""
    now = now or datetime.datetime.now(datetime.UTC)
    missing = schedule.missing_results(log, now, data_through=data_through)
    if missing:
        last = max(e["start"] for e in missing)[:10]
        print(
            f"::warning::Data is stale: games through {data_through}, but "
            f"{len(missing)} settled matches up to {last} are missing."
        )
    return missing


def write_kalshi_alert(log, coverage, team_slugs, path=None):
    """Record this build's alerts in the log and write the day's issue to `path`
    (`alerts.update`). Runs only on fresh prices (this build's fetch worked) and
    unless KALSHI_ALERTS=0. A stale file from an earlier run is always removed,
    so a day without alerts posts nothing. Returns the issue dict or None."""
    path = path or site_config.KALSHI_ALERT
    if os.path.exists(path):
        os.remove(path)
    if (
        os.environ.get("KALSHI_ALERTS", "1") == "0"
        or not coverage
        or not coverage.get("priced")
    ):
        return None
    now = datetime.datetime.strptime(coverage["at"], "%Y-%m-%dT%H:%MZ").replace(
        tzinfo=datetime.UTC
    )
    alert = alerts.update(log, now, coverage.get("data_through"), _slugify, team_slugs)
    schedule.save_log(log, site_config.PREDICTIONS_LOG)
    if alert is None:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(json.dumps(alert, ensure_ascii=False))
    print(f"Kalshi alert: {alert['new']} new match(es); issue written to {path}")
    return alert
