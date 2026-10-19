"""Cost of stale ratings: rebuild each settled logged series with ratings k days older.

uv run python scripts/research/call_staleness.py <predictions.json> (the published log,
https://prometheus.thaiv.dev/predictions.json). Prints lags and paired log-loss costs.
"""

import datetime
import json
import sys

import numpy as np
import pandas as pd

from prometheus import form, markets, schedule
from prometheus.evaluation import paired_bootstrap

log = json.load(open(sys.argv[1]))["matches"]
rows = pd.DataFrame(log if isinstance(log, list) else list(log.values()))
rows = rows[(rows.matched == True) & rows.winner.notna() & rows.best_of.notna()]
# lags in production (live calls and alerts)
live = rows[rows.reconstructed == False]
lag = (
    pd.to_datetime(live.predicted.str[:10]) - pd.to_datetime(live.data_through)
).dt.days
print(
    "live calls",
    len(live),
    "lag days (predicted - data_through):",
    lag.value_counts().sort_index().to_dict(),
)
al = [a for a in rows.alert.dropna() if isinstance(a, dict) and "forecast" in a]
alag = pd.Series(
    [
        (pd.Timestamp(a["at"][:10]) - pd.Timestamp(a["forecast"]["data_through"])).days
        for a in al
    ]
)
slag = pd.Series(
    [
        (
            pd.Timestamp(a["forecast"]["start"][:10])
            - pd.Timestamp(a["forecast"]["data_through"])
        ).days
        for a in al
    ]
)
print(
    "alerts",
    len(al),
    "alert-time lag:",
    alag.value_counts().sort_index().to_dict(),
    "start-day lag:",
    slag.value_counts().sort_index().to_dict(),
)

states = form.load_states()
before = schedule.RatingsBefore(states)
out = []
for e in rows.to_dict("records"):
    start = markets._parse_start(e["start"])
    rec = {
        "won": float(e["winner"] == 1),
        "league": e["league"],
        "intl": e["league"] in ("Worlds", "MSI", "EWC", "FST"),
    }
    ok = True
    for k in (0, 1, 2, 7):
        r = before(start.date() - datetime.timedelta(days=k))
        if not all(e[f"ours{i}"] in r.index for i in (1, 2)):
            ok = False
            break
        a, b = (r.loc[e[f"ours{i}"]] for i in (1, 2))
        p, _ = schedule.game_probability(
            a,
            b,
            at=start,
            event=e.get("league"),
            title=e.get("event", ""),
            event_day=start,
        )
        rec[k] = schedule.series_probability(
            p, int(e["best_of"]), schedule.series_rho(a.league, b.league)
        )
    if ok:
        out.append(rec)
df = pd.DataFrame(out)


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


for name, m in (
    ("all", df.won >= 0),
    ("international", df.intl),
    ("domestic/other", ~df.intl),
):
    d = df[m]
    base = ll(d[0], d.won)
    print(f"{name}: n={len(d)} LL day-before {base.mean():.4f}")
    for k in (1, 2, 7):
        mean, lo, hi = paired_bootstrap(ll(d[k], d.won).to_numpy(), base.to_numpy())
        print(f"   {k} more day(s) stale: {mean:+.4f} ({lo:+.4f} to {hi:+.4f})")
