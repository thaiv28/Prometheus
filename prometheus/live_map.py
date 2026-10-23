"""Frozen live-map blend and 30-second entry policy; stdlib, no credentials.

Market input is last trade, never midpoint. Model input is unshifted and pinned
by content hash. Actual books and conservative executor fees gate execution.
"""

import datetime as dt
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

VERSION = "live-map-30s-v1"
PREFIX = "prometheus/live-trading/signals/"
MODEL = Path(__file__).with_name("live") / "time_model_objectives_v1.json"
ARTIFACT = Path(__file__).with_name("live_map_blend.json")


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("undated_live_observation")
    return parsed.astimezone(dt.UTC)


def number(value):
    if isinstance(value, bool):
        raise ValueError("invalid_live_number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("invalid_live_number")
    return result


def probability(value):
    result = number(value)
    if not 0 < result < 1:
        raise ValueError("invalid_live_probability")
    return result


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@lru_cache(maxsize=1)
def artifact():
    value = json.loads(ARTIFACT.read_text())
    if (
        value["version"] != VERSION
        or value["model_sha256"] != hashlib.sha256(MODEL.read_bytes()).hexdigest()
    ):
        raise ValueError("live_model_version_mismatch")
    return value


def blend(raw, market, at, frozen=None):
    frozen = artifact() if frozen is None else frozen
    month = timestamp(at).strftime("%Y-%m")
    fit = next((s for s in frozen["snapshots"] if s["month"] == month), None)
    cutoff = timestamp(month + "-01T00:00:00Z")
    if not fit or timestamp(fit["latest_training_available"]) >= cutoff:
        raise ValueError("no_earlier_only_live_blend")

    def logit(p):
        p = min(1 - 1e-4, max(1e-4, probability(p)))
        return math.log(p / (1 - p))

    z = number(fit["market_weight"]) * logit(market) + number(
        fit["model_weight"]
    ) * logit(raw)
    value = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
    return value, month


def raw_probability(observation):
    from .live.timeline import predict

    if observation["model_sha256"] != artifact()["model_sha256"]:
        raise ValueError("live_model_version_mismatch")
    inputs = observation["inputs"]
    if not 5 <= round(number(inputs["clock_seconds"]) / 60, 1) <= 30:
        raise ValueError("outside_live_entry_minutes")
    if type(observation["blue"]) is not int or observation["blue"] not in (0, 1):
        raise ValueError("ambiguous_live_sides")
    # No v1 fallback, no series shift, no probability taken on trust from JSON.
    value = predict(json.loads(MODEL.read_text()), **inputs)
    return value if observation["blue"] == 0 else 1 - value


def normalize_trades(trades, tickers):
    """Both YES contracts -> team-0 price/backed side, as in the research tape."""
    out, seen = [], {}
    if sorted(tickers.values()) != [0, 1]:
        raise ValueError("ambiguous_live_trade_contracts")
    for trade in trades:
        ticker = trade["ticker"]
        if ticker not in tickers:
            raise ValueError("foreign_live_trade")
        identity = (ticker, trade["trade_id"])
        body = canonical(trade)
        if identity in seen:
            if seen[identity] != body:
                raise ValueError("conflicting_live_trade")
            continue
        seen[identity] = body
        side = trade.get("taker_outcome_side", trade.get("taker_side"))
        if side not in {"yes", "no"}:
            raise ValueError("ambiguous_live_trade_side")
        yes, no = (
            probability(trade["yes_price_dollars"]),
            probability(trade["no_price_dollars"]),
        )
        if abs(yes + no - 1) > 1e-6 or number(trade["count_fp"]) <= 0:
            raise ValueError("invalid_live_trade")
        team = tickers[ticker]
        out.append(
            {
                "at": trade["created_time"],
                "p0": yes if team == 0 else no,
                "back": team if side == "yes" else 1 - team,
                "cost": yes if side == "yes" else no,
                "id": identity,
            }
        )
    return sorted(out, key=lambda row: (timestamp(row["at"]), row["id"]))


def market_state(trades, at):
    now = timestamp(at)
    identities = [tuple(t["id"]) for t in trades]
    if len(identities) != len(set(identities)) or trades != sorted(
        trades, key=lambda row: (timestamp(row["at"]), tuple(row["id"]))
    ):
        raise ValueError("duplicate_or_unordered_live_trades")
    for trade in trades:
        if (
            type(trade["back"]) is not int
            or trade["back"] not in (0, 1)
            or abs(
                probability(trade["cost"])
                - (
                    probability(trade["p0"])
                    if trade["back"] == 0
                    else 1 - probability(trade["p0"])
                )
            )
            > 1e-6
        ):
            raise ValueError("invalid_live_trade_orientation")
    recent = [t for t in trades if 0 <= (now - timestamp(t["at"])).total_seconds() < 30]
    if len(recent) < 2:
        raise ValueError("live_trade_window_empty")
    if (now - timestamp(recent[-1]["at"])).total_seconds() > 10:
        raise ValueError("live_trade_stale")
    prices = [probability(t["p0"]) for t in recent]
    if max(prices) - min(prices) > 0.010000001:
        raise ValueError("live_trade_price_moving")
    costs = []
    for side in (0, 1):
        backed = [t for t in recent if t["back"] == side]
        costs.append(
            max(
                probability(backed[-1]["cost"]),
                prices[-1] if side == 0 else 1 - prices[-1],
            )
            if backed
            else None
        )
    return prices[-1], costs


def validate_observation(observation, at):
    """Validate feed/rating chronology before any extra market request."""
    now = timestamp(at)
    if (
        observation.get("version") != VERSION
        or observation.get("state") != "live"
        or observation.get("flat") is not False
    ):
        raise ValueError("invalid_live_state")
    source, receipt, calculated = (
        timestamp(observation[k]) for k in ("source_at", "received_at", "calculated_at")
    )
    if not source <= receipt <= calculated <= now:
        raise ValueError("live_timestamp_order")
    if (
        (now - source).total_seconds() > 45
        or (now - receipt).total_seconds() > 15
        or (now - calculated).total_seconds() > 8
    ):
        raise ValueError("live_feed_stale")
    start = timestamp(observation["start"])
    if start >= source or any(
        timestamp(t) >= start.replace(hour=0, minute=0, second=0, microsecond=0)
        for t in observation["rating_as_of"]
    ):
        raise ValueError("live_rating_not_earlier_day")
    if len(observation["rating_as_of"]) != 2:
        raise ValueError("live_ratings_missing")
    return raw_probability(observation)


def evaluate(observation, trades, book, at, fee):
    """Return best qualifying side. `fee(price)` is the executor reserve bound."""
    now = timestamp(at)
    raw = validate_observation(observation, at)
    if not 0 <= (now - timestamp(book["at"])).total_seconds() <= 3:
        raise ValueError("live_book_stale")
    bid, ask = probability(book["bid"]), probability(book["ask"])
    if bid > ask:
        raise ValueError("crossed_live_book")
    market, costs = market_state(trades, at)
    p, snapshot = blend(raw, market, at)
    decision = entry(p, costs, fee, asks=(ask, 1 - bid))
    return {**decision, "snapshot": snapshot, "raw": raw, "market": market}


def entry(p, costs, fee, asks=None):
    """Shared numerical entry kernel for offline tape replay and real books."""
    candidates = []
    for side in (0, 1):
        if costs[side] is None:
            continue
        cost = probability(costs[side])
        ask_side = probability(asks[side]) if asks is not None else cost
        cost = max(cost, ask_side)
        chance = p if side == 0 else 1 - p
        edge = chance - cost - number(fee(cost))
        if edge >= 0.05 - 1e-12:
            candidates.append(
                {
                    "side": side,
                    "probability": chance,
                    "original_ask": ask_side,
                    "tape_cost": cost,
                    "net_edge": edge,
                }
            )
    if not candidates:
        raise ValueError("live_no_after_fee_edge")
    return max(candidates, key=lambda c: (c["net_edge"], -c["side"]))


def proposal(observation, trades, book, at, fee):
    decision = evaluate(observation, trades, book, at, fee)
    teams = observation["teams"]
    if (
        len(teams) != 2
        or len(set(teams)) != 2
        or not all(isinstance(t, str) and t for t in teams)
    ):
        raise ValueError("ambiguous_live_teams")
    # Physical-map fence survives model releases and provider event/ID relisting.
    # The ledger additionally fences the exact executable exchange event.
    fixture_id = (
        "live-map:"
        + hashlib.sha256(
            canonical(
                [
                    sorted(teams),
                    timestamp(observation["start"]).isoformat(),
                    observation["map_number"],
                ]
            )
        ).hexdigest()
    )
    signal_id = hashlib.sha256(
        canonical([fixture_id, observation["source_at"], at])
    ).hexdigest()
    return {
        "schema_version": 1,
        "kind": VERSION,
        "blend_sha256": hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(),
        "alert_id": signal_id,
        "fixture_id": fixture_id,
        "alert_at": at,
        "start": observation["start"],
        "teams": teams,
        "backed_team": teams[decision["side"]],
        "team_homes": observation["team_homes"],
        "international": observation["international"],
        "group": "live-map",
        "event_ticker": observation["event_ticker"],
        "series_id": observation["series_event_ticker"],
        "map_number": observation["map_number"],
        "probability": str(decision["probability"]),
        "original_ask": str(decision["original_ask"]),
        "expires_at": (timestamp(at) + dt.timedelta(seconds=8)).isoformat(),
        "live": {
            "observation": observation,
            "trades": trades,
            "book": book,
            "decision": decision,
        },
    }


def validate(proposal_value, config, at):
    """Recompute rather than trusting probability/identity/side in a stored signal."""
    from decimal import Decimal

    from .execution.core import fee_bound

    now = timestamp(at)
    live_config = config.raw.get("live_maps") or {}
    if live_config.get("mode", "off") not in {"shadow", "live"}:
        raise ValueError("live_maps_disabled")
    if live_config["mode"] == "live" and config.mode not in {"demo", "live"}:
        raise ValueError("live_maps_global_off")
    activated = timestamp(live_config["activation_at"])
    if config.mode in {"demo", "live"}:
        activated = max(activated, timestamp(config.raw["activation_at"]))
    if timestamp(proposal_value["alert_at"]) < activated:
        raise ValueError("live_before_activation")
    if now > timestamp(proposal_value["expires_at"]):
        raise ValueError("live_signal_expired")
    saved = proposal_value["live"]
    # Re-evaluate at the original decision instant, then independently enforce age.
    expected = proposal(
        saved["observation"],
        saved["trades"],
        saved["book"],
        proposal_value["alert_at"],
        lambda price: fee_bound(
            Decimal(str(price)),
            1,
            config.number("fee_rate_upper_bound"),
            config.number("balance_precision_usd"),
        ),
    )
    if canonical(expected) != canonical(proposal_value):
        raise ValueError("live_signal_mismatch")
    if (
        (now - timestamp(proposal_value["alert_at"])).total_seconds() < 0
        or (now - timestamp(saved["observation"]["source_at"])).total_seconds() > 45
        or (now - timestamp(saved["observation"]["received_at"])).total_seconds() > 15
    ):
        raise ValueError("live_signal_stale")
    event, series, number = (
        proposal_value["event_ticker"],
        proposal_value["series_id"],
        proposal_value["map_number"],
    )
    map_identity = event.startswith("KXLOLMAP-") and series.startswith("KXLOLGAME-")
    bo1_identity = (
        saved["observation"].get("best_of") == 1
        and number == 1
        and event == series
        and event.startswith("KXLOLGAME-")
    )
    if (
        type(number) is not int
        or not 1 <= number <= 9
        or not (map_identity or bo1_identity)
    ):
        raise ValueError("invalid_live_market_identity")
    return expected
