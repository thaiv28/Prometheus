"""Mocked failure-path tests: no credentials, network or real exchange orders."""

import copy
import datetime as dt
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from prometheus import market_blend
from prometheus.execution.core import Config, fee_bound, run
from prometheus.execution.ledger import DynamoLedger, _decode, _item

NOW = dt.datetime(2026, 10, 15, 12, tzinfo=dt.UTC)


def settings(**changes):
    return {
        "mode": "demo",
        "activation_at": "2026-10-15T11:00:00Z",
        "max_alert_age_seconds": 3600,
        "max_quote_age_seconds": 30,
        "max_price": "0.60",
        "min_after_fee_edge": "0.05",
        "fee_rate_upper_bound": "0.07",
        "order_budget_usd": "5",
        "fixture_budget_usd": "5",
        "daily_budget_usd": "20",
        "max_exposure_usd": "20",
        "min_balance_usd": "5",
        "max_contracts": 10,
        "balance_precision_usd": ".0001",
        "starting_bankroll_usd": "50",
        "kelly_fraction": "1",
        **changes,
    }


def saved(**changes):
    return {
        "schema_version": 1,
        "alert_id": "a",
        "fixture_id": "f",
        "alert_at": "2026-10-15T11:59:00Z",
        "start": "2026-10-16T12:00:00Z",
        "teams": ["A", "B"],
        "backed_team": "A",
        "event_ticker": "KXLOLGAME-F",
        "probability": "0.75",
        "original_ask": "0.60",
        "group": "minor-domestic",
        "provenance": {"method": "forge"},
        **changes,
    }


class Conditional(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "TransactionCanceledException"}}


class AtomicDynamo:
    """Minimal atomic service fake, not a replacement ledger implementation.

    Executes the actual generated conditional Dynamo requests atomically, with
    rollback, making races/restarts testable without adding AWS test dependencies.
    """

    def __init__(self):
        self.data, self.lock = {}, threading.Lock()
        self.requests = []

    @staticmethod
    def key(item):
        return item["pk"]["S"], item["sk"]["S"]

    def transact_write_items(self, TransactItems):
        with self.lock:
            self.requests.append(copy.deepcopy(TransactItems))
            next_data = copy.deepcopy(self.data)
            for action in TransactItems:
                op = action.get("Put") or action.get("Update") or action["Delete"]
                item = op.get("Item") or op["Key"]
                key = self.key(item)
                old = _decode(next_data.get(key, {}))
                values = _decode(op.get("ExpressionAttributeValues", {}))
                condition = op.get("ConditionExpression", "")
                if condition == "attribute_not_exists(pk)" and old:
                    raise Conditional
                if (
                    condition == "revision = :revision"
                    and old.get("revision") != values[":revision"]
                ):
                    raise Conditional
                if " <= :available" in condition:
                    field = "held" if "held <= :available" in condition else "committed"
                    if field in old and old[field] > values[":available"]:
                        raise Conditional
                for field in ("held", "realized"):
                    expected = values.get(f":expected_{field}")
                    if expected is not None and old.get(field, Decimal(0)) != expected:
                        raise Conditional
                if "Put" in action:
                    next_data[key] = copy.deepcopy(item)
                elif "Delete" in action:
                    next_data.pop(key, None)
                else:
                    old.update(_decode(op["Key"]))
                    for addition in (
                        op["UpdateExpression"].removeprefix("ADD ").split(",")
                    ):
                        field, delta = addition.split()
                        old[field] = old.get(field, Decimal(0)) + values[delta]
                    next_data[key] = _item(old)
            self.data = next_data

    def get_item(self, Key, **kwargs):
        return (
            {"Item": copy.deepcopy(self.data[self.key(Key)])}
            if self.key(Key) in self.data
            else {}
        )

    def put_item(self, Item, **kwargs):
        with self.lock:
            if kwargs.get("ConditionExpression") and self.key(Item) in self.data:
                raise Conditional
            self.data[self.key(Item)] = copy.deepcopy(Item)

    def query(self, ExpressionAttributeValues, **kwargs):
        values = _decode(ExpressionAttributeValues)
        return {
            "Items": [
                copy.deepcopy(v)
                for (pk, sk), v in self.data.items()
                if pk == values[":pk"] and sk.startswith(values[":prefix"])
            ]
        }


class Exchange:
    def __init__(self):
        self.calls, self.orders, self.fill_rows, self.settlement_rows = [], [], [], []
        self.timeout, self.invisible, self.cancel_fails = False, False, False
        self.cash, self.risk = "100", "0"
        self.routes = [
            {
                "ticker": "KXLOLGAME-F-A",
                "side": "bid",
                "price": "0.60",
                "limit": "0.6000",
                "quantity": "10",
                "at": NOW.isoformat(),
            }
        ]

    @staticmethod
    def now():
        return NOW

    def resolve(self, alert, now, config):
        return copy.deepcopy(self.routes)

    def balance(self):
        return self.cash

    def exposure(self):
        return self.risk

    def place(self, body):
        self.calls.append(copy.deepcopy(body))
        order = {
            **body,
            "order_id": "o",
            "status": "canceled",
            "fill_count_fp": "0",
            "remaining_count_fp": "0",
            "book_side": body["side"],
        }
        self.orders.append(order)
        if self.timeout:
            raise TimeoutError("accepted but response lost")
        return {
            "order_id": "o",
            "client_order_id": body["client_order_id"],
            "fill_count": "0",
            "remaining_count": "0",
            "ts_ms": 1,
        }

    def lookup(self, client_id, order_id=None):
        if self.invisible:
            return None
        return next(
            (
                copy.deepcopy(o)
                for o in self.orders
                if o["client_order_id"] == client_id
            ),
            None,
        )

    def fills(self, order_id, expected=None):
        return copy.deepcopy(self.fill_rows)

    def settlements(self, ticker):
        return copy.deepcopy(self.settlement_rows)

    def cancel(self, order_id, market_ticker=None):
        if self.cancel_fails:
            raise TimeoutError
        for order in self.orders:
            if order["order_id"] == order_id:
                order["status"] = "canceled"


def harness(config=None):
    client, api = AtomicDynamo(), Exchange()
    ledger = DynamoLedger("private", client)
    config = config or settings()
    execute = lambda alerts: run(
        alerts, lambda: config, ledger, lambda environment: api, now=NOW
    )
    return client, api, ledger, execute


def test_blended_execution_reprices_market_and_records_actual_probability():
    forecast = market_blend.estimate(0.9, 0.7, NOW)
    alert = saved(trading=forecast, probability=forecast["probability"])
    _, api, ledger, execute = harness(settings(min_after_fee_edge="0"))
    api.routes[0]["market_mid"] = "0.2"
    execute([alert])
    assert api.calls == [] and held(ledger) == 0
    api.routes[0]["market_mid"] = "0.7"
    execute([alert])
    assert len(api.calls) == 1
    plan = json.loads(ledger.get("demo", "INTENT#f")["payload"])
    # The frozen alert is retained alongside the current execution estimate.
    assert plan is not None
    assert float(plan["execution_probability"]) == pytest.approx(
        forecast["probability"]
    )


def test_blended_execution_requires_current_mid_and_excludes_cross_league():
    forecast = market_blend.estimate(0.9, 0.7, NOW)
    _, api, _, execute = harness(settings(min_after_fee_edge="0"))
    execute([saved(trading=forecast, probability=forecast["probability"])])
    assert api.calls == []
    execute([saved(group="other-cross-league")])
    assert api.calls == []


@pytest.mark.parametrize(
    "teams,back,group,homes,allowed",
    [
        (["A", "Cloud9"], "A", "major-domestic", {}, False),
        (["Cloud9 Kia", "B"], "Cloud9 Kia", "major-international", {}, False),
        (["C9", "B"], "B", "minor-domestic", {}, False),
        (["A", "B"], "A", "major-international", {"A": "LCK", "B": "LCS"}, False),
        (["B", "A"], "A", "major-international", {"A": "LCK", "B": "LTA N"}, False),
        (["A", "B"], "B", "major-international", {"A": "LCK", "B": "LCS"}, True),
        (["A", "B"], "A", "major-domestic", {"A": "LCS", "B": "LCS"}, True),
        (["A", "B"], "A", "major-international", {}, False),
    ],
)
def test_personal_trading_vetoes(teams, back, group, homes, allowed):
    _, api, _, execute = harness()
    execute([saved(teams=teams, backed_team=back, group=group, team_homes=homes)])
    assert bool(api.calls) == allowed


def held(ledger):
    account = ledger.get("demo", "ACCOUNT")
    return account["held"] if account else Decimal(0)


def fill(api, count="3", price=".59", fee=".04"):
    api.orders[0]["fill_count_fp"] = count
    api.fill_rows = [
        {
            "fill_id": "fill",
            "order_id": "o",
            "ticker": "KXLOLGAME-F-A",
            "count_fp": count,
            "yes_price_dollars": price,
            "no_price_dollars": str(1 - Decimal(price)),
            "fee_cost": fee,
            "book_side": "bid",
        }
    ]


def test_default_off_no_credentials_no_exchange_calls():
    client = AtomicDynamo()

    def forbidden(environment):
        raise AssertionError("off must not load keys")

    result = run(
        [saved()],
        lambda: {"mode": "off", "activation_at": None},
        DynamoLedger("private", client),
        forbidden,
        NOW,
    )
    assert result == {"submitted": 0, "skipped": 0, "reconciled": 0, "errors": 0}
    assert client.data == {}


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "paper"},
        {"order_budget_usd": "0"},
        {"max_price": "NaN"},
        {"max_contracts": "1.5"},
    ],
)
def test_active_config_requires_explicit_valid_limits(change):
    with pytest.raises((ValueError, KeyError)):
        Config.parse(settings(**change))
    with pytest.raises(KeyError):
        Config.parse({"mode": "live"})


@pytest.mark.parametrize(
    "change",
    [
        {"alert_at": "2026-10-15T10:59:00Z"},
        {"alert_at": "2026-10-15T12:00:01Z"},
        {"start": NOW.isoformat()},
        {"group": "unposted-paper"},
        {"event_ticker": ""},
        {"teams": ["A", "A"]},
        {"probability": "nan"},
    ],
)
def test_stale_future_backlog_invalid_alerts_do_not_submit(change):
    client, api, ledger, execute = harness()
    assert execute([saved(**change)])["skipped"] == 1
    assert not api.calls
    assert not ledger.pending()
    assert any("SKIP#" in key[1] for key in client.data)


def test_intent_precedes_submission_and_v2_body():
    client, api, ledger, execute = harness()
    original = api.place

    def submit(body):
        assert ledger.pending()[0]["status"] == "submitting"
        assert held(ledger) == Decimal("4.41")
        assert body["side"] == "bid"
        assert body["price"] == "0.6000" and body["count"] == "7.00"
        assert body["time_in_force"] == "immediate_or_cancel"
        assert "action" not in body and "yes_price" not in body
        return original(body)

    api.place = submit
    assert execute([saved()])["submitted"] == 1
    assert len(client.requests[0]) == 6


def test_timeout_unknown_keeps_reservation_across_process_restart_and_id_change():
    client, api, ledger, execute = harness()
    api.timeout, api.invisible = True, True
    assert execute([saved()])["errors"] == 1
    reserve = held(ledger)
    restarted = DynamoLedger("private", client)
    result = run(
        [saved(alert_id="different", fixture_id="changed", teams=["B", "A"])],
        lambda: settings(),
        restarted,
        lambda environment: api,
        NOW,
    )
    assert result["submitted"] == 0
    assert len(api.calls) == 1 and held(ledger) == reserve
    # Exact provider-id-independent fixture fence also survives ticker changes.
    execute([saved(event_ticker="KXLOLGAME-NEW")])
    assert len(api.calls) == 1


def test_reconcile_unfilled_releases_budget_but_fixture_is_forever_fenced():
    _client, api, ledger, execute = harness()
    execute([saved()])
    assert execute([saved()])["reconciled"] == 1
    assert held(ledger) == 0 and len(api.calls) == 1
    assert ledger.get("demo", "DAY#2026-10-15")["committed"] == 0
    execute([saved(alert_id="again")])
    assert len(api.calls) == 1


def test_partial_fill_actual_fees_settlement_and_no_reissue():
    _client, api, ledger, execute = harness()
    execute([saved()])
    fill(api)
    assert execute([])["reconciled"] == 1
    assert held(ledger) == Decimal("1.81")
    row = ledger.pending()[0]
    assert row["actual_cost"] == "1.77" and row["actual_fees"] == "0.04"
    assert row["fills"]["count"] == 1
    assert (
        json.loads(ledger.get("demo", "EVIDENCE#f#fills#fill")["payload"])["fill_id"]
        == "fill"
    )
    api.settlement_rows = [
        {
            "ticker": "KXLOLGAME-F-A",
            "market_result": "yes",
            "yes_count_fp": "3",
            "no_count_fp": "0",
            "revenue": 300,
            "fee_cost": ".04",
            "settled_time": NOW.isoformat(),
        }
    ]
    execute([])
    assert held(ledger) == 0 and ledger.pending() == []
    assert ledger.get("demo", "DAY#2026-10-15")["committed"] == Decimal("1.81")
    execute([saved()])
    assert len(api.calls) == 1


def test_eventual_fill_visibility_and_bad_fill_keep_full_reservation():
    _client, api, ledger, execute = harness()
    execute([saved()])
    api.orders[0]["fill_count_fp"] = "3"
    original = held(ledger)
    execute([])
    assert held(ledger) == original
    fill(api, price=".61")
    assert execute([])["errors"] == 1
    assert held(ledger) == original


@pytest.mark.parametrize(
    "change", [{"yes_count_fp": "2"}, {"revenue": 0}, {"market_result": "scalar"}]
)
def test_invalid_or_ambiguous_settlement_never_releases_position(change):
    _client, api, ledger, execute = harness()
    execute([saved()])
    fill(api)
    api.settlement_rows = [
        {
            "ticker": "KXLOLGAME-F-A",
            "market_result": "yes",
            "yes_count_fp": "3",
            "no_count_fp": "0",
            "revenue": 300,
            "fee_cost": ".04",
            "settled_time": NOW.isoformat(),
            **change,
        }
    ]
    execute([])
    assert held(ledger) == Decimal("1.81")


def test_off_cancels_only_tracked_order_reconciles_both_environments_and_does_not_sell():
    _client, api, ledger, execute = harness()
    execute([saved()])
    api.orders[0]["status"] = "resting"
    fill(api)
    environments = []

    def factory(environment):
        environments.append(environment)
        return api

    result = run([], lambda: {"mode": "off"}, ledger, factory, NOW)
    assert result["reconciled"] == 1 and environments == ["demo"]
    assert api.orders[0]["status"] == "canceled" and len(api.calls) == 1
    assert held(ledger) == Decimal("1.81")


def test_pause_cancel_failure_retains_entire_reservation():
    _client, api, ledger, execute = harness()
    execute([saved()])
    api.orders[0]["status"], api.cancel_fails = "resting", True
    result = run([], lambda: {"mode": "off"}, ledger, lambda env: api, NOW)
    assert result["errors"] == 1 and held(ledger) == Decimal("4.41")


@pytest.mark.parametrize(
    "change",
    [{"mode": "off"}, {"max_price": ".50"}, {"activation_at": NOW.isoformat()}],
)
def test_configuration_switch_after_reservation_aborts_without_post(change):
    _client, api, ledger, _execute = harness()
    count = 0

    def provider():
        nonlocal count
        count += 1
        return settings() if count == 1 else settings(**change)

    result = run([saved()], provider, ledger, lambda env: api, NOW)
    assert not api.calls and held(ledger) == 0
    assert result["skipped"] == 1


def test_concurrent_workers_cannot_double_reserve_or_submit():
    _client, api, ledger, execute = harness()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: execute([saved()]), range(16)))
    assert len(api.calls) == 1
    assert held(ledger) >= 0


def test_concurrent_different_fixtures_respect_daily_and_exposure_caps():
    _client, api, ledger, execute = harness(
        settings(daily_budget_usd="5", max_exposure_usd="5")
    )
    api.invisible = True
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda i: execute(
                    [
                        saved(
                            fixture_id=f"f{i}",
                            alert_id=f"a{i}",
                            event_ticker=f"KXLOLGAME-{i}",
                        )
                    ]
                ),
                range(4),
            )
        )
    assert len(api.calls) == 1
    assert held(ledger) == Decimal("4.41")


@pytest.mark.parametrize("risk,cash", [("20", "100"), ("0", "5")])
def test_account_exposure_balance_or_available_cap_blocks(risk, cash):
    _client, api, ledger, execute = harness()
    api.risk, api.cash = risk, cash
    execute([saved()])
    assert not api.calls and held(ledger) == 0


def test_remaining_exposure_shrinks_order_instead_of_exceeding_cap():
    _, api, ledger, execute = harness()
    api.risk = "18"
    execute([saved()])
    assert api.calls[0]["count"] == "3.00"
    assert held(ledger) + Decimal(api.risk) <= Decimal("20")


@pytest.mark.parametrize(
    "route",
    [
        {"price": ".61"},
        {"quantity": ".9"},
        {"at": "2026-10-15T11:58:00Z"},
        {"at": "2026-10-15T12:00:01Z"},
    ],
)
def test_original_price_cap_liquidity_and_quote_freshness(route):
    _client, api, _ledger, execute = harness()
    api.routes[0].update(route)
    execute([saved()])
    assert not api.calls


def test_after_fee_edge_not_raw_edge_and_fee_rounding():
    _client, api, _ledger, execute = harness()
    execute([saved(probability=".66")])  # raw6points, afterfee4points
    assert not api.calls
    assert fee_bound(Decimal(".60"), 8, Decimal(".07"), Decimal(".0001")) == Decimal(
        ".24"
    )


def test_ask_direction_keeps_yes_book_price_while_budget_uses_backed_no_cost():
    _client, api, ledger, execute = harness()
    api.routes[0].update(side="ask", price=".40", limit=".6000")
    execute([saved()])
    assert api.calls[0]["side"] == "ask" and api.calls[0]["price"] == ".6000"
    assert held(ledger) == Decimal("4.30")


def test_stale_cas_cannot_overwrite_new_fill_or_release_budget_twice():
    _client, _api, ledger, execute = harness()
    execute([saved()])
    old = ledger.pending()[0]
    execute([])
    assert held(ledger) == 0
    assert ledger.replace(old, {**old, "held": "0", "committed": "0"}) is None
    assert held(ledger) == 0
    assert json.loads(ledger.get("demo", "INTENT#f")["payload"])["status"] == "unfilled"


def test_one_hundred_fractional_fills_are_reserved_and_stored_individually():
    _client, api, ledger, execute = harness()
    api.routes[0]["quantity"] = "1"
    execute([saved()])
    initial = held(ledger)
    api.orders[0]["fill_count_fp"] = "1.00"
    api.fill_rows = [
        {
            "fill_id": f"fragment-{i}",
            "order_id": "o",
            "ticker": "KXLOLGAME-F-A",
            "count_fp": ".01",
            "yes_price_dollars": ".60",
            "no_price_dollars": ".40",
            "fee_cost": ".000268",
            "book_side": "bid",
        }
        for i in range(100)
    ]
    execute([])
    row = ledger.pending()[0]
    assert held(ledger) == Decimal(".626800") <= initial
    assert row["fills"] == {"count": 100, "prefix": "EVIDENCE#f#fills#"}
    assert len(json.dumps(row)) < 4000
    assert ledger.get("demo", "EVIDENCE#f#fills#fragment-99")
    assert fee_bound(Decimal(".90"), 1, Decimal(".07"), Decimal(".0001")) == Decimal(
        ".03"
    )
    assert fee_bound(Decimal(".50"), 1, Decimal(".07"), Decimal(".0001")) == Decimal(
        ".03"
    )


def test_better_fractional_fill_near_half_is_inside_fee_bound_at_high_limit():
    for price in (".5001", ".501", ".51", ".90", ".9999"):
        bound = fee_bound(Decimal(price), 1, Decimal(".07"), Decimal(".0001"))
        # 100 minimum fragments filled at .5, with both model and balance
        # rounding included and no rebate credited.
        assert bound >= 100 * Decimal(".000275")


def test_switch_after_claim_immediately_before_post_aborts():
    _client, api, ledger, _execute = harness()
    reads = 0

    def config():
        nonlocal reads
        reads += 1
        return settings() if reads < 3 else {"mode": "off"}

    result = run([saved()], config, ledger, lambda env: api, NOW)
    assert result["skipped"] == 1 and result["submitted"] == 0
    assert len(api.calls) == 0 and held(ledger) == 0


def test_off_reconciles_live_and_demo_namespaces_separately():
    client = AtomicDynamo()
    ledger = DynamoLedger("private", client)
    demo, live = Exchange(), Exchange()
    for environment, api in (("demo", demo), ("live", live)):
        assert (
            run(
                [saved()],
                lambda environment=environment: settings(mode=environment),
                ledger,
                lambda env, api=api: api,
                NOW,
            )["submitted"]
            == 1
        )
        api.orders[0]["status"] = "resting"
    envs = []

    def factory(env):
        envs.append(env)
        return demo if env == "demo" else live

    result = run([], lambda: {"mode": "off"}, ledger, factory, NOW)
    assert result["reconciled"] == 2 and envs == ["demo", "live"]
    assert not ledger.pending()
    assert demo.calls[0]["client_order_id"] != live.calls[0]["client_order_id"]


def test_active_queries_skip_completed_history():
    client, _api, ledger, execute = harness()
    execute([saved()])
    execute([])
    # Historical intent remains immutable evidence, but is no longer traversed.
    assert ledger.get("demo", "INTENT#f")
    assert ledger.get("demo", "ACTIVE#f") is None
    assert ledger.pending() == []
    assert ("ENV#demo", "FIXTURE#f") in client.data


def test_conflicting_fill_evidence_fails_closed():
    _client, api, ledger, execute = harness()
    execute([saved()])
    fill(api)
    execute([])
    reserved = held(ledger)
    api.fill_rows[0]["fee_cost"] = ".05"
    result = execute([])
    assert result["errors"] == 1 and held(ledger) == reserved


def test_scalar_cancellation_settlement_needs_finalized_market_and_actual_payout():
    _client, api, ledger, execute = harness()
    execute([saved()])
    fill(api)
    api.settlement_rows = [
        {
            "ticker": "KXLOLGAME-F-A",
            "market_result": "scalar",
            "yes_count_fp": "3",
            "no_count_fp": "0",
            "revenue": 99,
            "fee_cost": ".04",
            "settled_time": NOW.isoformat(),
            "finalized_market": {
                "ticker": "KXLOLGAME-F-A",
                "status": "finalized",
                "result": "scalar",
                "settlement_value_dollars": ".3333",
                "settlement_ts": NOW.isoformat(),
            },
        }
    ]
    execute([])
    assert held(ledger) == 0 and ledger.pending() == []
    row = json.loads(ledger.get("demo", "INTENT#f")["payload"])
    assert row["settlements"]["count"] == 1 and row["status"] == "settled"


def test_midnight_between_reservation_and_post_aborts_daily_spending():
    _client, api, ledger, _execute = harness()
    before = dt.datetime(2026, 10, 15, 23, 59, 59, tzinfo=dt.UTC)
    after = before + dt.timedelta(seconds=2)
    reads = iter([before, after])
    api.now = lambda: next(reads)
    api.routes[0]["at"] = before.isoformat()
    proposed = saved(alert_at=before.isoformat())
    result = run([proposed], lambda: settings(), ledger, lambda env: api, before)
    assert result["submitted"] == 0 and result["skipped"] == 1
    assert not api.calls and held(ledger) == 0
    assert ledger.get("demo", "DAY#2026-10-15")["committed"] == 0
