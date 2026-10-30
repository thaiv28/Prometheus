"""Private DynamoDB intent ledger, with atomic spending and duplicate fences.

Table keys: pk (string), sk (string). No TTL: unknown orders retain reservations
and fixture/event fences permanently. The boto3 client is injected by the runner.
"""

import copy
import hashlib
import json
from decimal import Decimal

from prometheus import live_map

from .core import decimal


def fence_keys(alert):
    event_prefix = "MAPEVENT" if alert.get("kind") == live_map.VERSION else "EVENT"
    return [
        f"FIXTURE#{alert['fixture_id']}",
        f"{event_prefix}#{alert['event_ticker']}",
    ]


def _item(value):
    return {
        key: {"N": str(val)} if isinstance(val, (int, Decimal)) else {"S": str(val)}
        for key, val in value.items()
    }


def _decode(item):
    return {
        key: (value.get("S") if "S" in value else Decimal(value["N"]))
        for key, value in item.items()
    }


def _conditional(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in {
        "ConditionalCheckFailedException",
        "TransactionCanceledException",
    }


class DynamoLedger:
    def __init__(self, table_name, client):
        self.table = table_name
        self.client = client

    @staticmethod
    def key(environment, sk):
        return {"pk": f"ENV#{environment}", "sk": sk}

    def get(self, environment, sk):
        result = self.client.get_item(
            TableName=self.table,
            Key=_item(self.key(environment, sk)),
            ConsistentRead=True,
        )
        return _decode(result["Item"]) if result.get("Item") else None

    def put_meta(self, environment, sk, value):
        """Store small execution metadata in the environment partition."""
        self.client.put_item(
            TableName=self.table,
            Item=_item({**self.key(environment, sk), **value}),
        )

    def intents(self, environment):
        """All intent payloads, including settled history, in one environment."""
        query = {
            "TableName": self.table,
            "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
            "ExpressionAttributeValues": _item(
                {":pk": f"ENV#{environment}", ":prefix": "INTENT#"}
            ),
            "ConsistentRead": True,
        }
        result = []
        while True:
            page = self.client.query(**query)
            result.extend(
                json.loads(_decode(item)["payload"]) for item in page.get("Items", [])
            )
            if not page.get("LastEvaluatedKey"):
                return result
            query["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def pending(self, environment=None):
        result = []
        environments = (environment,) if environment else ("demo", "live")
        for environment in environments:
            query = {
                "TableName": self.table,
                "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
                "ExpressionAttributeValues": _item(
                    {":pk": f"ENV#{environment}", ":prefix": "ACTIVE#"}
                ),
                "ConsistentRead": True,
            }
            while True:
                page = self.client.query(**query)
                for item in page.get("Items", []):
                    item = _decode(item)
                    intent = self.get(environment, item["intent_key"])
                    if intent is None:
                        raise ValueError("missing_active_intent")
                    row = json.loads(intent["payload"])
                    row["revision"] = int(intent["revision"])
                    if row["status"] not in {"settled", "unfilled", "aborted"}:
                        result.append(row)
                if not page.get("LastEvaluatedKey"):
                    break
                query["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return result

    def held_contracts(self, environment, series_id, team):
        """Filled, unsettled contracts backing this team across all strategies."""
        total = Decimal(0)
        for row in self.pending(environment):
            if (
                row.get("series_id") != series_id
                or row["alert"].get("backed_team") != team
            ):
                continue
            # Reconcile preserves the exchange count when fills become evidence pointers.
            order = row.get("order") or {}
            if "fill_count_fp" in order:
                total += decimal(order["fill_count_fp"])
            else:
                total += sum(
                    (decimal(fill["count_fp"]) for fill in row.get("fills", [])),
                    Decimal(0),
                )
        return total

    def reserve(self, plan, config, balance):
        env = plan["environment"]
        amount = decimal(plan["held"])
        cap = min(
            config.number("max_exposure_usd"),
            balance - config.number("min_balance_usd"),
        )
        account_key = plan.get("account", "ACCOUNT")
        game = plan["alert"].get("game", "lol")
        starting = (
            config.number("starting_bankroll_usd")
            if game == "lol"
            else decimal(config.raw["games"][game]["starting_bankroll_usd"])
        )
        sizing = plan.get("sizing") or {}
        if sizing.get("method") == "kelly-v1":
            cap = min(
                cap,
                starting + decimal(sizing["realized_before"]),
            )
        if amount > cap or amount > config.number("daily_budget_usd"):
            return None
        row = copy.deepcopy(plan)
        row["revision"] = 0
        transactions = []
        for sk, field, limit in (
            (account_key, "held", cap),
            (f"DAY#{plan['day']}", "committed", config.number("daily_budget_usd")),
        ):
            condition = f"attribute_not_exists({field}) OR {field} <= :available"
            values = {":amount": amount, ":available": limit - amount}
            if sk == account_key and sizing.get("method") == "kelly-v1":
                condition = f"({condition})"
                for name in ("held", "realized"):
                    expected = decimal(sizing[f"{name}_before"])
                    key = f":expected_{name}"
                    values[key] = expected
                    match = f"{name} = {key}"
                    if expected == 0:
                        match = f"(attribute_not_exists({name}) OR {match})"
                    condition += f" AND {match}"
            transactions.append(
                {
                    "Update": {
                        "TableName": self.table,
                        "Key": _item(self.key(env, sk)),
                        "UpdateExpression": f"ADD {field} :amount",
                        "ConditionExpression": condition,
                        "ExpressionAttributeValues": _item(values),
                    }
                }
            )
        if plan.get("series_id"):
            cap_value = config.raw.get("live_series_cap_usd")
            update = {
                "TableName": self.table,
                "Key": _item(
                    self.key(
                        env, plan.get("series_key") or f"SERIES#{plan['series_id']}"
                    )
                ),
                "UpdateExpression": "ADD held :amount",
                "ExpressionAttributeValues": _item({":amount": amount}),
            }
            if cap_value is not None:
                cap_value = decimal(cap_value)
                if amount > cap_value:
                    return None
                update["ConditionExpression"] = (
                    "attribute_not_exists(held) OR held <= :available"
                )
                update["ExpressionAttributeValues"] = _item(
                    {":amount": amount, ":available": cap_value - amount}
                )
            transactions.append({"Update": update})
        for sk in fence_keys(plan["alert"]):
            transactions.append(
                {
                    "Put": {
                        "TableName": self.table,
                        "Item": _item(
                            {**self.key(env, sk), "intent": plan["client_order_id"]}
                        ),
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                }
            )
        transactions.append(
            {
                "Put": {
                    "TableName": self.table,
                    "Item": _item(
                        {
                            **self.key(env, f"INTENT#{plan['alert']['fixture_id']}"),
                            "revision": 0,
                            "payload": json.dumps(row, separators=(",", ":")),
                        }
                    ),
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            }
        )
        transactions.append(
            {
                "Put": {
                    "TableName": self.table,
                    "Item": _item(
                        {
                            **self.key(env, f"ACTIVE#{plan['alert']['fixture_id']}"),
                            "intent_key": f"INTENT#{plan['alert']['fixture_id']}",
                        }
                    ),
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            }
        )
        try:
            self.client.transact_write_items(TransactItems=transactions)
        except Exception as error:
            if _conditional(error):
                return None
            raise
        return row

    def replace(self, previous, row):
        env = previous["environment"]
        row = copy.deepcopy(row)
        row["revision"] = previous["revision"] + 1
        for kind in ("fills", "settlements"):
            evidence = row.get(kind, [])
            if isinstance(evidence, list) and evidence:
                self.evidence(row, kind, evidence)
                row[kind] = {
                    "count": len(evidence),
                    "prefix": f"EVIDENCE#{row['alert']['fixture_id']}#{kind}#",
                }
        changes = [
            {
                "Put": {
                    "TableName": self.table,
                    "Item": _item(
                        {
                            **self.key(
                                env, f"INTENT#{previous['alert']['fixture_id']}"
                            ),
                            "revision": row["revision"],
                            "payload": json.dumps(row, separators=(",", ":")),
                        }
                    ),
                    "ConditionExpression": "revision = :revision",
                    "ExpressionAttributeValues": _item(
                        {":revision": previous["revision"]}
                    ),
                }
            }
        ]
        account_key = previous.get("account", "ACCOUNT")
        for sk, field in (
            (account_key, "held"),
            (f"DAY#{previous['day']}", "committed"),
        ):
            delta = decimal(row[field]) - decimal(previous[field])
            profit_delta = (
                decimal(row.get("realized_profit", 0))
                - decimal(previous.get("realized_profit", 0))
                if sk == account_key
                else Decimal(0)
            )
            if delta or profit_delta:
                expression = f"ADD {field} :delta"
                values = {":delta": delta}
                if profit_delta:
                    expression += ", realized :profit_delta"
                    values[":profit_delta"] = profit_delta
                changes.append(
                    {
                        "Update": {
                            "TableName": self.table,
                            "Key": _item(self.key(env, sk)),
                            "UpdateExpression": expression,
                            "ExpressionAttributeValues": _item(values),
                        }
                    }
                )
        if previous.get("series_id"):
            delta = decimal(row["held"]) - decimal(previous["held"])
            if delta:
                changes.append(
                    {
                        "Update": {
                            "TableName": self.table,
                            "Key": _item(
                                self.key(
                                    env,
                                    previous.get("series_key")
                                    or f"SERIES#{previous['series_id']}",
                                )
                            ),
                            "UpdateExpression": "ADD held :delta",
                            "ExpressionAttributeValues": _item({":delta": delta}),
                        }
                    }
                )
        if "map_held_before" in (previous.get("sizing") or {}):
            delta = decimal(row["held"]) - decimal(previous["held"])
            profit_delta = decimal(row.get("realized_profit", 0)) - decimal(
                previous.get("realized_profit", 0)
            )
            if delta or profit_delta:
                changes.append(
                    {
                        "Update": {
                            "TableName": self.table,
                            "Key": _item(self.key(env, "LIVE_MAPS")),
                            "UpdateExpression": "ADD held :delta, realized :profit",
                            "ExpressionAttributeValues": _item(
                                {":delta": delta, ":profit": profit_delta}
                            ),
                        }
                    }
                )
        if row["status"] in {"settled", "unfilled", "aborted"}:
            changes.append(
                {
                    "Delete": {
                        "TableName": self.table,
                        "Key": _item(
                            self.key(env, f"ACTIVE#{previous['alert']['fixture_id']}")
                        ),
                    }
                }
            )
        try:
            self.client.transact_write_items(TransactItems=changes)
        except Exception as error:
            if _conditional(error):
                return None
            raise
        return row

    def seen(self, alert, environment):
        return any(self.get(environment, sk) is not None for sk in fence_keys(alert))

    def evidence(self, row, kind, values):
        for value in values:
            payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
            identity = (
                value.get("fill_id") or hashlib.sha256(payload.encode()).hexdigest()
            )
            sk = f"EVIDENCE#{row['alert']['fixture_id']}#{kind}#{identity}"
            try:
                self.client.put_item(
                    TableName=self.table,
                    Item=_item(
                        {**self.key(row["environment"], sk), "payload": payload}
                    ),
                    ConditionExpression="attribute_not_exists(pk)",
                )
            except Exception as error:
                if not _conditional(error):
                    raise
                previous = self.get(row["environment"], sk)
                if previous is None or previous["payload"] != payload:
                    raise ValueError("conflicting_execution_evidence") from error

    def claim(self, row):
        if row["status"] != "intent":
            return None
        return self.replace(row, {**row, "status": "submitting"})

    def abort(self, row, reason):
        return self.replace(
            row,
            {
                **row,
                "status": "aborted",
                "reason": reason,
                "held": "0",
                "committed": "0",
            },
        )

    def ack(self, row, response):
        if not isinstance(response.get("order_id"), str) or not response["order_id"]:
            raise ValueError("missing_order_id")
        if (
            response.get("client_order_id", row["client_order_id"])
            != row["client_order_id"]
        ):
            raise ValueError("client_identity_mismatch")
        return self.replace(
            row,
            {
                **row,
                "status": "submitted",
                "order_id": response["order_id"],
                "submission": response,
            },
        )

    def note_error(self, row, reason, now):
        # Do not overwrite a newer reconciliation with an old revision.
        return self.replace(row, {**row, "error": reason, "error_at": now.isoformat()})

    def skip(self, alert, environment, reason, now):
        identity = hashlib.sha256(
            str(alert.get("alert_id", "invalid")).encode()
        ).hexdigest()
        self.client.put_item(
            TableName=self.table,
            Item=_item(
                {
                    **self.key(environment, f"SKIP#{identity}"),
                    "reason": reason,
                    "at": now.isoformat(),
                    "alert_id": alert.get("alert_id", "invalid"),
                }
            ),
        )

    def shadow(self, alert, payload, now):
        try:
            self.client.put_item(
                TableName=self.table,
                Item=_item(
                    {
                        **self.key("shadow", f"MAP#{alert['event_ticker']}"),
                        "payload": json.dumps(payload, separators=(",", ":")),
                        "at": now.isoformat(),
                    }
                ),
                ConditionExpression="attribute_not_exists(pk)",
            )
        except Exception as error:
            if not _conditional(error):
                raise
