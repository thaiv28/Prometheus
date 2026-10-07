"""
elo_variants_objectives.py: objective-based margins of victory for player-built Elo.

Each candidate turns end-of-game objective counts (towers, dragons, barons, first
objectives) into the winner's actual score with `elo_variants.bounded` (0.65 to 1, the
published range), falls back to the published game-length score where a stat is missing,
is tuned on seasons up to 2021 (domestic Elo-live log loss) and reported on 2022 onward
against the published Elo on the same games (`elo_variants.held_out`).

Usage (one candidate per process so they can run in parallel; results are pickled):
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_variants_objectives.py --run towers_diff
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_variants_objectives.py --report
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_variants as ev  # noqa: E402

OUT = Path("/tmp/elo_variants_objectives")


def _f(games, col):
    return games[col].to_numpy(dtype=float)


def diff_margin(stat):
    """Winner minus loser `stat`, squashed."""

    def make(scale, center=0.0):
        return ev.with_fallback(
            lambda g: ev.bounded(_f(g, f"w_{stat}") - _f(g, f"l_{stat}"), scale, center)
        )

    return make


def tower_share(scale, center):
    """Winner's share of all towers taken, squashed (no towers at all: game-length fallback)."""

    def fn(g):
        w, l = _f(g, "w_towers"), _f(g, "l_towers")
        tot = w + l
        share = np.divide(w, tot, out=np.full_like(w, np.nan), where=tot > 0)
        return ev.bounded(share, scale, center)

    return ev.with_fallback(fn)


WEIGHT_SETS = {
    "equal": (1.0, 1.0, 1.0),
    "t1d1b2": (1.0, 1.0, 2.0),
    "t1d0.5b1.5": (1.0, 0.5, 1.5),
    "t1d2b3": (1.0, 2.0, 3.0),
}


def composite_raw(g, weights):
    wt, wd, wb = WEIGHT_SETS[weights]
    return (
        wt * (_f(g, "w_towers") - _f(g, "l_towers"))
        + wd * (_f(g, "w_dragons") - _f(g, "l_dragons"))
        + wb * (_f(g, "w_barons") - _f(g, "l_barons"))
    )


def composite(weights, scale, center):
    return ev.with_fallback(
        lambda g: ev.bounded(composite_raw(g, weights), scale, center)
    )


def blended(alpha, weights, scale, center):
    """alpha x composite score + (1 - alpha) x published game-length score."""
    gl = ev.game_length_margin()

    def fn(g):
        return alpha * ev.bounded(composite_raw(g, weights), scale, center) + (
            1 - alpha
        ) * gl(g)

    return ev.with_fallback(fn)


def first_objectives(scale, center, alpha):
    """Count of first tower, dragon and baron the winner took (0-3), squashed, blended
    with game length (alpha = weight on the count). Any flag missing: game-length score."""
    gl = ev.game_length_margin()

    def fn(g):
        n = _f(g, "w_firsttower") + _f(g, "w_firstdragon") + _f(g, "w_firstbaron")
        return alpha * ev.bounded(n, scale, center) + (1 - alpha) * gl(g)

    return ev.with_fallback(fn)


K = [20, 28]
CANDIDATES = {
    # control: the published game-length margin with only K tuned, to separate a K gain
    # from a margin gain (every candidate below tunes K over the same values)
    "k_control": (
        "Control: game length, K tuned",
        lambda: ev.game_length_margin(),
        {"K": K},
    ),
    # name: (label, make_margin, grid)
    "towers_diff": (
        "Tower diff",
        diff_margin("towers"),
        {"scale": [2, 4, 8], "center": [0, 3, 6], "K": K},
    ),
    "towers_share": (
        "Tower share",
        tower_share,
        {"scale": [0.05, 0.1, 0.2], "center": [0.6, 0.75, 0.9], "K": K},
    ),
    "dragons_diff": (
        "Dragon diff",
        diff_margin("dragons"),
        {"scale": [1, 2, 4], "center": [0, 2], "K": K},
    ),
    "barons_diff": (
        "Baron diff",
        diff_margin("barons"),
        {"scale": [0.5, 1, 2], "center": [0, 1], "K": K},
    ),
    "composite": (
        "Objective composite",
        composite,
        {"weights": list(WEIGHT_SETS), "scale": [3, 6], "center": [0, 6], "K": K},
    ),
    # blend: the composite's weights/scale/center are filled in from its train-years choice
    "blend": ("Composite + game length", None, {"alpha": [0.25, 0.5, 0.75], "K": K}),
    "first_obj": (
        "First tower/dragon/baron",
        first_objectives,
        {"scale": [0.5, 1], "center": [1, 2], "alpha": [0.5, 1.0], "K": K},
    ),
}


def run(name):
    label, make, grid = CANDIDATES[name]
    t0 = time.time()
    inputs = ev.load_inputs()
    if name == "blend":
        comp = pickle.loads((OUT / "composite.pkl").read_bytes())["params"]
        fixed = {k: comp[k] for k in ("weights", "scale", "center")}
        label = f"{label} ({fixed})"
        make = lambda alpha: blended(alpha, **fixed)  # noqa: E731
    res = ev.held_out(inputs, make, grid, label)
    train = res.train_years
    base_train = (
        inputs.baseline_scores(train, forge=False)
        .log_loss("elo_live", "Domestic")
        .mean()
    )
    out = {
        "name": name,
        "label": label,
        "params": res.params,
        "row": res.row,
        "tuning": res.tuning.drop(columns="params").to_dict("records"),
        "train_best": float(res.tuning["objective"].iloc[0]),
        "train_baseline": float(base_train),
        "n_grid": len(res.tuning),
        "deltas": ev.deltas(inputs.baseline_scores(res.test_years), res.scores),
        "seconds": time.time() - t0,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.pkl").write_bytes(pickle.dumps(out))
    print(res.row)
    print(
        f"train best {out['train_best']:.5f} vs baseline {base_train:.5f}; {out['seconds']:.0f} s"
    )


def report():
    rows = [
        pickle.loads((OUT / f"{n}.pkl").read_bytes())
        for n in CANDIDATES
        if (OUT / f"{n}.pkl").exists()
    ]
    print(
        "| Candidate | Grid | Chosen params | Train dom. Elo LL (baseline) |\n|---|---:|---|---|"
    )
    for r in rows:
        print(
            f"| {r['label']} | {r['n_grid']} | {r['params']} | {r['train_best']:.4f} ({r['train_baseline']:.4f}) |"
        )
    print("\n" + ev.COMPARE_HEADER)
    for r in rows:
        print(r["row"])
    print(
        f"\nTotal parameter sets: {sum(r['n_grid'] for r in rows)}; "
        f"wall time per candidate: {', '.join(f'{r["name"]} {r["seconds"]:.0f}s' for r in rows)}"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", choices=list(CANDIDATES))
    p.add_argument("--report", action="store_true")
    a = p.parse_args()
    if a.run:
        run(a.run)
    if a.report:
        report()
