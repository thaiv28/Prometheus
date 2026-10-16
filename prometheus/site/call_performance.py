"""Detailed 12-hour call performance; does not write or reconstruct saved calls."""

import os

from prometheus import forecast_groups, schedule
from prometheus.site import config
from prometheus.site.render import env, write


def history(log):
    rows = []
    for entry in sorted(log.values(), key=lambda e: e.get("start", ""), reverse=True):
        early = entry.get("market_12h") or {}
        group = forecast_groups.classify(entry)
        if (
            not entry.get("matched")
            or entry.get("winner") not in (1, 2)
            or group is None
            or early.get("ours") is None
        ):
            continue
        made = schedule.paper_bets(
            early["ours"],
            (early.get("ask1"), early.get("ask2")),
            entry["winner"],
            (entry.get("market") or {}).get("p"),
        )
        if made is None:
            continue
        bet = made["value"]
        # Match paper_bets' first-side tie handling exactly.
        candidates = (
            [(early["ours"] - early["ask1"], 1)]
            if early.get("ask1") is not None and 0 < early["ask1"] < 1
            else []
        )
        if early.get("ask2") is not None and 0 < early["ask2"] < 1:
            candidates.append((1 - early["ours"] - early["ask2"], 2))
        side = max(candidates, key=lambda item: item[0])[1]
        rows.append(
            {
                "group": group,
                "start": entry["start"],
                "back": schedule.display_name(entry, side),
                "other": schedule.display_name(entry, 3 - side),
                "event": entry.get("event") or entry.get("league"),
                "source": "Backtest" if entry.get("reconstructed") else "Saved",
                "chance": early["ours"] if side == 1 else 1 - early["ours"],
                "ask": early[f"ask{side}"],
                **bet,
            }
        )
    return rows


def render_call_performance(log, view):
    rows = history(log)
    write(
        os.path.join(config.OUTPUT_DIR, "call-performance.html"),
        env.get_template("call_performance.html.j2").render(
            page_key="predictions",
            root_path="",
            view=view,
            groups=[
                {
                    "id": identifier,
                    "title": title,
                    "rows": [row for row in rows if row["group"] == identifier],
                }
                for identifier, title in forecast_groups.GROUPS
            ],
        ),
    )
