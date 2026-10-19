"""Dependency-free draft-v2 identity, feature lookup and frozen prior inference."""

import hashlib
import json
import math
import re
from functools import lru_cache
from itertools import combinations

from .feed import timestamp

ROLES = ("top", "jng", "mid", "bot", "sup")
ROLE_NAMES = {
    "top": "top",
    "jungle": "jng",
    "jng": "jng",
    "mid": "mid",
    "bottom": "bot",
    "bot": "bot",
    "support": "sup",
    "sup": "sup",
}
FEATURES = ("exp", "meta", "matchup", "synergy")
CHAMPION_ALIASES = {
    "monkeyking": "wukong",
    "nunu": "nunuwillump",
    "renata": "renataglasc",
}


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold()) if isinstance(value, str) else ""


@lru_cache(maxsize=262144)
def key(*values):
    return json.dumps(values, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def resolve(observation, history, names):
    """Exact champion tokens and unambiguous historical player names only.

    Riot esportsPlayerId is validated for uniqueness, never confused with an OE id.
    A team tag may be removed at a space or using the mapped team code.
    A unique global name supports transfers; collisions always fall back.
    """
    if history.get("schema") != "draft_history_v2":
        raise ValueError("unsupported_history")
    sides = observation.get("teams")
    if not isinstance(sides, list) or len(sides) != 2:
        raise ValueError("missing_participants")
    result, riot_ids, player_ids, champions = [], set(), set(), set()
    participant_ids = set()
    for side, (participants, name) in enumerate(zip(sides, names)):
        if not isinstance(participants, list) or len(participants) != 5:
            raise ValueError("incomplete_draft")
        aliases = history.get("teams", {}).get(name, {})
        roles = {}
        for p in participants:
            if not isinstance(p, dict):
                raise ValueError("invalid_participant")
            role = ROLE_NAMES.get(p.get("role"))
            if role is None or role in roles:
                raise ValueError("invalid_roles")
            ident = p.get("esportsPlayerId")
            if not isinstance(ident, str) or not ident or ident in riot_ids:
                raise ValueError("duplicate_or_missing_riot_player")
            riot_ids.add(ident)
            pid = p.get("participantId")
            if (
                type(pid) is not int
                or not side * 5 < pid <= (side + 1) * 5
                or pid in participant_ids
            ):
                raise ValueError("participant_side_mismatch")
            participant_ids.add(pid)
            summoner = p.get("summonerName", "")
            candidates = {normalized(summoner)}
            if isinstance(summoner, str) and " " in summoner.strip():
                candidates.add(normalized(summoner.strip().split(" ", 1)[1]))
            codes = observation.get("team_codes") or []
            code = normalized(codes[side]) if len(codes) == 2 else ""
            token = normalized(summoner)
            if code and token.startswith(code) and len(token) > len(code):
                candidates.add(token[len(code) :])
            ids = {i for token in candidates for i in aliases.get(token, [])}
            if not ids:
                ids = {
                    i
                    for token in candidates
                    for i in history.get("players", {}).get(token, [])
                }
            if len(ids) != 1:
                raise ValueError("unknown_or_ambiguous_player")
            player = ids.pop()
            if player in player_ids:
                raise ValueError("duplicate_player")
            player_ids.add(player)
            token = normalized(p.get("championId"))
            token = CHAMPION_ALIASES.get(token, token)
            champion = history.get("champions", {}).get(token)
            if champion is None or champion in champions:
                raise ValueError("unknown_or_duplicate_champion")
            champions.add(champion)
            roles[role] = {"player": player, "champion": champion}
        result.append(roles)
    return result


def pair_key(a, b):
    return key(*sorted((a, b)))


def feature_values(roster, history):
    sides = []
    for side, opponent in zip(roster, reversed(roster)):
        values = dict.fromkeys(FEATURES, 0.0)
        for role in ROLES:
            p, champ = side[role]["player"], side[role]["champion"]
            values["exp"] += math.log1p(history["experience"].get(key(p, champ), 0))
            for feature, lookup, shrink in (
                ("meta", key(role, champ), 50),
                ("matchup", key(role, champ, opponent[role]["champion"]), 20),
            ):
                total, n = history[feature].get(lookup, (0.0, 0))
                values[feature] += total / (n + shrink)
        tokens = [f"{role}:{side[role]['champion']}" for role in ROLES]
        for a, b in combinations(tokens, 2):
            total, n = history["synergy"].get(pair_key(a, b), (0.0, 0))
            values["synergy"] += total / (n + 20)
        sides.append(values)
    return {k: sides[0][k] - sides[1][k] for k in FEATURES}


def prior_shift(values, p_blue, model):
    if type(p_blue) not in (int, float) or not 0 < p_blue < 1:
        raise ValueError("missing_forge_probability")
    p = min(max(p_blue, 1e-4), 1 - 1e-4)
    x = {**values, "forge_logit": math.log(p / (1 - p))}
    prior = model["draft_prior"]

    def logit(params):
        return params["intercept"] + sum(
            params[k] * x[k] for k in params if k != "intercept"
        )

    shift = logit(prior["draft"]) - logit(prior["base"])
    if not math.isfinite(shift):
        raise ValueError("invalid_draft_shift")
    return shift


def prepare(page, history, model, p_first, previous=None, *, not_before=None):
    """Freeze at first complete API observation; later conflicts stop future use.

    Each observation is in blue/red order. Context is blue-oriented. A previous
    context preserves historical calls across refreshes/restarts. All readiness
    and conflict gates use receipt times, never retroactively apply later picks.
    """
    game = page.get("game") or {}
    packet = dict(previous) if previous else None
    if (
        packet
        and packet.get("status") == "ready"
        and packet.get("game_id") != game.get("id")
    ):
        return {"status": "context_game_mismatch"}
    floor = not_before if not (packet and packet.get("status") == "ready") else None
    names = [t["name"] for t in page["match"]["teams"]]
    blue = game.get("blue")
    if blue not in (0, 1):
        return {"status": "missing_side"}
    ordered = [names[blue], names[1 - blue]]
    reason = "missing_participants"
    for observation in game.get("draft_observations", []):
        at = observation["at"]
        if floor and timestamp(at) < timestamp(floor):
            at = floor
        # A future or stale history must never leak into a retrospective map.
        day = (game.get("start") or observation.get("source_at") or at)[:10]
        if history.get("as_of") != day or (
            history.get("data_through") and history["data_through"][:10] >= day
        ):
            reason = "history_day_mismatch"
            continue
        try:
            roster = resolve(observation, history, ordered)
            signature = fingerprint(roster)
            if packet and packet.get("status") == "ready":
                if (
                    timestamp(at) >= timestamp(packet["ready_at"])
                    and signature != packet["signature"]
                ):
                    packet.setdefault("invalid_at", at)
                continue
            values = feature_values(roster, history)
            shift = prior_shift(values, p_first if blue == 0 else 1 - p_first, model)
            packet = {
                "status": "ready",
                "game_id": game.get("id"),
                "ready_at": at,
                "signature": signature,
                "features": values,
                "shift": shift,
                "history_as_of": history["as_of"],
                "history_through": history.get("data_through"),
                "model": fingerprint(model),
            }
        except (ValueError, KeyError, TypeError) as error:
            reason = str(error)
            if (
                packet
                and packet.get("status") == "ready"
                and timestamp(at) >= timestamp(packet["ready_at"])
            ):
                packet.setdefault("invalid_at", at)
    return packet or {"status": reason}


def available(packet, at, model):
    return bool(
        packet
        and packet.get("status") == "ready"
        and packet.get("model")
        == (model if isinstance(model, str) else fingerprint(model))
        and timestamp(at) >= timestamp(packet["ready_at"])
        and (
            not packet.get("invalid_at")
            or timestamp(at) < timestamp(packet["invalid_at"])
        )
    )
