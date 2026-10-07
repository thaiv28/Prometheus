"""Predict blue map-win chance from saved checkpoint weights and visible stats."""

import argparse
import json
from pathlib import Path

from evaluate_visible_elo import predict_visible


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models", type=Path, default=Path("data/visible_elo/visible_models.json")
    )
    parser.add_argument("--minute", type=int, choices=(10, 15, 20), required=True)
    parser.add_argument("--blue-gold", type=float, required=True)
    parser.add_argument("--red-gold", type=float, required=True)
    parser.add_argument("--blue-elo", type=float, required=True)
    parser.add_argument("--red-elo", type=float, required=True)
    parser.add_argument(
        "--variant", choices=("gold_elo", "scoreboard_elo"), default="gold_elo"
    )
    parser.add_argument("--blue-kills", type=int)
    parser.add_argument("--red-kills", type=int)
    parser.add_argument(
        "--raw", action="store_true", help="Return the uncalibrated model score"
    )
    args = parser.parse_args()
    if args.variant == "scoreboard_elo" and (
        args.blue_kills is None or args.red_kills is None
    ):
        parser.error("scoreboard_elo requires both kill counts")
    parameters = json.loads(args.models.read_text())["models"]
    p = predict_visible(
        parameters,
        args.minute,
        args.blue_gold,
        args.red_gold,
        args.blue_kills or 0,
        args.red_kills or 0,
        args.blue_elo,
        args.red_elo,
        variant=args.variant,
        calibrated=not args.raw,
    )
    print(
        json.dumps(
            {
                "minute": args.minute,
                "variant": args.variant,
                "blue_win_probability": p,
                "red_win_probability": 1 - p,
                "calibrated": not args.raw,
            }
        )
    )


if __name__ == "__main__":
    main()
