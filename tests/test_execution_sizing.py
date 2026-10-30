"""Kelly objective, bankroll compounding and atomic funding boundaries."""

import copy
import itertools
import json
import math
from decimal import Decimal

import pytest
from test_execution import NOW, fill, harness, saved, settings

from prometheus.execution.core import Config, fee_bound, plan_order, reconcile
from prometheus.execution.ledger import _item
from prometheus.execution.sizing import QUANTITY_STEP, kelly_order


def growth(n, p, c, capital):
    if capital - n * c <= 0:
        return -math.inf
    return p * math.log1p(n * (1 - c) / capital) + (1 - p) * math.log1p(
        -n * c / capital
    )


def test_fractional_kelly_matches_exhaustive_feasible_log_growth():
    for p, c, capital, cap in itertools.product(
        (0.51, 0.6, 0.8, 0.99), (0.1, 0.5, 0.8), (0.05, 1, 7), (0.03, 0.17, 1.234, 3)
    ):
        chosen = kelly_order(p, c, capital, cap)
        n = float(chosen["count"]) if chosen else 0
        optimum = max(growth(k / 100, p, c, capital) for k in range(int(cap * 100) + 1))
        assert growth(n, p, c, capital) == pytest.approx(optimum, abs=1e-12)
        if chosen:
            quantity = Decimal(chosen["count"])
            assert quantity % QUANTITY_STEP == 0
            assert quantity <= Decimal(str(cap))
            assert chosen["quantity_step"] == "0.01"


def test_fee_cost_bankroll_and_small_fractional_edges():
    assert kelly_order(".6", ".5", 50, 100)["count"] == "20.00"
    assert kelly_order(".6", ".5", 100, 100)["count"] == "40.00"
    assert kelly_order(".6", ".52", 50, 100)["count"] == "16.03"
    assert kelly_order(".51", ".5", 1, 100)["count"] == "0.04"
    assert kelly_order(".51", ".5", ".01", 100) is None
    assert kelly_order(".5", ".5", 50, 100) is None


def test_fractional_depth_caps_round_down_and_never_exhaust_bankroll():
    assert kelly_order(".8", ".5", 50, ".239")["count"] == "0.23"
    assert kelly_order(".8", ".5", 50, ".009") is None
    assert kelly_order(".8", ".5", ".005", 100) is None
    with pytest.raises(ValueError, match="finite"):
        kelly_order(".8", ".5", 50, "NaN")


@pytest.mark.parametrize(
    "changes",
    [
        {"starting_bankroll_usd": "0"},
        {"kelly_fraction": "0"},
        {"kelly_fraction": "1.01"},
        {"kelly_fraction": "NaN"},
    ],
)
def test_active_configuration_needs_explicit_valid_kelly_capital(changes):
    with pytest.raises(ValueError):
        Config.parse(settings(**changes))
    assert Config.parse({"mode": "off"}).mode == "off"


@pytest.mark.parametrize("key", ["starting_bankroll_usd", "kelly_fraction"])
def test_missing_kelly_settings_cannot_activate(key):
    configuration = settings()
    del configuration[key]
    with pytest.raises(KeyError):
        Config.parse(configuration)


def roomy(**changes):
    return Config.parse(
        settings(
            order_budget_usd="100",
            fixture_budget_usd="100",
            daily_budget_usd="100",
            max_exposure_usd="100",
            max_contracts=100,
            min_after_fee_edge="0",
            **changes,
        )
    )


def plan(config=None, account=None, **kwargs):
    _, api, _, _ = harness()
    api.routes[0]["quantity"] = "100"
    return plan_order(
        saved(probability=".70"),
        api.routes,
        config or roomy(),
        Decimal(100),
        NOW,
        account,
        **kwargs,
    )


def test_strategy_uses_seed_profit_and_open_commitments_not_entire_account():
    initial = plan()
    won = plan(account={"realized": Decimal(25)})
    open_risk = plan(account={"held": Decimal(20)})
    half = plan(roomy(kelly_fraction=".5"))
    assert initial["sizing"]["bankroll_usd"] == "50"
    assert initial["sizing"]["effective_bankroll_usd"] == "50"
    assert int(float(won["request"]["count"])) > int(float(initial["request"]["count"]))
    assert int(float(open_risk["request"]["count"])) < int(
        float(initial["request"]["count"])
    )
    assert int(float(half["request"]["count"])) < int(
        float(initial["request"]["count"])
    )
    with pytest.raises(ValueError, match="exhausted"):
        plan(account={"realized": Decimal(-50)})
    remaining = plan(committed=Decimal(99))
    assert Decimal(remaining["committed"]) <= 1


def test_route_selection_maximizes_growth_when_cheapest_depth_is_small():
    _, api, _, _ = harness()
    cheap = {
        **api.routes[0],
        "ticker": "cheap",
        "price": ".59",
        "limit": ".5900",
        "quantity": "1",
    }
    deep = {**api.routes[0], "ticker": "deep"}
    row = plan_order(saved(), [cheap, deep], roomy(), Decimal(100), NOW)
    assert row["route"]["ticker"] == "deep"


@pytest.mark.parametrize(
    "outcome,revenue,profit",
    [("yes", 300, "1.19"), ("no", 0, "-1.81"), ("yes", 9999, "1.19")],
)
def test_stale_funding_snapshot_cannot_reserve_and_profit_is_credited_once(
    outcome, revenue, profit
):
    _, _, ledger, _ = harness()
    proposed = plan()
    config = roomy()
    first = ledger.reserve(proposed, config, Decimal(100))
    assert first is not None
    other = copy.deepcopy(proposed)
    other["alert"].update(fixture_id="other", event_ticker="OTHER")
    assert ledger.reserve(other, config, Decimal(100)) is None
    assert ledger.abort(first, "test_cleanup")

    # Start an independent ledger; use actual filled cost/fee and verified payout.
    _, api, ledger, execute = harness()
    execute([saved()])
    fill(api, count="3", price=".59", fee=".04")
    execute([])
    assert ledger.get("demo", "ACCOUNT").get("realized", 0) == 0
    stale = ledger.pending()[0]
    api.settlement_rows = [
        {
            "ticker": api.orders[0]["ticker"],
            "yes_count_fp": "3",
            "market_result": outcome,
            "revenue": revenue,
        }
    ]
    execute([])
    assert ledger.get("demo", "ACCOUNT")["realized"] == Decimal(profit)
    execute([])
    reconcile(stale, api, ledger)
    assert ledger.get("demo", "ACCOUNT")["realized"] == Decimal(profit)
    row = json.loads(ledger.get("demo", "INTENT#f")["payload"])
    assert row["realized_profit"] == profit


def test_atomic_strategy_cap_and_realized_snapshot_are_enforced():
    client, _, ledger, _ = harness()
    client.put_item(
        Item=_item(
            {
                "pk": "ENV#demo",
                "sk": "ACCOUNT",
                "realized": Decimal(-49),
                "held": Decimal(0),
            }
        )
    )
    proposed = plan()
    assert ledger.reserve(proposed, roomy(), Decimal(100)) is None
    proposed["sizing"]["realized_before"] = "-49"
    assert ledger.reserve(proposed, roomy(), Decimal(100)) is None


def test_executor_compounds_verified_profit_on_the_next_fixture():
    _, api, ledger, execute = harness(roomy().raw)
    api.routes[0]["quantity"] = "100"
    execute([saved(probability=".70")])
    first_count = Decimal(api.calls[0]["count"])
    fill(api, count=str(first_count), price=".59", fee=".15")
    api.settlement_rows = [
        {
            "ticker": api.orders[0]["ticker"],
            "yes_count_fp": str(first_count),
            "market_result": "yes",
            "revenue": int(first_count * 100),
        }
    ]
    execute([])
    earned = Decimal(first_count) * Decimal(".41") - Decimal(".15")
    assert ledger.get("demo", "ACCOUNT")["realized"] == earned
    execute([saved(probability=".70", fixture_id="next", event_ticker="NEXT")])
    second = json.loads(ledger.get("demo", "INTENT#next")["payload"])
    assert Decimal(second["sizing"]["bankroll_usd"]) == 50 + earned
    assert Decimal(second["request"]["count"]) > first_count


@pytest.mark.parametrize("quantity", ["0.01", "0.03", "0.90", "2.379"])
def test_fractional_depth_reaches_order_without_truncation_or_float(quantity):
    _, api, _, _ = harness()
    api.routes[0]["quantity"] = quantity
    row = plan_order(saved(), api.routes, roomy(), Decimal(100), NOW)
    expected = Decimal(quantity).quantize(QUANTITY_STEP, rounding="ROUND_FLOOR")
    assert row["request"]["count"] == f"{expected:.2f}"
    assert Decimal(row["held"]) == expected * Decimal(".63")
    assert json.loads(json.dumps(row))["sizing"]["count"] == f"{expected:.2f}"


@pytest.mark.parametrize("cap", ["order", "fixture", "daily", "exposure", "cash"])
def test_subcontract_order_respects_every_remaining_spending_cap(cap):
    _, api, _, _ = harness()
    config, balance, kwargs = roomy(), Decimal(100), {}
    if cap in {"order", "fixture"}:
        config = Config.parse({**config.raw, f"{cap}_budget_usd": ".0189"})
    elif cap == "cash":
        balance = Decimal("5.0189")
    else:
        kwargs["committed" if cap == "daily" else "exposure"] = Decimal("99.9811")
    row = plan_order(saved(), api.routes, config, balance, NOW, **kwargs)
    assert row["request"]["count"] == "0.03"
    assert Decimal(row["held"]) <= Decimal(".0189")
    if cap == "cash":
        assert balance - Decimal(row["held"]) >= config.number("min_balance_usd")


def test_fractional_order_partial_fill_settlement_and_retry_accounting():
    _, api, ledger, execute = harness(settings(order_budget_usd=".0315"))
    assert execute([saved()])["submitted"] == 1
    assert api.calls[0]["count"] == "0.05"
    assert ledger.get("demo", "ACCOUNT")["held"] == Decimal(".0315")
    fill(api, count=".03", price=".59", fee=".0006")
    execute([])
    assert ledger.get("demo", "ACCOUNT")["held"] == Decimal(".0183")
    api.settlement_rows = [
        {
            "ticker": api.orders[0]["ticker"],
            "yes_count_fp": ".03",
            "market_result": "yes",
            "revenue": 3,
        }
    ]
    execute([])
    execute([])
    execute([saved()])
    assert ledger.get("demo", "ACCOUNT")["held"] == 0
    assert ledger.get("demo", "ACCOUNT")["realized"] == Decimal(".0117")
    assert ledger.get("demo", "DAY#2026-10-15")["committed"] == Decimal(".0183")
    assert len(api.calls) == 1


def test_existing_whole_contract_intent_reconciles_without_resizing():
    _, api, ledger, _ = harness()
    legacy = plan()
    legacy["request"]["count"] = "7.00"
    legacy["sizing"]["count"] = 7
    del legacy["sizing"]["quantity_step"]
    legacy["held"] = legacy["committed"] = "4.41"
    reserved = ledger.reserve(legacy, roomy(), Decimal(100))
    assert reserved is not None
    api.place(reserved["request"])
    fill(api)
    assert reconcile(reserved, api, ledger)
    assert ledger.get("demo", "ACCOUNT")["held"] == Decimal("1.81")
    assert ledger.pending()[0]["request"]["count"] == "7.00"
    assert len(api.calls) == 1


def test_fractional_reserve_bounds_maximum_fragment_rounding_without_rebates():
    from decimal import ROUND_CEILING

    for precision, price, quantity in itertools.product(
        (Decimal(".0001"), Decimal(".01")),
        (Decimal(".0001"), Decimal(".35"), Decimal(".5"), Decimal(".9999")),
        (Decimal(".01"), Decimal(".03"), Decimal("1.23")),
    ):
        worst_price = min(price, Decimal(".5"))
        fragment_fee = (
            Decimal(".07") * worst_price * (1 - worst_price) * QUANTITY_STEP
        ).quantize(Decimal(".000001"), rounding=ROUND_CEILING) + precision
        worst_fragment_fees = int(quantity / QUANTITY_STEP) * fragment_fee
        assert (
            fee_bound(price, quantity, Decimal(".07"), precision) >= worst_fragment_fees
        )


@pytest.mark.parametrize("p,c,bankroll", [(".6", ".5", 50), (".73", ".63", 100)])
def test_held_position_kelly_offsets_contracts_and_preserves_defaults(p, c, bankroll):
    original = kelly_order(p, c, bankroll, 1000)
    assert original == kelly_order(p, c, bankroll, 1000, 0, 0)
    held = Decimal("3.25")
    extra = kelly_order(p, c, bankroll, 1000, held, held * Decimal(c))
    assert (
        abs(Decimal(extra["count"]) - (Decimal(original["count"]) - held))
        <= QUANTITY_STEP
    )
    for n in (Decimal(original["count"]), Decimal(original["count"]) + 1):
        assert kelly_order(p, c, bankroll, 1000, n, n * Decimal(c)) is None


@pytest.mark.parametrize("held_cost", [50, 51])
def test_held_position_cannot_exhaust_loss_wealth(held_cost):
    assert kelly_order(".6", ".5", 50, 100, 100, held_cost) is None


@pytest.mark.parametrize("position", [("NaN", 0), (0, "Infinity"), (-1, 0), (0, -1)])
def test_held_position_inputs_must_be_finite_and_nonnegative(position):
    with pytest.raises(ValueError):
        kelly_order(".6", ".5", 50, 100, *position)


def test_held_position_unequal_cost_matches_exhaustive_growth():
    p, c, capital, held, cost = 0.75, 0.6, 10, 2.3, 1.1
    chosen = kelly_order(p, c, capital, 20, held, cost)
    win_base, loss_base = capital + held - cost, capital - cost

    def value(n):
        if loss_base - n * c <= 0:
            return -math.inf
        return p * math.log1p(n * (1 - c) / win_base) + (1 - p) * math.log1p(
            -n * c / loss_base
        )

    optimum = max(value(k / 100) for k in range(2001))
    assert value(float(chosen["count"])) == pytest.approx(optimum, abs=1e-12)


@pytest.mark.parametrize("fixture_cost,expected", [(".63", "1.00"), (".70", None)])
def test_topup_minimum_and_cumulative_fixture_budget(fixture_cost, expected):
    _, api, _, _ = harness()
    account = {
        "held": fixture_cost,
        "fixture_leg": 2,
        "fixture_contracts": "1",
        "fixture_cost": fixture_cost,
    }
    config = Config.parse({**roomy().raw, "fixture_budget_usd": "1.26"})
    if expected is None:
        config = Config.parse({**config.raw, "fixture_budget_usd": "1.19"})
        with pytest.raises(ValueError, match="existing_position_covers_target"):
            plan_order(saved(), api.routes, config, Decimal(100), NOW, account)
    else:
        row = plan_order(saved(), api.routes, config, Decimal(100), NOW, account)
        assert row["request"]["count"] == expected
        assert Decimal(row["held"]) + Decimal(fixture_cost) <= config.number(
            "fixture_budget_usd"
        )
