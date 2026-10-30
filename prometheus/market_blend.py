"""Frozen market/model forecasts for trading; stdlib only, no runtime fitting.

FORGE/Elo probabilities stay independent. Each dated snapshot uses only older
completed series; no snapshot means no trading estimate, never a raw fallback.
"""

import copy
import datetime as dt
import json
import math
from functools import lru_cache
from pathlib import Path

from prometheus.other_games import GAMES

VERSION = "market-blend-v1"
POLICY = "blended-net-v1"
GAME_VERSION = "game-blend-v1"
GAME_PATH = Path(__file__).with_name("game_blends")
PATH = Path(__file__).with_name("market_blend.json")
_INSTALLED = {}


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


def _validate(game, data):
    from prometheus.alert_contract import GAMES

    if game not in GAMES:
        raise ValueError("unsupported game")
    if game != "lol" and (
        data.get("game") != game
        or data.get("series_ticker") != GAMES[game]["series"]
        or not isinstance(data.get("clip"), float)
        or not 0 < data["clip"] < 0.5
    ):
        raise ValueError("invalid game blend artifact")
    if data.get("version") != (VERSION if game == "lol" else GAME_VERSION):
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


@lru_cache(maxsize=4)
def load(game="lol"):
    if game in _INSTALLED:
        return _INSTALLED[game]
    if game != "lol" and game not in GAMES:
        raise ValueError("unsupported game")
    return _validate(
        game,
        json.loads((PATH if game == "lol" else GAME_PATH / f"{game}.json").read_text()),
    )


def install(game, data):
    """Install a validated append-only game refit; failures retain current models."""
    if game not in GAMES:
        return False
    try:
        if isinstance(data, (str, bytes, bytearray)):
            data = json.loads(data)
        candidate = _validate(game, copy.deepcopy(data))
        packaged = _validate(game, json.loads((GAME_PATH / f"{game}.json").read_text()))
        if any(
            candidate.get(key) != packaged.get(key)
            for key in ("version", "game", "series_ticker", "clip")
        ):
            return False
        # Snapshots already in force never change: a refit recomputed over all
        # data can nudge past months (late links), so keep the loaded ones and
        # append only months after the last loaded snapshot.
        old = (_INSTALLED.get(game) or packaged)["snapshots"]
        added = [
            m
            for m in candidate["snapshots"]
            if m["available_from"] > old[-1]["available_from"]
        ]
        for model in added:
            if not (
                0.2 <= model["market_slope"] <= 3
                and -1 <= model["gap_slope"] <= 2
                and model["training_series"] >= 300
            ):
                return False
        candidate = _validate(game, {**packaged, "snapshots": [*old, *added]})
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError, OSError):
        return False
    _INSTALLED[game] = candidate
    load.cache_clear()
    return True


def snapshot(at, game="lol"):
    try:
        data = load(game)
    except FileNotFoundError:
        if game == "lol":
            raise
        return None
    when = timestamp(at).isoformat()
    return next(
        (m for m in reversed(data["snapshots"]) if m["available_from"] <= when), None
    )


def combine(raw, market, model, clip=1e-6):
    if not valid_probability(raw) or not valid_probability(market):
        return None

    # Match the research clipping/coefficients exactly, preserving team symmetry.
    def logit(p):
        p = min(1 - clip, max(clip, p))
        return math.log(p / (1 - p))

    z = model["market_slope"] * logit(market) + model["gap_slope"] * (
        logit(raw) - logit(market)
    )
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def estimate(raw, market, at, game="lol"):
    model = snapshot(at, game)
    if model is None:
        return None
    data = load(game)
    if (p := combine(raw, market, model, data.get("clip", 1e-6))) is None:
        return None
    return {
        "version": data["version"],
        **({"game": game} if game != "lol" else {}),
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
    game = saved.get("game", "lol")
    if (
        saved.get("version") != (VERSION if game == "lol" else GAME_VERSION)
        or saved.get("policy") != POLICY
    ):
        raise ValueError("unsupported trading forecast")
    data = load(game)
    model = next(
        (m for m in data["snapshots"] if m["available_from"] == saved.get("model")),
        None,
    )
    if model is None or any(
        saved.get(k) != model[k]
        for k in ("market_slope", "gap_slope", "trained_through")
    ):
        raise ValueError("unknown trading snapshot")
    p = combine(
        float(saved["raw_probability"]), float(market), model, data.get("clip", 1e-6)
    )
    if p is None:
        raise ValueError("invalid current trading probability")
    return p
