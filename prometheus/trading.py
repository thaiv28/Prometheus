"""Shared public alert/page trading policy; no account access or order placement."""

import datetime as dt
import math
from decimal import Decimal

from prometheus import forecast_groups, market_blend, markets
from prometheus.alert_contract import TRADE_GROUPS

PAPER_STAKE = 1.0
# Match the approved live executor settings. Public alerts never read account
# configuration/credentials; update this profile if those two limits change.
ALERT_FEE_RATE = Decimal("0.07")
ALERT_BALANCE_PRECISION = Decimal("0.0001")


def quote(entry, early=False, *, execution_fees=False):
    """Frozen model inputs; paper fees by default, execution bounds for alerts."""
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
        net_edge = probability - ask - unit_fee
        fee_policy = None
        if execution_fees:
            # Same implementation as Lambda; imports only stdlib modules and
            # frozen model code, never its API adapter, secrets or account.
            from prometheus.execution.core import fee_bound

            bound = fee_bound(
                Decimal(str(ask)), Decimal(1), ALERT_FEE_RATE, ALERT_BALANCE_PRECISION
            )
            net_edge = float(Decimal(str(probability)) - Decimal(str(ask)) - bound)
            unit_fee = float(bound)
            cost_fee = unit_fee * PAPER_STAKE / ask
            fee_policy = {
                "version": "execution-fee-bound-v1",
                "rate_upper_bound": str(ALERT_FEE_RATE),
                "balance_precision_usd": str(ALERT_BALANCE_PRECISION),
                "unit_fee": str(bound),
            }
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
                "net_edge": net_edge,
                "fee": cost_fee,
                "unit_fee": unit_fee,
                "trading": backed,
                **({"fee_policy": fee_policy} if fee_policy else {}),
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
