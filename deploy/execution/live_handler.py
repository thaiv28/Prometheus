"""Immediate SQS live-map runner. Queue is a pointer, never an order payload."""

import datetime as dt
import hashlib
import json
import os
import re

from prometheus import live_map
from prometheus.alert_contract import trade_veto
from prometheus.execution.core import (
    ZERO,
    Config,
    decimal,
    map_budget,
    plan_order,
    run,
    validate_alert,
)
from prometheus.execution.kalshi import Kalshi, PublicKalshi
from prometheus.execution.ledger import DynamoLedger

MAX_SIGNAL_BYTES = 128 * 1024


def handle(event, clients, aliases):
    def configuration():
        value = json.loads(
            clients["ssm"].get_parameter(Name=os.environ["EXECUTION_CONFIG_PARAMETER"])[
                "Parameter"
            ]["Value"]
        )
        Config.parse(value)
        return value

    initial = configuration()
    maps = initial.get("live_maps") or {}
    failures = []
    # Disabled queue deliveries cannot load signals, credentials or account data.
    if maps.get("mode", "off") == "off":
        return {"batchItemFailures": []}
    ledger = DynamoLedger(os.environ["EXECUTION_TABLE"], clients["dynamodb"])
    for record in event.get("Records", []):
        alert = {"alert_id": "invalid"}
        try:
            if (
                record.get("eventSource") != "aws:sqs"
                or record.get("eventSourceARN") != maps["queue_arn"]
            ):
                raise ValueError("foreign_live_queue")
            pointer = json.loads(record["body"])
            digest = pointer["sha256"]
            if (
                not re.fullmatch(r"[0-9a-f]{64}", digest)
                or pointer["key"] != live_map.PREFIX + digest + ".json"
            ):
                raise ValueError("invalid_live_signal_pointer")
            response = clients["s3"].get_object(
                Bucket=os.environ["PREDICTIONS_BUCKET"], Key=pointer["key"]
            )
            if response.get("ContentLength", 0) > MAX_SIGNAL_BYTES:
                raise ValueError("oversize_live_signal")
            payload = response["Body"].read(MAX_SIGNAL_BYTES + 1)
            if (
                len(payload) > MAX_SIGNAL_BYTES
                or hashlib.sha256(payload).hexdigest() != digest
            ):
                raise ValueError("live_signal_hash_mismatch")
            candidate = json.loads(payload)
            if (
                not isinstance(candidate, dict)
                or candidate.get("kind") != live_map.VERSION
            ):
                raise ValueError("unsupported_live_alert")
            alert = candidate
            now = dt.datetime.now(dt.UTC)
            config = Config.parse(configuration())
            validate_alert(alert, config, now)
            if reason := trade_veto(alert):
                raise ValueError(reason)
            if config.raw["live_maps"]["mode"] == "shadow":
                # No credential, portfolio or order endpoint is called in shadow.
                api = PublicKalshi(aliases)
                routes = api.resolve(alert, now, config)
                checked = api.now()
                validate_alert(alert, config, checked)
                source_environment = (
                    config.mode if config.mode in {"demo", "live"} else "live"
                )
                account = ledger.get(source_environment, "ACCOUNT") or {}
                series = (
                    ledger.get(source_environment, f"SERIES#{alert['series_id']}") or {}
                )
                capital = (
                    config.number("starting_bankroll_usd")
                    + decimal(account.get("realized", 0))
                    - decimal(account.get("held", 0))
                )
                cap = max(ZERO, capital) * decimal(
                    config.raw["live_maps"]["series_fraction"]
                )
                account = {
                    **account,
                    "series_available": cap - decimal(series.get("held", 0)),
                    **map_budget(config, ledger.get(source_environment, "LIVE_MAPS")),
                }
                day = (
                    ledger.get(source_environment, f"DAY#{checked.date().isoformat()}")
                    or {}
                )
                plan = plan_order(
                    alert,
                    routes,
                    config,
                    config.number("starting_bankroll_usd")
                    + decimal(account.get("realized", 0)),
                    checked,
                    account,
                    day.get("committed", ZERO),
                )
                if configuration() != config.raw:
                    raise ValueError("configuration_changed")
                ledger.shadow(
                    alert,
                    {
                        "assumption": "proposed IOC at displayed depth; no fill asserted",
                        "plan": plan,
                        "decision_at": checked.isoformat(),
                        "signal_key": pointer["key"],
                    },
                    checked,
                )
                continue

            def api_factory(environment):
                credentials = json.loads(
                    clients["secretsmanager"].get_secret_value(
                        SecretId=os.environ[f"{environment.upper()}_SECRET_ARN"]
                    )["SecretString"]
                )
                return Kalshi(
                    environment,
                    credentials["key_id"],
                    credentials["private_key_pem"],
                    canonical_aliases=aliases,
                )

            result = run(
                [alert],
                configuration,
                ledger,
                api_factory,
                now=now,
                reconcile_existing=False,
            )
            if result["errors"]:
                failures.append({"itemIdentifier": record["messageId"]})
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            # Malformed/expired entries are terminal; preserve private skip evidence.
            ledger.skip(
                alert,
                "shadow"
                if maps.get("mode") == "shadow"
                else initial.get("mode", "off"),
                str(error),
                dt.datetime.now(dt.UTC),
            )
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
