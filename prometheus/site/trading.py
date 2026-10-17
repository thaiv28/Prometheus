"""Blended after-fee paper record from earlier-only, observed 12h inputs."""

from prometheus import forecast_groups, schedule, trading
from prometheus.alert_contract import TRADE_GROUPS
from prometheus.evaluation import paired_bootstrap


def history(entries):
    out = []
    for entry in entries:
        if not entry.get("matched") or entry.get("winner") not in (1, 2):
            continue
        estimate = trading.quote(entry, early=True)
        if estimate is None or estimate["pick"]["net_edge"] <= 0:
            continue
        pick = estimate["pick"]
        side, ask = pick["side"], pick["price"]
        close = (entry.get("market") or {}).get("p")
        won = entry["winner"] == side
        fee = pick["fee"]
        out.append(
            {
                "group": forecast_groups.classify(entry),
                "start": entry["start"],
                "back": schedule.display_name(entry, side),
                "other": schedule.display_name(entry, 3 - side),
                "event": entry.get("event") or entry.get("league"),
                "source": "backtest" if entry.get("reconstructed") else "saved",
                "chance": pick["p"],
                "ask": ask,
                "edge": pick["edge"],
                "net_edge": pick["net_edge"],
                "won": won,
                "profit": (1 / ask if won else 0) - 1 - fee,
                "outlay": 1 + fee,
                "clv": None
                if close is None
                else (close if side == 1 else 1 - close) - ask,
            }
        )
    return out


def groups(entries):
    bets = history(entries)
    result = []
    for identifier, title in forecast_groups.GROUPS:
        if identifier not in TRADE_GROUPS:
            continue
        sources = []
        for source in ("saved", "backtest"):
            selected = [
                b for b in bets if b["group"] == identifier and b["source"] == source
            ]
            outlay = sum(b["outlay"] for b in selected)
            profits = [b["profit"] for b in selected]
            clvs = [b["clv"] for b in selected if b["clv"] is not None]

            def interval(values):
                if len(values) < schedule.MARKET_MIN_SERIES:
                    return None
                _, low, high = paired_bootstrap(values, [0] * len(values))
                return float(low), float(high)

            # Ratio bootstrap for all-in outlay, retaining the existing 30-bet
            # publication threshold. CLV has its own observation denominator.
            roi_ci = None
            if len(selected) >= schedule.MARKET_MIN_SERIES:
                import numpy as np

                rng = np.random.default_rng(0)
                ix = rng.integers(len(selected), size=(2000, len(selected)))
                estimates = np.asarray(profits)[ix].sum(1) / np.asarray(
                    [b["outlay"] for b in selected]
                )[ix].sum(1)
                roi_ci = tuple(float(x) for x in np.percentile(estimates, [2.5, 97.5]))
            row = {
                "edge": 0,
                "net": True,
                "bets": len(selected),
                "won": sum(b["won"] for b in selected),
                "roi": sum(profits) / outlay if outlay else None,
                "roi_ci": roi_ci,
                "clv": sum(clvs) / len(clvs) if clvs else None,
                "clv_ci": interval(clvs),
                "beat": sum(c > 0 for c in clvs) / len(clvs) if clvs else None,
            }
            sources.append({"name": source, "rows": [row]})
        result.append({"id": identifier, "label": title, "sources": sources})
    return result
