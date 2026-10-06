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
made before the match, with CLV (the closing price for the team backed minus
the alerted price). `issue` writes the GitHub issue the publish workflow posts.
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
    bets = settled_alerts(log, rate)
    profit = sum(b["profit"] for b in bets)
    return len(bets), sum(b["won"] for b in bets), float(len(bets)), profit


def settled_alerts(log, rate=0.07):
    """Each settled alert as a $1 paper bet: won, profit after Kalshi's fee at
    `rate`, and CLV (closing line value: the last price before the start for the
    team backed, minus the price alerted; None when the match has no price). CLV
    doesn't wait on the result, so it shows an edge in far fewer bets than profit."""
    out = []
    for entry in log.values():
        alert = entry.get("alert")
        if not alert or entry.get("winner") not in (1, 2):
            continue
        won = entry["winner"] == alert["side"]
        price = alert["price"]
        close = (entry.get("market") or {}).get("p")
        if close is not None and alert["side"] == 2:
            close = 1 - close
        out.append(
            {
                "won": won,
                "profit": (1 / price - 1 if won else -1) - markets.fee(price, 1, rate),
                "clv": None if close is None else close - price,
            }
        )
    return out


def clv_summary(bets):
    """(mean CLV, share of bets beating the close) over bets with a close, or
    (None, None)."""
    clvs = [b["clv"] for b in bets if b["clv"] is not None]
    if not clvs:
        return None, None
    return sum(clvs) / len(clvs), sum(c > 0 for c in clvs) / len(clvs)


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


def _current(entry, side, now_s):
    """FORGE's chance for `side`, what a contract on it costs now (None when this
    run has no price for the match) and the edge."""
    market = entry.get("market") or {}
    p = entry["p_series"] if side == 1 else 1 - entry["p_series"]
    price = market.get(f"ask{side}") if market.get("at") == now_s else None
    return p, price, None if price is None else p - price


def shown(log, now, chosen):
    """Matches for today's issue, soonest first: those qualifying now (`chosen`)
    and those alerted earlier today (UTC) that haven't started."""
    now_s, day = now.strftime("%Y-%m-%dT%H:%MZ"), now.strftime("%Y-%m-%d")
    ids = {a["entry"]["match_id"] for a in chosen}
    out = [
        e
        for e in log.values()
        if e.get("alert")
        and e["start"] > now_s
        and (e["match_id"] in ids or e["alert"]["at"][:10] == day)
    ]
    return sorted(out, key=lambda e: (e["start"], e["match_id"]))


def _row(entry, now_s, slugify, team_slugs):
    side = entry["alert"]["side"]
    p, price, edge = _current(entry, side, now_s)
    was = 100 * entry["alert"]["edge"]
    if edge is None:
        edge_cell = f"no price now (alerted at +{was:.1f})"
    elif edge > EDGE:
        edge_cell = f"**+{100 * edge:.1f}**"
    else:
        edge_cell = f"gone: {100 * edge:+.1f} now (alerted at +{was:.1f})"
    back, other = _name(entry, side), _name(entry, 3 - side)
    return (
        f"| {_when(entry)} | {entry.get('event') or entry.get('league')} | **{back}** v {other} | "
        f"{round(100 * p)}% | {'—' if price is None else f'{round(100 * price)}¢'} | {edge_cell} | "
        f"{_links(entry, side, slugify, team_slugs)} |"
    )


HEAD = [
    "| Start (UTC / Pacific) | Event | Back | FORGE | Kalshi ask | Edge | Links |",
    "|---|---|---|---:|---:|---:|---|",
]


def issue(entries, log, now, data_through, slugify, team_slugs):
    """(title, body) of the day's alert issue, in GitHub markdown: `entries` from
    `shown`, at this run's prices."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    live = sum(
        1 for e in entries if (_current(e, e["alert"]["side"], now_s)[2] or 0) > EDGE
    )
    gone = len(entries) - live
    title = (
        f"{day_key(now)} {live} FORGE call{'s' if live != 1 else ''} {round(100 * EDGE)}+ points above Kalshi"
        + (f" ({gone} gone)" if gone else "")
    )
    settled, won, staked, profit = paper_record(log)
    clv, beat = clv_summary(settled_alerts(log))
    if settled:
        record_line = (
            f"**Alerts so far:** {settled} settled, {won} won, {100 * profit / staked:+.1f}% after the 7% fee"
            + (
                f"; closing line value {100 * clv:+.1f} points, {round(100 * beat)}% beat the close"
                if clv is not None
                else ""
            )
            + "."
        )
    else:
        record_line = "**Alerts so far:** none settled yet."
    body = "\n".join(
        [
            f"**{live} FORGE call{'s' if live != 1 else ''}** {round(100 * EDGE)}+ points above Kalshi's ask, "
            f"starting within {MAX_HOURS} hours"
            + (
                f"; {gone} earlier alert{'s' if gone != 1 else ''} no longer qualif{'y' if gone != 1 else 'ies'}"
                if gone
                else ""
            )
            + f". Prices as of {now:%H:%M} UTC; games through {data_through}.",
            "",
            *HEAD,
            *(_row(e, now_s, slugify, team_slugs) for e in entries),
            "",
            "**Edge:** FORGE's series chance minus the ask, in points. The 7% fee costs 2–5¢ per $1 more.",
            "",
            record_line,
            "",
            "<details><summary>How this is chosen</summary>",
            "",
            f"FORGE calls only (same major league); Elo lost to the market in the [backtest]({REPORT_URL}). "
            f"Edge over {round(100 * EDGE)} points, {MIN_HOURS}–{MAX_HOURS} hours before the start. Backtest: "
            "+12.9% after fees (−5.0% to +31.2%), closing line value +0.95 points (−0.13 to +2.03); "
            "neither significant. A paper test, not advice. Each alert is scored at its first price.",
            "</details>",
            "",
            f"cc @{OWNER}",
        ]
    )
    return title, body


def update(log, now, data_through, slugify, team_slugs):
    """Select and record this run's alerts, then the issue to post: a dict with
    title, body, day (the title prefix the workflow matches) and comment (the
    matches new since the last run, which GitHub emails; None when there are
    none), or None when there is nothing to show today."""
    chosen = select(log, now)
    new_ids = [a["entry"]["match_id"] for a in chosen if "alert" not in a["entry"]]
    record(chosen, now)
    entries = shown(log, now, chosen)
    if not entries:
        return None
    title, body = issue(entries, log, now, data_through, slugify, team_slugs)
    comment = None
    if new_ids:
        now_s = now.strftime("%Y-%m-%dT%H:%MZ")
        rows = [
            _row(e, now_s, slugify, team_slugs)
            for e in entries
            if e["match_id"] in new_ids
        ]
        comment = "\n".join(
            [
                f"**New:** {len(rows)} match{'es' if len(rows) != 1 else ''} at {now:%H:%M} UTC.",
                "",
                *HEAD,
                *rows,
                "",
                f"cc @{OWNER}",
            ]
        )
    return {
        "title": title,
        "body": body,
        "day": day_key(now),
        "comment": comment,
        "new": len(new_ids),
    }
