"""Kelly objective, bankroll compounding and atomic funding boundaries."""

import copy
import itertools
import json
import math
from decimal import Decimal

import pytest
from test_execution import NOW, fill, harness, saved, settings

from prometheus.execution.core import Config, plan_order, reconcile
from prometheus.execution.ledger import _item
from prometheus.execution.sizing import kelly_order


def growth(n, p, c, capital):
    if capital - n * c <= 0:
        return -math.inf
    return p * math.log1p(n * (1 - c) / capital) + (1 - p) * math.log1p(
        -n * c / capital
    )


def test_integer_kelly_matches_exhaustive_feasible_log_growth():
    for p, c, capital, cap in itertools.product(
        (0.51, 0.6, 0.8, 0.99), (0.1, 0.5, 0.8), (1, 7, 50), (1, 10, 100)
    ):
        chosen = kelly_order(p, c, capital, cap)
        n = chosen["count"] if chosen else 0
        optimum = max(growth(k, p, c, capital) for k in range(cap + 1))
        assert growth(n, p, c, capital) == pytest.approx(optimum, abs=1e-12)


def test_fee_cost_bankroll_and_small_integer_edges():
    assert kelly_order(".6", ".5", 50, 100)["count"] == 20
    assert kelly_order(".6", ".5", 100, 100)["count"] == 40
    assert kelly_order(".6", ".52", 50, 100)["count"] == 16
    assert kelly_order(".51", ".5", 1, 100) is None
    assert kelly_order(".5", ".5", 50, 100) is None


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
    first_count = int(Decimal(api.calls[0]["count"]))
    fill(api, count=str(first_count), price=".59", fee=".15")
    api.settlement_rows = [
        {
            "ticker": api.orders[0]["ticker"],
            "yes_count_fp": str(first_count),
            "market_result": "yes",
            "revenue": first_count * 100,
        }
    ]
    execute([])
    earned = Decimal(first_count) * Decimal(".41") - Decimal(".15")
    assert ledger.get("demo", "ACCOUNT")["realized"] == earned
    execute([saved(probability=".70", fixture_id="next", event_ticker="NEXT")])
    second = json.loads(ledger.get("demo", "INTENT#next")["payload"])
    assert Decimal(second["sizing"]["bankroll_usd"]) == 50 + earned
    assert Decimal(second["request"]["count"]) > first_count
