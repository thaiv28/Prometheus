"""Live results: every series the live service followed, with our pre-match call
and a figure per recorded map.

The maps come from `data/live/<match>/pages/map<n>.min.json` (compact copies of
the worker's finished-map files, restored by `scripts/live_archive.sh`), the
settled map winners from `<match>/results.json`, and the call before the series
from the saved prediction log. Without `data/live` there are no live results.
"""

import datetime
import json
import os
from pathlib import Path

from prometheus.site import config as site_config
from prometheus.site.predictions import _by_day, _pct_pair, fixture_row
from prometheus.site.render import env, write

# How far a live match's first map may be from the logged start (Leaguepedia's
# and Kalshi's times can be hours off when a day runs early or late).
MATCH_WINDOW = datetime.timedelta(hours=12)
RECENT_DAYS = 7  # Live's Table III

# The figure, in SVG units (scaled to the column's width).
W, PAD_L, PAD_R = 480, 26, 8
CHANCE_TOP, CHANCE_BOTTOM = 8, 98
GOLD_TOP, GOLD_BOTTOM = 108, 144
AXIS_Y = 158
H = 162


def _time(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def load_archive(root=None):
    """{match id: {"maps": {n: compact map}, "results": {n: winner index}}}."""
    root = Path(root or os.path.join(site_config.ROOT_DIR, "data", "live"))
    out = {}
    for path in sorted(root.glob("*/pages/map*.min.json")):
        try:
            data = json.loads(path.read_text())
            match = out.setdefault(data["match"]["id"], {"maps": {}, "results": {}})
            match["maps"][data["number"]] = data
        except (OSError, ValueError, KeyError):
            continue
    for match_id, match in out.items():
        try:
            results = json.loads((root / match_id / "results.json").read_text())
            match["results"] = {
                int(n): r["winner"] for n, r in results.items() if "winner" in r
            }
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return out


def _log_entry(entries, teams, start):
    """The logged match for these two teams nearest `start`, within the window."""
    best = None
    for e in entries:
        if {e.get("ours1"), e.get("ours2")} != set(teams):
            continue
        gap = abs(_time(e["start"]) - start)
        if gap <= MATCH_WINDOW and (best is None or gap < best[0]):
            best = (gap, e)
    return best[1] if best else None


def _path(points, x, y, until):
    """A step line through (s, value) points, held to `until`."""
    d = ""
    for i, (s, v) in enumerate(points):
        end = points[i + 1][0] if i + 1 < len(points) else max(until, s)
        d += f"{'V' if i else f'M{x(s):.1f},'}{y(v):.1f}H{x(end):.1f}"
    return d


def figure(compact, flip):
    """One map's chance over game time (the first listed team's), the market and
    the gold lead, as SVG pieces for the template."""
    side = (lambda p: 1 - p) if flip else (lambda p: p)
    calls = [(s, side(p)) for s, p in compact["calls"]]
    pre = compact["pregame"].get("p")
    if pre is not None:
        calls.insert(0, (0, side(pre)))
    market = [(s, side(m)) for s, m in compact["market"] if m is not None]
    gold = [(s, -g if flip else g) for s, g in compact["gold"]]
    span = max(
        [compact.get("length") or 0] + [s for s, _ in calls + market + gold] + [60]
    )
    x = lambda s: PAD_L + (W - PAD_L - PAD_R) * min(s, span) / span
    y = lambda p: CHANCE_BOTTOM - (CHANCE_BOTTOM - CHANCE_TOP) * p
    gold_max = max([abs(g) for _, g in gold] + [1000])
    gold_mid = (GOLD_TOP + GOLD_BOTTOM) / 2
    col = max(1.0, min(3.0, (W - PAD_L - PAD_R) / max(1, len(gold)) * 0.7))
    columns = []
    for s, g in gold:
        h = abs(g) / gold_max * (GOLD_BOTTOM - GOLD_TOP) / 2
        top = gold_mid - h if g > 0 else gold_mid
        columns.append(
            {
                "x": f"{x(s) - col / 2:.1f}",
                "y": f"{top:.1f}",
                "w": f"{col:.1f}",
                "h": f"{max(0.5, h):.1f}",
            }
        )
    every = next((st for st in (300, 600, 900) if span / st <= 6), 1200)
    ticks = [
        {"x": f"{round(x(s)) + 0.5}", "label": f"{s // 60}′"}
        for s in range(0, int(span) + 1, every)
    ]
    end = calls[-1] if calls else None
    return {
        "w": W,
        "h": H,
        "left": PAD_L,
        "right": W - PAD_R,
        "y100": CHANCE_TOP,
        "y50": f"{y(0.5):.1f}",
        "y0": CHANCE_BOTTOM,
        "gold_mid": f"{gold_mid + 0.5:.1f}",
        "gold_top": GOLD_TOP,
        "gold_bottom": GOLD_BOTTOM,
        "axis_y": AXIS_Y,
        "ours": _path(calls, x, y, span) if calls else None,
        "market": _path(market, x, y, span) if market else None,
        "pre": {"x": f"{x(0):.1f}", "y": f"{y(calls[0][1]):.1f}"}
        if pre is not None
        else None,
        "end": {"x": f"{x(end[0]):.1f}", "y": f"{y(end[1]):.1f}"} if end else None,
        "columns": columns,
        "ticks": ticks,
        "gold_label": f"{gold_max / 1000:.0f}k",
        "label": _figure_label(calls, market),
    }


def _figure_label(calls, market):
    parts = []
    if calls:
        parts.append(
            f"Our call went from {round(100 * calls[0][1])} to {round(100 * calls[-1][1])} in 100"
        )
    if market:
        parts.append(
            f"Kalshi from {round(100 * market[0][1])} to {round(100 * market[-1][1])}"
        )
    return "; ".join(parts) + "." if parts else "No calls recorded."


def _minutes(seconds):
    return f"{seconds // 60}′" if seconds else None


def series_view(log, archive, team_slugs, now=None):
    """Every followed series, newest first: its fixture row (the call before the
    series, Kalshi's close, the result) and its maps."""
    entries = [e for e in log.values() if e.get("matched")]
    out = []
    for match_id, match in archive.items():
        maps = match["maps"]
        first = maps[min(maps)]
        teams = first["match"]["teams"]
        starts = [m["start_at"] or m["ended_at"] for m in maps.values()]
        starts = [s for s in starts if s]
        if not starts:
            continue
        start = min(_time(s) for s in starts)
        entry = _log_entry(entries, teams, start)
        if entry:
            row = fixture_row(entry, team_slugs)
            flip = teams[0] != entry["ours1"]
            names = [row["name1"], row["name2"]]
        else:
            stamp = start.strftime("%Y-%m-%dT%H:%MZ")
            row = {
                "id": match_id,
                "start": stamp,
                "day": stamp[:10],
                "time": stamp[11:16],
                "league": first["match"].get("league") or "",
                "event": first["match"].get("event") or "",
                "best_of": first["match"].get("best_of"),
                "name1": teams[0],
                "name2": teams[1],
                "slug1": None,
                "slug2": None,
            }
            flip, names = False, list(teams)
        row["href"] = f"#s-{match_id}"
        winners = dict(match["results"])
        for n, m in maps.items():
            if m.get("winner") in (0, 1):
                winners.setdefault(n, m["winner"])
        played = max(list(winners) + list(maps))
        if row.get("score"):
            played = max(played, sum(int(v) for v in row["score"].split("–")))
        map_rows = []
        for n in range(1, played + 1):
            # Winners are by live team order; `won` by the row's (log) order.
            won = winners.get(n)
            won = None if won is None else (1 - won if flip else won)
            if won is None and n == played and row.get("winner") in (1, 2):
                won = row["winner"] - 1  # the last map goes to the series winner
            m = maps.get(n)
            recorded = bool(m and (m["calls"] or m["gold"]))
            item = {
                "number": n,
                "winner": names[won] if won is not None else None,
                "recorded": recorded,
            }
            if recorded:
                pre = m["pregame"]
                p = pre.get("p")
                mk = pre.get("market")
                item.update(
                    length=_minutes(m.get("length")),
                    pre=_pct_pair(1 - p if flip else p)[0] if p is not None else None,
                    pre_market=_pct_pair(1 - mk if flip else mk)[0]
                    if mk is not None
                    else None,
                    figure=figure(m, flip),
                )
            map_rows.append(item)
        out.append(
            {
                "id": match_id,
                "row": row,
                "names": names,
                "maps": map_rows,
                "missing": [m["number"] for m in map_rows if not m["recorded"]],
                "date": f"{start.day} {start.strftime('%B')}",
            }
        )
    out.sort(key=lambda s: s["row"]["start"], reverse=True)
    return out


def month_views(series):
    """One page per month, newest first: key, label, the register's days and the
    series' figures."""
    months = {}
    for s in series:
        months.setdefault(s["row"]["start"][:7], []).append(s)
    out = []
    for key, items in months.items():
        first = datetime.date.fromisoformat(key + "-01")
        out.append(
            {
                "key": key,
                "label": f"{first.strftime('%B')} {first.year}",
                "days": _by_day([s["row"] for s in items]),
                "series": items,
            }
        )
    return out


def recent(series, now):
    """Live's Table III: the last week's series, linked to their month page."""
    since = (now - datetime.timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%dT%H:%MZ")
    rows = []
    for s in series:
        if s["row"]["start"] < since:
            break
        rows.append(
            dict(
                s["row"], href=f"live-results/{s['row']['start'][:7]}.html#s-{s['id']}"
            )
        )
    return _by_day(rows)


def render_live_results(months):
    """live-results/<month>.html, with links to the months either side."""
    if not months:
        return
    folder = os.path.join(site_config.OUTPUT_DIR, "live-results")
    os.makedirs(folder, exist_ok=True)
    template = env.get_template("live_results.html.j2")
    for i, month in enumerate(months):
        write(
            os.path.join(folder, f"{month['key']}.html"),
            template.render(
                page_key="live",
                root_path="../",
                metric=site_config.LIVE,
                month=month,
                newer=months[i - 1] if i > 0 else None,
                older=months[i + 1] if i + 1 < len(months) else None,
            ),
        )
