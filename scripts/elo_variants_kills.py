"""
elo_variants_kills.py: kill-based margins of victory for player-built Elo.

Each candidate replaces the published game-length winner score (0.65 to 1.0) with one
built from end-of-game kills, falls back to the game-length score where kills weren't
recorded (or, for kill share, a 0-0 game), is tuned on seasons up to 2021 only
(`elo_variants.held_out`, objective: domestic Elo-live log loss) and reported on
2022 onwards against the published Elo on the same games.

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python -u scripts/elo_variants_kills.py            # all
    VECLIB_MAXIMUM_THREADS=1 uv run python -u scripts/elo_variants_kills.py --only 0   # one
    VECLIB_MAXIMUM_THREADS=1 uv run python -u scripts/elo_variants_kills.py --report   # tables

Each candidate's result is saved to --cache (default /tmp/elo_variants_kills), so
candidates can run separately and --report prints the tables from the saved results.
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_variants as ev  # noqa: E402

K_GRID = [20, 28]


def _minutes(g):
    return g["gamelength"].to_numpy(dtype=float) / 60


def kill_diff(g):
    return (g["w_kills"] - g["l_kills"]).to_numpy(dtype=float)


def kill_share(g):
    w, l = g["w_kills"].to_numpy(dtype=float), g["l_kills"].to_numpy(dtype=float)
    total = w + l
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(total > 0, w / total, np.nan)  # 0-0: NaN, so the fallback scores it


def gold_diff(g):
    return (g["w_totalgold"] - g["l_totalgold"]).to_numpy(dtype=float)


# --- candidates: make_margin(**params) -> margin function -----------------------------


def m_kill_diff(scale, lower):
    return ev.with_fallback(lambda g: ev.bounded(kill_diff(g), scale, lower=lower))


def m_kill_share(scale, lower):
    return ev.with_fallback(lambda g: ev.bounded(kill_share(g), scale, center=0.5, lower=lower))


def m_kill_diff_per_min(scale, lower):
    return ev.with_fallback(lambda g: ev.bounded(kill_diff(g) / _minutes(g), scale, lower=lower))


def m_kill_diff_length_blend(weight, scale):
    """weight x kill-difference score + (1 - weight) x the published game-length score."""
    length = ev.game_length_margin()
    return ev.with_fallback(
        lambda g: weight * ev.bounded(kill_diff(g), scale) + (1 - weight) * length(g)
    )


def m_kills_gold(kill_scale, gold_scale):
    """Mean of a kill-difference score and a gold-difference score."""
    return ev.with_fallback(
        lambda g: 0.5 * ev.bounded(kill_diff(g), kill_scale) + 0.5 * ev.bounded(gold_diff(g), gold_scale)
    )


CANDIDATES = [
    ("Kill difference, logistic", m_kill_diff,
     {"scale": [3, 6, 10, 15], "lower": [0.55, 0.65], "K": K_GRID}),
    ("Kill share, logistic around 0.5", m_kill_share,
     {"scale": [0.05, 0.1, 0.2], "lower": [0.55, 0.65], "K": K_GRID}),
    ("Kill difference per minute, logistic", m_kill_diff_per_min,
     {"scale": [0.1, 0.2, 0.35, 0.5], "lower": [0.55, 0.65], "K": K_GRID}),
    ("Kill difference + game length blend", m_kill_diff_length_blend,
     {"weight": [0.25, 0.5, 0.75], "scale": [5, 10], "K": K_GRID}),
    ("Kills and gold, mean of two logistics", m_kills_gold,
     {"kill_scale": [5, 10], "gold_scale": [3000, 6000], "K": K_GRID}),
    # Control, not a kill candidate: the published margin with only K tuned on the same grid,
    # to separate a gain from kills from a gain from a larger K.
    ("Control: game length, K tuned", lambda: ev.game_length_margin(), {"K": K_GRID}),
]


def run(inputs, i, cache):
    """Tune candidate `i` on the train years, score it held out and save the result."""
    label, make, grid = CANDIDATES[i]
    t = time.time()
    r = ev.held_out(inputs, make, grid, label)
    d = ev.deltas(inputs.baseline_scores(r.test_years), r.scores)
    out = {"label": label, "params": r.params, "points": len(ev.param_grid(grid)),
           "train": r.tuning["objective"].iloc[0], "tuning": r.tuning.drop(columns="params"),
           "row": r.row, "deltas": d, "seconds": time.time() - t}
    with open(cache / f"{i}.pkl", "wb") as f:
        pickle.dump(out, f)
    print(f"  {label}: train {out['train']:.5f}, {out['points']} points, {out['seconds']:.0f} s")
    print(r.row, flush=True)


def report(cache):
    with open(cache / "meta.pkl", "rb") as f:
        meta = pickle.load(f)
    results = []
    for i in range(len(CANDIDATES)):
        with open(cache / f"{i}.pkl", "rb") as f:
            results.append(pickle.load(f))
    base_train, train, test = meta["base_train"], meta["train"], meta["test"]
    print(f"\n## Training-years objective (domestic Elo live, {train[0]}–{train[-1]})\n")
    print(f"| Variant | Grid points | Best params | Train log loss | Δ vs baseline ({base_train:.5f}) |")
    print("|---|---:|---|---:|---:|")
    for r in results:
        print(f"| {r['label']} | {r['points']} | {r['params']} | {r['train']:.5f} "
              f"| {r['train'] - base_train:+.5f} |")
    print(f"\n## Held out ({test[0]}–{test[-1]})\n")
    print(ev.COMPARE_HEADER)
    for r in results:
        print(r["row"])
    best = min(results, key=lambda r: r["train"])
    print(f"\nChosen by training years: {best['label']} {best['params']}")
    print(best["deltas"].to_string(float_format=lambda v: f"{v:.5f}"))
    print(f"\nGrid points in total: {sum(r['points'] for r in results)}; "
          f"candidate time {sum(r['seconds'] for r in results):.0f} s")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", type=int, action="append", help="candidate index (repeatable)")
    parser.add_argument("--report", action="store_true", help="print the tables from saved results")
    parser.add_argument("--cache", default="/tmp/elo_variants_kills")
    args = parser.parse_args()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    if args.report:
        report(cache)
        return

    t0 = time.time()
    inputs = ev.load_inputs()
    cov = ev.coverage(inputs)["kills"]
    print(f"Kills recorded for both teams: {cov.min():.2f} to {cov.max():.2f} of games per season")
    # Baseline's training-years objective, for choosing among candidates on training data.
    train, test = ev.split_years(inputs.frame["year"].unique())
    base = ev.score(inputs, inputs.baseline(), years=train, forge=False)
    base_train = base.log_loss("elo_live", "Domestic").mean()
    with open(cache / "meta.pkl", "wb") as f:
        pickle.dump({"base_train": base_train, "train": train, "test": test}, f)
    print(f"Baseline train ({train[0]}–{train[-1]}) domestic Elo-live log loss: {base_train:.5f}", flush=True)
    for i in args.only if args.only is not None else range(len(CANDIDATES)):
        run(inputs, i, cache)
    print(f"Total runtime: {time.time() - t0:.0f} s")
    if args.only is None:
        report(cache)


if __name__ == "__main__":
    main()
