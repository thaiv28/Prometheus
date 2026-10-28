"""Live-map policy, delivery and execution failures; no live credentials/orders."""

import copy
import datetime as dt
import hashlib
import io
import json
import urllib.error
import urllib.parse
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_execution import NOW, AtomicDynamo, Exchange, settings
from test_execution_api import PublicClient, market
from test_execution_deploy import function_response
from test_execution_runner import Parameter

from deploy.execution import control, live_handler
from prometheus import live_map
from prometheus.execution.core import Config, fee_bound, run
from prometheus.execution.kalshi import PATH, Kalshi, PublicKalshi
from prometheus.execution.ledger import DynamoLedger, _decode, _item
from prometheus.live.signals import Outbox

QUEUE = "arn:aws:sqs:us-west-2:123456789012:signals"


def config(mode="demo", map_mode="live"):
    return settings(
        mode=mode,
        live_maps={
            "mode": map_mode,
            "activation_at": "2026-10-15T11:00:00Z",
            "queue_arn": QUEUE,
            "kelly_fraction": ".25",
            "map_fraction": ".01",
            "series_fraction": ".02",
        },
    )


def fee(price):
    return fee_bound(Decimal(str(price)), 1, Decimal(".07"), Decimal(".0001"))


def observation():
    objectives = {"towers": 0, "dragons": 0, "barons": 0, "inhibitors": 0, "kills": 0}
    return {
        "version": live_map.VERSION,
        "state": "live",
        "flat": False,
        "inputs": {
            "clock_seconds": 600,
            "blue_gold": 14000,
            "red_gold": 8000,
            "blue_elo": 1500,
            "red_elo": 1500,
            "objectives": [objectives.copy(), objectives.copy()],
            "momentum": 0.0,
        },
        "model_sha256": live_map.artifact()["model_sha256"],
        "blue": 0,
        "source_at": (NOW - dt.timedelta(seconds=21)).isoformat(),
        "received_at": NOW.isoformat(),
        "calculated_at": NOW.isoformat(),
        "start": "2026-10-15T11:49:00Z",
        "teams": ["A", "B"],
        "team_homes": {"A": "LCK", "B": "LCK"},
        "international": False,
        "rating_as_of": ["2026-10-14T10:00:00Z"] * 2,
        "map_number": 1,
        "event_ticker": "KXLOLMAP-F",
        "series_event_ticker": "KXLOLGAME-F",
    }


def trades():
    return [
        {
            "ticker": "MAP-A",
            "trade_id": str(i),
            "count_fp": "1.00",
            "taker_side": side,
            "created_time": (NOW - dt.timedelta(seconds=seconds)).isoformat(),
            "yes_price_dollars": ".50",
            "no_price_dollars": ".50",
        }
        for i, (seconds, side) in enumerate(((25, "yes"), (1, "no")))
    ]


def tape():
    return live_map.normalize_trades(trades(), {"MAP-A": 0, "MAP-B": 1})


def book():
    return {"at": NOW.isoformat(), "bid": ".48", "ask": ".50"}


def signal():
    return live_map.proposal(observation(), tape(), book(), NOW.isoformat(), fee)


def test_runtime_blend_reproduces_frozen_earlier_only_coefficients_and_symmetry():
    frozen = live_map.artifact()
    for row in frozen["snapshots"]:
        at = row["month"] + "-15T00:00:00Z"
        p, month = live_map.blend(0.8, 0.6, at)
        opposite, _ = live_map.blend(0.2, 0.4, at)
        assert month == row["month"]
        assert p + opposite == pytest.approx(1)
        assert live_map.timestamp(
            row["latest_training_available"]
        ) < live_map.timestamp(row["month"] + "-01T00:00:00Z")
    with pytest.raises(ValueError, match="no_earlier_only"):
        live_map.blend(0.8, 0.6, "2026-11-01T00:00:00Z")
    broken = copy.deepcopy(frozen)
    broken["snapshots"][-1]["latest_training_available"] = "2026-10-01T00:00:00Z"
    with pytest.raises(ValueError, match="no_earlier_only"):
        live_map.blend(0.8, 0.6, "2026-10-15T00:00:00Z", broken)


def test_normalization_deduplicates_orients_and_refuses_conflicts():
    raw = trades()
    assert len(live_map.normalize_trades(raw + raw, {"MAP-A": 0, "MAP-B": 1})) == 2
    flipped = live_map.normalize_trades(raw, {"MAP-A": 1, "MAP-B": 0})
    assert [r["back"] for r in flipped] == [1, 0]
    conflicting = copy.deepcopy(raw[0])
    conflicting["count_fp"] = "2.00"
    with pytest.raises(ValueError, match="conflicting_live_trade"):
        live_map.normalize_trades([raw[0], conflicting], {"MAP-A": 0, "MAP-B": 1})
    raw[0]["ticker"] = "FOREIGN"
    with pytest.raises(ValueError, match="foreign_live_trade"):
        live_map.normalize_trades(raw, {"MAP-A": 0, "MAP-B": 1})


def test_exact_thirty_second_window_uses_arrival_and_real_taker_trades():
    assert live_map.market_state(tape(), NOW.isoformat())[0] == 0.5
    old = copy.deepcopy(tape())
    old[0]["at"] = (NOW - dt.timedelta(seconds=30)).isoformat()
    with pytest.raises(ValueError, match="window_empty"):
        live_map.market_state(old, NOW.isoformat())
    moving = copy.deepcopy(tape())
    moving[0]["p0"] = 0.52
    moving[0]["cost"] = 0.52
    with pytest.raises(ValueError, match="price_moving"):
        live_map.market_state(moving, NOW.isoformat())
    stale = copy.deepcopy(tape())
    for row in stale:
        row["at"] = (NOW - dt.timedelta(seconds=11)).isoformat()
    with pytest.raises(ValueError, match="trade_stale"):
        live_map.market_state(stale, NOW.isoformat())


@pytest.mark.parametrize(
    "change",
    [
        lambda o: o.update(flat=True),
        lambda o: o.update(state="finished"),
        lambda o: o.update(source_at=(NOW - dt.timedelta(seconds=46)).isoformat()),
        lambda o: o.update(received_at=(NOW + dt.timedelta(seconds=1)).isoformat()),
        lambda o: o.update(
            calculated_at=(NOW - dt.timedelta(seconds=9)).isoformat(),
            received_at=(NOW - dt.timedelta(seconds=9)).isoformat(),
        ),
        lambda o: o["inputs"].update(clock_seconds=1900),
        lambda o: o["inputs"]["objectives"][0].update(towers=None),
        lambda o: o.update(model_sha256="wrong"),
        lambda o: o.update(rating_as_of=["2026-10-15T01:00:00Z"] * 2),
    ],
)
def test_bad_or_stale_model_input_fails_closed(change):
    o = observation()
    change(o)
    with pytest.raises((ValueError, KeyError, TypeError)):
        live_map.proposal(o, tape(), book(), NOW.isoformat(), fee)


def test_actual_ask_and_execution_fee_bound_gate_entry():
    selected = signal()
    assert selected["backed_team"] == "A"
    assert (
        live_map.validate(selected, Config.parse(config()), NOW.isoformat()) == selected
    )
    costly = book()
    costly["ask"] = ".99"
    with pytest.raises(ValueError, match="no_after_fee_edge"):
        live_map.proposal(observation(), tape(), costly, NOW.isoformat(), fee)
    with pytest.raises(ValueError, match="no_after_fee_edge"):
        live_map.proposal(observation(), tape(), book(), NOW.isoformat(), lambda _: 1)
    changed = copy.deepcopy(selected)
    changed["probability"] = ".99"
    with pytest.raises(ValueError, match="signal_mismatch"):
        live_map.validate(changed, Config.parse(config()), NOW.isoformat())
    with pytest.raises(ValueError, match="expired"):
        live_map.validate(
            selected,
            Config.parse(config()),
            (NOW + dt.timedelta(seconds=9)).isoformat(),
        )


class LiveExchange(Exchange):
    def __init__(self):
        super().__init__()
        self.routes[0].update(
            ticker="KXLOLMAP-F-A",
            price=".50",
            limit="0.5000",
            live_probability=str(signal()["probability"]),
            live_checked_at=NOW.isoformat(),
        )


def harness(settings_value=None):
    client, api = AtomicDynamo(), LiveExchange()
    ledger = DynamoLedger("private", client)
    value = settings_value or config()
    execute = lambda alerts: run(alerts, lambda: value, ledger, lambda _: api, now=NOW)
    return client, api, ledger, execute


def test_map_entry_is_capped_fenced_and_uncertain_response_never_reissued():
    _, api, ledger, execute = harness()
    api.timeout = True
    assert execute([signal()])["errors"] == 1
    account = ledger.get("demo", "ACCOUNT")
    assert Decimal("0") < account["held"] <= Decimal(".50")
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] == account["held"]
    api.invisible = True
    assert execute([signal()])["submitted"] == 0
    assert len(api.calls) == 1
    assert ledger.get("demo", "ACCOUNT")["held"] == account["held"]


@pytest.mark.parametrize("bo1", [False, True])
def test_map_reservation_ignores_pregame_event_and_series_exposure(bo1):
    from test_execution import saved

    from prometheus.execution.core import plan_order

    _, api, ledger, execute = harness()
    cfg = Config.parse(config())
    plan = plan_order(saved(), api.routes, cfg, Decimal(100), NOW)
    row = ledger.reserve(plan, cfg, Decimal(100))
    assert row is not None
    pregame = ledger.get("demo", "SERIES#KXLOLGAME-F")
    assert pregame["held"] > Decimal("1")
    assert ledger.get("demo", "EVENT#KXLOLGAME-F")
    candidate = bo1_signal() if bo1 else signal()
    assert execute([candidate])["submitted"] == 1
    assert len(api.calls) == 1
    assert ledger.get("demo", f"MAPEVENT#{candidate['event_ticker']}")
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] > 0
    assert ledger.get("demo", "SERIES#KXLOLGAME-F") == pregame


def test_map_event_fence_blocks_another_fixture_for_same_event():
    client, api, ledger, execute = harness()
    candidate = signal()
    assert execute([candidate])["submitted"] == 1
    o = observation()
    o["map_number"] = 2
    candidate = live_map.proposal(o, tape(), book(), NOW.isoformat(), fee)
    assert ledger.get("demo", f"FIXTURE#{candidate['fixture_id']}") is None
    assert ledger.seen(candidate, "demo")
    assert execute([candidate])["submitted"] == 0
    assert len(api.calls) == 1
    assert "duplicate_fixture_or_event" in [
        _decode(row).get("reason") for row in client.data.values()
    ]


def test_map_series_reservation_survives_race():
    from prometheus.execution.core import plan_order

    _, api, ledger, _ = harness()
    cfg = Config.parse(config())
    account = {"series_available": ".75"}
    first = plan_order(signal(), api.routes, cfg, Decimal(100), NOW, account)
    second = copy.deepcopy(first)
    second["alert"]["fixture_id"] = "second"
    second["alert"]["event_ticker"] = "KXLOLMAP-G"
    second["client_order_id"] = "second"
    # Refresh the account snapshot so only the series cap rejects it.
    amount = Decimal(first["held"])
    assert 2 * amount > Decimal(".75")
    second["sizing"]["held_before"] = str(amount)
    reserve = Config.parse({**cfg.raw, "live_series_cap_usd": ".75"})
    assert ledger.reserve(first, reserve, Decimal(100))
    assert ledger.reserve(second, reserve, Decimal(100)) is None
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] == amount


def test_second_map_is_sized_to_remaining_map_series_cap():
    _, api, ledger, execute = harness()
    api.invisible = True
    assert execute([signal()])["submitted"] == 1
    first = ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"]
    o = observation()
    o.update(map_number=2, event_ticker="KXLOLMAP-G")
    second = live_map.proposal(o, tape(), book(), NOW.isoformat(), fee)
    assert execute([second])["submitted"] == 1
    total = ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"]
    assert 0 < total - first < first
    assert total <= (Decimal(50) - first) * Decimal(".02")


def test_old_map_intent_without_series_key_releases_original_series_row():
    from prometheus.execution.core import plan_order

    _, api, ledger, _ = harness()
    cfg = Config.parse(config())
    account = {"series_available": "1"}
    plan = plan_order(signal(), api.routes, cfg, Decimal(100), NOW, account)
    del plan["series_key"]
    row = ledger.reserve(plan, cfg, Decimal(100))
    assert row is not None
    assert ledger.get("demo", "SERIES#KXLOLGAME-F")["held"] > 0
    ledger.abort(row, "configuration_changed")
    assert ledger.get("demo", "SERIES#KXLOLGAME-F")["held"] == 0
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F") is None


def test_map_pause_and_personal_vetoes_cannot_submit():
    for value in (
        config(map_mode="off"),
        config(map_mode="shadow"),
        config(mode="off"),
    ):
        _, api, _, execute = harness(value)
        assert execute([signal()])["submitted"] == 0
        assert not api.calls
    candidate = signal()
    candidate["teams"] = ["Cloud9", "B"]
    candidate["backed_team"] = "Cloud9"
    # Changing identities cannot be repaired from public names.
    _, api, _, execute = harness()
    assert execute([candidate])["submitted"] == 0
    assert not api.calls


class LivePublicClient(PublicClient):
    def __init__(self):
        super().__init__()
        self.parent = copy.deepcopy(self.event)

        def adjust(m, is_map):
            m["rules_primary"] = m["rules_primary"].replace(
                "Oct 16, 2026 at 8:00 AM EDT", "Oct 15, 2026 at 7:49 AM EDT"
            )
            if is_map:
                m["rules_primary"] = m["rules_primary"].replace(
                    "wins the", "wins game 1 in the"
                )
                m["ticker"] = m["ticker"].replace("KXLOLGAME", "KXLOLMAP")
                m["event_ticker"] = "KXLOLMAP-F"
            return m

        self.parent["markets"] = [adjust(m, False) for m in self.parent["markets"]]
        self.event.update(series_ticker="KXLOLMAP", event_ticker="KXLOLMAP-F")
        self.event["markets"] = [adjust(m, True) for m in self.event["markets"]]
        self.books = {
            "KXLOLMAP-F-A": {
                "yes_dollars": [[".48", "10"]],
                "no_dollars": [[".50", "10"]],
            },
            "KXLOLMAP-F-B": {
                "yes_dollars": [[".48", "10"]],
                "no_dollars": [[".50", "10"]],
            },
        }

    @staticmethod
    def now():
        return NOW

    def request(self, method, path, body=None, **query):
        if path == "/events/KXLOLGAME-F":
            return {"event": copy.deepcopy(self.parent)}
        if path == "/series/KXLOLMAP":
            return {"series": self.series}
        if path == "/markets/trades":
            raw = trades() if query["ticker"].endswith("-A") else []
            for row in raw:
                row["ticker"] = query["ticker"]
            return {
                "trades": raw,
                "cursor": "",
                "_received_at": NOW.isoformat(),
                "_server_time": NOW.isoformat(),
                "_cache_age": "0",
            }
        return super().request(method, path, body, **query)


def test_map_resolver_checks_both_maps_and_parent_series_and_refreshes_probability():
    api = LivePublicClient()
    routes = api.resolve(signal(), NOW, Config.parse(config()))
    assert len(routes) == 2
    assert all(Decimal(r["live_probability"]) > Decimal(".55") for r in routes)
    api.parent["markets"][0]["rules_primary"] = market("A")["rules_primary"]
    with pytest.raises(ValueError, match="series_identity"):
        api.resolve(signal(), NOW, Config.parse(config()))
    api = LivePublicClient()
    api.event["markets"][0]["rules_primary"] = api.event["markets"][0][
        "rules_primary"
    ].replace("game 1", "game 2")
    with pytest.raises(ValueError):
        api.resolve(signal(), NOW, Config.parse(config()))


def test_shadow_transport_refuses_all_private_or_write_endpoints():
    api = PublicKalshi()
    for method, path in (
        ("POST", "/portfolio/orders"),
        ("GET", "/portfolio/balance"),
        ("DELETE", "/markets/X"),
    ):
        with pytest.raises(ValueError, match="shadow_private"):
            api.headers(method, path)


def test_outbox_persists_before_queueing_and_reuses_immutable_bytes(tmp_path):
    calls = []
    path = tmp_path / "signal.json"
    path.write_bytes(live_map.canonical(signal()))
    box = Outbox(
        SimpleNamespace(put_object=lambda **kw: calls.append(("s3", kw))),
        SimpleNamespace(send_message=lambda **kw: calls.append(("sqs", kw))),
        "private",
        "queue",
    )
    box.deliver(path, signal())
    assert [kind for kind, _ in calls] == ["s3", "sqs"]
    pointer = json.loads(calls[1][1]["MessageBody"])
    assert pointer["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert calls[0][1]["IfNoneMatch"] == "*"
    box = Outbox(
        SimpleNamespace(put_object=lambda **_: (_ for _ in ()).throw(OSError())),
        SimpleNamespace(
            send_message=lambda **_: pytest.fail("queue before persistence")
        ),
        "private",
        "queue",
    )
    with pytest.raises(OSError):
        box.deliver(path, signal())


@pytest.mark.parametrize("position", ["none", "covered", "series_cap"])
def test_queue_shadow_path_does_not_load_credentials_or_call_orders(
    monkeypatch, position
):
    content = live_map.canonical(signal())
    digest = hashlib.sha256(content).hexdigest()
    pointer = {"key": live_map.PREFIX + digest + ".json", "sha256": digest}
    record = {
        "messageId": "one",
        "eventSource": "aws:sqs",
        "eventSourceARN": QUEUE,
        "body": json.dumps(pointer),
    }
    db = AtomicDynamo()
    parameter = Parameter(config(map_mode="shadow"))
    if position == "covered":
        db.put_item(
            Item=_item(
                {
                    "pk": "ENV#demo",
                    "sk": "ACTIVE#pregame",
                    "intent_key": "INTENT#pregame",
                }
            )
        )
        db.put_item(
            Item=_item(
                {
                    "pk": "ENV#demo",
                    "sk": "INTENT#pregame",
                    "revision": 0,
                    "payload": json.dumps(
                        {
                            "status": "filled",
                            "series_id": "KXLOLGAME-F",
                            "alert": {"backed_team": "A"},
                            "order": {"fill_count_fp": "4.60"},
                        }
                    ),
                }
            )
        )
    elif position == "series_cap":
        parameter.value["series_fraction"] = ".10"
        for sk, held in (
            ("ACCOUNT", "5"),
            ("SERIES#KXLOLGAME-F", "3.9"),
            ("MAPSERIES#KXLOLGAME-F", ".5"),
        ):
            db.put_item(Item=_item({"pk": "ENV#demo", "sk": sk, "held": Decimal(held)}))
    monkeypatch.setenv("EXECUTION_CONFIG_PARAMETER", "/config")
    monkeypatch.setenv("EXECUTION_TABLE", "private")
    monkeypatch.setenv("PREDICTIONS_BUCKET", "private")

    class Frozen:
        @staticmethod
        def now(*_):
            return NOW

    monkeypatch.setattr(
        live_handler, "dt", SimpleNamespace(datetime=Frozen, UTC=dt.UTC)
    )
    monkeypatch.setattr(live_handler, "PublicKalshi", lambda _: LivePublicClient())
    aws = {
        "ssm": parameter,
        "s3": SimpleNamespace(get_object=lambda **_: {"Body": io.BytesIO(content)}),
        "dynamodb": db,
        "secretsmanager": SimpleNamespace(
            get_secret_value=lambda **_: pytest.fail("shadow credentials")
        ),
    }
    assert live_handler.handle({"Records": [record]}, aws, {}) == {
        "batchItemFailures": []
    }
    row = DynamoLedger("private", db).get("shadow", "MAP#KXLOLMAP-F")
    if position == "covered":
        assert row is None
        assert "existing_position_covers_target" in [
            _decode(v).get("reason") for v in db.data.values()
        ]
    else:
        payload = json.loads(row["payload"])
        assert "proposed IOC" in payload["assumption"]
        if position == "series_cap":
            assert 0 < Decimal(payload["plan"]["held"]) <= Decimal(".10")
        else:
            assert DynamoLedger("private", db).get("demo", "ACCOUNT") is None
    record["eventSourceARN"] = "foreign"
    assert live_handler.handle({"Records": [record]}, aws, {}) == {
        "batchItemFailures": []
    }
    parameter.value["live_maps"]["mode"] = "off"
    aws["s3"] = SimpleNamespace(get_object=lambda **_: pytest.fail("off source read"))
    assert live_handler.handle({"Records": [record]}, aws, {}) == {
        "batchItemFailures": []
    }


def test_separate_live_map_activation_requires_verified_runtime_and_explicit_limits():
    parameter = Parameter(config(mode="off", map_mode="off"))
    functions = SimpleNamespace(get_function=lambda **_: function_response())
    with pytest.raises(ValueError, match="Global execution"):
        control.set_live_map_mode(
            parameter, "/config", "live", functions=functions, function="runner"
        )
    assert not parameter.writes
    control.set_live_map_mode(
        parameter, "/config", "shadow", functions=functions, function="runner", now=NOW
    )
    assert (
        parameter.value["mode"] == "off"
        and parameter.value["live_maps"]["mode"] == "shadow"
    )
    control.set_live_map_mode(parameter, "/config", "off", now=NOW)
    assert parameter.value["live_maps"]["mode"] == "off"
    with pytest.raises(ValueError):
        control.configure(parameter, "/config", {"live_maps": {"mode": "live"}})
    for field, value in (
        ("kelly_fraction", "1.01"),
        ("map_fraction", ".051"),
        ("series_fraction", ".11"),
    ):
        bad = config()
        bad["live_maps"][field] = value
        with pytest.raises(ValueError, match="risk_limit"):
            Config.parse(bad)
    widest = config()
    widest["live_maps"].update(
        kelly_fraction="1", map_fraction=".05", series_fraction=".10"
    )
    assert Config.parse(widest)
    for budget in ("0", "invalid", None):
        value = config()
        value["live_maps"]["budget_usd"] = budget
        assert Config.parse(value)
    assert Config.parse(config())  # No strategy budget required.


def test_old_map_budget_does_not_limit_new_reservations():
    client, _, ledger, execute = harness()
    client.put_item(
        Item=_item({"pk": "ENV#demo", "sk": "LIVE_MAPS", "realized": Decimal("-15")})
    )
    assert execute([signal()])["submitted"] == 1
    assert ledger.get("demo", "LIVE_MAPS") == {
        "pk": "ENV#demo",
        "sk": "LIVE_MAPS",
        "realized": Decimal("-15"),
    }
    row = ledger.pending()[0]
    assert "map_held_before" not in row["sizing"]
    assert "map_realized_before" not in row["sizing"]


def test_legacy_map_budget_still_releases_and_realizes_profit():
    from prometheus.execution.core import plan_order

    client, api, ledger, _ = harness()
    cfg = Config.parse(config())
    plan = plan_order(
        signal(), api.routes, cfg, Decimal(100), NOW, {"series_available": "1"}
    )
    plan["sizing"].update(map_held_before="0", map_realized_before="0")
    row = ledger.reserve(plan, cfg, Decimal(100))
    assert ledger.get("demo", "LIVE_MAPS") is None
    # Old reservations already wrote this row before the budget was retired.
    client.put_item(
        Item=_item({"pk": "ENV#demo", "sk": "LIVE_MAPS", "held": Decimal(row["held"])})
    )
    ledger.replace(
        row,
        {
            **row,
            "status": "settled",
            "held": "0",
            "committed": ".25",
            "realized_profit": ".75",
        },
    )
    maps = ledger.get("demo", "LIVE_MAPS")
    assert maps["held"] == 0 and maps["realized"] == Decimal(".75")


def test_transport_template_is_disabled_and_has_no_credentials_or_public_writes():
    root = Path(__file__).resolve().parents[1]
    template = json.loads(
        (root / "deploy/execution/live-map-transport.json").read_text()
    )
    assert template["Parameters"]["QueueConsumerEnabled"]["Default"] == "false"
    mapping = template["Resources"]["Consumer"]["Properties"]
    assert mapping["BatchSize"] == 1 and mapping["MaximumBatchingWindowInSeconds"] == 0
    assert mapping["FunctionResponseTypes"] == ["ReportBatchItemFailures"]
    assert "secretsmanager" not in json.dumps(template)
    assert "AWS::Lambda::Function" not in json.dumps(template)
    assert "s3:DeleteObject" not in json.dumps(template)


def test_map_partial_fill_settlement_releases_map_series_once():
    _, api, ledger, execute = harness()
    execute([signal()])
    api.orders[0].update(fill_count_fp=".50", status="canceled")
    api.fill_rows = [
        {
            "fill_id": "fill",
            "order_id": "o",
            "ticker": "KXLOLMAP-F-A",
            "count_fp": ".50",
            "yes_price_dollars": ".50",
            "no_price_dollars": ".50",
            "fee_cost": ".01",
            "book_side": "bid",
        }
    ]
    assert execute([])["reconciled"] == 1
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] == Decimal(".26")
    assert ledger.held_contracts("demo", "KXLOLGAME-F", "A") == Decimal(".50")
    api.settlement_rows = [
        {
            "ticker": "KXLOLMAP-F-A",
            "market_result": "yes",
            "yes_count_fp": ".50",
            "no_count_fp": "0",
            "revenue": 50,
        }
    ]
    assert execute([])["reconciled"] == 1
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] == 0
    assert ledger.get("demo", "ACCOUNT")["realized"] == Decimal(".24")
    assert ledger.held_contracts("demo", "KXLOLGAME-F", "A") == 0
    assert ledger.get("demo", "LIVE_MAPS") is None
    execute([])
    assert ledger.get("demo", "ACCOUNT")["realized"] == Decimal(".24")
    execute([signal()])
    assert len(api.calls) == 1


def test_map_freshness_and_pause_rechecked_after_claim():
    _, api, ledger, execute = harness()
    original = ledger.claim

    def claim(row):
        claimed = original(row)
        api.now = lambda: NOW + dt.timedelta(seconds=9)
        return claimed

    ledger.claim = claim
    assert execute([signal()])["submitted"] == 0
    assert not api.calls and not ledger.pending()
    assert ledger.get("demo", "ACCOUNT")["held"] == 0
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] == 0


def test_valid_personal_vetoes_are_preserved_for_map_strategy():
    for cloud9 in (True, False):
        o = observation()
        if cloud9:
            o["teams"] = ["Cloud9", "B"]
            o["team_homes"] = {"Cloud9": "LCS", "B": "LCK"}
        else:
            o["team_homes"] = {"A": "LCK", "B": "LCS"}
        o["international"] = True
        alert = live_map.proposal(o, tape(), book(), NOW.isoformat(), fee)
        client, api, _, execute = harness()
        assert execute([alert])["submitted"] == 0 and not api.calls
        reasons = [_decode(v).get("reason") for v in client.data.values()]
        assert (
            "cloud9_fixture" if cloud9 else "against_north_america_international"
        ) in reasons


def test_duplicate_or_unsorted_stored_trade_evidence_is_rejected():
    for rows in (tape() + tape(), list(reversed(tape()))):
        with pytest.raises(ValueError, match="duplicate_or_unordered"):
            live_map.market_state(rows, NOW.isoformat())


def test_private_worker_observation_keeps_unshifted_model_and_exact_input_parity():
    from prometheus.live.signals import observation as collect
    from prometheus.live.timeline import MODEL_PATH, predict

    model = json.loads(MODEL_PATH.read_text())

    def frame(seconds, gold):
        stamp = (NOW - dt.timedelta(seconds=621 - seconds)).isoformat()
        return {
            "at": NOW.isoformat(),
            "actual_received_at": NOW.isoformat(),
            "source_at": stamp,
            "teams": [
                {**observation()["inputs"]["objectives"][0], "gold": gold},
                {
                    **observation()["inputs"]["objectives"][1],
                    "gold": gold - 1000 if seconds else gold,
                },
            ],
        }

    frames = [frame(0, 2500), frame(300, 8000), frame(590, 12000), frame(600, 13000)]
    game = SimpleNamespace(
        timeline=(model, [{"elo": 1500, "as_of": "2026-10-14 00:00:00"}] * 2),
        start={"source_at": frames[0]["source_at"]},
        forge={"homes": ["LCK", "LCK"]},
        mapping={
            "teams": [{"name": "A"}, {"name": "B"}],
            "league": "LCK",
            "best_of": 3,
        },
        start_time=observation()["start"],
        number=1,
        signal_event="KXLOLMAP-F",
        signal_series="KXLOLGAME-F",
    )
    page = {"status": "live", "game": {"blue": 0, "frames": frames}}
    o = collect(game, page, NOW.isoformat())
    assert o["best_of"] == 3
    assert o["inputs"]["momentum"] == 0
    assert live_map.raw_probability(o) == pytest.approx(predict(model, **o["inputs"]))
    assert page["game"]["frames"][-1]["clock_estimate"] == 600
    # Many source frames share one receipt; receipt equality cannot identify
    # which frame the last successful model call used.
    bad = copy.deepcopy(page)
    bad["game"]["frames"][-1]["teams"][0]["gold"] = None
    with pytest.raises(ValueError, match="latest_frame_not_modeled"):
        collect(game, bad, NOW.isoformat())


def test_worker_records_first_candidate_then_only_retries_same_bytes(
    tmp_path, monkeypatch
):
    from prometheus.live import signals

    class Frozen:
        @staticmethod
        def now(*_):
            return NOW

    monkeypatch.setattr(signals, "datetime", Frozen)
    game = SimpleNamespace(
        id="g",
        number=1,
        mapping={"match_id": "m"},
        dir=tmp_path,
        signal_event="KXLOLMAP-F",
        signal_tickers={"MAP-A": 0, "MAP-B": 1},
        latest_signal_book=book(),
        request_dir=lambda _: tmp_path,
    )
    calls = []

    def fetch(url, path):
        calls.append(url)
        return {}, {"trades": trades() if "MAP-A" in url else [], "cursor": ""}

    delivered = []
    observer = signals.Signals(
        fetch,
        SimpleNamespace(
            deliver=lambda path, candidate: delivered.append(path.read_bytes())
        ),
    )
    observer.observations[game.id] = observation()
    observer.poll(game, {})
    assert len(calls) == 2 and len(delivered) == 1
    observer.poll(game, {})
    assert len(calls) == 2 and len(delivered) == 1
    # Restart retains the per-map candidate/delivered files.
    signals.Signals(
        lambda *_: pytest.fail("restart should not reselect"), observer.outbox
    ).poll(game, {})
    assert len(delivered) == 1


@pytest.mark.parametrize("wrong_kind", [False, True])
def test_queue_live_path_cannot_execute_non_map_payload_or_duplicate_unknown_order(
    monkeypatch, wrong_kind
):
    from test_execution import saved

    candidate = saved() if wrong_kind else signal()
    content = live_map.canonical(candidate)
    digest = hashlib.sha256(content).hexdigest()
    record = {
        "messageId": "one",
        "eventSource": "aws:sqs",
        "eventSourceARN": QUEUE,
        "body": json.dumps(
            {"key": live_map.PREFIX + digest + ".json", "sha256": digest}
        ),
    }
    db = AtomicDynamo()
    api = LiveExchange()
    api.timeout = True
    parameter = Parameter(config())
    for key, value in {
        "EXECUTION_CONFIG_PARAMETER": "/config",
        "EXECUTION_TABLE": "private",
        "PREDICTIONS_BUCKET": "private",
        "DEMO_SECRET_ARN": "demo-secret",
    }.items():
        monkeypatch.setenv(key, value)

    class Frozen:
        @staticmethod
        def now(*_):
            return NOW

    monkeypatch.setattr(
        live_handler, "dt", SimpleNamespace(datetime=Frozen, UTC=dt.UTC)
    )
    monkeypatch.setattr(live_handler, "Kalshi", lambda *_args, **_kw: api)
    secrets = []

    def secret(**kw):
        secrets.append(kw)
        return {
            "SecretString": json.dumps({"key_id": "test", "private_key_pem": "test"})
        }

    aws = {
        "ssm": parameter,
        "s3": SimpleNamespace(get_object=lambda **_: {"Body": io.BytesIO(content)}),
        "dynamodb": db,
        "secretsmanager": SimpleNamespace(get_secret_value=secret),
    }
    first = live_handler.handle({"Records": [record]}, aws, {})
    if wrong_kind:
        assert first == {"batchItemFailures": []}
        assert not secrets and not api.calls
    else:
        assert first == {"batchItemFailures": [{"itemIdentifier": "one"}]}
        assert len(secrets) == len(api.calls) == 1
        ledger = DynamoLedger("private", db)
        reserved = ledger.get("demo", "ACCOUNT")["held"]
        assert live_handler.handle({"Records": [record]}, aws, {}) == {
            "batchItemFailures": []
        }
        assert ledger.get("demo", "ACCOUNT")["held"] == reserved
        assert len(secrets) == len(api.calls) == 1


def test_physical_map_fence_survives_exchange_event_relisting():
    _, api, _, execute = harness()
    first = signal()
    o = observation()
    o["event_ticker"] = "KXLOLMAP-RELISTED"
    o["start"] = "2026-10-15T11:49:00+00:00"
    relisted = live_map.proposal(o, tape(), book(), NOW.isoformat(), fee)
    assert relisted["fixture_id"] == first["fixture_id"]
    api.invisible = True
    execute([first])
    execute([relisted])
    assert len(api.calls) == 1


@pytest.mark.parametrize("broken", [{"mode": "invalid"}, "invalid", ["invalid"]])
def test_emergency_off_controls_survive_malformed_live_map_configuration(broken):
    parameter = Parameter(config())
    parameter.value["live_maps"] = broken
    control.set_mode(parameter, "/config", "off", now=NOW)
    assert parameter.value["mode"] == "off"
    assert Config.parse(parameter.value).mode == "off"
    control.set_live_map_mode(parameter, "/config", "off", now=NOW)
    assert parameter.value["live_maps"]["mode"] == "off"


def bo1_signal(best_of=1, map_number=1):
    o = observation()
    o.update(best_of=best_of, map_number=map_number, event_ticker="KXLOLGAME-F")
    return live_map.proposal(o, tape(), book(), NOW.isoformat(), fee)


class Bo1PublicClient(LivePublicClient):
    probe_error = "exchange_not_found"

    def __init__(self):
        super().__init__()
        self.books = {
            k.replace("KXLOLMAP", "KXLOLGAME"): v for k, v in self.books.items()
        }
        self.bo1_calls = []

    def request(self, method, path, body=None, **query):
        self.bo1_calls.append(path)
        if path == "/events/KXLOLMAP-F-1":
            if self.probe_error is None:
                return {"event": {"event_ticker": "KXLOLMAP-F-1"}}
            if self.probe_error == "exchange_not_found":
                raise LookupError(self.probe_error)
            raise RuntimeError(self.probe_error)
        return super().request(method, path, body, **query)


@pytest.mark.parametrize("covers_target", [False, True])
def test_live_map_end_to_end_through_queue_with_pregame_position(
    monkeypatch, tmp_path, capsys, covers_target
):
    from test_execution import saved

    from prometheus.execution.core import plan_order

    candidate = bo1_signal()
    path = tmp_path / "signal.json"
    path.write_bytes(live_map.canonical(candidate))
    uploads, messages = [], []
    Outbox(
        SimpleNamespace(put_object=lambda **kw: uploads.append(kw)),
        SimpleNamespace(send_message=lambda **kw: messages.append(kw)),
        "private",
        "queue",
    ).deliver(path, candidate)
    assert len(uploads) == len(messages) == 1
    record = {
        "messageId": "one",
        "eventSource": "aws:sqs",
        "eventSourceARN": config()["live_maps"]["queue_arn"],
        "body": messages[0]["MessageBody"],
    }

    db = AtomicDynamo()
    ledger = DynamoLedger("private", db)
    cfg = Config.parse(config())
    pregame_plan = plan_order(saved(), Exchange().routes, cfg, Decimal(60), NOW)
    pregame_row = ledger.reserve(pregame_plan, cfg, Decimal(60))
    assert pregame_row is not None
    ledger.replace(
        pregame_row,
        {
            **pregame_row,
            "status": "filled",
            "order": {"fill_count_fp": "4.60" if covers_target else "0.10"},
        },
    )
    pregame = ledger.get("demo", "SERIES#KXLOLGAME-F")
    capital = (
        cfg.number("starting_bankroll_usd") - ledger.get("demo", "ACCOUNT")["held"]
    )
    assert pregame["held"] > capital * Decimal(cfg.raw["live_maps"]["series_fraction"])
    assert ledger.get("demo", "EVENT#KXLOLGAME-F")

    public = Bo1PublicClient()
    posts = []
    orders = {}
    backed_ticker = f"KXLOLGAME-F-{candidate['backed_team']}"

    def http_open(request, timeout):
        assert timeout == 10
        url = urllib.parse.urlsplit(request.full_url)
        endpoint = url.path.removeprefix(PATH)
        query = dict(urllib.parse.parse_qsl(url.query))
        body = json.loads(request.data) if request.data else None
        if endpoint == "/portfolio/balance":
            result = {"balance_dollars": "60"}
        elif endpoint == "/portfolio/positions":
            result = {
                "market_positions": [
                    {
                        "ticker": backed_ticker,
                        "market_exposure_dollars": str(pregame["held"]),
                    },
                    {"ticker": "unrelated", "market_exposure_dollars": "-1.20"},
                ]
            }
        elif endpoint == "/portfolio/events/orders" and request.method == "POST":
            posts.append(body)
            order = {
                **body,
                "order_id": "filled-map",
                "status": "executed",
                "book_side": body["side"],
                "fill_count_fp": body["count"],
                "remaining_count_fp": "0.00",
            }
            orders[order["order_id"]] = order
            result = {**order, "fill_count": body["count"], "remaining_count": "0.00"}
        elif endpoint == "/portfolio/orders":
            result = {
                "orders": []
                if query.get("status") == "resting"
                else list(orders.values())
            }
        elif endpoint.startswith("/portfolio/orders/"):
            result = {"order": orders[endpoint.rsplit("/", 1)[1]]}
        else:
            try:
                result = public.request(request.method, endpoint, body, **query)
            except LookupError:
                raise urllib.error.HTTPError(
                    request.full_url, 404, "missing", {}, None
                ) from None
        response = io.BytesIO(json.dumps(result).encode())
        response.headers = {"Date": "Thu, 15 Oct 2026 12:00:00 GMT"}
        return response

    class Client(Bo1PublicClient):
        request = Kalshi.request

        def __init__(self, environment, *_args, canonical_aliases=None):
            super().__init__()
            self.environment = environment
            self.aliases = canonical_aliases or {}
            self.opener = SimpleNamespace(open=http_open)

        def headers(self, method, path):
            return {}

    class Frozen:
        @staticmethod
        def now(*_):
            return NOW

    for key, value in {
        "EXECUTION_CONFIG_PARAMETER": "/config",
        "EXECUTION_TABLE": "private",
        "PREDICTIONS_BUCKET": "private",
        "DEMO_SECRET_ARN": "demo-secret",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        live_handler, "dt", SimpleNamespace(datetime=Frozen, UTC=dt.UTC)
    )
    monkeypatch.setattr(live_handler, "Kalshi", Client)

    def get_object(**kw):
        assert kw == {"Bucket": uploads[0]["Bucket"], "Key": uploads[0]["Key"]}
        return {"Body": io.BytesIO(uploads[0]["Body"])}

    aws = {
        "ssm": Parameter(config()),
        "s3": SimpleNamespace(get_object=get_object),
        "dynamodb": db,
        "secretsmanager": SimpleNamespace(
            get_secret_value=lambda **_: {
                "SecretString": json.dumps(
                    {"key_id": "test", "private_key_pem": "test"}
                )
            }
        ),
    }
    assert live_handler.handle({"Records": [record]}, aws, {}) == {
        "batchItemFailures": []
    }
    skips = [_decode(row) for (_, sk), row in db.data.items() if sk.startswith("SKIP#")]
    if covers_target:
        assert [row["reason"] for row in skips] == ["existing_position_covers_target"]
        assert not posts
        assert ledger.get("demo", "MAPEVENT#KXLOLGAME-F") is None
        return
    assert not skips, skips
    logged = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert logged["event"] == "live_map" and logged["outcome"] == "run"
    assert logged["result"]["submitted"] == 1 and logged["reason"] is None
    assert len(posts) == 1
    assert posts[0]["ticker"] == backed_ticker
    assert ledger.get("demo", "MAPEVENT#KXLOLGAME-F")
    assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F")["held"] > 0
    assert ledger.get("demo", "SERIES#KXLOLGAME-F") == pregame
    assert live_handler.handle({"Records": [record]}, aws, {}) == {
        "batchItemFailures": []
    }
    assert len(posts) == 1


def test_bo1_validates_and_resolves_series_markets_with_one_parent_read():
    candidate = bo1_signal()
    cfg = Config.parse(config())
    assert live_map.canonical(
        live_map.validate(candidate, cfg, NOW.isoformat())
    ) == live_map.canonical(candidate)
    api = Bo1PublicClient()
    routes = api.resolve(candidate, NOW, cfg)
    assert len(routes) == 2
    assert all(Decimal(r["live_probability"]) > Decimal(".55") for r in routes)
    assert api.bo1_calls.count("/events/KXLOLGAME-F") == 1
    assert "/series/KXLOLGAME" in api.bo1_calls
    assert "/events/KXLOLMAP-F-1" in api.bo1_calls


@pytest.mark.parametrize("best_of,number", [(3, 1), (1, 2)])
def test_bo1_identity_rejects_longer_series_or_second_map(best_of, number):
    candidate = bo1_signal(best_of, number)
    with pytest.raises(ValueError, match="invalid_live_market_identity"):
        live_map.validate(candidate, Config.parse(config()), NOW.isoformat())
    with pytest.raises(ValueError, match="invalid_live_market_identity"):
        Bo1PublicClient().resolve(candidate, NOW, Config.parse(config()))


@pytest.mark.parametrize(
    "error,reason",
    [
        (None, "live_bo1_map_market_exists"),
        ("exchange_http_500", "live_bo1_unverified"),
        ("exchange_transport_uncertain", "live_bo1_unverified"),
    ],
)
def test_bo1_probe_fails_closed_before_books(error, reason):
    api = Bo1PublicClient()
    api.probe_error = error
    with pytest.raises(ValueError, match=reason):
        api.resolve(bo1_signal(), NOW, Config.parse(config()))
    assert not any(path.endswith("/orderbook") for path in api.bo1_calls)


def worker_game(tmp_path, best_of=1):
    return SimpleNamespace(
        id="g",
        dir=tmp_path,
        ticker=None,
        series_ticker="KXLOLGAME-F-A",
        number=1,
        mapping={
            "match_id": "m",
            "best_of": best_of,
            "teams": [{"name": "A"}, {"name": "B"}],
        },
    )


def test_worker_discovers_bo1_but_not_deciding_map(tmp_path):
    from prometheus.live.signals import Signals

    markets = Bo1PublicClient().parent["markets"]
    game = worker_game(tmp_path)
    Signals.discover(game, markets)
    assert game.signal_event == game.signal_series == "KXLOLGAME-F"
    assert game.signal_tickers == {"KXLOLGAME-F-A": 0, "KXLOLGAME-F-B": 1}
    assert game.signal_skip is None
    game.mapping["best_of"] = 3
    Signals.discover(game, markets)
    assert game.signal_event is None
    assert game.signal_skip == "no_map_market"


@pytest.mark.parametrize("reason", ["no_map_market", None])
def test_worker_journals_unarmed_reason_once(tmp_path, reason):
    from prometheus.live.signals import Signals

    game = worker_game(tmp_path)
    game.signal_skip = reason
    observer = Signals(lambda *_: pytest.fail("unarmed game must not fetch"))
    observer.poll(game, {}, fresh_model=True)
    observer.poll(game, {}, fresh_model=True)
    rows = [
        json.loads(line)
        for line in (tmp_path / "trading/decisions.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 1
    assert (rows[0]["match"], rows[0]["game"], rows[0]["map"]) == (
        game.mapping["match_id"],
        game.id,
        game.number,
    )
    assert rows[0]["reason"] == "signal_markets_unavailable:" + (
        reason or "not_discovered"
    )


@pytest.mark.parametrize(
    "best_of,has_map,expected", [(1, False, True), (3, False, False), (1, True, False)]
)
def test_bo1_series_quote_supplies_fresh_signal_book(
    tmp_path, monkeypatch, best_of, has_map, expected
):
    from prometheus.live import service

    game = worker_game(tmp_path, best_of)
    game.request_dir = lambda _: tmp_path
    game.latest_signal_book = None
    if has_map:
        game.ticker = "KXLOLMAP-F-A"
    monkeypatch.setattr(service, "utc_now", lambda: NOW.isoformat())
    monkeypatch.setattr(
        service,
        "fetch_json",
        lambda *_: (
            {"headers": {"Date": "Thu, 15 Oct 2026 12:00:00 GMT"}},
            {
                "orderbook_fp": {
                    "yes_dollars": [[".48", "10"]],
                    "no_dollars": [[".50", "10"]],
                }
            },
        ),
    )
    path = tmp_path / "series_quotes.jsonl"
    service.Game.poll_quote(game, game.series_ticker, path)
    assert (game.latest_signal_book is not None) is expected
    assert json.loads(path.read_text())["ticker"] == game.series_ticker


@pytest.mark.parametrize(
    "failure",
    [
        "no_series_market",
        "event_market_count",
        "market_rule_mismatch",
        "market_side_mismatch",
        "duplicate_side",
    ],
)
def test_worker_discovery_reports_each_failure(tmp_path, failure):
    from prometheus.live.signals import Signals

    game = worker_game(tmp_path)
    markets = Bo1PublicClient().parent["markets"]
    if failure == "no_series_market":
        markets = []
    elif failure == "event_market_count":
        markets.pop()
    elif failure == "market_rule_mismatch":
        markets[1]["rules_primary"] = markets[1]["rules_primary"].replace(
            "wins the", "wins game 1 in the"
        )
    else:
        markets[1]["rules_primary"] = markets[1]["rules_primary"].replace(
            "If B", "If A" if failure == "duplicate_side" else "If C"
        )
    Signals.discover(game, markets)
    assert game.signal_event is None
    assert game.signal_skip == (
        "market_side_mismatch" if failure == "duplicate_side" else failure
    )


def pause_frames(golds, start_offset=600, spacing=0.17):
    begin = NOW - dt.timedelta(seconds=start_offset)
    return begin.isoformat(), [
        {
            "source_at": (NOW + dt.timedelta(seconds=i * spacing)).isoformat(),
            "teams": [{"gold": g}, {"gold": 0}],
        }
        for i, g in enumerate(golds)
    ]


@pytest.mark.parametrize(
    "golds,start_offset,expected",
    [
        ([100 + i // 6 for i in range(60)], 600, False),  # gold ticks each ~1 s
        ([100] * 60, 600, True),  # ten seconds unchanged: a pause
        ([100] * 60, 60, False),  # passive gold not started yet
        ([100] * 20, 600, False),  # under five seconds of frames
    ],
)
def test_pause_needs_ten_seconds_of_unchanged_gold(golds, start_offset, expected):
    from prometheus.live.signals import paused

    start, frames = pause_frames(golds, start_offset)
    assert paused(frames, start) is expected


def test_pause_without_game_start_fails_closed():
    from prometheus.live.signals import paused

    _, frames = pause_frames([100] * 60)
    with pytest.raises(ValueError, match="live_game_start_unknown"):
        paused(frames, None)


@pytest.mark.parametrize("hours,passes", [(1, True), (2, False), (3, False)])
def test_live_source_start_tolerance(hours, passes):
    o = observation()
    o["start"] = (
        live_map.timestamp(o["source_at"]) + dt.timedelta(hours=hours)
    ).isoformat()
    if passes:
        assert 0 < live_map.validate_observation(o, NOW.isoformat()) < 1
    else:
        with pytest.raises(ValueError, match=r"^live_source_before_start$"):
            live_map.validate_observation(o, NOW.isoformat())


@pytest.mark.parametrize(
    "target,team,expected", [(4, "A", None), (6, "A", "1.40"), (6, "B", "6.00")]
)
def test_map_buys_only_target_minus_same_team_pregame_fills(target, team, expected):
    from test_execution import saved

    from prometheus.execution.core import plan_order

    value = {**config(), "starting_bankroll_usd": "500", "max_contracts": 6}
    _, api, ledger, execute = harness(value)
    cfg = Config.parse(value)
    plan = plan_order(
        saved(backed_team=team), Exchange().routes, cfg, Decimal(100), NOW
    )
    row = ledger.reserve(plan, cfg, Decimal(100))
    ledger.replace(
        row,
        {
            **row,
            "status": "filled",
            "held": "2.76",
            "committed": "2.76",
            "order": {"fill_count_fp": "4.60"},
            "fills": [{"fill_id": "pregame-fill", "count_fp": "4.60"}],
        },
    )
    # Fills are evidence pointers after replace; the order count survives.
    assert isinstance(ledger.pending()[0]["fills"], dict)
    api.routes[0]["quantity"] = str(target)
    result = execute([signal()])
    if expected is None:
        assert result["skipped"] == 1 and not api.calls
        assert ledger.get("demo", "MAPSERIES#KXLOLGAME-F") is None
        assert "existing_position_covers_target" in [
            _decode(v).get("reason") for v in ledger.client.data.values()
        ]
    else:
        assert result["submitted"] == 1
        assert api.calls[0]["count"] == expected
        row = next(
            r for r in ledger.pending() if r["alert"].get("kind") == live_map.VERSION
        )
        assert row["sizing"]["target_count"] == f"{target:.2f}"
        assert Decimal(row["sizing"]["held_contracts"]) == (
            Decimal("4.6") if team == "A" else 0
        )
        assert Decimal(row["held"]) == Decimal(expected) * Decimal(
            row["sizing"]["unit_cost_bound"]
        )


@pytest.mark.parametrize("is_map", [False, True])
@pytest.mark.parametrize("cap_state", ["shrinks", "blocks", "absent"])
def test_global_series_cap_sums_pregame_and_map_costs(is_map, cap_state):
    from test_execution import saved

    value = config()
    if cap_state != "absent":
        value["series_fraction"] = ".10"
    client, api, ledger, execute = harness(value)
    for sk, held in (
        ("ACCOUNT", "5"),
        ("SERIES#KXLOLGAME-F", "4.1" if cap_state == "blocks" else "3.9"),
        ("MAPSERIES#KXLOLGAME-F", ".5"),
    ):
        client.put_item(Item=_item({"pk": "ENV#demo", "sk": sk, "held": Decimal(held)}))
    candidate = signal() if is_map else saved()
    result = execute([candidate])
    if cap_state == "blocks":
        assert result["skipped"] == 1 and not api.calls
    else:
        assert result["submitted"] == 1
        row = ledger.pending()[0]
        if cap_state == "shrinks":
            assert 0 < Decimal(row["held"]) <= Decimal(".10")
        else:
            assert Decimal(row["held"]) > Decimal(".10")


@pytest.mark.parametrize("fraction", ["0", "-.1", "1.01", "NaN", "Infinity"])
def test_invalid_global_series_fraction(fraction):
    with pytest.raises(ValueError):
        Config.parse({**config(), "series_fraction": fraction})


def test_global_series_fraction_can_be_saved_through_control():
    parameter = Parameter({**config(), "mode": "off"})
    assert control.configure(parameter, "/config", {"series_fraction": ".10"})[
        "updated_fields"
    ] == ["series_fraction"]
    assert parameter.value["series_fraction"] == ".10"
    assert Config.parse({**config(), "series_fraction": "1"})
