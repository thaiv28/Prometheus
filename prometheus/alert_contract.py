"""Versioned immutable alert identity and a stdlib-only execution adapter.

Only authoritative posted alert records qualify here. This module selects no
trades and never changes saved terms. Execution/account data belongs elsewhere.
"""

import hashlib
import json
from decimal import Decimal, InvalidOperation

SCHEMA_VERSION = 1
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
                    "backed_team": pinned["backed_team"],
                    "event_ticker": pinned["event_ticker"],
                    "probability": str(probability),
                    "original_ask": str(ask),
                    "group": saved.get("group"),
                    "provenance": saved.get("forecast") or {},
                }
            )
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
    return out
