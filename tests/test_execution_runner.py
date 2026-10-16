"""AWS/control boundary tests; no AWS SDK, credentials or network required."""

import datetime
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from prometheus.execution import core, kalshi, ledger


def load(name):
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).resolve().parents[1] / "deploy" / "execution" / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


control, handler = load("control"), load("handler")


class Parameter:
    def __init__(self, value):
        self.value = value
        self.writes = []

    def get_parameter(self, **kwargs):
        return {"Parameter": {"Value": json.dumps(self.value)}}

    def put_parameter(self, **kwargs):
        self.writes.append(kwargs)
        self.value = json.loads(kwargs["Value"])


def clients(monkeypatch, configuration):
    for name, value in {
        "EXECUTION_CONFIG_PARAMETER": "/private/config",
        "EXECUTION_TABLE": "private-ledger",
        "PREDICTIONS_BUCKET": "private-backup",
        "PREDICTIONS_KEY": "private-log.json",
        "DEMO_SECRET_ARN": "demo-secret",
        "LIVE_SECRET_ARN": "live-secret",
    }.items():
        monkeypatch.setenv(name, value)
    used = []

    def forbidden(**kwargs):
        pytest.fail("Off/empty runner must not read predictions or credentials")

    monkeypatch.setattr(
        ledger,
        "DynamoLedger",
        lambda table, client: SimpleNamespace(pending=lambda: []),
    )
    return {
        "ssm": Parameter(configuration),
        "s3": SimpleNamespace(get_object=forbidden),
        "secretsmanager": SimpleNamespace(get_secret_value=forbidden),
        "dynamodb": object(),
    }, used


def test_off_empty_uses_no_source_credentials_or_exchange(monkeypatch):
    aws, _ = clients(monkeypatch, {"mode": "off", "activation_at": None})
    assert handler.handler({}, None, clients=aws) == {
        "submitted": 0,
        "skipped": 0,
        "reconciled": 0,
        "errors": 0,
    }


def test_active_runner_reads_exact_private_source_and_lazily_own_environment(
    monkeypatch,
):
    # Config validation is exercised by core tests. Here assert only the wrapper
    # forwards authoritative terms/config, not invocation data or public exports.
    monkeypatch.setattr(core.Config, "parse", lambda value: value)
    aws, used = clients(monkeypatch, {"mode": "demo"})
    source = {
        "matches": [
            {
                "match_id": "fixture",
                "ours1": "A",
                "ours2": "B",
                "league": "LFL",
                "event": "Summer",
                "start": "2026-10-20T10:00Z",
                "market": {"ticker": "KXLOLGAME-F"},
                "alert": {
                    "side": 1,
                    "team": "A",
                    "p": 0.7,
                    "price": 0.5,
                    "at": "2026-10-19T10:00Z",
                    "group": "minor-domestic",
                },
            }
        ]
    }

    def read_source(**kwargs):
        used.append(("source", kwargs))
        return {"Body": io.BytesIO(json.dumps(source).encode())}

    def read_secret(**kwargs):
        used.append(("secret", kwargs))
        return {
            "SecretString": json.dumps(
                {"key_id": "private-test-id", "private_key_pem": "private-test-key"}
            )
        }

    aws["s3"] = SimpleNamespace(get_object=read_source)
    aws["secretsmanager"] = SimpleNamespace(get_secret_value=read_secret)
    monkeypatch.setattr(kalshi, "Kalshi", lambda mode, key, pem: (mode, key, pem))

    def run(proposals, configuration, private_ledger, api):
        assert len(proposals) == 1 and proposals[0]["probability"] == "0.7"
        assert configuration() == {"mode": "demo"}
        assert api("demo") == ("demo", "private-test-id", "private-test-key")
        assert api("demo") == api("demo")
        return {"submitted": 1, "skipped": 0, "reconciled": 0, "errors": 0}

    monkeypatch.setattr(core, "run", run)
    result = handler.handler({"matches": ["UNTRUSTED"]}, None, clients=aws)
    assert result["submitted"] == 1
    assert used == [
        ("source", {"Bucket": "private-backup", "Key": "private-log.json"}),
        ("secret", {"SecretId": "demo-secret"}),
    ]
    assert "private-test" not in json.dumps(result)


def test_runner_errors_trigger_retry_without_exposing_private_details(monkeypatch):
    aws, _ = clients(monkeypatch, {"mode": "off"})
    monkeypatch.setattr(core, "run", lambda *args: {"errors": 1})
    with pytest.raises(RuntimeError, match="reservations retained"):
        handler.handler({}, None, clients=aws)


def test_control_off_never_needs_limits_and_renews_epoch():
    parameter = Parameter(
        {"mode": "live", "order_budget_usd": "unchanged-private-limit"}
    )
    now = datetime.datetime(2026, 10, 20, 10, tzinfo=datetime.UTC)
    result = control.set_mode(parameter, "/private/config", "off", now)
    assert result == {"mode": "off", "activation_at": now.isoformat()}
    assert parameter.value["order_budget_usd"] == "unchanged-private-limit"
    assert "unchanged" not in json.dumps(result)
    assert parameter.writes[0]["Overwrite"] is True


def test_control_cannot_activate_with_unset_limits_or_unknown_mode():
    parameter = Parameter({"mode": "off", "activation_at": None})
    with pytest.raises((KeyError, ValueError)):
        control.set_mode(parameter, "/private/config", "live")
    with pytest.raises(ValueError):
        control.set_mode(parameter, "/private/config", "paper")
    assert not parameter.writes


def test_source_outage_still_reconciles_existing_intents(monkeypatch):
    monkeypatch.setattr(core.Config, "parse", lambda value: value)
    aws, _ = clients(monkeypatch, {"mode": "demo"})

    def outage(**kwargs):
        raise RuntimeError("PRIVATE source exception")

    aws["s3"] = SimpleNamespace(get_object=outage)
    ran = []

    def run(proposals, *args):
        assert proposals == []
        ran.append(True)
        return {"submitted": 0, "errors": 0, "reconciled": 1}

    monkeypatch.setattr(core, "run", run)
    with pytest.raises(RuntimeError, match="existing intents reconciled") as error:
        handler.handler({}, None, clients=aws)
    assert ran and "PRIVATE source exception" not in str(error.value)
