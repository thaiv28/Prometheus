"""Daily model-versus-ask paper alerts, with separate forward records.

Domestic major-league FORGE calls are `alert`; calibrated cross-home international
Elo calls are `international_paper_alert`, explicitly experimental in the issue.
Minor-league FORGE calls remain `paper_alert`, recorded but never posted.

All tracks require >5 points over a fresh ask and 6+ hours before start, with
complete settled team results. Each keeps its first terms. International calls
also pin model provenance. The issue reports domestic and international results
separately; retrospective candidates never enter these forward records.
"""

import copy
import datetime
import urllib.parse
from zoneinfo import ZoneInfo

from prometheus import markets, regional_calibration, schedule
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

EDGE = 0.05
MAJORS = {l.value for l in ALL_MAJOR_LEAGUES}
MIN_HOURS = 6
SITE_URL = "https://prometheus.thaiv.dev"
REPORT_URL = "https://github.com/thaiv28/Prometheus/blob/main/docs/market_report.md"
PACIFIC = ZoneInfo("America/Los_Angeles")
OWNER = "thaiv28"


def _start(entry):
    return datetime.datetime.strptime(entry["start"], "%Y-%m-%dT%H:%MZ").replace(
        tzinfo=datetime.UTC
    )


def _stale(log, entry, now):
    """Whether a team in this call has a settled match its ratings lack: the market
    has seen that result, so an edge against it is likely the data's age."""
    through = entry.get("data_through")
    teams = {entry.get("team1"), entry.get("team2")} - {None}
    return bool(
        through and teams and schedule.missing_results(log, now, teams, through)
    )


def select(log, now, edge=EDGE, minor=False, international=False):
    """Alert candidates, soonest first: dicts with the entry, the team backed
    (side 1 or 2), FORGE's chance for it, its price and the edge. Only prices read
    at this build (`market.at` is `now`) count. FORGE calls within a major league,
    or with `minor` within a non-major one (the paper track). A call whose ratings
    lack a team's settled result (`schedule.missing_results`) is skipped.
    `international=True` selects calibrated cross-home international Elo only."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    out = []
    for entry in log.values():
        market = entry.get("market") or {}
        if international:
            homes = [entry.get("home1"), entry.get("home2")]
            scope = (
                entry.get("method") == "elo-cross"
                and all(homes)
                and homes[0] != homes[1]
                and not any(h in INTERNATIONAL_LEAGUES for h in homes)
                and (entry.get("calibration") or {}).get("version")
                == regional_calibration.VERSION
                and regional_calibration.eligible(
                    entry.get("league"), entry.get("event", ""), entry["start"]
                )
            )
        else:
            scope = (
                entry.get("method") == "forge"
                and (entry.get("home1") in MAJORS) != minor
            )
        if not entry.get("matched") or not scope or market.get("at") != now_s:
            continue
        hours = (_start(entry) - now).total_seconds() / 3600
        if hours < MIN_HOURS:
            continue
        if _stale(log, entry, now):
            continue
        sides = [
            (1, entry["p_series"], market.get("ask1")),
            (2, 1 - entry["p_series"], market.get("ask2")),
        ]
        best = max(
            (
                (p - price, side, p, price)
                for side, p, price in sides
                if price is not None and 0 < price < 1
            ),
            default=None,
        )
        if best and best[0] > edge:
            gap, side, p, price = best
            out.append(
                {"entry": entry, "side": side, "p": p, "price": price, "edge": gap}
            )
    return sorted(out, key=lambda a: (a["entry"]["start"], a["entry"]["match_id"]))


def record(alerts, now, key="alert"):
    """Store each alert on its log entry under `key`, unless the match already has one."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    new = 0
    for a in alerts:
        if key not in a["entry"]:
            a["entry"][key] = {
                "side": a["side"],
                "team": a["entry"].get(f"ours{a['side']}")
                or a["entry"].get(f"team{a['side']}"),
                "p": round(a["p"], 4),
                "price": round(a["price"], 4),
                "edge": round(a["edge"], 4),
                "at": now_s,
            }
            if key == "international_paper_alert":
                a["entry"][key]["forecast"] = copy.deepcopy(
                    {
                        name: a["entry"].get(name)
                        for name in (
                            "calibration",
                            "method",
                            "p_game",
                            "p_series",
                            "home1",
                            "home2",
                            "data_through",
                            "start",
                        )
                    }
                )
            new += 1
    return new


def alert_side(entry, alert):
    """Resolve the originally backed team, independently of fixture ordering."""
    team = alert.get("team")
    if team is None:
        return alert["side"]  # legacy records, prior to identity pinning
    return next(
        (i for i in (1, 2) if team == (entry.get(f"ours{i}") or entry.get(f"team{i}"))),
        None,
    )


def paper_record(log, rate=0.07, key="alert"):
    """(alerts settled, won, staked, profit) for $1 on each recorded alert after
    Kalshi's fee at `rate`; `key="paper_alert"` for the minor-league paper track."""
    bets = settled_alerts(log, rate, key)
    profit = sum(b["profit"] for b in bets)
    return len(bets), sum(b["won"] for b in bets), float(len(bets)), profit


def settled_alerts(log, rate=0.07, key="alert"):
    """Each settled alert as a $1 paper bet: won, profit after Kalshi's fee at
    `rate`, and CLV (closing line value: the last price before the start for the
    team backed, minus the price alerted; None when the match has no price). CLV
    doesn't wait on the result, so it shows an edge in far fewer bets than profit."""
    out = []
    for entry in log.values():
        alert = entry.get(key)
        if not alert or entry.get("winner") not in (1, 2):
            continue
        side = alert_side(entry, alert)
        if side is None:
            continue
        won = entry["winner"] == side
        price = alert["price"]
        close = (entry.get("market") or {}).get("p")
        if close is not None and side == 2:
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


def shown(log, now, chosen, key="alert"):
    """Matches for today's issue, soonest first: those qualifying now (`chosen`)
    and those alerted earlier today (UTC) that haven't started."""
    now_s, day = now.strftime("%Y-%m-%dT%H:%MZ"), now.strftime("%Y-%m-%d")
    ids = {a["entry"]["match_id"] for a in chosen}
    out = [
        e
        for e in log.values()
        if e.get(key)
        and alert_side(e, e[key]) is not None
        and e["start"] > now_s
        and (e["match_id"] in ids or e[key]["at"][:10] == day)
    ]
    return sorted(out, key=lambda e: (e["start"], e["match_id"]))


def _row(entry, now_s, slugify, team_slugs, key="alert"):
    side = alert_side(entry, entry[key])
    p, price, edge = _current(entry, side, now_s)
    if key == "international_paper_alert":
        p, price = entry[key]["p"], entry[key]["price"]
    was = 100 * entry[key]["edge"]
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


def issue(
    entries, log, now, data_through, slugify, team_slugs, international_entries=()
):
    """(title, body) of the day's alert issue, in GitHub markdown: `entries` from
    `shown`, at this run's prices."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    live = sum(
        1
        for e in entries
        if (_current(e, alert_side(e, e["alert"]), now_s)[2] or 0) > EDGE
    )
    gone = len(entries) - live
    title = (
        f"{day_key(now)} {live} FORGE call{'s' if live != 1 else ''} {round(100 * EDGE)}+ points above Kalshi"
        + (f" ({gone} gone)" if gone else "")
    )
    if international_entries:
        title += f"; {len(international_entries)} international paper"
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
            f"starting {MIN_HOURS}+ hours from now"
            + (
                f"; {gone} earlier alert{'s' if gone != 1 else ''} no longer qualif{'y' if gone != 1 else 'ies'}"
                if gone
                else ""
            )
            + f". Prices as of {now:%H:%M} UTC; games through {data_through}.",
            "",
            "## Domestic — FORGE",
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
            f"Edge over {round(100 * EDGE)} points, {MIN_HOURS} or more hours before the start. Backtest: "
            "+12.9% after fees (−5.0% to +31.2%), closing line value +0.95 points (−0.13 to +2.03); "
            "neither significant. A paper test, not advice. Each alert is scored at its first price.",
            "</details>",
            "",
            *international_section(
                international_entries, log, now_s, slugify, team_slugs
            ),
            f"cc @{OWNER}",
        ]
    )
    return title, body


INTERNATIONAL_KEY = "international_paper_alert"
INTERNATIONAL_HEAD = [
    HEAD[0]
    .replace("FORGE", "First Elo")
    .replace("Kalshi ask", "First ask")
    .replace("Edge", "Current edge"),
    HEAD[1],
]
INTERNATIONAL_REPORT = "https://github.com/thaiv28/Prometheus/blob/main/docs/research/international_alerts.md"


def international_section(entries, log, now_s, slugify, team_slugs):
    settled, won, staked, profit = paper_record(log, key=INTERNATIONAL_KEY)
    clv, beat = clv_summary(settled_alerts(log, key=INTERNATIONAL_KEY))
    record_line = (
        f"**International paper record:** {settled} settled, {won} won, {100 * profit / staked:+.1f}% after fees"
        if settled
        else "**International paper record:** none settled yet."
    )
    if clv is not None:
        record_line += f"; closing line value {100 * clv:+.1f} points, {round(100 * beat)}% beat the close"
    return [
        "## International — experimental paper track",
        "",
        "Calibrated cross-region Elo, separate from the domestic FORGE alerts above. "
        "Same >5-point edge and 6+ hour minimum; fresh asks and complete team results required. "
        "No demonstrated market edge.",
        "",
        *INTERNATIONAL_HEAD,
        *(_row(e, now_s, slugify, team_slugs, INTERNATIONAL_KEY) for e in entries),
        *([] if entries else ["No upcoming qualifying international calls to show."]),
        "",
        record_line,
        "",
        "Each paper call keeps its first team, chance, ask, timestamp and model snapshot; "
        "returns use those original terms; the current edge can change. "
        "Historical candidates are excluded from this forward record.",
        "",
        f"[Retrospective evaluation]({INTERNATIONAL_REPORT}): 46 calls at 12h, "
        "+43.0% after assumed fees (95% −34.6% to +138.1%), CLV −0.42 points. "
        "Removing the two largest wins gives −11.0%; only three tournaments contributed calls. "
        "This does not validate the full first-qualifying hourly policy.",
        "",
    ]


def update(log, now, data_through, slugify, team_slugs):
    """Record first terms and render separate domestic/international issue tracks.

    Minor-league FORGE paper calls remain unposted. No historical backfill.
    """
    record(select(log, now, minor=True), now, key="paper_alert")
    chosen = select(log, now)
    international = select(log, now, international=True)
    new_ids = [a["entry"]["match_id"] for a in chosen if "alert" not in a["entry"]]
    new_international = [
        a["entry"]["match_id"]
        for a in international
        if INTERNATIONAL_KEY not in a["entry"]
    ]
    record(chosen, now)
    record(international, now, key=INTERNATIONAL_KEY)
    entries = shown(log, now, chosen)
    international_entries = shown(log, now, international, INTERNATIONAL_KEY)
    if not entries and not international_entries:
        return None
    title, body = issue(
        entries, log, now, data_through, slugify, team_slugs, international_entries
    )
    comment = None
    if new_ids or new_international:
        now_s = now.strftime("%Y-%m-%dT%H:%MZ")
        parts = []
        if new_ids:
            rows = [
                _row(e, now_s, slugify, team_slugs)
                for e in entries
                if e["match_id"] in new_ids
            ]
            parts += [
                f"**New:** {len(rows)} match{'es' if len(rows) != 1 else ''} at {now:%H:%M} UTC.",
                "",
                *HEAD,
                *rows,
                "",
            ]
        if new_international:
            rows = [
                _row(e, now_s, slugify, team_slugs, INTERNATIONAL_KEY)
                for e in international_entries
                if e["match_id"] in new_international
            ]
            parts += [
                f"**New international experimental paper calls:** {len(rows)} at {now:%H:%M} UTC. Separate from domestic FORGE alerts; no demonstrated market edge.",
                "",
                *INTERNATIONAL_HEAD,
                *rows,
                "",
            ]
        comment = "\n".join([*parts, f"cc @{OWNER}"])
    return {
        "title": title,
        "body": body,
        "day": day_key(now),
        "comment": comment,
        "new": len(new_ids) + len(new_international),
    }
