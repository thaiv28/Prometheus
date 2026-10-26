"""Current fixture decisions, at most one IOC order. Money is Decimal, never float.

The ledger owns atomic fixture/event fences and spending reservations. An intent
that might have reached the exchange is never automatically submitted again.
"""

import copy
import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from prometheus import live_map, market_blend
from prometheus.alert_contract import CANDIDATE_KIND, TRADE_GROUPS, trade_veto
from prometheus.execution.sizing import QUANTITY_STEP, kelly_order

ZERO = Decimal(0)
CENT = Decimal(".01")
GROUPS = TRADE_GROUPS


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("non-finite decimal")
    return result


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return result.astimezone(dt.UTC)


@dataclass(frozen=True)
class Config:
    mode: str
    raw: dict

    @classmethod
    def parse(cls, value):
        value = copy.deepcopy(value)
        mode = value.get("mode", "off")
        if mode not in {"off", "demo", "live"}:
            raise ValueError("invalid execution mode")
        if mode != "off":
            timestamp(value["activation_at"])
            for name in (
                "max_alert_age_seconds",
                "max_quote_age_seconds",
                "max_price",
                "fee_rate_upper_bound",
                "order_budget_usd",
                "fixture_budget_usd",
                "daily_budget_usd",
                "max_exposure_usd",
                "max_contracts",
                "balance_precision_usd",
                "starting_bankroll_usd",
            ):
                if decimal(value[name]) <= 0:
                    raise ValueError(f"{name} must be positive")
            if decimal(value["min_balance_usd"]) < 0:
                raise ValueError("negative minimum balance")
            if not 0 < decimal(value["max_price"]) < 1:
                raise ValueError("max_price must be inside (0, 1)")
            if decimal(value["balance_precision_usd"]) not in {Decimal(".0001"), CENT}:
                raise ValueError("unsupported balance precision")
            if decimal(value["fee_rate_upper_bound"]) > 1:
                raise ValueError("fee upper bound must not exceed 1")
            if not 0 <= decimal(value["min_after_fee_edge"]) < 1:
                raise ValueError("invalid edge")
            if decimal(value["max_contracts"]) != int(value["max_contracts"]):
                raise ValueError("max_contracts must be an integer")
            if not 0 < decimal(value["kelly_fraction"]) <= 1:
                raise ValueError("kelly_fraction must be inside (0, 1]")
        # Emergency global OFF must remain writable even with malformed map settings.
        if mode == "off":
            return cls(mode, value)
        maps = value.get("live_maps") or {}
        if maps.get("mode", "off") not in {"off", "shadow", "live"}:
            raise ValueError("invalid_live_map_mode")
        if mode != "off" and maps.get("mode", "off") != "off":
            timestamp(maps["activation_at"])
            if not str(maps["queue_arn"]).startswith("arn:aws:sqs:"):
                raise ValueError("invalid_live_queue")
            for field, upper in (
                ("kelly_fraction", ".25"),
                ("map_fraction", ".01"),
                ("series_fraction", ".02"),
            ):
                if not 0 < decimal(maps[field]) <= decimal(upper):
                    raise ValueError("invalid_live_map_risk_limit")
            # The strategy's own money: it can never lose more than this.
            if decimal(maps["budget_usd"]) <= 0:
                raise ValueError("invalid_live_map_budget")
        return cls(mode, value)

    from_dict = parse

    def number(self, key):
        return decimal(self.raw[key])


def fee_bound(price, count, rate, precision):
    """Bound all 0.01-contract fragments, ignoring rounding rebates.

    Official fixed-point and fee-rounding guides: a fill may be as small as .01
    contracts, fee rounds to six dollar decimals, balances align to .0001 for
    Direct / .01 for non-Direct. At most 100*quantity fills on the 0.01 grid;
    allow one full precision increment and one microdollar per fragment. The
    accumulator's eventual rebates only improve on this conservative bound.
    """
    # A better execution price can be closer to .5 and carry a larger quadratic
    # fee. Bound the maximum on the entire allowed [0, limit] interval.
    fee_price = min(price, Decimal(".5"))
    per_contract = rate * fee_price * (1 - fee_price) + 100 * (
        precision + Decimal(".000001")
    )
    return per_contract.quantize(CENT, rounding=ROUND_CEILING) * count


def validate_alert(alert, config, now):
    if alert.get("kind") == live_map.VERSION:
        if alert.get("schema_version") != 1 or alert.get("group") != "live-map":
            raise ValueError("unsupported_live_alert")
        live_map.validate(alert, config, now.isoformat())
        if reason := trade_veto(alert):
            raise ValueError(reason)
        return
    if alert.get("schema_version") != 1 or alert.get("group") not in GROUPS:
        raise ValueError("unsupported_alert")
    for name in ("alert_id", "fixture_id", "event_ticker", "backed_team"):
        if not isinstance(alert.get(name), str) or not alert[name]:
            raise ValueError("missing_identity")
    teams = alert.get("teams")
    if (
        not isinstance(teams, list)
        or len(teams) != 2
        or len(set(teams)) != 2
        or alert["backed_team"] not in teams
    ):
        raise ValueError("ambiguous_teams")
    if reason := trade_veto(alert):
        raise ValueError(reason)
    is_candidate = alert.get("kind") == CANDIDATE_KIND
    if not is_candidate:
        when = timestamp(alert["alert_at"])
        if when < timestamp(config.raw["activation_at"]):
            raise ValueError("before_activation")
        age = (now - when).total_seconds()
        if age < 0 or age > config.number("max_alert_age_seconds"):
            raise ValueError("stale_alert")
    if timestamp(alert["start"]) <= now:
        raise ValueError("fixture_started")
    for name in ("probability",) if is_candidate else ("probability", "original_ask"):
        if not 0 < decimal(alert[name]) < 1:
            raise ValueError("invalid_probability_or_price")


def map_budget(config, row):
    """Live maps' remaining money: budget + their realized profit - their held."""
    row = row or {}
    held, realized = decimal(row.get("held", 0)), decimal(row.get("realized", 0))
    return {
        "map_held": held,
        "map_realized": realized,
        "map_budget_available": decimal(config.raw["live_maps"]["budget_usd"])
        + realized
        - held,
    }


def plan_order(
    alert, routes, config, balance, now, account=None, committed=ZERO, exposure=ZERO
):
    """Choose the feasible route/0.01-grid quantity with greatest log growth.

    No book walking/slippage: quantity must exist at the chosen limit. Route
    `price` is always the backed outcome's cost; YES-book `limit` is inverted
    for an ask (buying the opposite team's NO).
    """
    account = account or {}
    held, realized = (
        decimal(account.get("held", 0)),
        decimal(account.get("realized", 0)),
    )
    committed, exposure = decimal(committed), decimal(exposure)
    if held < 0 or committed < 0 or exposure < 0:
        raise ValueError("invalid_bankroll_state")
    capital = config.number("starting_bankroll_usd") + realized - held
    is_map = alert.get("kind") == live_map.VERSION
    fraction = (
        decimal(config.raw["live_maps"]["kelly_fraction"])
        if is_map
        else config.number("kelly_fraction")
    )
    effective = capital * fraction
    budget = min(
        config.number("order_budget_usd"),
        config.number("fixture_budget_usd"),
        balance - config.number("min_balance_usd") - held,
        config.number("max_exposure_usd") - exposure - held,
        config.number("daily_budget_usd") - committed,
        effective,
    )
    if is_map:
        # Free capital is conservative: existing commitments reduce the cap base.
        budget = min(
            budget,
            capital * decimal(config.raw["live_maps"]["map_fraction"]),
            decimal(account["series_available"]),
            decimal(account["map_budget_available"]),
        )
    if effective <= 0 or budget <= 0:
        raise ValueError("bankroll_or_spending_cap_exhausted")
    candidates = []
    for route in routes:
        age = (now - timestamp(route["at"])).total_seconds()
        age_limit = (
            min(config.number("max_quote_age_seconds"), Decimal(3))
            if is_map
            else config.number("max_quote_age_seconds")
        )
        if not 0 <= age <= age_limit:
            continue
        if not is_map and timestamp(route.get("first_start", alert["start"])) <= now:
            continue
        price = decimal(route["price"])
        price_cap = config.number("max_price")
        if alert.get("kind") != CANDIDATE_KIND:
            price_cap = min(price_cap, decimal(alert["original_ask"]))
        if not 0 < price <= price_cap:
            continue
        unit_fee = fee_bound(
            price,
            1,
            config.number("fee_rate_upper_bound"),
            config.number("balance_precision_usd"),
        )
        p = decimal(alert["probability"])
        if is_map:
            if (
                route.get("live_probability") is None
                or not 0
                <= (now - timestamp(route["live_checked_at"])).total_seconds()
                <= 3
            ):
                continue
            p = decimal(route["live_probability"])
        if alert.get("trading"):
            if route.get("market_mid") is None:
                continue
            p = decimal(market_blend.refresh(alert["trading"], route["market_mid"]))
        net_edge = p - price - unit_fee
        required_edge = (
            max(config.number("min_after_fee_edge"), Decimal(".05"))
            if is_map
            else config.number("min_after_fee_edge")
        )
        if net_edge <= ZERO or net_edge < required_edge:
            continue
        cap = min(
            config.number("max_contracts"),
            decimal(route["quantity"]),
            budget / (price + unit_fee),
        ).quantize(QUANTITY_STEP, rounding=ROUND_FLOOR)
        sizing = kelly_order(p, price + unit_fee, effective, cap)
        if sizing:
            candidates.append((price, route, sizing, unit_fee, p, net_edge))
    if not candidates:
        raise ValueError("price_edge_liquidity_or_balance")
    price, route, sizing, unit_fee, probability, net_edge = min(
        candidates,
        key=lambda x: (-decimal(x[2]["expected_log_growth"]), x[0], x[1]["ticker"]),
    )
    count = decimal(sizing["count"])
    client_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, f"prometheus:{config.mode}:{alert['fixture_id']}"
        )
    )
    return {
        "alert": copy.deepcopy(alert),
        "environment": config.mode,
        "series_id": alert["series_id"] if is_map else alert["event_ticker"],
        "series_key": (
            f"MAPSERIES#{alert['series_id']}"
            if is_map
            else f"SERIES#{alert['event_ticker']}"
        ),
        "client_order_id": client_id,
        "route": copy.deepcopy(route),
        "execution_probability": str(probability),
        "execution_net_edge": str(net_edge),
        "sizing": {
            "method": "kelly-v1",
            "starting_bankroll_usd": str(config.number("starting_bankroll_usd")),
            "kelly_fraction": str(fraction),
            "held_before": str(held),
            "realized_before": str(realized),
            "bankroll_usd": str(capital),
            "effective_bankroll_usd": str(effective),
            "unit_cost_bound": str(price + unit_fee),
            **(
                {
                    "map_held_before": str(account["map_held"]),
                    "map_realized_before": str(account["map_realized"]),
                }
                if is_map
                else {}
            ),
            **sizing,
        },
        "request": {
            "ticker": route["ticker"],
            "client_order_id": client_id,
            "side": route["side"],
            "count": f"{count:.2f}",
            "price": route["limit"],
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "cancel_order_on_pause": True,
            "post_only": False,
            "reduce_only": False,
        },
        "held": str((price + unit_fee) * count),
        "committed": str((price + unit_fee) * count),
        "created_at": now.isoformat(),
        "day": now.date().isoformat(),
        "status": "intent",
        "fills": [],
        "settlements": [],
    }


def reconcile(row, api, ledger, pause=False, notify=None):
    """Only release an uncertain reservation after exchange evidence is complete."""
    order = api.lookup(row["client_order_id"], row.get("order_id"))
    if order is None:
        return False  # Not found is NOT evidence a timed-out POST was rejected.
    if order.get("ticker") != row["request"]["ticker"]:
        raise ValueError("order_identity_mismatch")
    if order.get("book_side") != row["request"]["side"]:
        raise ValueError("order_direction_mismatch")
    if order.get("client_order_id") != row["client_order_id"]:
        raise ValueError("client_identity_mismatch")
    if order.get("status") == "resting":
        # IOC must not rest; cancel even when enabled. Never release on cancel ACK.
        api.cancel(order["order_id"], row["request"]["ticker"])
        order = api.lookup(row["client_order_id"], order["order_id"])
        if order is None or order.get("status") == "resting":
            return False
    expected = decimal(order["fill_count_fp"])
    fills = api.fills(order["order_id"], expected)
    total = sum((decimal(f["count_fp"]) for f in fills), ZERO)
    if expected < 0 or total < 0 or total > decimal(row["request"]["count"]):
        raise ValueError("invalid_fill_quantity")
    if total != expected:
        return False  # Eventual consistency; keep the full reservation.
    if len({f["fill_id"] for f in fills}) != len(fills):
        raise ValueError("duplicate_fill_ids")
    cost, fees = ZERO, ZERO
    for fill in fills:
        if (
            fill["order_id"] != order["order_id"]
            or fill.get("ticker", fill.get("market_ticker")) != row["request"]["ticker"]
        ):
            raise ValueError("fill_identity_mismatch")
        price_field = (
            "yes_price_dollars" if row["route"]["side"] == "bid" else "no_price_dollars"
        )
        price, count, fee = (
            decimal(fill[price_field]),
            decimal(fill["count_fp"]),
            decimal(fill["fee_cost"]),
        )
        if (
            fill.get("book_side") != row["request"]["side"]
            or count <= 0
            or count * 100 != int(count * 100)
            or fee < 0
            or not 0 < price <= decimal(row["route"]["price"])
        ):
            raise ValueError("invalid_or_over_limit_fill")
        cost += price * count
        fees += fee
    terminal = order.get("status") in {"canceled", "executed"}
    update = copy.deepcopy(row)
    update.update(
        order_id=order["order_id"],
        order=order,
        fills=fills,
        actual_cost=str(cost),
        actual_fees=str(fees),
    )
    if not terminal:
        update["status"] = "unknown"
        ledger.replace(row, update)
        return False
    update.update(
        status="filled" if total else "unfilled",
        held=str(cost + fees),
        committed=str(cost + fees),
    )
    if total:
        settlements = api.settlements(row["request"]["ticker"])
        verified = []
        for settlement in settlements:
            count_field = (
                "yes_count_fp" if row["route"]["side"] == "bid" else "no_count_fp"
            )
            if (
                settlement.get("ticker") != row["request"]["ticker"]
                or decimal(settlement[count_field]) < total
            ):
                continue
            outcome = settlement.get("market_result")
            if outcome in {"yes", "no"}:
                yes_value = Decimal(1) if outcome == "yes" else ZERO
            elif outcome == "scalar":
                market = settlement.get("finalized_market") or {}
                if (
                    market.get("ticker") != row["request"]["ticker"]
                    or market.get("status") != "finalized"
                    or market.get("result") != "scalar"
                    or not market.get("settlement_ts")
                ):
                    continue
                yes_value = decimal(market["settlement_value_dollars"])
                if not 0 <= yes_value <= 1:
                    continue
            else:
                continue
            value = yes_value if row["route"]["side"] == "bid" else 1 - yes_value
            # Scalar payouts round down to cents. A settled account record must
            # contain our entire quantity and at least its actual payout; netted
            # or ambiguous pooled positions retain their reservation for review.
            expected_revenue = (total * value).quantize(CENT, rounding=ROUND_FLOOR)
            if decimal(settlement["revenue"]) / 100 < expected_revenue:
                continue
            verified.append((settlement, expected_revenue))
        if verified:
            settlements = [s for s, _ in verified]
            # Keep exchange account settlement evidence. Do not attribute pooled
            # settlement revenue to this order if the account has other positions.
            update.update(
                status="settled",
                settlements=settlements,
                held="0",
                realized_profit=str(
                    min(revenue for _, revenue in verified) - cost - fees
                ),
            )
    stored = ledger.replace(row, update)
    if stored is not None and total > 0 and not row.get("notified") and notify:
        try:
            if notify(update):
                ledger.replace(
                    stored, {**update, "notified": dt.datetime.now(dt.UTC).isoformat()}
                )
        except Exception:
            pass  # Best effort; pending filled intents retry on reconciliation.
    return True


def prefilter(proposals, quotes, now, config, canonical):
    """Cheap two-sided quote screen; full resolution still verifies every order."""
    kept = []
    for proposal in proposals:
        if proposal.get("kind") != CANDIDATE_KIND:
            kept.append(proposal)
            continue
        try:
            markets = quotes.get(proposal["event_ticker"], [])
            if len(markets) != 2:
                continue
            sides = {}
            for market in markets:
                name = canonical(market["yes_sub_title"], proposal["teams"])
                bid, ask = decimal(market["yes_bid"]), decimal(market["yes_ask"])
                if (
                    name in sides
                    or not 0 < bid <= ask < 1
                    or ask - bid > Decimal(".10")
                ):
                    raise ValueError("invalid_quote")
                sides[name] = (bid, ask)
            if set(sides) != set(proposal["teams"]):
                continue
            own = sides[proposal["backed_team"]]
            other = sides[
                next(t for t in proposal["teams"] if t != proposal["backed_team"])
            ]
            mid = ((own[0] + own[1]) / 2 + 1 - (other[0] + other[1]) / 2) / 2
            cost = min(own[1], 1 - other[0])
            p = decimal(market_blend.refresh(proposal["trading"], mid))
            fee = fee_bound(
                cost,
                1,
                config.number("fee_rate_upper_bound"),
                config.number("balance_precision_usd"),
            )
            if cost <= config.number("max_price") and p - cost - fee > 0:
                kept.append(proposal)
        except (KeyError, TypeError, ValueError, AttributeError, ArithmeticError):
            continue
    return kept


def run(
    alerts,
    config_provider,
    ledger,
    api_factory,
    now=None,
    *,
    reconcile_existing=True,
    notify=None,
):
    """Run privately; return counters only, never credentials/account contents.

    `api_factory(environment)` loads that environment's own Secrets Manager key.
    Off still reconciles/cancels prior demo AND live intents; no prior intents
    means no API calls/credentials. No liquidation, resubmission or paper mode.
    """
    now = now or dt.datetime.now(dt.UTC)
    config = Config.parse(config_provider())
    result = {"submitted": 0, "skipped": 0, "reconciled": 0, "errors": 0, "filtered": 0}
    apis = {}

    def api_for(environment):
        if environment not in apis:
            apis[environment] = api_factory(environment)
        return apis[environment]

    for row in ledger.pending() if reconcile_existing else ():
        try:
            api = api_for(row["environment"])
            result["reconciled"] += int(
                reconcile(
                    row, api, ledger, config.mode != row["environment"], notify=notify
                )
            )
        except Exception:
            # Unknown status, missing credentials or cancellation failure retains
            # the durable reservation and is visible in the private intent.
            ledger.note_error(row, "reconciliation_failed", now)
            result["errors"] += 1
    if config.mode == "off":
        return result
    alerts = list(alerts)
    candidates = []
    for alert in alerts:
        if alert.get("kind") != CANDIDATE_KIND:
            continue
        try:
            validate_alert(alert, config, now)
            if ledger.seen(alert, config.mode):
                raise ValueError("duplicate_fixture_or_event")
            candidates.append(alert)
        except (ValueError, KeyError, TypeError, ArithmeticError):
            result["filtered"] += 1
    if candidates:
        try:
            api = api_for(config.mode)
            screened = prefilter(
                candidates, api.open_markets(), now, config, api.canonical
            )
        except Exception:
            result["errors"] += 1
            screened = []
        result["filtered"] += len(candidates) - len(screened)
        candidates = screened
    accepted = {id(alert) for alert in candidates}
    alerts = [
        alert
        for alert in alerts
        if alert.get("kind") != CANDIDATE_KIND or id(alert) in accepted
    ]
    for alert in alerts:
        reserved = None
        resolving = False
        try:
            validate_alert(alert, config, now)
            if (
                alert.get("kind") == live_map.VERSION
                and config.raw["live_maps"]["mode"] != "live"
            ):
                raise ValueError("live_maps_not_activated")
            if ledger.seen(alert, config.mode):
                raise ValueError("duplicate_fixture_or_event")
            api = api_for(config.mode)
            resolving = True
            routes = api.resolve(alert, now, config)
            balance = decimal(api.balance())
            exposure = decimal(api.exposure())
            if exposure < 0:
                raise ValueError("invalid_account_exposure")
            reserve_config = Config.parse(
                {
                    **config.raw,
                    "max_exposure_usd": str(
                        config.number("max_exposure_usd") - exposure
                    ),
                }
            )
            # Real time after network reads, injectable for deterministic tests.
            checked = api.now() if hasattr(api, "now") else dt.datetime.now(dt.UTC)
            validate_alert(alert, config, checked)
            account = ledger.get(config.mode, "ACCOUNT") or {}
            day = ledger.get(config.mode, f"DAY#{checked.date().isoformat()}") or {}
            if alert.get("kind") == live_map.VERSION:
                series = ledger.get(config.mode, f"MAPSERIES#{alert['series_id']}")
                series_cap = max(
                    ZERO,
                    config.number("starting_bankroll_usd")
                    + decimal(account.get("realized", 0))
                    - decimal(account.get("held", 0)),
                ) * decimal(config.raw["live_maps"]["series_fraction"])
                account = {
                    **account,
                    "series_available": series_cap
                    - decimal((series or {}).get("held", 0)),
                    **map_budget(config, ledger.get(config.mode, "LIVE_MAPS")),
                }
                reserve_config = Config.parse(
                    {**reserve_config.raw, "live_series_cap_usd": str(series_cap)}
                )
            plan = plan_order(
                alert,
                routes,
                config,
                balance,
                checked,
                account,
                day.get("committed", ZERO),
                exposure,
            )
            reserved = ledger.reserve(plan, reserve_config, balance)
            if reserved is None:
                raise ValueError("duplicate_or_spending_cap")
            current = Config.parse(config_provider())
            if current.raw != config.raw or current.mode != config.mode:
                ledger.abort(reserved, "configuration_changed")
                reserved = None
                raise ValueError("configuration_changed")
            # A CAS claim is the last durable step before the POST. Crashes from
            # here onward are reconciled, never blindly retried.
            reserved = ledger.claim(reserved)
            if reserved is None:
                raise ValueError("intent_already_claimed")
            # Recheck after the durable claim, immediately before the HTTP
            # request. A changed configuration aborts without touching orders.
            current = Config.parse(config_provider())
            checked = api.now() if hasattr(api, "now") else dt.datetime.now(dt.UTC)
            try:
                if current.raw != config.raw:
                    raise ValueError("configuration_changed")
                validate_alert(alert, current, checked)
                if checked.date().isoformat() != reserved["day"]:
                    raise ValueError("utc_spending_day_changed")
                plan_order(
                    alert,
                    [plan["route"]],
                    current,
                    balance,
                    checked,
                    account,
                    day.get("committed", ZERO),
                    exposure,
                )
            except (ValueError, KeyError, TypeError, ArithmeticError):
                ledger.abort(reserved, "pre_submission_check_failed")
                raise
            try:
                response = api.place(plan["request"])
                ledger.ack(reserved, response)
                result["submitted"] += 1
            except Exception:
                ledger.note_error(reserved, "submission_uncertain", checked)
                result["errors"] += 1
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            if resolving or alert.get("kind") == live_map.VERSION:
                ledger.skip(alert, config.mode, str(error), now)
            key = (
                "filtered"
                if not resolving and alert.get("kind") == CANDIDATE_KIND
                else "skipped"
            )
            result[key] += 1
        except Exception:
            if resolving or alert.get("kind") == live_map.VERSION:
                ledger.skip(alert, config.mode, "exchange_or_ledger_unavailable", now)
            result["errors"] += 1
    return result
