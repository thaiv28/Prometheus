"""Test Glicko-2 volatility on published player RD, without changing Elo defaults.

Fixed initial grid: tau {0.3,0.6,1.2} x sigma0 {0.03,0.06,0.10} x
period_days {7,30}. Minimize games-weighted domestic + within-other-league
Elo log loss through 2021, then freeze before scoring 2022+. Extend once at
an edge: local Cartesian product of the initial winner and its outward
neighbor on each edge axis (tau .15/2.4, sigma0 .015/.16, days 3.5/60).
No second extension. Keep all published RD shrink, floor, Elo and slope rules.

Usage:
    VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_glicko2.py

Outputs: report docs/research/elo_glicko2.md and gitignored protocol, selection,
results and season-end player sigma snapshots in data/research/elo_glicko2/.
Native DB benchmark checks are run separately; see the generated report.
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
import elo_glicko as glicko

from prometheus import elo

AXES = ((0.3, 0.6, 1.2), (0.03, 0.06, 0.10), (7, 30))
OUTWARD = ((0.15, 2.4), (0.015, 0.16), (3.5, 60))
AUDIT = Path("data/research/elo_glicko2")


def extension(best):
    """One local outward extension, specified before any scoring."""
    axes = []
    for x, axis, endpoints in zip(best, AXES, OUTWARD):
        options = [x]
        if x == axis[0]:
            options.append(endpoints[0])
        elif x == axis[-1]:
            options.append(endpoints[1])
        axes.append(options)
    return [x for x in itertools.product(*axes) if x != tuple(best)]


def dump(name, value):
    (AUDIT / name).write_text(json.dumps(value, indent=2))


def sigma_distribution(inputs, kw, test):
    """Last observed posterior per player/calendar season; held-out seasons only."""
    start = time.perf_counter()
    records, _, _ = elo.compute_elo_records(
        inputs.games[glicko.ev.ELO_COLUMNS],
        elo.calculate_game_length_elo_change,
        rosters=inputs.rosters,
        player_records=True,
        **kw,
    )
    states = records.attrs["player_volatility"]
    # Synthetic fallback team players do not describe individual players.
    states = states[~states.playerid.map(lambda p: isinstance(p, tuple))].copy()
    states["year"] = states.date.dt.year
    states = states[states.year.isin(test)]
    states = states.drop_duplicates(["playerid", "year"], keep="last")
    states["tier"] = np.where(
        states.home_league.isin(elo.MAJOR_LEAGUES), "Major", "Other"
    )
    states.to_csv(AUDIT / "season_end_sigma.csv", index=False)
    lines = [
        "| Season | Tier | Players | σ p05 | σ p25 | σ median | σ p75 | σ p95 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for (year, tier), group in states.groupby(["year", "tier"]):
        quantiles = group.sigma.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).to_numpy()
        values = " | ".join(f"{x:.5f}" for x in quantiles)
        lines.append(f"| {year} | {tier} | {len(group):,} | {values} |")
    return (
        records.set_index(["gameid", "teamid"]).pre_match_elo,
        lines,
        time.perf_counter() - start,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=Path("docs/research/elo_glicko2.md"))
    args = ap.parse_args()
    AUDIT.mkdir(parents=True, exist_ok=True)
    ev, enp = glicko.ev, glicko.enp
    inputs = ev.load_inputs(verbose=False)
    pairs = glicko.em.load_pair_games()
    train, test = ev.split_years(inputs.frame.year.unique())
    short = glicko.tuning_inputs(inputs, train)
    margin = ev.game_length_margin()
    protocol = {
        "axes": AXES,
        "outward": OUTWARD,
        "extension": "one local Cartesian outward extension",
        "train": train,
        "test": test,
        "objective": "games-weighted domestic + within-other-league Elo log loss",
    }
    dump("protocol.json", protocol)
    tuning = []

    def tune(grid, stage):
        candidates = []
        for coords in grid:
            tick = time.perf_counter()
            pre = ev.replay(short, margin, player_volatility=coords)
            loss = float(enp.objective(inputs, pairs, pre, train))
            row = (stage, coords, loss, time.perf_counter() - tick)
            tuning.append(row)
            dump("tuning.json", tuning)
            print(f"{stage} {coords}: objective {loss:.8f}; {row[-1]:.1f}s", flush=True)
            candidates.append((loss, coords))
        return min(candidates, key=lambda x: x[0])

    initial = tune(itertools.product(*AXES), "Initial")
    extra = extension(initial[1])
    selected = (
        min([initial, tune(extra, "Extension")], key=lambda x: x[0])
        if extra
        else initial
    )
    kw = {"player_volatility": selected[1]}
    dump(
        "selection.json",
        {
            "protocol": protocol,
            "initial": initial,
            "extra": extra,
            "selected": selected,
            "kwargs": kw,
        },
    )
    print(f"Frozen selected {kw}", flush=True)
    # No held-out losses are computed before the frozen selection above.
    published = ev.replay(inputs, margin)
    variant = ev.replay(inputs, margin, **kw)
    prefix = ev.replay(short, margin, **kw)
    np.testing.assert_array_equal(
        prefix.to_numpy(), variant.reindex(prefix.index).to_numpy()
    )
    baseline = glicko.sections(inputs, pairs, published, test)
    candidate = glicko.sections(inputs, pairs, variant, test)
    rows = glicko.comparison(baseline, candidate)
    roster = glicko.comparison(baseline, candidate, glicko.roster_changes(inputs))
    passes = any(r[5] < 0 for r in rows) and not any(r[4] > 0 for r in rows)
    native_pre, distribution, diagnostic_time = sigma_distribution(inputs, kw, test)
    np.testing.assert_array_equal(
        native_pre.to_numpy(), variant.reindex(native_pre.index).to_numpy()
    )
    times = glicko.timing_check(inputs, margin, kw)
    dump(
        "results.json",
        {
            "held_out": rows,
            "roster": roster,
            "held_out_pass": passes,
            "timing": times,
            "diagnostic_seconds": diagnostic_time,
        },
    )
    boundary = [
        name
        for name, x, axis, ends in zip(
            ("tau", "sigma0", "period_days"), selected[1], AXES, OUTWARD
        )
        if x in (axis[0], axis[-1], *ends)
    ]
    lines = [
        f"# Glicko-2 player volatility ({datetime.date.today().isoformat()})\n",
        "Research only; published defaults unchanged. Negative Δ log loss is better.\n",
        "## Design and fixed protocol\n",
        "Each player starts at σ0 on the Glicko-2 scale (173.7178 points). Before a game, RD² adds (173.7178σ)² × elapsed whole days / period_days, capped at 280². Published RD floor 140, information .125 and move scaling RD²/140² remain unchanged, as do K 20, rookie discounts, league offsets and non-major update slope .0065. Same-day games add no growth. After growth and before shrink, use φ = RD/173.7178 in the volatility solve; the updated σ affects later games only.\n",
        "For the game's team expectation E and native game-length soft score s, let b = update_slope × 173.7178, v = 1/[b²E(1−E)], Δ = vb(s−E). Every starter uses this team evidence with their own φ and σ; the opposing side has the same v and Δ². No opponent g(RD) or player-specific E. The [Glickman Illinois step](https://www.glicko.net/glicko/glicko2.pdf) solves for σ with tolerance 1e−6 (the current source PDF is dated 2022; the requested 2013 step is retained). This is volatility added to Elo/RD, not the full Glicko-2 rating update.\n",
        f"Initial grid: τ {{.3,.6,1.2}} × σ0 {{.03,.06,.10}} × period_days {{7,30}} (18 settings). Tune {train[0]}–{train[-1]} on the chronological prefix through its final tuning game, including intervening differently labelled seasons; objective: games-weighted domestic + within-other-league Elo log loss. One edge extension uses the initial winner plus its outward neighbor on each boundary axis: τ .15/2.4, σ0 .015/.16, days 3.5/60, all new local Cartesian cells. No second extension. Initial winner {initial[1]}; extension {len(extra)} cells; selected `{kw}` (objective {selected[0]:.8f}). Remaining boundary coordinates: {', '.join(boundary) or 'none'}.\n",
        f"Selection is frozen in `{AUDIT}/selection.json` before {test[0]}–{test[-1]} held-out scoring. Exact prefix/full and native/replay parity passed. Scoring reuses elo_glicko.py: leave-one-year-out curves within each partition, variant-specific Form opponent adjustments and refitted FORGE blends. Within-other-league Form fits use all other major-league years, including tuning years. This evaluates the rating design, not an earlier-only deployment simulation; inherited international calibration remains. Historical holdouts have been viewed in previous research. Intervals are paired individual-game bootstrap 95% CIs; no series clustering or multiplicity correction.\n",
        "## Tuning\n",
        "| Stage | (τ, σ0, days) | Objective | Seconds (replay + scoring) |",
        "|---|---|---:|---:|",
    ]
    lines += [
        f"| {stage} | {coords} | {loss:.8f} | {seconds:.2f} |"
        for stage, coords, loss, seconds in tuning
    ]
    lines += [
        "\n## Held-out vs published\n",
        *glicko.table(rows),
        "\n## Roster-change slices\n",
        "Either team changed its known five starters since its previous game. Unknown/incomplete rosters and first appearances do not establish change. Full-section fits are sliced after scoring; slices are reported separately from the seven-section gate.\n",
        *glicko.table(roster),
        "\n## Season-end volatility by league tier\n",
        "Posterior σ at each player's last observed game in each held-out calendar year, assigned to that game's home-league tier (major vs other). One player-season per row; inactive players are not carried forward and synthetic team fallback players are excluded. 2026 is partial. Quantiles describe states at last observation, without an extra offseason update. Raw snapshots are saved in the audit CSV.\n",
        *distribution,
        "\n## Runtime\n",
        glicko.timing_text(times).replace("selected RD", "selected volatility"),
        f"Additional diagnostic replay with player histories: {diagnostic_time:.2f} s. Diagnostics are collected only when player_records=True; no added CI job or benchmark grid in CI.\n",
        "## Verdict\n",
        f"Held-out gate: **{'PASS' if passes else 'FAIL'}**. Requires a significant gain in at least one of the seven Elo/FORGE target sections and none significantly worse. Roster slices are reported, not extra gate sections. Final adoption also requires no native guarded value significantly worse; see [native comparison](elo_glicko2_native.md). Keep the published default pending that combined verdict; no parameter or weight file is changed by this research. Remaining boundary optima are unresolved.\n",
    ]
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Held-out gate {'PASS' if passes else 'FAIL'}; wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
