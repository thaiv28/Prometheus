"""Public-document V2 fixtures with a fully mocked transport."""

import base64
import copy
import datetime as dt
import email.utils
import io
import json
from decimal import Decimal
from typing import ClassVar

import pytest

from prometheus.execution.core import Config
from prometheus.execution.kalshi import PATH, Kalshi, NoRedirect

NOW = dt.datetime(2026, 10, 15, 12, tzinfo=dt.UTC)


def config():
    # Only the limits used by route resolution are needed by this transport test.
    return Config("demo", {"max_quote_age_seconds": 30, "fee_rate_upper_bound": ".07"})


def alert():
    return {
        "event_ticker": "KXLOLGAME-F",
        "start": "2026-10-16T12:00:00Z",
        "teams": ["A", "B"],
        "backed_team": "A",
    }


def market(team):
    return {
        "ticker": f"KXLOLGAME-F-{team}",
        "event_ticker": "KXLOLGAME-F",
        "market_type": "binary",
        "yes_sub_title": team,
        "status": "active",
        "notional_value_dollars": "1.0000",
        "price_ranges": [{"start": "0", "end": "1", "step": ".01"}],
        "close_time": "2026-10-17T12:00:00Z",
        "rules_primary": f"If {team} wins the Worlds 2026: A vs. B League of Legends "
        "match originally scheduled for Oct 16, 2026 at 8:00 AM EDT, ...",
    }


class PublicClient(Kalshi):
    def __init__(self):
        self.aliases = {}
        self.event = {
            "event_ticker": "KXLOLGAME-F",
            "series_ticker": "KXLOLGAME",
            "mutually_exclusive": True,
            "markets": [market("A"), market("B")],
        }
        self.series = {"fee_type": "quadratic", "fee_multiplier": 1}
        self.books = {
            "KXLOLGAME-F-A": {
                "yes_dollars": [[".20", "4"]],
                "no_dollars": [[".3", "2"], [".4", "3"]],
            },
            "KXLOLGAME-F-B": {
                "yes_dollars": [[".7", "5"], [".6", "8"]],
                "no_dollars": [],
            },
        }
        self.received = NOW.isoformat()
        self.server, self.age = NOW.isoformat(), "0"
        self.calls = []
        self.event_changes, self.series_changes = [], []

    def request(self, method, path, body=None, **query):
        self.calls.append((method, path, body, query))
        if path == "/events/fee_changes":
            return {"event_fee_changes": self.event_changes, "cursor": ""}
        if path == "/series/fee_changes":
            return {"series_fee_change_arr": self.series_changes}
        if path.startswith("/events/"):
            return {"event": copy.deepcopy(self.event)}
        if path == "/series/KXLOLGAME":
            return {"series": self.series}
        if path.endswith("/orderbook"):
            return {
                "orderbook_fp": self.books[path.split("/")[2]],
                "_received_at": self.received,
                "_server_time": self.server,
                "_cache_age": self.age,
            }
        raise AssertionError(path)


def test_routes_resolve_backed_yes_and_opponent_no_from_actual_books():
    api = PublicClient()
    routes = api.resolve(alert(), NOW, config())
    assert routes == [
        {
            "ticker": "KXLOLGAME-F-A",
            "outcome_team": "A",
            "side": "bid",
            "price": "0.6",
            "limit": "0.6000",
            "quantity": "3",
            "at": NOW.isoformat(),
        },
        {
            "ticker": "KXLOLGAME-F-B",
            "outcome_team": "B",
            "side": "ask",
            "price": "0.3",
            "limit": "0.7000",
            "quantity": "5",
            "at": NOW.isoformat(),
        },
    ]
    assert [call[1] for call in api.calls][-2:] == [
        "/markets/KXLOLGAME-F-A/orderbook",
        "/markets/KXLOLGAME-F-B/orderbook",
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda api: api.event.update(series_ticker="KXLOLMAP"),
        lambda api: api.event.update(event_ticker="different"),
        lambda api: api.event.update(mutually_exclusive=False),
        lambda api: api.event["markets"].append(market("Draw")),
        lambda api: api.event["markets"][0].update(yes_sub_title="B"),
        lambda api: api.event["markets"][0].update(
            rules_primary=market("A")["rules_primary"].replace("A vs. B", "A vs. C")
        ),
        lambda api: api.event["markets"][0].update(
            rules_primary=market("A")["rules_primary"].replace("8:00 AM", "9:00 AM")
        ),
        lambda api: api.event["markets"][0].update(
            rules_primary=market("A")["rules_primary"].replace(" at 8:00 AM EDT", "")
        ),
        lambda api: api.event["markets"][0].update(notional_value_dollars="2"),
        lambda api: api.event["markets"][0].pop("notional_value_dollars"),
        lambda api: api.event["markets"][1].update(
            rules_primary=market("A")["rules_primary"], yes_sub_title="A"
        ),
        lambda api: api.event.update(fee_multiplier_override=2),
        lambda api: api.series.update(fee_type="new_unrecognized_fee"),
    ],
)
def test_ambiguous_fixture_route_or_unbounded_fees_fail_closed(mutate):
    api = PublicClient()
    mutate(api)
    with pytest.raises(ValueError):
        api.resolve(alert(), NOW, config())


@pytest.mark.parametrize(
    "change",
    [
        {"server": None},
        {"age": "1"},
        {"server": "2026-10-15T11:59:00Z"},
        {"server": "2026-10-15T12:00:06Z"},
    ],
)
def test_stale_cached_or_undated_orderbook_rejected(change):
    api = PublicClient()
    for key, value in change.items():
        setattr(api, key, value)
    with pytest.raises(ValueError):
        api.resolve(alert(), NOW, config())


def test_only_explicit_aliases_can_resolve_team_spelling():
    api = PublicClient()
    api.event["markets"][0]["rules_primary"] = market("A")["rules_primary"].replace(
        "If A wins", "If Alpha wins"
    )
    api.event["markets"][0]["yes_sub_title"] = "Alpha"
    with pytest.raises(ValueError):
        api.resolve(alert(), NOW, config())
    api.aliases = {"Alpha": "A"}
    assert len(api.resolve(alert(), NOW, config())) == 2


def test_v2_write_cancel_and_read_paths_and_pagination_are_distinct():
    api = object.__new__(Kalshi)
    calls = []

    def request(method, path, body=None, **query):
        calls.append((method, path, body, query))
        return {
            "orders": [{"order_id": "o", "client_order_id": "c"}],
            "cursor": "next" if not query.get("cursor") else "",
        }

    api.request = request
    api.place({"ticker": "T", "side": "ask", "price": ".7", "count": "1.00"})
    api.cancel("o")
    assert calls[0][0:2] == ("POST", "/portfolio/events/orders")
    assert calls[1][0:2] == ("DELETE", "/portfolio/events/orders/o")
    assert len(api.pages("/portfolio/orders", "orders")) == 2
    assert calls[-1][3]["cursor"] == "next"


def test_lookup_paginates_current_then_historical_no_blind_resubmission():
    api = object.__new__(Kalshi)
    paths = []

    def pages(path, field, **query):
        paths.append(path)
        return (
            []
            if path == "/portfolio/orders"
            else [{"client_order_id": "stable", "order_id": "old"}]
        )

    api.pages = pages
    assert api.lookup("stable")["order_id"] == "old"
    assert paths == ["/portfolio/orders", "/historical/orders"]


def test_book_transport_no_redirect_and_no_post_retry():
    api = object.__new__(Kalshi)
    api.environment = "demo"
    api.headers = lambda method, path: {}

    class Failed:
        count = 0

        def open(self, request, timeout):
            self.count += 1
            assert request.full_url.startswith(
                "https://external-api.demo.kalshi.co/trade-api/v2/"
            )
            raise TimeoutError

    api.opener = Failed()
    with pytest.raises(RuntimeError, match="uncertain"):
        api.place({"ticker": "T"})
    assert api.opener.count == 1
    with pytest.raises(ValueError, match="redirect"):
        NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")


def test_transport_records_receipt_server_date_and_cache_age_without_account_logging():
    api = object.__new__(Kalshi)
    api.environment = "demo"
    api.headers = lambda method, path: {}

    class Response(io.BytesIO):
        headers: ClassVar = {"Date": email.utils.format_datetime(NOW), "Age": "0"}

    class Transport:
        def open(self, request, timeout):
            return Response(json.dumps({"orderbook_fp": {}}).encode())

    api.opener = Transport()
    result = api.request("GET", "/markets/T/orderbook")
    assert result["_server_time"] == NOW.isoformat()
    assert result["_cache_age"] == "0" and result["_received_at"]


def test_whole_account_unsettled_positions_and_unrelated_resting_orders_are_counted():
    api = object.__new__(Kalshi)

    def pages(path, field, **query):
        if path == "/portfolio/positions":
            return [{"ticker": "unrelated", "market_exposure_dollars": "-4.20"}]
        return [
            {
                "ticker": "unrelated",
                "book_side": "ask",
                "no_price_dollars": ".30",
                "remaining_count_fp": "3",
            }
        ]

    api.pages = pages
    assert api.exposure() == Decimal("7.20")


def test_fills_preserve_actual_fees_and_deduplicate_current_historical_overlap():
    api = object.__new__(Kalshi)
    row = {"fill_id": "f", "fee_cost": ".02", "order_id": "o"}
    api.pages = lambda *args, **kwargs: [copy.deepcopy(row)]
    assert api.fills("o") == [row]


@pytest.mark.parametrize("kind", ["rsa", "ed25519"])
def test_official_request_signature_path_without_query(kind):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

    key = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if kind == "rsa"
        else ed25519.Ed25519PrivateKey.generate()
    )
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    api = Kalshi("demo", "test-key", pem)
    headers = api.headers("GET", "/portfolio/orders?limit=5")
    message = (
        headers["KALSHI-ACCESS-TIMESTAMP"] + "GET" + PATH + "/portfolio/orders"
    ).encode()
    signature = base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"])
    if kind == "rsa":
        key.public_key().verify(
            signature,
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            hashes.SHA256(),
        )
    else:
        key.public_key().verify(signature, message)
    assert headers["KALSHI-ACCESS-KEY"] == "test-key"


def test_scalar_settlement_requires_finalized_public_market_not_determined_result():
    api = object.__new__(Kalshi)
    api.now = lambda: NOW
    api.pages = lambda *args, **kwargs: [
        {
            "ticker": "T",
            "market_result": "scalar",
            "settled_time": NOW.isoformat(),
            "revenue": 99,
            "fee_cost": ".01",
        }
    ]
    market = {
        "ticker": "T",
        "result": "scalar",
        "status": "determined",
        "settlement_value_dollars": ".3333",
        "settlement_ts": NOW.isoformat(),
    }
    api.request = lambda *args, **kwargs: {"market": market}
    assert api.settlements("T") == []
    market["status"] = "finalized"
    assert (
        api.settlements("T")[0]["finalized_market"]["settlement_value_dollars"]
        == ".3333"
    )


def test_current_complete_fill_count_does_not_fetch_historical_endpoint():
    api = object.__new__(Kalshi)
    paths = []

    def pages(path, *args, **kwargs):
        paths.append(path)
        return [{"fill_id": "f", "count_fp": "1.00", "fee_cost": ".02"}]

    api.pages = pages
    assert len(api.fills("o", Decimal("1.00"))) == 1
    assert paths == ["/portfolio/fills"]


def test_current_event_fee_override_history_is_authoritative_and_null_clears():
    api = PublicClient()
    api.event_changes = [
        {
            "event_ticker": "KXLOLGAME-F",
            "fee_type_override": "quadratic",
            "fee_multiplier_override": 2,
            "scheduled_ts": "2026-10-15T11:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="fee_bound_exceeded"):
        api.resolve(alert(), NOW, config())
    api.event_changes.append(
        {
            "event_ticker": "KXLOLGAME-F",
            "fee_type_override": None,
            "fee_multiplier_override": None,
            "scheduled_ts": "2026-10-15T11:30:00Z",
        }
    )
    assert len(api.resolve(alert(), NOW, config())) == 2


@pytest.mark.parametrize("level", ["series", "event"])
def test_announced_fee_change_before_match_cannot_exceed_reserve_bound(level):
    api = PublicClient()
    if level == "series":
        api.series_changes = [
            {
                "series_ticker": "KXLOLGAME",
                "fee_type": "quadratic",
                "fee_multiplier": 2,
                "scheduled_ts": "2026-10-15T12:00:05Z",
            }
        ]
    else:
        api.event_changes = [
            {
                "event_ticker": "KXLOLGAME-F",
                "fee_type_override": "quadratic",
                "fee_multiplier_override": 2,
                "scheduled_ts": "2026-10-15T12:00:05Z",
            }
        ]
    with pytest.raises(ValueError, match="fee_bound_exceeded"):
        api.resolve(alert(), NOW, config())
