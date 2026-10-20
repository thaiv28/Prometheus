"""First positive after-fee blended edges in domestic/international fixtures.

Legacy international records remain authoritative; unposted minor records are
retained as history. Notifications never reconstruct historical candidates.
"""

import copy
import datetime
import math
import urllib.parse
from zoneinfo import ZoneInfo

from prometheus import alert_contract, forecast_groups, markets, schedule, trading

EDGE = 0.0
MIN_HOURS = 6
SITE_URL = "https://prometheus.thaiv.dev"
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


def select(log, now, edge=EDGE):
    """Blended net edge >edge, 6h, same-run prices and complete team results."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    out = []
    for entry in log.values():
        market = entry.get("market") or {}
        p = entry.get("p_series")
        if (
            not entry.get("matched")
            or entry.get("winner") in (1, 2)
            or entry.get("method") not in ("forge", "elo", "elo-cross")
            or forecast_groups.classify(entry) not in alert_contract.TRADE_GROUPS
            or not isinstance(p, (int, float))
            or not math.isfinite(p)
            or not 0 < p < 1
            or market.get("at") != now_s
        ):
            continue
        hours = (_start(entry) - now).total_seconds() / 3600
        if hours < MIN_HOURS:
            continue
        if _stale(log, entry, now):
            continue
        estimate = trading.quote(entry, execution_fees=True)
        if estimate and estimate["pick"]["net_edge"] > edge:
            out.append({"entry": entry, **estimate["pick"]})
    return sorted(out, key=lambda a: (a["entry"]["start"], a["entry"]["match_id"]))


def mark_candidates(log, now):
    """Refresh eligible forecasts, regardless of edge, lead or saved quote time."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    count = 0
    for entry in log.values():
        if entry.get("winner") in (1, 2) or _start(entry) <= now:
            continue
        group = forecast_groups.classify(entry)
        p = entry.get("p_series")
        if (
            entry.get("matched")
            and entry.get("method") in ("forge", "elo", "elo-cross")
            and group in alert_contract.TRADE_GROUPS
            and isinstance(p, (int, float))
            and math.isfinite(p)
            and 0 < p < 1
            and (entry.get("market") or {}).get("ticker")
            and not _stale(log, entry, now)
        ):
            try:
                entry[alert_contract.CANDIDATE_KEY] = alert_contract.candidate(
                    entry, now_s, group, forecast_groups.international(entry)
                )
                count += 1
                continue
            except (KeyError, TypeError):
                pass  # A malformed entry is never traded; the build carries on.
        entry.pop(alert_contract.CANDIDATE_KEY, None)
    return count


def record(alerts, now, key="alert"):
    """Store each alert on its log entry under `key`, unless the match already has one."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    new = 0
    for a in alerts:
        if key not in a["entry"] and not (
            key == "alert" and a["entry"].get(INTERNATIONAL_KEY)
        ):
            a["entry"][key] = {
                "side": a["side"],
                "team": a["entry"].get(f"ours{a['side']}")
                or a["entry"].get(f"team{a['side']}"),
                "p": round(a["p"], 4),
                "price": round(a["price"], 4),
                "edge": round(a["edge"], 4),
                "at": now_s,
            }
            if a.get("trading"):
                a["entry"][key].update(
                    trading=copy.deepcopy(a["trading"]),
                    policy=a["trading"]["policy"],
                    net_edge=round(a["net_edge"], 6),
                    fee=a["fee"],
                )
            if a.get("fee_policy"):
                a["entry"][key]["fee_policy"] = copy.deepcopy(a["fee_policy"])
            if key in ("alert", INTERNATIONAL_KEY):
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
            a["entry"][key]["group"] = forecast_groups.classify(a["entry"])
            if key == "alert":
                a["entry"][key]["forecast"]["international"] = (
                    forecast_groups.international(a["entry"])
                )
                a["entry"][key]["execution"] = alert_contract.identity(
                    a["entry"], a["entry"][key]
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
    """Current model chance for `side`, what a contract on it costs now (None when this
    run has no price for the match) and the edge."""
    market = entry.get("market") or {}
    if (
        market.get("at") != now_s
        or (estimate := trading.quote(entry, execution_fees=True)) is None
    ):
        return None, None, None
    quote = next((q for q in estimate["choices"] if q["side"] == side), None)
    return (
        (quote["p"], quote["price"], quote["net_edge"]) if quote else (None, None, None)
    )


INTERNATIONAL_KEY = "international_paper_alert"  # immutable legacy records


def notified(entry):
    """A read-only view of either generation of posted alert; no duplicate bet."""
    if entry.get("alert"):
        return entry
    if entry.get(INTERNATIONAL_KEY):
        return {**entry, "alert": entry[INTERNATIONAL_KEY]}
    return None


def record_group(entry):
    saved = entry["alert"]
    return saved.get("group") or forecast_groups.classify(
        {**entry, **(saved.get("forecast") or {})}
    )


def shown(log, now, chosen):
    """Today's upcoming notifications, including earlier calls whose edge faded."""
    now_s, day = now.strftime("%Y-%m-%dT%H:%MZ"), now.strftime("%Y-%m-%d")
    ids = {a["entry"]["match_id"] for a in chosen}
    entries = [view for entry in log.values() if (view := notified(entry))]
    return sorted(
        (
            e
            for e in entries
            if alert_side(e, e["alert"]) is not None
            and e["start"] > now_s
            and (e["match_id"] in ids or e["alert"]["at"][:10] == day)
        ),
        key=lambda e: (e["start"], e["match_id"]),
    )


def _row(entry, now_s, slugify, team_slugs):
    saved = entry["alert"]
    side = alert_side(entry, saved)
    _, _, edge = _current(entry, side, now_s)
    was = 100 * saved.get("net_edge", saved["edge"])
    if edge is None:
        edge_cell = f"no price now (alerted at +{was:.1f})"
    elif edge > EDGE:
        edge_cell = f"**+{100 * edge:.1f}**"
    else:
        edge_cell = f"gone: {100 * edge:+.1f} now (alerted at +{was:.1f})"
    back, other = _name(entry, side), _name(entry, 3 - side)
    return (
        f"| {_when(entry)} | {entry.get('event') or entry.get('league')} | **{back}** v {other} | "
        f"{round(100 * saved['p'])}% | {round(100 * saved['price'])}¢ | {edge_cell} | "
        f"{_links(entry, side, slugify, team_slugs)} |"
    )


HEAD = [
    "| Start (UTC / Pacific) | Event | Back | First chance | First ask | Net edge | Links |",
    "|---|---|---|---:|---:|---:|---|",
]


def _sections(entries, now_s, slugify, team_slugs, log=None):
    parts = []
    for identifier, label in forecast_groups.GROUPS:
        group = [e for e in entries if record_group(e) == identifier]
        if group:
            parts += [
                f"## {label}",
                "",
                *HEAD,
                *(_row(e, now_s, slugify, team_slugs) for e in group),
                "",
            ]
            if log is not None:
                prior = {
                    e["match_id"]: e
                    for original in log.values()
                    if (e := notified(original)) and record_group(e) == identifier
                }
                settled, won, stake, profit = paper_record(prior)
                parts += [
                    (
                        f"Record: {settled} settled, {won} won; {100 * profit / stake:+.1f}% after fees."
                        if settled
                        else "Record: none settled yet."
                    ),
                    "",
                ]
    return parts


def issue(entries, log, now, data_through, slugify, team_slugs):
    """One policy, with separate fixture groups and frozen first terms."""
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    live = sum(
        (_current(e, alert_side(e, e["alert"]), now_s)[2] or 0) > EDGE for e in entries
    )
    gone = len(entries) - live
    title = (
        f"{day_key(now)} {live} blended call{'s' if live != 1 else ''} above fees"
        + (f" ({gone} gone)" if gone else "")
    )
    body = "\n".join(
        [
            f"Blended chance above a fresh ask and the execution fee bound, {MIN_HOURS}+ hours before start. Domestic and international fixtures; other cross-league excluded. "
            f"Prices as of {now:%H:%M} UTC; games through {data_through}.",
            "",
            *_sections(entries, now_s, slugify, team_slugs, log),
            "First picks and prices stay fixed; current edges can change. $1 per pick, after fees.",
            "",
            f"[Alert history and profit]({SITE_URL}/alerts.html)",
            "",
            f"cc @{OWNER}",
        ]
    )
    return title, body


def update(log, now, data_through, slugify, team_slugs):
    """Notify all groups once; preserve legacy terms and historical paper records."""
    chosen = select(log, now)
    new_ids = {a["entry"]["match_id"] for a in chosen if notified(a["entry"]) is None}
    record(chosen, now)
    entries = shown(log, now, chosen)
    if not entries:
        return None
    title, body = issue(entries, log, now, data_through, slugify, team_slugs)
    comment = None
    if new_ids:
        now_s = now.strftime("%Y-%m-%dT%H:%MZ")
        comment = "\n".join(
            [
                f"**New:** {len(new_ids)} match{'es' if len(new_ids) != 1 else ''} at {now:%H:%M} UTC.",
                "",
                *_sections(
                    [e for e in entries if e["match_id"] in new_ids],
                    now_s,
                    slugify,
                    team_slugs,
                ),
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
