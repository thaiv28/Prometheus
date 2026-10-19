"""Private scheduled Lambda entry point. No site build imports this module."""

import json
import os
from pathlib import Path

from prometheus.alert_contract import saved_alerts

ALIASES_PATH = Path(__file__).with_name("market_aliases.json")


def handler(event, context, *, clients=None):
    # boto3 is supplied by Lambda, not a normal site dependency.
    if clients is None:
        import boto3

        clients = {
            name: boto3.client(name)
            for name in ("ssm", "s3", "secretsmanager", "dynamodb")
        }
    if "Records" in event:
        from deploy.execution.live_handler import handle

        return handle(event, clients, json.loads(ALIASES_PATH.read_text()))
    from prometheus.execution.core import Config, run
    from prometheus.execution.kalshi import Kalshi
    from prometheus.execution.ledger import DynamoLedger

    def configuration():
        raw = clients["ssm"].get_parameter(
            Name=os.environ["EXECUTION_CONFIG_PARAMETER"]
        )["Parameter"]["Value"]
        value = json.loads(raw)
        Config.parse(
            value
        )  # Invalid configuration fails closed, including before submission.
        return value

    apis = {}

    def api(environment):
        if environment in apis:
            return apis[environment]
        secret = clients["secretsmanager"].get_secret_value(
            SecretId=os.environ[f"{environment.upper()}_SECRET_ARN"]
        )
        credentials = json.loads(secret["SecretString"])
        apis[environment] = Kalshi(
            environment,
            credentials["key_id"],
            credentials["private_key_pem"],
            canonical_aliases=json.loads(ALIASES_PATH.read_text()),
        )

        return apis[environment]

    # OFF still reconciles any existing positions/intents, but never reads the
    # large prediction object or any credential when its ledger is empty.
    initial = configuration()
    proposals = []
    source_failed = False
    if initial.get("mode", "off") != "off":
        # Latest successful PRIVATE save; no invocation/public-site payload.
        try:
            source = clients["s3"].get_object(
                Bucket=os.environ["PREDICTIONS_BUCKET"],
                Key=os.environ["PREDICTIONS_KEY"],
            )
            proposals = saved_alerts(json.loads(source["Body"].read()))
        except Exception:
            # Source outages must not prevent cancellation/fill reconciliation.
            source_failed = True
    ledger = DynamoLedger(os.environ["EXECUTION_TABLE"], clients["dynamodb"])
    result = run(proposals, configuration, ledger, api)
    # Only aggregate counters reach function logs/response. Detailed account,
    # intent, fill, fee and skip records stay in the private DynamoDB ledger.
    if source_failed:
        raise RuntimeError(
            "Private alert source unavailable; existing intents reconciled"
        )
    if result.get("errors"):
        raise RuntimeError(
            "Execution incomplete; private reservations retained for reconciliation"
        )
    return result
