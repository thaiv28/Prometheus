"""Frozen: runs against `prometheus/elo.py` at commit 00237c0 (options since removed).

elo_glicko_scale.py: Joint Glicko RD and non-major Elo update-scale research.

Fixed before scoring: extend the v2 Glicko winner over RD floor {140,180,220}
and information {0.125,0.0625}, new/reference = twice floor/floor, growth 10.
Keep the rookie discount; disable provisional and time-away multipliers. Select
G* on <=2021 games-weighted domestic + within-other-league Elo log loss.
Then tune non-major domestic slope {ln(10)/400,.0065,.0070,.0080} x K
{20,22,24,28} on G*. Majors/international keep native slope and K 20.
If the winner hits an upper edge, extend that axis once (.0090 or K 32),
scoring all new Cartesian cells. Freeze G* and G*+S* before scoring 2022+.
Reuse v2 curves, Form/FORGE refits, sections and roster-change slices.
No published defaults, DB or weights change; not full Glicko-2.

Usage:
    VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_glicko_scale.py --out docs/research/elo_glicko_scale.md
"""

import argparse
import datetime
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_fitted_scale as scale
import elo_glicko as glicko

SLOPES = (scale.elo.EXPECTED_SLOPE, 0.0065, 0.0070, 0.0080)
KS = (20, 22, 24, 28)


def stage1_grid():
    return [
        glicko.parameters("Replace, keep discount", (floor, 2, 10, information))
        for floor, information in itertools.product((140, 180, 220), (0.125, 0.0625))
    ]


def stage2_grid(leagues, rd, slopes=SLOPES, ks=KS):
    return [(label, rd | kw) for label, kw in scale.other_grid(leagues, slopes, ks)]


def extension(leagues, rd, best):
    slope = next(iter(best["league_slopes"].values()))
    k = 20 * next(iter(best["league_factors"].values()))
    slopes = SLOPES + ((0.0090,) if slope == SLOPES[-1] else ())
    ks = KS + ((32,) if k == KS[-1] else ())
    original = {label for label, _ in stage2_grid(leagues, rd)}
    return [
        (label, kw)
        for label, kw in stage2_grid(leagues, rd, slopes, ks)
        if label not in original
    ]


def verdict(a, b, c):
    """Guard every reported section, including its roster-change slice."""
    targets = {"Elo, cross-league", "Elo, other leagues", "FORGE, other leagues"}
    if (
        not any(r[4] > 0 for r in b)
        and any(r[0] in targets and r[5] < 0 for r in c)
        and not any(r[4] > 0 for r in c)
    ):
        return "Ship G*+S*"
    if not any(r[4] > 0 for r in a) and any(r[5] < 0 for r in a):
        return "Ship G* only"
    return "Ship neither"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--out", type=Path, default=Path("docs/research/elo_glicko_scale.md")
    )
    args = ap.parse_args()
    started = time.perf_counter()
    ev, enp = glicko.ev, glicko.enp
    inputs = ev.load_inputs(verbose=False)
    pairs = glicko.em.load_pair_games()
    train, test = ev.split_years(inputs.frame.year.unique())
    short = glicko.tuning_inputs(inputs, train)
    margin = ev.game_length_margin()
    audit = Path("data/research/elo_glicko_scale")
    audit.mkdir(parents=True, exist_ok=True)
    protocol = {
        "stage1": stage1_grid(),
        "slopes": SLOPES,
        "ks": KS,
        "extension": "once, upper slope .0090 / K 32; all new Cartesian cells",
        "objective": "games-weighted domestic + within-other-league Elo log loss",
        "train": train,
        "test": test,
    }
    (audit / "protocol.json").write_text(json.dumps(protocol, indent=2))
    timings, tuning = [], []

    def replay(label, source, kw):
        tick = time.perf_counter()
        pre = ev.replay(source, margin, **kw)
        seconds = time.perf_counter() - tick
        timings.append((label, len(source.games), seconds))
        (audit / "timings.json").write_text(json.dumps(timings, indent=2))
        print(f"{label}: replay {seconds:.2f}s", flush=True)
        return pre

    def tune(stage, grid):
        candidates = []
        for label, kw in grid:
            pre = replay(f"{stage}: {label}", short, kw)
            loss = enp.objective(inputs, pairs, pre, train)
            tuning.append((stage, label, kw, float(loss)))
            (audit / "tuning.json").write_text(json.dumps(tuning, indent=2))
            print(f"  objective {loss:.8f}", flush=True)
            candidates.append((loss, label, kw))
        return min(candidates, key=lambda x: x[0])

    first = tune(
        "RD boundary", [(str(glicko.coordinates(kw)), kw) for kw in stage1_grid()]
    )
    leagues = inputs.games.league.unique()
    second = tune("Scale initial", stage2_grid(leagues, first[2]))
    extra = extension(leagues, first[2], second[2])
    initial = second
    if extra:
        second = min([second, tune("Scale extension", extra)], key=lambda x: x[0])
    (audit / "selection.json").write_text(
        json.dumps(
            {"protocol": protocol, "G*": first, "initial": initial, "G*+S*": second},
            indent=2,
        )
    )
    print(f"Frozen: G* {first}; G*+S* {second}", flush=True)
    # No held-out scores have been computed before the frozen selection above.
    pres = {"Published": replay("Published full", inputs, {})}
    for label, kw in (("G*", first[2]), ("G*+S*", second[2])):
        pres[label] = replay(f"{label} full", inputs, kw)
        prefix = replay(f"{label} prefix parity", short, kw)
        np.testing.assert_array_equal(
            prefix.to_numpy(), pres[label].reindex(prefix.index).to_numpy()
        )
    changed = glicko.roster_changes(inputs)
    results = {
        label: glicko.sections(inputs, pairs, pre, test) for label, pre in pres.items()
    }
    lines = [
        f"# Joint Glicko RD + non-major update scale ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/elo_glicko_scale.py`. Research only; published behavior unchanged. Negative Δ log loss is better.\n",
        f"Tune {train[0]}–{train[-1]}; hold out {test[0]}–{test[-1]}. Fixed base: RD (280,140,140,10), information .125, no normalization, provisional_games=0, away_factor=0; published rookie discount retained. Stage 1: floor {{140,180,220}} × information {{.125,.0625}}, new=2×floor, reference=floor, c=10 (six settings, no slope change). Stage 2: non-major domestic slope {{ln(10)/400,.0065,.0070,.0080}} × K {{20,22,24,28}} (16 settings, including G*). Major/international event slope ln(10)/400 and base K 20 throughout; RD still scales player moves. Offsets keep native rules, though earlier ratings can change their values.\n",
        "Both stages minimize games-weighted domestic plus within-other-league Elo log loss on the chronological prefix through the last tuning game, including intervening differently labelled seasons. One training-only upper-edge extension adds slope .0090 and/or K 32 and scores all new Cartesian cells; no lower-edge extension or second extension. Choices are frozen before held-out scoring in gitignored `data/research/elo_glicko_scale/selection.json`.\n",
        f"Extension: {len(extra)} new cells; initial winner {initial[1]}; final winner {second[1]}.\n",
        "Scoring reuses elo_glicko.py unchanged: leave-one-year-out forecast curves within each partition, replay-specific Form opponent adjustment/weights and FORGE blends. The within-other-league helper fits Form weights on all other major-league years, including tuning years. This is a rating-design comparison, not an earlier-only deployment simulation; existing international calibration behavior is inherited unchanged. Intervals are 95% paired individual-game bootstraps, without series clustering or multiplicity adjustment. Historical holdouts have been viewed in earlier research. Selected prefix/full replay equality is checked exactly.\n",
        "## Tuning\n",
        "| Stage | Configuration | Objective |",
        "|---|---|---:|",
    ]
    for stage, label, _, loss in tuning:
        lines.append(f"| {stage} | {label} | {loss:.8f} |")
    lines += [
        f"\nG*: `{first[2]}`.\n",
        f"G*+S*: {second[1]}; tuning objective {second[0]:.8f}.\n",
    ]
    all_rows = []
    summary = {}
    for name, base, variant in (
        ("(a) G* vs published", "Published", "G*"),
        ("(b) G*+S* vs published", "Published", "G*+S*"),
        ("(c) G*+S* vs G*", "G*", "G*+S*"),
    ):
        rows = glicko.comparison(results[base], results[variant])
        roster = glicko.comparison(results[base], results[variant], changed)
        all_rows.append(rows + [(f"Roster change: {r[0]}", *r[1:]) for r in roster])
        summary[name] = {"all": rows, "roster": roster}
        lines += [f"## {name}\n"]
        lines += [
            x.replace("Published loss", f"{base} loss") for x in glicko.table(rows)
        ]
        lines += [
            "\n### Roster-change slices\n",
            "Either team changed its known five starters since its last game; first appearances excluded. Full-section fits are sliced after scoring.\n",
        ]
        lines += [
            x.replace("Published loss", f"{base} loss") for x in glicko.table(roster)
        ]
    decision = verdict(*all_rows)
    median = float(np.median([r[2] for r in timings]))
    lines += [
        "\n## Verdict\n",
        f"**{decision}**\n",
        "Ship G*+S* requires no significantly worse section in (b) or (c), and a significant (c) gain in Elo cross-league or Elo/FORGE within other leagues. Otherwise ship G* only if (a) has a significant gain and no significant regression; otherwise ship neither. Guards include all roster-change slices. This is the requested research verdict; no production change is made. Any optimum still at the final grid boundary remains unresolved.\n",
        "## Replay runtime\n",
        f"Median across all {len(timings)} replays: {median:.2f} s (prefix and full replays mixed). Total run {time.perf_counter() - started:.1f} s. Every replay is recorded below.\n",
        "| Replay | Games | Seconds |",
        "|---|---:|---:|",
    ]
    lines += [f"| {label} | {n:,} | {seconds:.2f} |" for label, n, seconds in timings]
    (audit / "results.json").write_text(
        json.dumps(
            {"comparisons": summary, "verdict": decision, "median_seconds": median},
            indent=2,
        )
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print(f"{decision}; median replay {median:.2f}s; wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
