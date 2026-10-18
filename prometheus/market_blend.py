"""Frozen market/model forecasts for trading; stdlib only, no runtime fitting.

FORGE/Elo probabilities stay independent. Each dated snapshot uses only older
completed series; no snapshot means no trading estimate, never a raw fallback.
"""

import datetime as dt
import json
import math
from functools import lru_cache
from pathlib import Path

VERSION = "market-blend-v1"
POLICY = "blended-net-v1"
PATH = Path(__file__).with_name("market_blend.json")


def timestamp(value):
    if isinstance(value, dt.datetime):
        return (
            value.replace(tzinfo=dt.UTC)
            if value.tzinfo is None
            else value.astimezone(dt.UTC)
        )
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return timestamp(parsed)


def valid_probability(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and 0 < value < 1


@lru_cache(maxsize=1)
def load():
    data = json.loads(PATH.read_text())
    if data.get("version") != VERSION:
        raise ValueError("unsupported market blend artifact")
    previous = ""
    for model in data["snapshots"]:
        if (
            model["available_from"] <= previous
            or model["trained_through"] >= model["available_from"]
        ):
            raise ValueError("unordered or non-causal market blend snapshot")
        if model["training_series"] < 300 or not all(
            math.isfinite(model[k]) for k in ("market_slope", "gap_slope")
        ):
            raise ValueError("invalid market blend coefficients")
        previous = model["available_from"]
    return data


def snapshot(at):
    when = timestamp(at).isoformat()
    return next(
        (m for m in reversed(load()["snapshots"]) if m["available_from"] <= when), None
    )


def combine(raw, market, model):
    if not valid_probability(raw) or not valid_probability(market):
        return None

    # Match the research clipping/coefficients exactly, preserving team symmetry.
    def logit(p):
        p = min(1 - 1e-6, max(1e-6, p))
        return math.log(p / (1 - p))

    z = model["market_slope"] * logit(market) + model["gap_slope"] * (
        logit(raw) - logit(market)
    )
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def estimate(raw, market, at):
    model = snapshot(at)
    if model is None or (p := combine(raw, market, model)) is None:
        return None
    return {
        "version": VERSION,
        "policy": POLICY,
        "model": model["available_from"],
        "trained_through": model["trained_through"],
        "market_slope": model["market_slope"],
        "gap_slope": model["gap_slope"],
        "raw_probability": raw,
        "market_probability": market,
        "probability": p,
    }


def refresh(saved, market):
    """Update only market input to the exact frozen, backed-side model."""
    if saved.get("version") != VERSION or saved.get("policy") != POLICY:
        raise ValueError("unsupported trading forecast")
    model = next(
        (m for m in load()["snapshots"] if m["available_from"] == saved.get("model")),
        None,
    )
    if model is None or any(
        saved.get(k) != model[k]
        for k in ("market_slope", "gap_slope", "trained_through")
    ):
        raise ValueError("unknown trading snapshot")
    p = combine(float(saved["raw_probability"]), float(market), model)
    if p is None:
        raise ValueError("invalid current trading probability")
    return p
