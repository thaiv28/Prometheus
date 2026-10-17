"""Shared public alert/page trading policy; no account access or order placement."""

import datetime as dt
import math

from prometheus import forecast_groups, market_blend, markets
from prometheus.alert_contract import TRADE_GROUPS

PAPER_STAKE = 1.0


def quote(entry, early=False):
    """Frozen/prospective model inputs and paper fees at their observed time."""
    if forecast_groups.classify(entry) not in TRADE_GROUPS:
        return None
    book = entry.get("market_12h" if early else "market") or {}
    raw = book.get("ours") if early else entry.get("p_series")
    if not book.get("at"):
        return None
    if early and (
        not entry.get("start")
        or market_blend.timestamp(book["at"])
        > market_blend.timestamp(entry["start"]) - dt.timedelta(hours=12)
    ):
        return None
    forecast = market_blend.estimate(raw, book.get("p"), book["at"])
    if forecast is None:
        return None
    p = forecast["probability"]
    choices = []
    for side in (1, 2):
        ask = book.get(f"ask{side}")
        if (
            not isinstance(ask, (int, float))
            or not math.isfinite(ask)
            or not 0 < ask < 1
        ):
            continue
        probability = p if side == 1 else 1 - p
        cost_fee = markets.fee(ask, PAPER_STAKE)
        unit_fee = cost_fee * ask / PAPER_STAKE
        backed = {
            **forecast,
            "raw_probability": raw if side == 1 else 1 - raw,
            "market_probability": book["p"] if side == 1 else 1 - book["p"],
            "probability": probability,
        }
        choices.append(
            {
                "side": side,
                "p": probability,
                "price": ask,
                "edge": probability - ask,
                "net_edge": probability - ask - unit_fee,
                "fee": cost_fee,
                "unit_fee": unit_fee,
                "trading": backed,
            }
        )
    if not choices:
        return None
    pick = max(choices, key=lambda c: (c["net_edge"], -c["side"]))
    return {
        "probability": p,
        "forecast": forecast,
        "pick": pick,
        "choices": choices,
        "at": book["at"],
    }
