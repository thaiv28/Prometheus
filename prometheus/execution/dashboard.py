"""Deterministic, private ledger dashboard; money stays Decimal throughout."""

import datetime as dt
import json
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from zoneinfo import ZoneInfo

from prometheus.alert_contract import kalshi_url

PT = ZoneInfo("America/Los_Angeles")
MARKETS = {
    "lol": ("League", "🟦", "#2563eb"),
    "cs2": ("CS2", "🟥", "#dc2626"),
    "valorant": ("Valorant", "🟩", "#16a34a"),
}
ZERO = Decimal(0)


def number(value):
    return Decimal(str(value or 0))


def money(value, signed=False):
    value = value.quantize(Decimal("0.01"))
    sign = "−" if value < 0 else "+" if signed and value > 0 else ""
    return f"{sign}${abs(value):.2f}"


def timestamp(value):
    if isinstance(value, (int, float, Decimal)):
        return dt.datetime.fromtimestamp(float(value), dt.UTC)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.UTC)


def date_label(value):
    return f"{value:%b} {value.day}"


def pt_time(value):
    value = value.astimezone(PT)
    return f"{date_label(value)}, {value.hour % 12 or 12}:{value:%M %p}"


def contracts(row):
    order = row.get("order") or {}
    if "fill_count_fp" in order:
        return number(order["fill_count_fp"])
    fills = row.get("fills", [])
    return (
        sum((number(f.get("count_fp")) for f in fills), ZERO)
        if isinstance(fills, list)
        else ZERO
    )


def changed_at(row):
    """Prefer transition timestamps, then exchange evidence and notification times."""
    values = [
        row.get(key) for key in ("settled_at", "filled_at", "notified", "issue_closed")
    ]
    order = row.get("order") or {}
    values.extend(order.get(key) for key in ("last_update_time", "created_time"))
    for kind in ("fills", "settlements"):
        evidence = row.get(kind, [])
        if isinstance(evidence, list):
            for item in evidence:
                values.extend(
                    item.get(key) for key in ("created_time", "settled_time", "ts")
                )
    return [timestamp(value) for value in values if value is not None]


def escape(value):
    return str(value).replace("|", r"\|")


def match(row):
    alert = row["alert"]
    return (
        f"[{' v '.join(escape(team) for team in alert['teams'])}]({kalshi_url(alert)})"
    )


def chart(title, dates, lines, colors):
    values = [value for line in lines for value in line]
    low = (min(values) - 5).to_integral_value(rounding=ROUND_FLOOR)
    high = (max(values) + 5).to_integral_value(rounding=ROUND_CEILING)
    palette = json.dumps(
        {"themeVariables": {"xyChart": {"plotColorPalette": ", ".join(colors)}}}
    )
    return [
        "```mermaid",
        f"%%{{init: {palette}}}%%",
        "xychart-beta",
        f"    x-axis {json.dumps([date_label(day) for day in dates])}",
        f'    y-axis "{title}" {low} --> {high}',
        *(
            "    line [" + ", ".join(f"{value:.2f}" for value in line) + "]"
            for line in lines
        ),
        "```",
        "",
    ]


def render(rows, accounts, config, now):
    """Render all markets from executor intents and their authoritative accounts."""
    rows = list(rows)
    games = config.get("games", {})
    present = [
        game
        for game in MARKETS
        if game == "lol"
        or games.get(game, {}).get("enabled")
        or any(row["alert"].get("game", "lol") == game for row in rows)
    ]
    trades = [
        row
        for row in rows
        if row.get("status") in {"filled", "settled"} or contracts(row) > 0
    ]
    settled = [row for row in trades if row.get("status") == "settled"]
    opened = [row for row in trades if row.get("status") != "settled"]
    # Stable tie ordering also makes DynamoDB query order immaterial.
    sort_key = lambda row: (
        timestamp(row["alert"]["start"]),
        row["alert"]["event_ticker"],
        row["alert"]["backed_team"],
    )
    opened.sort(key=sort_key)
    settled.sort(key=sort_key, reverse=True)
    seeds, stats = {}, {}
    for game in present:
        seeds[game] = number(
            config.get("starting_bankroll_usd", 50)
            if game == "lol"
            else games.get(game, {}).get("starting_bankroll_usd", 50)
        )
        own = [row for row in settled if row["alert"].get("game", "lol") == game]
        profit = sum((number(row.get("realized_profit")) for row in own), ZERO)
        cost = sum(
            (
                number(row.get("actual_cost")) + number(row.get("actual_fees"))
                for row in own
            ),
            ZERO,
        )
        stake = sum(
            (
                number(row.get("held"))
                for row in opened
                if row["alert"].get("game", "lol") == game
            ),
            ZERO,
        )
        account = accounts.get("ACCOUNT" if game == "lol" else f"ACCOUNT#{game}") or {}
        free = max(
            ZERO,
            seeds[game] + number(account.get("realized")) - number(account.get("held")),
        )
        stats[game] = (
            seeds[game],
            profit,
            sum(number(row.get("realized_profit")) > 0 for row in own),
            sum(number(row.get("realized_profit")) < 0 for row in own),
            cost,
            stake,
            free,
        )
    totals = tuple(sum(values, ZERO) for values in zip(*stats.values()))
    changes = [value for row in trades for value in changed_at(row)]
    updated = max(changes) if changes else now
    body = [
        f"**Updated** {pt_time(updated)} PT · **Net P&L {money(totals[1], True)}** · **Open {money(totals[5])} across {len(opened)} positions**",
        "",
    ]
    today = now.astimezone(dt.UTC).date()
    first = min(
        (timestamp(row["alert"]["start"]).date() for row in trades), default=today
    )
    dates = [first + dt.timedelta(days=day) for day in range((today - first).days + 1)]
    if len(dates) > 30:
        dates = [dates[i * (len(dates) - 1) // 29] for i in range(30)]
    if len(dates) > 1:
        lines = [
            [
                seeds[game]
                + sum(
                    (
                        number(row.get("realized_profit"))
                        for row in settled
                        if row["alert"].get("game", "lol") == game
                        and timestamp(row["alert"]["start"]).date() <= day
                    ),
                    ZERO,
                )
                for day in dates
            ]
            for game in present
        ]
        body += [
            "### Bankroll by market",
            "",
            " · ".join(f"{MARKETS[game][1]} {MARKETS[game][0]}" for game in present),
            "",
        ]
        body += chart(
            "Bankroll ($)", dates, lines, [MARKETS[game][2] for game in present]
        )
        body += ["### Total bankroll", ""]
        body += chart(
            "Bankroll ($)",
            dates,
            [[sum(values, ZERO) for values in zip(*lines)]],
            ["#111827"],
        )
    body += [
        "### By market",
        "",
        "| Market | Bankroll | Settled P&L | Record | ROI | Open stake | Free to bet |",
        "|---|---:|---:|:---:|---:|---:|---:|",
    ]
    for game in [*present, "total"]:
        seed, profit, wins, losses, cost, stake, free = (
            totals if game == "total" else stats[game]
        )
        total = game == "total"
        bold = lambda value, total=total: f"**{value}**" if total else value
        pnl = money(profit, True)
        if total or profit:
            pnl = f"**{pnl}**"
        roi = f"{profit / cost * 100:.1f}%".replace("-", "−") if cost else "—"
        body.append(
            f"| {bold('Total' if total else MARKETS[game][0])} | {bold(money(seed))} | {pnl} | {bold(f'{wins:g}–{losses:g}')} | {roi} | {bold(money(stake))} | {bold(money(free))} |"
        )
    body += ["", "### Open positions", ""]
    if opened:
        body += [
            "| Starts (PT) | Market | Match | Backing | Stake | Wins | Our chance |",
            "|---|---|---|---|---:|---:|---:|",
        ]
        for row in opened:
            alert = row["alert"]
            winnings = (
                contracts(row)
                - number(row.get("actual_cost"))
                - number(row.get("actual_fees"))
            )
            body.append(
                f"| {pt_time(timestamp(alert['start']))} | {MARKETS[alert.get('game', 'lol')][0]} | {match(row)} | {escape(alert['backed_team'])} | {money(number(row.get('held')))} | {money(winnings, True)} | {number(row.get('execution_probability')):.0%} |"
            )
    else:
        body.append("_No open positions._")
    body += [
        "",
        "### Last 10 results",
        "",
        "| Date | Market | Match | Backed | Result | P&L |",
        "|---|---|---|---|:---:|---:|",
    ]
    for row in settled[:10]:
        alert = row["alert"]
        profit = number(row.get("realized_profit"))
        result = "✅" if profit > 0 else "❌" if profit < 0 else "➖"
        body.append(
            f"| {date_label(timestamp(alert['start']).astimezone(PT))} | {MARKETS[alert.get('game', 'lol')][0]} | {match(row)} | {escape(alert['backed_team'])} | {result} | {money(profit, True)} |"
        )
    body += ["", "_Each trade also has its own issue, closed when it settles._", ""]
    return "\n".join(body)
