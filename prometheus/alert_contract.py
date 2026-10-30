"""Private forecast candidates and immutable legacy alert execution contracts.

Adapters select no trades; execution/account data belongs elsewhere.
"""

import datetime as dt
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from prometheus import market_blend
from prometheus.other_games import GAMES as OTHER_GAMES

GAMES = {
    "lol": {
        "series": "KXLOLGAME",
        "rules_word": "League of Legends",
        "kalshi_slug": "league-of-legends-game",
    },
    **{
        slug: {
            "series": game.series_ticker,
            "rules_word": game.rules_word,
            "kalshi_slug": game.kalshi_slug,
        }
        for slug, game in OTHER_GAMES.items()
    },
}
GAME_GROUPS = {
    group: slug for slug, game in OTHER_GAMES.items() for group in game.trade_groups
}

SCHEMA_VERSION = 1
CANDIDATE_KIND = "candidate-v1"
CANDIDATE_KEY = "execution_candidate"
CANDIDATE_MAX_AGE = dt.timedelta(hours=3)
POSTED_KEYS = ("alert", "international_paper_alert")
GROUPS = frozenset(
    (
        "major-domestic",
        "major-international",
        "minor-domestic",
        "mixed-international",
        "minor-international",
        "other-cross-league",
    )
)
TRADE_GROUPS = (GROUPS - {"other-cross-league"}) | frozenset(
    group for game in OTHER_GAMES.values() for group in game.trade_groups
)
GROUPS = GROUPS | frozenset(
    group for game in OTHER_GAMES.values() for group in game.groups
)


# Letters that Unicode doesn't split into a base letter and an accent.
_PLAIN_LETTERS = str.maketrans(
    {"ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "đ": "d", "ł": "l", "þ": "th"}
)


def kalshi_url(alert):
    """Canonical event link shared by execution issues and the dashboard."""
    game = GAMES[alert.get("game", "lol")]
    return (
        f"https://kalshi.com/markets/{game['series'].lower()}/"
        f"{game['kalshi_slug']}/{alert['event_ticker'].lower()}"
    )


def fold(name):
    """Lower-case, accent-free, punctuation-free form of a team name."""
    name = str(name).lower().translate(_PLAIN_LETTERS)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def trade_veto(alert):
    """Personal execution restrictions; alerts themselves remain visible."""
    teams = alert.get("teams") or []
    for team in teams:
        folded = "".join(c for c in team.casefold() if c.isalnum())
        if folded == "c9" or folded.startswith("cloud9"):
            return "cloud9_fixture"
    if alert.get("game", "lol") == "lol" and (
        alert.get("international")
        or alert.get("group")
        in {
            "major-international",
            "mixed-international",
            "minor-international",
        }
    ):
        homes = alert.get("team_homes") or {}
        if any(not homes.get(team) for team in teams):
            return "missing_international_home_leagues"
        for team in teams:
            home = "".join(c for c in homes[team].upper() if c.isalnum())
            if home in {"LCS", "NALCS", "LTAN", "NACL"} and team != alert.get(
                "backed_team"
            ):
                return "against_north_america_international"
    return None


def _digest(parts):
    return hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def identity(entry, saved):
    """Pin before the fixture's provider ID, ordering or start can change."""
    teams = sorted(entry.get(f"ours{i}") or entry.get(f"team{i}") or "" for i in (1, 2))
    back = saved.get("team") or (
        entry.get(f"ours{saved['side']}") or entry.get(f"team{saved['side']}")
    )
    start = (saved.get("forecast") or {}).get("start") or entry.get("start")
    fixture_id = _digest([teams, start, entry.get("league"), entry.get("event")])
    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "alert_id": _digest([fixture_id, saved["at"], back]),
        "event_ticker": (entry.get("market") or {}).get("ticker"),
        "teams": teams,
        "team_homes": {
            entry.get(f"ours{i}") or entry.get(f"team{i}") or "": entry.get(f"home{i}")
            for i in (1, 2)
        },
        "international": (saved.get("forecast") or {}).get("international"),
        "backed_team": back,
        "start": start,
    }


def saved_alerts(document):
    """JSON-compatible contracts from the PRIVATE persisted prediction document.

    Reconstructed fixtures may carry a real forward alert; the alert timestamp,
    not the fixture's reconstructed flag, identifies that forward proposal.
    Legacy international records are posted; legacy paper_alert records are not.
    Invalid/ambiguous records are omitted, never repaired from later prices.
    """
    entries = document.get("matches", []) if isinstance(document, dict) else document
    if isinstance(entries, dict):
        entries = entries.values()
    out = []
    for entry in entries:
        saved = next((entry[key] for key in POSTED_KEYS if entry.get(key)), None)
        if not saved:
            continue
        try:
            pinned = saved.get("execution") or identity(entry, saved)
            teams = pinned["teams"]
            probability, ask = Decimal(str(saved["p"])), Decimal(str(saved["price"]))
            if (
                pinned.get("schema_version") != SCHEMA_VERSION
                or len(teams) != 2
                or not all(isinstance(t, str) and t for t in teams)
                or teams[0] == teams[1]
                or pinned["backed_team"] not in teams
                or not pinned.get("event_ticker")
                or not probability.is_finite()
                or not 0 < probability < 1
                or not ask.is_finite()
                or not 0 < ask < 1
            ):
                continue
            out.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "alert_id": pinned["alert_id"],
                    "fixture_id": pinned["fixture_id"],
                    "alert_at": saved["at"],
                    "start": pinned["start"],
                    "teams": list(teams),
                    "team_homes": dict(pinned.get("team_homes") or {}),
                    "international": pinned.get("international"),
                    "backed_team": pinned["backed_team"],
                    "event_ticker": pinned["event_ticker"],
                    "probability": str(probability),
                    "original_ask": str(ask),
                    "group": saved.get("group"),
                    "provenance": saved.get("forecast") or {},
                    **({"trading": saved["trading"]} if saved.get("trading") else {}),
                }
            )
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
    return out


def candidate(entry, now_s, group, international):
    """Pin current forecast inputs independently of public alert selection."""
    teams = sorted(entry.get(f"ours{i}") or entry[f"team{i}"] for i in (1, 2))
    first = entry.get("ours1") or entry["team1"]
    second = entry.get("ours2") or entry["team2"]
    return {
        "kind": CANDIDATE_KIND,
        "schema_version": SCHEMA_VERSION,
        "at": now_s,
        "fixture_id": _digest(
            [teams, entry["start"], entry.get("league"), entry.get("event")]
        ),
        "event_ticker": entry["market"]["ticker"],
        "teams": teams,
        "team_homes": {
            entry.get(f"ours{i}") or entry[f"team{i}"]: entry.get(f"home{i}")
            for i in (1, 2)
        },
        "international": international,
        "group": group,
        "start": entry["start"],
        "raw": {
            first: round(entry["p_series"], 6),
            second: round(1 - entry["p_series"], 6),
        },
        "provenance": {
            key: entry.get(key)
            for key in (
                "calibration",
                "method",
                "p_game",
                "p_series",
                "home1",
                "home2",
                "data_through",
                "start",
            )
        },
    }


def saved_candidates(document, now):
    """Two backed-side proposals from fresh private forecast records."""
    entries = document.get("matches", []) if isinstance(document, dict) else document
    if isinstance(entries, dict):
        entries = list(entries.values())
    if not isinstance(entries, (list, tuple)):
        return []
    out = []
    for entry in entries:
        try:
            saved = entry[CANDIDATE_KEY]
            game = saved.get("game", "lol")
            if game not in GAMES:
                continue
            if saved["group"] in GAME_GROUPS:
                if (
                    game != GAME_GROUPS[saved["group"]]
                    or saved.get("series_ticker") != GAMES[game]["series"]
                ):
                    continue
            elif game != "lol":
                continue
            snap = market_blend.snapshot(now, game)
            if snap is None:
                continue
            teams = saved["teams"]
            when = dt.datetime.fromisoformat(saved["at"].replace("Z", "+00:00"))
            start = dt.datetime.fromisoformat(saved["start"].replace("Z", "+00:00"))
            raw = saved["raw"]
            if (
                saved["kind"] != CANDIDATE_KIND
                or saved["schema_version"] != SCHEMA_VERSION
                or saved["group"] not in TRADE_GROUPS
                or not isinstance(teams, list)
                or len(teams) != 2
                or not all(isinstance(t, str) and t for t in teams)
                or teams[0] == teams[1]
                or not all(
                    isinstance(saved[k], str) and saved[k]
                    for k in ("fixture_id", "event_ticker")
                )
                or not isinstance(saved["international"], bool)
                or not isinstance(saved["team_homes"], dict)
                or not isinstance(saved["provenance"], dict)
                or start <= now
                or not dt.timedelta(0) <= now - when <= CANDIDATE_MAX_AGE
                or not all(market_blend.valid_probability(raw[t]) for t in teams)
            ):
                continue
            for backed in teams:
                out.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "kind": CANDIDATE_KIND,
                        "alert_id": _digest(
                            [saved["fixture_id"], CANDIDATE_KIND, backed]
                        ),
                        **{
                            key: saved[key]
                            for key in (
                                "fixture_id",
                                "start",
                                "teams",
                                "team_homes",
                                "international",
                                "event_ticker",
                                "group",
                                "provenance",
                            )
                        },
                        **(
                            {"game": game, "series_ticker": saved["series_ticker"]}
                            if game != "lol"
                            else {}
                        ),
                        "alert_at": saved["at"],
                        "backed_team": backed,
                        "probability": str(raw[backed]),
                        "trading": {
                            "version": market_blend.load(game)["version"],
                            **({"game": game} if game != "lol" else {}),
                            "policy": market_blend.POLICY,
                            "model": snap["available_from"],
                            **{
                                key: snap[key]
                                for key in (
                                    "trained_through",
                                    "market_slope",
                                    "gap_slope",
                                )
                            },
                            "raw_probability": raw[backed],
                        },
                    }
                )
        except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation):
            continue
    return out
