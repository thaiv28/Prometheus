"""Manual central mode control; no API credentials or orders are accessed."""

import argparse
import datetime
import json
from pathlib import Path

FIELDS = frozenset(
    (
        "live_maps",
        "starting_bankroll_usd",
        "kelly_fraction",
        "series_fraction",
        "order_budget_usd",
        "fixture_budget_usd",
        "daily_budget_usd",
        "max_exposure_usd",
        "min_balance_usd",
        "max_contracts",
        "max_price",
        "min_after_fee_edge",
        "fee_rate_upper_bound",
        "balance_precision_usd",
        "max_alert_age_seconds",
        "max_quote_age_seconds",
    )
)


def configure(client, parameter, settings):
    from prometheus.execution.core import Config

    if not isinstance(settings, dict) or not settings or set(settings) - FIELDS:
        raise ValueError("Supply only explicit bankroll and risk-limit fields")
    current = json.loads(client.get_parameter(Name=parameter)["Parameter"]["Value"])
    if current.get("mode", "off") != "off":
        raise ValueError("Turn execution off before changing limits")
    if "live_maps" in settings and settings["live_maps"].get("mode", "off") != "off":
        raise ValueError("Configure live-map limits while off; activate separately")
    current.update(settings)
    # Validate the whole active configuration, but persist OFF with its original epoch.
    Config.parse(
        {
            **current,
            "mode": "live",
            "activation_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    )
    client.put_parameter(
        Name=parameter,
        Type="String",
        Value=json.dumps(current, separators=(",", ":")),
        Overwrite=True,
    )
    return {"mode": "off", "updated_fields": sorted(settings)}


def set_mode(client, parameter, mode, now=None, functions=None, function=None):
    from prometheus.execution.core import Config

    if mode not in ("off", "demo", "live"):
        raise ValueError("Mode must be off, demo or live")
    if mode != "off":
        from deploy.execution.release import verify_runtime

        if functions is None or not function:
            raise ValueError("A verified deployed executor is required for activation")
        verify_runtime(functions, function)
    current = json.loads(client.get_parameter(Name=parameter)["Parameter"]["Value"])
    current["mode"] = mode
    current["activation_at"] = (now or datetime.datetime.now(datetime.UTC)).isoformat()
    # OFF is always available even if limits are unset. Active modes require
    # explicit validated limits; this script never invents or changes a budget.
    Config.parse(current)
    client.put_parameter(
        Name=parameter,
        Type="String",
        Value=json.dumps(current, separators=(",", ":")),
        Overwrite=True,
    )
    return {"mode": mode, "activation_at": current["activation_at"]}


def set_live_map_mode(client, parameter, mode, now=None, functions=None, function=None):
    from prometheus.execution.core import Config

    if mode not in {"off", "shadow", "live"}:
        raise ValueError("Invalid live-map mode")
    current = json.loads(client.get_parameter(Name=parameter)["Parameter"]["Value"])
    if mode != "off":
        from deploy.execution.release import verify_runtime

        if functions is None or not function:
            raise ValueError("A verified executor is required")
        verify_runtime(functions, function)
        if mode == "live" and current.get("mode", "off") == "off":
            raise ValueError("Global execution must be demo/live before map activation")
    prior = current.get("live_maps")
    maps = {
        **(prior if isinstance(prior, dict) else {}),
        "mode": mode,
        "activation_at": (now or datetime.datetime.now(datetime.UTC)).isoformat(),
    }
    updated = {**current, "live_maps": maps}
    if mode != "off":
        Config.parse(
            {**updated, "mode": "demo", "activation_at": maps["activation_at"]}
        )
    client.put_parameter(
        Name=parameter,
        Type="String",
        Value=json.dumps(updated, separators=(",", ":")),
        Overwrite=True,
    )
    return {"live_map_mode": mode, "activation_at": maps["activation_at"]}


def main():
    import boto3

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--mode", choices=("off", "demo", "live"))
    action.add_argument("--live-map-mode", choices=("off", "shadow", "live"))
    action.add_argument(
        "--settings", help="JSON object containing explicit limits; requires OFF"
    )
    action.add_argument(
        "--settings-event", help="Read settings from a workflow dispatch event file"
    )
    parser.add_argument("--function")
    args = parser.parse_args()
    client = boto3.client("ssm")
    if args.settings is not None or args.settings_event is not None:
        settings = args.settings
        if args.settings_event:
            settings = json.loads(Path(args.settings_event).read_text())["inputs"][
                "settings"
            ]
        result = configure(client, args.parameter, json.loads(settings))
    elif args.live_map_mode is not None:
        result = set_live_map_mode(
            client,
            args.parameter,
            args.live_map_mode,
            functions=boto3.client("lambda") if args.live_map_mode != "off" else None,
            function=args.function,
        )
    else:
        result = set_mode(
            client,
            args.parameter,
            args.mode,
            functions=boto3.client("lambda") if args.mode != "off" else None,
            function=args.function,
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
