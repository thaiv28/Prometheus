"""
update_prices.py: refresh Kalshi's prices and the alerts between site builds.

Run hourly by `.github/workflows/prices.yml`. It needs no database and doesn't
rebuild the site: it reads the prediction log, fetches Kalshi's open series
markets once, updates the price on every rated match that hasn't started
(`markets.attach_prices`; prices still freeze at the start), records new alerts
and writes the day's alert issue (`alerts.update`), then writes `kalshi.json`
and `predictions.json`, which the workflow uploads to the live site. The
Predictions page and home's fixtures read `kalshi.json` when they load.

Kalshi names are matched against the teams in the log (every team we could
price is there); team page links come from the live site's `teams.json`.

Usage:
    uv run python scripts/update_prices.py [--log data/predictions.json] [--out output-prices]
"""

import argparse
import datetime
import json
import os
import urllib.request

import pandas as pd

from prometheus import alerts, markets, schedule

TEAMS_URL = "https://prometheus.thaiv.dev/teams.json"


def team_matcher(log):
    """`schedule.TeamMatcher` over the teams in the log, newest first, with the
    Leaguepedia and Kalshi aliases."""
    latest = {}
    for e in log.values():
        for side in (1, 2):
            name = e.get(f"ours{side}")
            if name:
                latest[name] = max(latest.get(name, ""), e["start"])
    teams = pd.DataFrame(
        {"teamname": list(latest), "latest_date": list(latest.values())}
    )
    aliases = (
        json.loads(schedule.ALIASES_PATH.read_text())
        if schedule.ALIASES_PATH.exists()
        else {}
    )
    return schedule.TeamMatcher(teams, {**aliases, **markets.MARKET_ALIASES})


def team_pages(url=TEAMS_URL):
    """{team name: page slug} from the site's search index; empty on failure."""
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": markets.USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return {t["n"]: t["s"] for t in json.load(response)}
    except Exception as e:  # links are a convenience; never fail the update
        print(f"Team pages not loaded ({e}); the issue will lack team links.")
        return {}


def run(log_path, out_dir, alert_path, now=None, fetch=None, pages=None):
    """One update. Returns a summary dict (also printed)."""
    now = (now or datetime.datetime.now(datetime.timezone.utc)).replace(
        second=0, microsecond=0
    )
    if os.path.exists(alert_path):
        os.remove(alert_path)
    log = schedule.load_log(log_path)
    if not log:
        return {"priced": 0, "alert": None, "note": "no prediction log"}
    open_markets = (fetch or markets.fetch_open_markets)()
    priced = markets.attach_prices(log, open_markets, team_matcher(log), now)

    alert = None
    if os.environ.get("KALSHI_ALERTS", "1") != "0" and priced:
        pages = team_pages() if pages is None else pages
        now_s = now.strftime("%Y-%m-%dT%H:%MZ")
        through = max(
            (e.get("data_through") or "" for e in log.values() if e["start"] > now_s),
            default="",
        )
        alert = alerts.update(
            log, now, through or "the last build", pages.get, set(pages.values())
        )
        if alert:
            os.makedirs(os.path.dirname(alert_path) or ".", exist_ok=True)
            with open(alert_path, "w") as f:
                json.dump(alert, f, ensure_ascii=False)

    schedule.save_log(log, log_path)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "kalshi.json"), "w") as f:
        json.dump(markets.prices_file(log, now), f, separators=(",", ":"))
    with open(os.path.join(out_dir, "predictions.json"), "w") as f:
        json.dump(
            markets.published_log(log), f, ensure_ascii=False, separators=(",", ":")
        )
    return {
        "priced": priced,
        "alert": alert and {"title": alert["title"], "new": alert["new"]},
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--log", default="data/predictions.json")
    parser.add_argument(
        "--out",
        default="output-prices",
        help="Where kalshi.json and predictions.json go",
    )
    parser.add_argument("--alert", default="data/kalshi_alert.json")
    args = parser.parse_args()
    print(json.dumps(run(args.log, args.out, args.alert)))


if __name__ == "__main__":
    main()
