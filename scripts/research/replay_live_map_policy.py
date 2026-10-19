"""Replay the production entry kernel against the fixed historical 30s selection.

Uses calls emitted by live_trading.py (earlier-only monthly fits); no fetching.
Actual books/freshness/fragmentation are additional live guards, not invented data.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
from decimal import Decimal

import live_trading as research

from prometheus import live_map
from prometheus.execution.core import fee_bound


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = pd.read_csv(args.calls, dtype={"game": str, "series": str})
    rows["arrival"] = pd.to_datetime(rows.arrival, utc=True, format="ISO8601")
    rows["end"] = pd.to_datetime(rows.end, utc=True, format="ISO8601")
    expected = research.select(rows, window=30)
    eligible = rows[
        rows.objectives_valid
        & ~rows.flat
        & rows.quiet.le(10)
        & rows.n_30.ge(2)
        & rows.range_30.le(0.010000001)
    ]
    replayed = []
    conservative = []
    error = 0.0
    for row in eligible.itertuples(index=False):
        p, _ = live_map.blend(row.p, row.p_lag, row.arrival.isoformat())
        error = max(error, abs(p - row.blend))
        costs = [
            None if pd.isna(c) else max(c, row.p_lag if side == 0 else 1 - row.p_lag)
            for side, c in enumerate((row.cost0_30, row.cost1_30))
        ]
        for target, fee in (
            (replayed, lambda c: float(research.effective_cost(c) - c)),
            (
                conservative,
                lambda c: float(
                    fee_bound(Decimal(str(c)), 1, Decimal(".07"), Decimal(".0001"))
                ),
            ),
        ):
            try:
                decision = live_map.entry(p, costs, fee)
                target.append(
                    {
                        **row._asdict(),
                        "side": decision["side"],
                        "prob": decision["probability"],
                        "price": decision["tape_cost"],
                        "eff": decision["tape_cost"] + fee(decision["tape_cost"]),
                        "win": row.won if decision["side"] == 0 else 1 - row.won,
                        "clv": np.nan,
                    }
                )
            except ValueError as ex:
                if str(ex) != "live_no_after_fee_edge":
                    raise
    selected = (
        pd.DataFrame(replayed).sort_values(["arrival", "game"]).drop_duplicates("game")
    )
    guarded = (
        pd.DataFrame(conservative)
        .sort_values(["arrival", "game"])
        .drop_duplicates("game")
    )
    assert selected.game.tolist() == expected.game.tolist()
    np.testing.assert_array_equal(selected.side, expected.side)
    np.testing.assert_allclose(selected.prob, expected.prob, rtol=0, atol=1e-14)
    np.testing.assert_allclose(selected.price, expected.price, rtol=0, atol=1e-14)
    guard_summary = research.summary(guarded)
    guard_summary["clv"] = None
    result = {
        "parity": "PASS",
        "monthly_blend_max_error": error,
        "historical_30s": research.summary(expected),
        "executor_fee_bound_tape_only": guard_summary,
        "kelly_30s": [research.kelly(expected, f) for f in (0.1, 0.25, 0.5, 1.0)],
        "capped_quarter_30s": research.kelly(
            expected, 0.25, map_cap=0.01, series_cap=0.02
        ),
        "limit": "Fee-bound sensitivity still uses trade costs: no asks/depth/fills or receipt ages reconstructed.",
    }
    args.out.write_text(
        json.dumps(result, indent=2, default=float, allow_nan=False) + "\n"
    )
    print(json.dumps(result, indent=2, default=float, allow_nan=False))


if __name__ == "__main__":
    main()
