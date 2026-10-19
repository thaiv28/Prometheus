"""League-offset Glicko-style uncertainty, opt-in against published player Elo.

Fixed 54-cell grid: floor {20,40,80}, new/floor {1.5,2.5,4}, growth
{1,3,6}, information {.25,1}. One local Cartesian edge extension uses
floor 10/160, ratio 1.1/6, growth 0/12, information .125/2. Select only
on <=2021 games-weighted domestic, international, within-other and
cross-league Elo losses. Freeze selection before scoring 2022+.

Usage: VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_offset_rd.py
Native checks are separate; this script never writes Elo tables or weights.
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_glicko as g

AXES = ((20, 40, 80), (1.5, 2.5, 4), (1, 3, 6), (0.25, 1))
OUTWARD = ((10, 160), (1.1, 6), (0, 12), (0.125, 2))
AUDIT = Path("data/research/elo_offset_rd")


def parameters(x):
    floor, ratio, growth, info = x
    return {"league_rd": (floor * ratio, floor, growth, info)}


def extension(x):
    axes = []
    for value, axis, outward in zip(x, AXES, OUTWARD):
        extra = (outward[0],) if value == axis[0] else ()
        if value == axis[-1]:
            extra = (outward[1],)
        axes.append((value,) + extra)
    return [v for v in itertools.product(*axes) if v != tuple(x)]


def objective(inputs, pairs, pre, years):
    scores = g.ev.score(inputs, pre, years=years, forge=False)
    losses = [scores.log_loss("elo_live", s) for s in ("Domestic", "International")]
    losses += [
        g.enp.other_losses(pairs, pre, years)[1],
        g.enp.cross_losses(pairs, pre, years)[1],
    ]
    return float(np.concatenate(losses).mean())


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    protocol = json.dumps(
        {
            "axes": AXES,
            "outward": OUTWARD,
            "objective": "games-weighted domestic + international + within-other + cross-league Elo",
            "train": "<=2021",
            "test": ">=2022",
        },
        indent=2,
    )
    path = AUDIT / "protocol.json"
    if path.exists() and path.read_text() != protocol:
        raise ValueError("Protocol changed")
    path.write_text(protocol)
    inputs = g.ev.load_inputs(verbose=False)
    pairs = g.em.load_pair_games()
    train, test = g.ev.split_years(inputs.frame.year.unique())
    short = g.tuning_inputs(inputs, train)
    margin = g.ev.game_length_margin()
    checkpoint = AUDIT / "tuning.jsonl"
    saved = (
        [json.loads(x) for x in checkpoint.read_text().splitlines()]
        if checkpoint.exists()
        else []
    )
    cache = {tuple(x["coordinates"]): x for x in saved}

    def tune(grid):
        rows = []
        for x in grid:
            x = tuple(x)
            if x not in cache:
                pre = g.ev.replay(short, margin, **parameters(x))
                row = {
                    "coordinates": x,
                    "objective": objective(inputs, pairs, pre, train),
                }
                with checkpoint.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                cache[x] = row
            rows.append(cache[x])
            print(f"{x}: {cache[x]['objective']:.8f}", flush=True)
        return min(rows, key=lambda r: r["objective"])

    initial = tune(itertools.product(*AXES))
    extra = extension(initial["coordinates"])
    best = (
        min([initial, tune(extra)], key=lambda r: r["objective"]) if extra else initial
    )
    kw = parameters(best["coordinates"])
    (AUDIT / "selection.json").write_text(
        json.dumps(
            {
                "initial": initial,
                "best": best,
                "kwargs": kw,
                "extension_cells": len(extra),
            },
            indent=2,
        )
    )
    print(f"Frozen {kw}", flush=True)
    base = g.ev.replay(inputs, margin)
    pre = g.ev.replay(inputs, margin, **kw)
    prefix = g.ev.replay(short, margin, **kw)
    np.testing.assert_array_equal(
        prefix.to_numpy(), pre.reindex(prefix.index).to_numpy()
    )
    baseline = g.sections(inputs, pairs, base, test)
    variant = g.sections(inputs, pairs, pre, test)
    rows = g.comparison(baseline, variant)
    roster = g.comparison(baseline, variant, g.roster_changes(inputs))
    times = g.timing_check(inputs, margin, kw)
    targeted = any(
        r[5] < 0
        and r[0] in ("Elo, international", "FORGE, international", "Elo, cross-league")
        for r in rows
    )
    passed = targeted and not any(r[4] > 0 for r in rows)
    result = {"rows": rows, "roster": roster, "times": times, "heldout_pass": passed}
    (AUDIT / "results.json").write_text(json.dumps(result, indent=2))
    lines = [
        "# League-offset uncertainty\n",
        f"Selected `{kw}`; initial {initial}; {len(extra)} extension cells. Tuning objective {best['objective']:.8f}.\n",
        __doc__,
        "\n## Held out 2022+\n",
        *g.table(rows),
        "\n## Roster-change slices\n",
        *g.table(roster),
        "\n## Method and limits\n",
        "Reuses elo_glicko sections, leave-one-year-out curves and replay-specific Form/FORGE fits. Within-other Form features use other major years including tuning years. Not a chronological deployment simulation. Individual-game paired-bootstrap 95% intervals, no clustering or multiplicity adjustment; historical holdouts were viewed in prior research. Calibration remains on here. Exact selected prefix/full parity passes. League uncertainty only changes cross-home international offset updates; player RD and non-major slope retain published defaults.\n",
        f"Held-out targeted gate: {'PASS' if passed else 'FAIL'} (international/cross-league gain, no section significantly worse). Native calibration removal verdict is in elo_offset_rd_native.md.\n",
        g.timing_text(times),
        "\n## Tuning audit\n",
        "| Coordinates (floor, ratio, growth, info) | Objective |",
        "|---|---:|",
        *[f"| {r['coordinates']} | {r['objective']:.8f} |" for r in cache.values()],
    ]
    Path("docs/research/elo_offset_rd.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
