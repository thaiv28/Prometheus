"""Test three fixed simplifications against published player-RD Elo.

No parameters are tuned: own-game RD information slope, move_down_bonus=0,
and both. The three arms are fixed before any held-out scoring. Report the
existing <=2021 domestic/other Elo objective for context, then all seven 2022+
sections and roster-change slices using the unchanged Glicko harness. No edge
extension applies to these fixed mechanisms. Production defaults stay unchanged.

Usage:
    VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_rd_simplify.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_glicko as g

VARIANTS = {
    "Game slope": {"player_rd_game_slope": True},
    "No move-down": {"move_down_bonus": 0},
    "Both": {"player_rd_game_slope": True, "move_down_bonus": 0},
}
AUDIT = Path("data/research/elo_rd_simplify")
REPORT = Path("docs/research/elo_rd_simplify.md")


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    # Freeze before loading/scoring the held-out data; no adaptive grid.
    (AUDIT / "protocol.json").write_text(json.dumps(VARIANTS, indent=2))
    inputs = g.ev.load_inputs(verbose=False)
    pairs = g.em.load_pair_games()
    train, test = g.ev.split_years(inputs.frame.year.unique())
    short = g.tuning_inputs(inputs, train)
    margin = g.ev.game_length_margin()
    objectives = {}
    for label, kw in {"Published": {}, **VARIANTS}.items():
        pre = g.ev.replay(short, margin, **kw)
        objectives[label] = float(g.enp.objective(inputs, pairs, pre, train))
        print(f"{label}: training objective {objectives[label]:.8f}", flush=True)
    pres, timings = {}, {name: [] for name in ("Published", *VARIANTS)}
    # Three interleaved full replays per arm; reverse order in round two.
    for order in (list(timings), list(reversed(timings)), list(timings)):
        for name in order:
            tick = time.perf_counter()
            pres[name] = g.ev.replay(inputs, margin, **VARIANTS.get(name, {}))
            timings[name].append(time.perf_counter() - tick)
            print(f"{name}: replay {timings[name][-1]:.2f}s", flush=True)
    # A DB built from published Elo is an independent default reproduction check.
    built = inputs.db_pre_match
    np.testing.assert_allclose(
        pres["Published"].reindex(built.index), built, atol=1e-9, rtol=0
    )
    for name, kw in VARIANTS.items():
        prefix = g.ev.replay(short, margin, **kw)
        np.testing.assert_array_equal(prefix, pres[name].reindex(prefix.index))
    changed = g.roster_changes(inputs)
    baseline = g.sections(inputs, pairs, pres["Published"], test)
    lines = [
        "# Elo RD slope and move-down simplifications\n",
        "Fixed three-arm experiment against published Elo (base 00237c0). "
        "Defaults remain unchanged. Negative Δ log loss is better.\n",
        f"Training objective: games-weighted domestic + within-other-league Elo, {train[0]}–{train[-1]}. "
        f"Held out: {test[0]}–{test[-1]}. No tuning, selection or boundary extension: all three mechanisms fixed in code before scoring. "
        "PLAYER_RD_INFORMATION remains .125, K 20 and all other settings published.\n",
        "Own-game slope uses OTHER_LEAGUE_SLOPE (.0065) for non-major domestic games and ln(10)/400 otherwise, "
        "in both slope² and E of the RD information term. No move-down disables only the stored +25 transfer bonus.\n",
        "Unchanged elo_glicko sections/comparison and elo_variants replay: leave-one-year-out forecast curves within each partition, "
        "replay-specific Form weights/opponent adjustment and FORGE refits. Other-league Form fits inherit other major-league years. "
        "This is a rating-design comparison, not an earlier-only deployment simulation. "
        "95% paired individual-game bootstrap intervals, without series clustering or multiplicity adjustment; historical holdouts were viewed in earlier research. "
        "Published DB/replay equality and each variant's prefix/full equality checked.\n",
        "| Fixed setting | ≤2021 objective |\n|---|---:|",
        *[f"| {name} | {loss:.8f} |" for name, loss in objectives.items()],
    ]
    summary = {}
    for name in VARIANTS:
        print(f"Scoring {name}", flush=True)
        scores = g.sections(inputs, pairs, pres[name], test)
        rows = g.comparison(baseline, scores)
        roster = g.comparison(baseline, scores, changed)
        passes = not any(r[4] > 0 for r in rows)
        summary[name] = {
            "kwargs": VARIANTS[name],
            "rows": rows,
            "roster": roster,
            "held_out_pass": passes,
        }
        lines += [
            f"\n## {name}\n",
            *g.table(rows),
            "\n### Roster-change diagnostic\n",
            *g.table(roster),
            f"\nHeld-out gate: **{'PASS' if passes else 'FAIL'}**. Roster-change slices are diagnostic; the requested gate guards forecast sections.\n",
        ]
    lines += [
        "\n## Runtime\n",
        "Three interleaved full replays per setting, reverse order in round two; VECLIB_MAXIMUM_THREADS=1. Concurrent machine load can affect timings.\n",
        "| Setting | Median seconds | Runs |\n|---|---:|---|",
    ]
    lines += [
        f"| {name} | {np.median(times):.2f} | {', '.join(f'{t:.2f}' for t in times)} |"
        for name, times in timings.items()
    ]
    lines += [
        "\n## Decision rule\n",
        "A simplification is worth it only if no forecast section (held-out and native) and no native markets series row is significantly worse. Significant gains are reported but not required. Run native for every held-out passer; see [native comparisons](elo_rd_simplify_native.md). No defaults or weights are promoted by this experiment.\n",
    ]
    (AUDIT / "results.json").write_text(
        json.dumps(
            {"variants": summary, "timings": timings, "objectives": objectives},
            indent=2,
        )
    )
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT}", flush=True)


if __name__ == "__main__":
    main()
