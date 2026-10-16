"""Manual central mode control; no API credentials or orders are accessed."""

import argparse
import datetime
import json


def set_mode(client, parameter, mode, now=None):
    from prometheus.execution.core import Config

    if mode not in ("off", "demo", "live"):
        raise ValueError("Mode must be off, demo or live")
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


def main():
    import boto3

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--mode", required=True, choices=("off", "demo", "live"))
    args = parser.parse_args()
    print(json.dumps(set_mode(boto3.client("ssm"), args.parameter, args.mode)))


if __name__ == "__main__":
    main()
