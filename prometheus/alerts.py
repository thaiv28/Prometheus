"""Daily alerts where FORGE's chance beats Kalshi's price by enough to matter.

After each build has refreshed the prediction log (our calls and Kalshi's prices),
`select` picks matches that start in the next `MIN_HOURS`–`MAX_HOURS` hours,
called by FORGE (both teams from one major league), where FORGE's chance for a
team beats what a contract on that team costs now (the ask) by more than `EDGE`.
That is the slice the market backtest supports (`docs/market_report.md`): Elo
calls in other leagues lost to the market and are never alerted.

Each alert is recorded on its log entry (`alert`: the team backed, FORGE's
chance, the price, the edge and when), once: a match alerted on two days keeps
its first alert, as a paper bet would. `paper_record` scores settled alerts as
$1 bets after Kalshi's taker fee, so the issue carries a running record of calls
made before the match. `issue` writes the GitHub issue the publish workflow posts.
"""

import datetime
import urllib.parse
from zoneinfo import ZoneInfo

from prometheus import markets

EDGE = 0.05
MIN_HOURS, MAX_HOURS = 6, 36
SITE_URL = "https://prometheus.thaiv.dev"
REPORT_URL = "https://github.com/thaiv28/Prometheus/blob/main/docs/market_report.md"
PACIFIC = ZoneInfo("America/Los_Angeles")
OWNER = "thaiv28"


def _start(entry):
    return datetime.datetime.strptime(entry["start"], "%Y-%m-%dT%H:%MZ").replace(
        tzinfo=datetime.timezone.utc
    )


def select(log, now, edge=EDGE):
    """Alert candidates, soonest first: dicts with the entry, the team backed
    (side 1 or 2), FORGE's chance for it, its price and the edge. Only prices read
    at this build (`market.at` is `now`) count."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    out = []
    for entry in log.values():
        market = entry.get("market") or {}
        if (
            not entry.get("matched")
            or entry.get("method") != "forge"
            or market.get("at") != now_s
        ):
            continue
        hours = (_start(entry) - now).total_seconds() / 3600
        if not MIN_HOURS <= hours <= MAX_HOURS:
            continue
        sides = [
            (1, entry["p_series"], market.get("ask1")),
            (2, 1 - entry["p_series"], market.get("ask2")),
        ]
        best = max(
            (
                (p - price, side, p, price)
                for side, p, price in sides
                if price is not None
            ),
            default=None,
        )
        if best and best[0] > edge:
            gap, side, p, price = best
            out.append(
                {"entry": entry, "side": side, "p": p, "price": price, "edge": gap}
            )
    return sorted(out, key=lambda a: (a["entry"]["start"], a["entry"]["match_id"]))


def record(alerts, now):
    """Store each alert on its log entry, unless the match already has one."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    new = 0
    for a in alerts:
        if "alert" not in a["entry"]:
            a["entry"]["alert"] = {
                "side": a["side"],
                "p": round(a["p"], 4),
                "price": round(a["price"], 4),
                "edge": round(a["edge"], 4),
                "at": now_s,
            }
            new += 1
    return new


def paper_record(log, rate=0.07):
    """(alerts settled, won, staked, profit) for $1 on each recorded alert after
    Kalshi's fee at `rate`."""
    settled = won = 0
    profit = 0.0
    for entry in log.values():
        alert = entry.get("alert")
        if not alert or entry.get("winner") not in (1, 2):
            continue
        settled += 1
        hit = entry["winner"] == alert["side"]
        won += hit
        profit += (1 / alert["price"] - 1 if hit else -1) - markets.fee(
            alert["price"], 1, rate
        )
    return settled, won, float(settled), profit


def _name(entry, side):
    return entry.get(f"ours{side}") or entry.get(f"team{side}")


def _when(entry):
    start = _start(entry)
    local = start.astimezone(PACIFIC)
    return f"{start:%a} {start.day} {start:%b} {start:%H:%M} / {local:%H:%M}"


def _links(entry, side, slugify, team_slugs):
    back, other = _name(entry, side), _name(entry, 3 - side)
    ticker = (entry.get("market") or {}).get("ticker")
    links = []
    if ticker:
        links.append(f"[Kalshi]({markets.event_url(ticker)})")
    links.append(
        f"[Prediction]({SITE_URL}/predictions.html?search={urllib.parse.quote(back)})"
    )
    for team in (back, other):
        slug = slugify(team)
        if slug in team_slugs:
            links.append(f"[{team}]({SITE_URL}/teams/{slug}.html)")
    return " · ".join(links)


def day_key(now):
    """The start of every alert title on `now`'s day, which the workflow uses to
    find that day's issue."""
    return f"Kalshi edges for {now:%a} {now.day} {now:%b}:"


def issue(alerts, log, now, data_through, slugify, team_slugs):
    """(title, body) of the day's alert issue, in GitHub markdown."""
    n = len(alerts)
    title = f"{day_key(now)} {n} FORGE call{'s' if n != 1 else ''} at least {round(100 * EDGE)} points above the price"
    rows = []
    for a in alerts:
        e, side = a["entry"], a["side"]
        back, other = _name(e, side), _name(e, 3 - side)
        rows.append(
            f"| {_when(e)} | {e.get('event') or e.get('league')} | **{back}** v {other} | "
            f"{round(100 * a['p'])}% | {round(100 * a['price'])}¢ | **+{100 * a['edge']:.1f}** | "
            f"{_links(e, side, slugify, team_slugs)} |"
        )
    settled, won, staked, profit = paper_record(log)
    if settled:
        record_line = (
            f"**Alerts so far:** {settled} settled, {won} won, {profit:+.2f} dollars on {staked:.0f} staked "
            f"({100 * profit / staked:+.1f}%) after the 7% taker fee."
        )
    else:
        record_line = "**Alerts so far:** none settled yet."
    body = "\n".join(
        [
            f"FORGE sees **{n} match{'es' if n != 1 else ''}** where its chance beats Kalshi's buying price by "
            f"{round(100 * EDGE)} points or more, starting in the next {MAX_HOURS} hours. Prices were read at the "
            f"{now:%H:%M} UTC build; FORGE's calls use games through {data_through}.",
            "",
            "| Start (UTC / Pacific) | Event | Back | FORGE | Kalshi ask | Edge | Links |",
            "|---|---|---|---:|---:|---:|---|",
            *rows,
            "",
            "**Edge** is FORGE's series chance minus the price you'd pay now (the ask), in points. Kalshi's 7% taker "
            "fee costs about 2–5¢ per $1 on top.",
            "",
            record_line,
            "",
            "<details><summary>How this is chosen</summary>",
            "",
            f"Only FORGE calls (both teams from the same major league), since Elo calls in other leagues lost to the "
            f"market in the [backtest]({REPORT_URL}). The edge must exceed {round(100 * EDGE)} points and the match must "
            f"start {MIN_HOURS} to {MAX_HOURS} hours after the build. In the backtest, value bets above 5 points "
            "returned +12.9% after taker fees (−5.0% to +31.2%), which is not significant. Treat these as a "
            "paper-trading test, not advice. Each alerted match is recorded in the prediction log and scored above "
            "once it is played.",
            "</details>",
            "",
            f"cc @{OWNER}",
        ]
    )
    return title, body
