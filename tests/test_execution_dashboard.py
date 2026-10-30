"""Offline ledger dashboard fixtures and mocked publication."""

import datetime as dt
import hashlib
import io
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from prometheus.alert_contract import kalshi_url
from prometheus.execution import dashboard, notify
from prometheus.execution.ledger import DynamoLedger, _item

NOW = dt.datetime(2026, 10, 29, 23, tzinfo=dt.UTC)


def fixture():
    rows = []
    profits = [".61", *[".96"] * 6, "5.96", "-4.74", "-4.74", "-4.75"]
    for i, profit in enumerate(profits):
        cost = "4" if i < 7 else "6.49" if i == 7 else str(abs(Decimal(profit)))
        rows.append(
            {
                "status": "settled",
                "realized_profit": profit,
                "actual_cost": cost,
                "actual_fees": "0",
                "held": "0",
                "settled_at": "2026-10-29T21:27:00Z",
                "alert": {
                    "teams": ["Anyone's Legend", "Team Liquid"],
                    "backed_team": "Team Liquid",
                    "start": f"2026-10-{22 if i == 0 else 24 if i < 8 else 26}T12:00:00Z",
                    "event_ticker": f"KXLOLGAME-{i}",
                },
            }
        )
    for i, (game, held) in enumerate(
        [
            ("lol", "3.70"),
            ("lol", "3.71"),
            ("cs2", "4.06"),
            *[("cs2", "2.38")] * 5,
            ("cs2", "2.41"),
        ]
    ):
        rows.append(
            {
                "status": "filled",
                "held": held,
                "actual_cost": str(Decimal(held) - Decimal(".03")),
                "actual_fees": ".03",
                "execution_probability": ".72",
                "order": {"fill_count_fp": "6.09"},
                "filled_at": "2026-10-29T21:27:00Z",
                "fills": {"count": 1, "prefix": "EVIDENCE#"},
                "alert": {
                    "game": game,
                    "teams": ["Donstu Esports", "KUUSAMO.gg"],
                    "backed_team": "Donstu Esports",
                    "start": f"2026-10-30T{9 + i:02}:00:00Z",
                    "event_ticker": (
                        "KXCS2GAME-26OCT300500DONKSM" if i == 2 else f"KXCS2GAME-{i}"
                    )
                    if game == "cs2"
                    else f"KXLOLGAME-OPEN{i}",
                },
            }
        )
    # The sample CS2 row starts at 2 AM PT and has the specified $2.03 win.
    rows[13]["alert"]["start"] = "2026-10-30T09:00:00Z"
    accounts = {
        "ACCOUNT": {"held": "7.41", "realized": "-1.90"},
        "ACCOUNT#cs2": {"held": "18.37"},
    }
    config = {
        "starting_bankroll_usd": "50",
        "games": {
            "cs2": {"enabled": True, "starting_bankroll_usd": "50"},
            "valorant": {"enabled": True, "starting_bankroll_usd": "50"},
        },
    }
    return rows, accounts, config


def test_example_structure_numbers_links_charts_and_stability():
    rows, accounts, config = fixture()
    body = dashboard.render(rows, accounts, config, NOW)
    assert body == dashboard.render(
        reversed(rows), accounts, config, NOW + dt.timedelta(minutes=45)
    )
    assert body.startswith(
        "**Updated** Oct 29, 2:27 PM PT · **Net P&L −$1.90** · **Open $25.78 across 9 positions**"
    )
    for line in [
        "| League | $50.00 | **−$1.90** | 8–3 | −3.9% | $7.41 | $40.69 |",
        "| CS2 | $50.00 | $0.00 | 0–0 | — | $18.37 | $31.63 |",
        "| Valorant | $50.00 | $0.00 | 0–0 | — | $0.00 | $50.00 |",
        "| **Total** | **$150.00** | **−$1.90** | **8–3** | −3.9% | **$25.78** | **$122.32** |",
        "🟦 League · 🟥 CS2 · 🟩 Valorant",
        'y-axis "Bankroll ($)" 43 --> 68',
        'y-axis "Bankroll ($)" 143 --> 168',
        "line [50.61, 50.61, 62.33, 62.33, 48.10, 48.10, 48.10, 48.10]",
        "| Oct 30, 2:00 AM | CS2 | [Donstu Esports v KUUSAMO.gg](https://kalshi.com/markets/kxcs2game/counter-strike-2-game/kxcs2game-26oct300500donksm) | Donstu Esports | $4.06 | +$2.03 | 72% |",
    ]:
        assert line in body
    assert body.count("```mermaid") == 2
    assert '"plotColorPalette": "#2563eb, #dc2626, #16a34a"' in body
    assert '"plotColorPalette": "#111827"' in body
    results = body.split("### Last 10 results")[1]
    assert results.count("| Oct") == 10
    assert "| ❌ | −$4.75 |" in results and "| ✅ | +$0.96 |" in results
    assert results.index("Oct 26") < results.index("Oct 24")
    assert body.endswith(
        "_Each trade also has its own issue, closed when it settles._\n"
    )


def test_empty_missing_config_partial_fills_dates_and_escape():
    body = dashboard.render([], {}, {"starting_bankroll_usd": "50"}, NOW)
    assert "mermaid" not in body and "_No open positions._" in body
    assert "CS2" not in body and "Oct 29, 4:00 PM PT" in body
    row = {
        "status": "unknown",
        "fills": [{"count_fp": "2"}, {"count_fp": "1"}],
        "held": "1.2",
        "actual_cost": "1.1",
        "actual_fees": ".1",
        "execution_probability": ".7",
        "alert": {
            "game": "cs2",
            "teams": ["A|B", "C"],
            "backed_team": "A|B",
            "start": "2026-09-01T02:00:00Z",
            "event_ticker": "CS2",
        },
    }
    body = dashboard.render([row], {"ACCOUNT#cs2": {"held": "99"}}, {}, NOW)
    assert "| CS2 | $50.00" in body and "| $1.20 | $0.00 |" in body
    assert r"[A\|B v C]" in body and r"| A\|B |" in body
    assert "Aug 31, 7:00 PM" in body and "+$1.80" in body
    axes = [line for line in body.splitlines() if "x-axis" in line]
    labels = json.loads(axes[0].split("x-axis ")[1])
    assert len(labels) == 30 and labels[0] == "Sep 1" and labels[-1] == "Oct 29"


def test_exchange_timestamps_and_league_link():
    assert dashboard.changed_at(
        {
            "order": {"last_update_time": "2026-10-29T21:27:00Z"},
            "fills": {"prefix": "x"},
        }
    ) == [dt.datetime(2026, 10, 29, 21, 27, tzinfo=dt.UTC)]
    assert (
        kalshi_url({"event_ticker": "KXLOLGAME-EVENT"})
        == "https://kalshi.com/markets/kxlolgame/league-of-legends-game/kxlolgame-event"
    )


class Response(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload).encode())
        self.status = status


@pytest.mark.parametrize("existing", [True, False])
def test_sync_patch_or_skip(existing):
    calls = []
    digest = hashlib.sha256(b"new").hexdigest()

    def open(request, timeout):
        calls.append(request)
        assert request.method == "PATCH" and request.full_url.endswith("/issues/42")
        assert json.loads(request.data) == {"body": "new"}
        assert timeout == 10
        return Response({})

    state = {"issue": Decimal(42), "hash": "old" if existing else digest}
    result = notify.sync_dashboard(
        "token", "owner/repo", "new", state, SimpleNamespace(open=open)
    )
    assert result == ({"issue": 42, "hash": digest} if existing else None)
    assert len(calls) == int(existing)


@pytest.mark.parametrize("found", [True, False])
def test_sync_find_create_and_pin(found):
    calls = []
    issue = {
        "number": 42,
        "node_id": "NODE",
        "title": "📊 Trading dashboard",
        "body": "old",
    }

    def open(request, timeout):
        calls.append(request.method)
        if request.full_url.endswith("graphql"):
            assert json.loads(request.data)["variables"] == {"id": "NODE"}
            return Response({"data": {"pinIssue": {"issue": {"id": "NODE"}}}})
        if request.method == "GET":
            return Response(
                [
                    {"title": issue["title"], "pull_request": {}},
                    {"title": issue["title"] + " extra"},
                    *([issue] if found else []),
                ]
            )
        if request.method == "POST":
            assert json.loads(request.data) == {"title": issue["title"], "body": "new"}
            return Response(issue, 201)
        return Response(issue)

    assert (
        notify.sync_dashboard(
            "token", "owner/repo", "new", {}, SimpleNamespace(open=open)
        )["issue"]
        == 42
    )
    assert calls == ["GET", "PATCH" if found else "POST", "POST"]


def test_sync_pagination_and_failures():
    calls = []

    def open(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            return Response([{"title": "other"}] * 100)
        raise TimeoutError

    assert (
        notify.sync_dashboard(
            "token", "owner/repo", "x", {}, SimpleNamespace(open=open)
        )
        is None
    )
    assert len(calls) == 2 and calls[-1].endswith("page=2")
    assert notify.sync_dashboard("token", "https://evil/repo", "x", {}) is None


def test_ledger_intents_paginate_and_put_meta():
    calls, writes = [], []

    def query(**kwargs):
        calls.append(kwargs.copy())
        assert kwargs["ExpressionAttributeValues"] == _item(
            {":pk": "ENV#live", ":prefix": "INTENT#"}
        )
        result = {
            "Items": [
                _item(
                    {
                        "payload": json.dumps(
                            {"status": "settled" if len(calls) == 1 else "filled"}
                        )
                    }
                )
            ]
        }
        if len(calls) == 1:
            result["LastEvaluatedKey"] = _item({"pk": "ENV#live", "sk": "INTENT#a"})
        return result

    ledger = DynamoLedger(
        "ledger",
        SimpleNamespace(query=query, put_item=lambda **kwargs: writes.append(kwargs)),
    )
    assert ledger.intents("live") == [{"status": "settled"}, {"status": "filled"}]
    assert calls[1]["ExclusiveStartKey"] == _item({"pk": "ENV#live", "sk": "INTENT#a"})
    ledger.put_meta("live", "DASHBOARD", {"issue": 42, "hash": "digest"})
    assert writes == [
        {
            "TableName": "ledger",
            "Item": _item(
                {"pk": "ENV#live", "sk": "DASHBOARD", "issue": 42, "hash": "digest"}
            ),
        }
    ]


def test_settled_fees_draw_and_ignored_reservations():
    rows, _, _ = fixture()
    row = {**rows[0], "realized_profit": "0", "actual_cost": "2", "actual_fees": ".20"}
    row["alert"] = {**row["alert"], "start": "2026-10-29T01:00:00Z"}
    pending = {**row, "status": "reserved", "held": "99"}
    body = dashboard.render([row, pending], {}, {"starting_bankroll_usd": "50"}, NOW)
    assert "mermaid" not in body
    assert "| League | $50.00 | $0.00 | 0–0 | 0.0% | $0.00 | $50.00 |" in body
    assert "| Oct 28 | League" in body and "| ➖ | $0.00 |" in body
    assert "_No open positions._" in body
    row["realized_profit"] = ".22"
    assert "| **+$0.22** | 1–0 | 10.0% |" in dashboard.render([row], {}, {}, NOW)


@pytest.mark.parametrize("status,pin_errors", [(500, False), (200, True), (200, False)])
def test_adopt_matching_body_without_rewriting_and_pin_failures(status, pin_errors):
    calls = []

    def open(request, timeout):
        calls.append(request.method)
        if request.method == "GET":
            return Response(
                [
                    {
                        "title": "📊 Trading dashboard",
                        "number": 42,
                        "node_id": "NODE",
                        "body": "same",
                    }
                ]
            )
        assert request.full_url == "https://api.github.com/graphql"
        return Response({"errors": ["denied"]} if pin_errors else {"data": {}}, status)

    result = notify.sync_dashboard(
        "token", "owner/repo", "same", {}, SimpleNamespace(open=open)
    )
    assert (result is not None) == (status == 200 and not pin_errors)
    assert calls == ["GET", "POST"]
