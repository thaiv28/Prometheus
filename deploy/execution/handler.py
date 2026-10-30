"""Private scheduled Lambda entry point. No site build imports this module."""

import datetime as dt
import json
import os
import time
from pathlib import Path

from prometheus import market_blend
from prometheus.alert_contract import saved_candidates
from prometheus.other_games import ACCOUNT_KEYS
from prometheus.other_games import GAMES as OTHER_GAMES

ALIASES_PATH = Path(__file__).with_name("market_aliases.json")
_BLEND_CHECKED = {}


def refresh_blends(clients, games):
    """Fetch enabled game artifacts at most hourly, including failed attempts."""
    rejected = 0
    now = time.monotonic()
    for entry in os.environ.get("GAME_BLEND_KEYS", "").split(","):
        if not (entry := entry.strip()):
            continue
        game, separator, key = entry.partition(":")
        if game not in OTHER_GAMES or not games.get(game, {}).get("enabled"):
            continue
        if game in _BLEND_CHECKED and now - _BLEND_CHECKED[game] < 3600:
            continue
        _BLEND_CHECKED[game] = now
        if not separator or not key:
            rejected += 1
            continue
        try:
            source = clients["s3"].get_object(
                Bucket=os.environ["PREDICTIONS_BUCKET"], Key=key
            )
            rejected += int(not market_blend.install(game, source["Body"].read()))
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code not in {"NoSuchKey", "404"}:
                rejected += 1
    return rejected


# Warm containers reuse secrets for an hour: each Secrets Manager read is a KMS
# request, and a read every minute ran past KMS's 20,000 free monthly requests.
SECRET_TTL_SECONDS = 3600
_secrets = {}


def cached_secret(client, secret_id, clock=time.monotonic):
    """SecretString for `secret_id`; failures are never cached.

    Keyed by secret ID only: the handler makes new boto3 clients per invocation.
    """
    hit = _secrets.get(secret_id)
    if hit and clock() - hit[0] < SECRET_TTL_SECONDS:
        return hit[1]
    value = client.get_secret_value(SecretId=secret_id)["SecretString"]
    _secrets[secret_id] = (clock(), value)
    return value


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
    from prometheus.execution.dashboard import render
    from prometheus.execution.kalshi import Kalshi
    from prometheus.execution.ledger import DynamoLedger
    from prometheus.execution.notify import close_issue, github_issue, sync_dashboard

    notify = close = None
    if secret_id := os.environ.get("GITHUB_ISSUES_SECRET_ID"):

        def notify(row):
            try:
                token = cached_secret(clients["secretsmanager"], secret_id)
                return github_issue(
                    token,
                    os.environ.get("GITHUB_ISSUES_REPO", "thaiv28/prometheus-trades"),
                    row,
                )
            except Exception:
                return False

        def close(row):
            try:
                token = cached_secret(clients["secretsmanager"], secret_id)
                return close_issue(
                    token,
                    os.environ.get("GITHUB_ISSUES_REPO", "thaiv28/prometheus-trades"),
                    row,
                )
            except Exception:
                return False

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
        credentials = json.loads(
            cached_secret(
                clients["secretsmanager"],
                os.environ[f"{environment.upper()}_SECRET_ARN"],
            )
        )
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
    blend_rejected = 0
    if initial.get("mode", "off") != "off":
        blend_rejected = refresh_blends(clients, initial.get("games", {}))
        # Latest successful PRIVATE save; no invocation/public-site payload.
        try:
            source = clients["s3"].get_object(
                Bucket=os.environ["PREDICTIONS_BUCKET"],
                Key=os.environ["PREDICTIONS_KEY"],
            )
            proposals = saved_candidates(
                json.loads(source["Body"].read()), dt.datetime.now(dt.UTC)
            )
        except Exception:
            # Source outages must not prevent cancellation/fill reconciliation.
            source_failed = True
        if any(g.get("enabled") for g in initial.get("games", {}).values()):
            for key in os.environ.get("GAME_CANDIDATE_KEYS", "").split(","):
                if not (key := key.strip()):
                    continue
                try:
                    source = clients["s3"].get_object(
                        Bucket=os.environ["PREDICTIONS_BUCKET"], Key=key
                    )
                    proposals.extend(
                        saved_candidates(
                            json.loads(source["Body"].read()), dt.datetime.now(dt.UTC)
                        )
                    )
                except Exception as error:
                    code = getattr(error, "response", {}).get("Error", {}).get("Code")
                    if code not in {"NoSuchKey", "404"}:
                        source_failed = True
    ledger = DynamoLedger(os.environ["EXECUTION_TABLE"], clients["dynamodb"])
    result = run(proposals, configuration, ledger, api, notify=notify, close=close)
    mode = initial.get("mode", "off")
    if mode != "off" and secret_id:
        try:
            state = ledger.get(mode, "DASHBOARD") or {}
            rows = ledger.intents(mode)
            accounts = {key: ledger.get(mode, key) for key in ACCOUNT_KEYS}
            body = render(rows, accounts, initial, dt.datetime.now(dt.UTC))
            state = sync_dashboard(
                cached_secret(clients["secretsmanager"], secret_id),
                os.environ.get("GITHUB_ISSUES_REPO", "thaiv28/prometheus-trades"),
                body,
                state,
            )
            if state:
                ledger.put_meta(mode, "DASHBOARD", state)
                result["dashboard_updated"] = 1
        except Exception:
            pass  # Dashboard reads, rendering and publication never affect execution.
    if blend_rejected:
        result["blend_rejected"] = blend_rejected
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
