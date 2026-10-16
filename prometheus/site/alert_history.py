"""The saved alert ledger; original terms only, never rebuilt model calls."""

import datetime
from pathlib import Path
from urllib.parse import quote

from prometheus import alerts, markets, schedule
from prometheus.site import config
from prometheus.site.predictions import alert_record
from prometheus.site.render import env, write

TRACKS = (
    ("domestic", "Domestic", "FORGE", "alert"),
    (
        "international",
        "International",
        "Experimental paper track",
        alerts.INTERNATIONAL_KEY,
    ),
    ("minor", "Minor leagues", "Unposted paper track", "paper_alert"),
)


def history_view(log, now):
    groups = []
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    for identifier, title, label, key in TRACKS:
        entries = [e for e in log.values() if e.get(key)]
        rows = []
        for entry in sorted(
            entries, key=lambda e: (e["start"], e["match_id"]), reverse=True
        ):
            saved = entry[key]
            side = alerts.alert_side(entry, saved)
            bet = alerts.settled_alerts({entry["match_id"]: entry}, key=key)
            settled = bet[0] if bet else None
            back = saved.get("team") or schedule.display_name(entry, saved["side"])
            other = schedule.display_name(entry, 3 - side) if side else "—"
            result = (
                "Won"
                if settled and settled["won"]
                else "Lost"
                if settled
                else "Pending"
                if entry["start"] > now_s
                else "Awaiting result"
            )
            if side is None:
                result = "Unresolved"
            score = None
            if settled and all(entry.get(f"score{i}") is not None for i in (1, 2)):
                score = f"{entry[f'score{side}']}–{entry[f'score{3 - side}']}"
            ticker = (entry.get("market") or {}).get("ticker")
            rows.append(
                {
                    "back": back,
                    "other": other,
                    "start": entry["start"],
                    "at": saved["at"],
                    "event": entry.get("event") or entry.get("league", ""),
                    "chance": saved["p"],
                    "ask": saved["price"],
                    "result": result,
                    "score": score,
                    "profit": settled["profit"] if settled else None,
                    "clv": settled["clv"] if settled else None,
                    "url": markets.event_url(ticker)
                    if ticker
                    else f"predictions.html?search={quote(back)}",
                }
            )
        summary = alert_record(entries, key=key)
        summary["profit"] = sum(r["profit"] for r in rows if r["profit"] is not None)
        groups.append(
            {
                "id": identifier,
                "title": title,
                "label": label,
                "rows": rows,
                "summary": summary,
            }
        )
    return groups


def render_alert_history(log, now=None, out_dir=None):
    now = now or datetime.datetime.now(datetime.UTC)
    write(
        str(Path(out_dir or config.OUTPUT_DIR) / "alerts.html"),
        env.get_template("alerts.html.j2").render(
            page_key="predictions",
            root_path="",
            groups=history_view(log, now),
        ),
    )
