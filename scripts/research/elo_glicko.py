"""Frozen: runs against `prometheus/elo.py` at commit 00237c0 (options since removed).

elo_glicko.py: Glicko-style player uncertainty versus published player Elo.

V2 protocol fixed before tuning: floor RD {60,80,100}, new/floor ratio
{1.5,2,2.5}, inactivity growth {10,20,35} points/sqrt(day), per-game information
multiplier {0.25,0.5,1}. Reference equals floor: settled-player RD weight is 1,
so only uncertainty increases K. Three arms: replace provisional/away with RD
(rookie discount kept or dropped), and RD on top of all published pieces.
81 candidates per arm. One predeclared local Cartesian boundary extension per
arm: keep its initial winner's coordinates and add the outward endpoint for
any boundary coordinate (floor 40/140, ratio 1.1/3.25, growth 0/55, information
0.125/2). At most 15 additional candidates per arm. No further extension;
remaining boundary optima are explicitly reported, not declared bracketed.
K, margins, offsets and transfers stay published. No expectation attenuation,
league RD or volatility estimation; this is not full Glicko-2.

Tune only on <=2021, minimizing games-weighted domestic plus within-other-league
Elo log loss, exactly as elo_new_players.py. Freeze each arm's winner and the
single overall winner before scoring 2022+. Use the existing harness's out-of-year
curves, refitted Form and FORGE, and paired game bootstrap intervals. As in that
harness, evaluation curves/blends are leave-one-year-out within the requested
partition, not an expanding-window deployment simulation. Repeat every section
on games where either team changed its five known starters since its last game;
first appearances and unknown/incomplete lineups do not establish a change.

V2 applies RD weights independently to each player. No side normalization:
settled players keep their baseline move even beside or against uncertain
players. Applied team means can be unequal, as with published provisional/away
factors. League offsets remain published. V1 side normalization is archived.

Usage:
    VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_glicko.py --out docs/research/elo_glicko.md
"""

import argparse
import datetime
import itertools
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_new_players as enp
import elo_variants as ev
import evaluate_metrics as em

from prometheus.evaluation import paired_bootstrap

ARMS = ("Replace, keep discount", "Replace, drop discount", "On top")


AXES = ((60, 80, 100), (1.5, 2, 2.5), (10, 20, 35), (0.25, 0.5, 1))
OUTWARD = ((40, 140), (1.1, 3.25), (0, 55), (0.125, 2))
V1_REPORT = Path(__file__).resolve().parents[2] / "docs/research/elo_glicko_v1.md"


def parameters(arm, coordinates):
    floor, ratio, growth, information = coordinates
    kw = {
        "player_rd": (floor * ratio, floor, floor, growth),
        "player_rd_information": information,
        "player_rd_normalize": False,
    }
    if arm != "On top":
        kw.update(provisional_games=0, away_factor=0)
    if arm == "Replace, drop discount":
        kw["rookie_penalty"] = 0
    return kw


def coordinates(kw):
    new, floor, _, growth = kw["player_rd"]
    return (floor, new / floor, growth, kw["player_rd_information"])


def designs():
    """243 initial candidates, all with reference equal to floor."""
    return {arm: [parameters(arm, x) for x in itertools.product(*AXES)] for arm in ARMS}


def extension(arm, kw):
    """Single local Cartesian extension, determined only by the tuning winner."""
    incumbent = coordinates(kw)
    axes = []
    for value, grid, outward in zip(incumbent, AXES, OUTWARD):
        extra = (outward[0],) if value == grid[0] else ()
        if value == grid[-1]:
            extra = (outward[1],)
        axes.append((value,) + extra)
    return [parameters(arm, x) for x in itertools.product(*axes) if x != incumbent]


def boundaries(kw, expanded=False):
    names = ("floor", "new/floor", "growth", "information")
    limits = OUTWARD if expanded else AXES
    return [
        name
        for name, value, grid in zip(names, coordinates(kw), limits)
        if value in (grid[0], grid[-1])
    ]


def tuning_inputs(inputs, years):
    """Replay the chronological prefix through the last tuning-season game.

    Include intervening games filed under other seasons, exactly as full replay
    does; never filter the chronology by season labels. Scoring still uses years.
    """
    positions = np.flatnonzero(inputs.games["year"].isin(years).to_numpy())
    return replace(inputs, games=inputs.games.iloc[: positions[-1] + 1], cache={})


def roster_changes(inputs):
    """Game IDs with a real five-starter change; order within a lineup is irrelevant."""
    last = {}
    changed = set()
    for row in inputs.games.itertuples(index=False):
        for team in (row.teamid, row.opponent_teamid):
            roster = inputs.rosters.get((row.gameid, team))
            roster = frozenset(roster) if roster else last.get(team)
            previous = last.get(team)
            if (
                roster is not None
                and previous is not None
                and len(roster) == len(previous) == 5
                and roster != previous
            ):
                changed.add(row.gameid)
            if roster is not None:
                last[team] = roster
    return changed


def sections(inputs, pairs, pre, years):
    """Aligned (game IDs, per-game losses) for all seven existing sections."""
    scores = ev.score(inputs, pre, years=years)
    out = {}
    for metric, label in (("elo_live", "Elo"), ("forge", "FORGE")):
        for subset in ev.TEST_SETS:
            mask = scores.mask(subset)
            out[f"{label}, {subset.lower()}"] = (
                scores.games.loc[mask, "gameid"].to_numpy(),
                scores.log_loss(metric, subset),
            )
    for label, fn in (
        ("Elo, other leagues", lambda: enp.other_losses(pairs, pre, years)),
        (
            "FORGE, other leagues",
            lambda: enp.other_forge_losses(inputs, pairs, pre, years),
        ),
        ("Elo, cross-league", lambda: enp.cross_losses(pairs, pre, years)),
    ):
        games, losses = fn()
        out[label] = (games["gameid"].to_numpy(), losses)
    return out


def comparison(base, variant, changed=None):
    rows = []
    for section, (ids, losses) in variant.items():
        base_ids, baseline = base[section]
        np.testing.assert_array_equal(ids, base_ids)
        mask = (
            np.ones(len(ids), dtype=bool)
            if changed is None
            else np.isin(ids, list(changed))
        )
        mean, lo, hi = paired_bootstrap(losses[mask], baseline[mask])
        rows.append((section, int(mask.sum()), baseline[mask].mean(), mean, lo, hi))
    return rows


def table(rows):
    lines = [
        "| Section | Games | Published loss | Δ log loss (95% CI) |",
        "|---|---:|---:|---|",
    ]
    for section, n, baseline, mean, lo, hi in rows:
        lines.append(
            f"| {section} | {n:,} | {baseline:.5f} | {mean:+.5f} ({lo:+.5f} to {hi:+.5f}) |"
        )
    return lines


def timing_check(inputs, margin, kw):
    """Three paired full replays per setting, reversing order on round two."""
    times = {"published": [], "rd": []}
    for order in (("published", "rd"), ("rd", "published"), ("published", "rd")):
        for label in order:
            start = time.perf_counter()
            ev.replay(inputs, margin, **(kw if label == "rd" else {}))
            times[label].append(time.perf_counter() - start)
    return times


def timing_text(times):
    return (
        "Paired full-replay timing check (three runs each, order AB/BA/AB): "
        f"published median {np.median(times['published']):.2f} s "
        f"({min(times['published']):.2f}–{max(times['published']):.2f}); "
        f"selected RD median {np.median(times['rd']):.2f} s "
        f"({min(times['rd']):.2f}–{max(times['rd']):.2f}). "
        "Use this paired check for overhead; the initial replay and later selected "
        "replays can face different concurrent machine load.\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=Path("docs/research/elo_glicko.md"))
    args = ap.parse_args()
    start = time.perf_counter()
    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    train, test = ev.split_years(inputs.frame["year"].unique())
    _, reproduction = ev.reproduction_check(inputs)
    print(reproduction, flush=True)
    margin = ev.game_length_margin()
    t = time.perf_counter()
    base = ev.replay(inputs, margin)
    baseline_time = time.perf_counter() - t
    base_objective = enp.objective(inputs, pairs, base, train)
    audit = Path("data/research/elo_glicko/v2")
    audit.mkdir(parents=True, exist_ok=True)
    protocol = {
        "axes": AXES,
        "outward": OUTWARD,
        "extension": "one local Cartesian extension per arm at initial winner",
        "weighting": "independent per-player RD squared / floor squared; no side normalization",
        "grid": designs(),
        "train_years": train,
        "test_years": test,
    }
    # Written before any candidate is scored. Checkpoints allow interrupted runs
    # to resume with the identical protocol, without retuning on held-out results.
    protocol_text = json.dumps(protocol, indent=2)
    protocol_path = audit / "protocol.json"
    if protocol_path.exists() and protocol_path.read_text() != protocol_text:
        raise ValueError("Existing v2 checkpoint has a different protocol")
    protocol_path.write_text(protocol_text)
    checkpoint = audit / "tuning.jsonl"
    saved = (
        [json.loads(x) for x in checkpoint.read_text().splitlines()]
        if checkpoint.exists()
        else []
    )
    cached = {json.dumps(r["kw"], sort_keys=True): r for r in saved}
    short_inputs = tuning_inputs(inputs, train)
    short_base = ev.replay(short_inputs, margin)
    np.testing.assert_array_equal(
        short_base.to_numpy(), base.reindex(short_base.index).to_numpy()
    )
    print(
        f"Tuning prefix: {len(short_inputs.games):,}/{len(inputs.games):,} games; exact baseline agreement",
        flush=True,
    )
    timings, winners, tuning, initial_winners = [], {}, [], {}

    def tune(arm, grid, stage):
        candidates = []
        for kw in grid:
            key = json.dumps(kw, sort_keys=True)
            cached_run = cached.get(key)
            if cached_run is None:
                t = time.perf_counter()
                pre = ev.replay(short_inputs, margin, **kw)
                elapsed = time.perf_counter() - t
                objective = enp.objective(inputs, pairs, pre, train)
                cached_run = {
                    "arm": arm,
                    "stage": stage,
                    "kw": kw,
                    "objective": objective,
                    "seconds": elapsed,
                }
                with checkpoint.open("a") as f:
                    f.write(json.dumps(cached_run) + "\n")
                cached[key] = cached_run
            objective = cached_run["objective"]
            timings.append(cached_run["seconds"])
            candidates.append((objective, kw))
            tuning.append((arm, stage, kw, objective))
            print(
                f"{arm} {stage} {coordinates(kw)}: {objective:.6f}; replay {timings[-1]:.2f}s",
                flush=True,
            )
        return min(candidates, key=lambda x: x[0])

    for arm, grid in designs().items():
        initial = tune(arm, grid, "initial")
        initial_winners[arm] = initial
        extra = extension(arm, initial[1])
        winners[arm] = (
            min([initial, tune(arm, extra, "extension")], key=lambda x: x[0])
            if extra
            else initial
        )
    best_arm = min(winners, key=lambda arm: winners[arm][0])
    # Freeze ALL choices before the first held-out score.
    (audit / "selection.json").write_text(
        json.dumps(
            {
                **protocol,
                "tuning": tuning,
                "best_arm": best_arm,
                "initial_winners": initial_winners,
                "winners": winners,
            },
            indent=2,
        )
    )
    print(f"Frozen overall winner: {best_arm} {winners[best_arm][1]}", flush=True)
    changed = roster_changes(inputs)
    baseline = sections(inputs, pairs, base, test)
    lines = [
        f"# Player Elo rating uncertainty ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/elo_glicko.py`. Research only; no published behavior, "
        "weights or DB changed. Negative Δ means improvement over current published Elo.\n",
        f"Tune {train[0]}–{train[-1]}; report {test[0]}–{test[-1]}. V2 fixed grid: "
        "RD_min ∈ {60,80,100}, RD_new/RD_min ∈ {1.5,2,2.5}, c ∈ {10,20,35}, "
        "information multiplier m ∈ {0.25,0.5,1}: 81 candidates per arm, 243 initially. "
        "RD_ref=RD_min for every setting. Objective: games-weighted domestic plus "
        "within-other-league Elo log loss. Each arm and the overall winner are selected "
        "only on tuning results before held-out scoring.\n",
        "One extension was fixed in advance: at each arm's initial winner, retain its "
        "coordinates and add the outward value for every boundary coordinate, testing "
        "their local Cartesian product once (floor 40/140, ratio 1.1/3.25, growth 0/55, "
        "information 0.125/2). This is a local extension, not the full enlarged grid. "
        "Any remaining outer-boundary optimum is unresolved; no second extension.\n",
        "RD² grows by c² × days inactive (capped at RD_new²), then after each game "
        "shrinks to max(RD_min², 1/(1/RD² + m q² E(1−E))), q=ln(10)/400. "
        "Pre-update RD²/RD_min² multiplies moves: at the floor the RD weight is exactly 1. "
        "Without legacy multipliers a settled player moves at K=20 even beside or "
        "against uncertain players. With legacy multipliers enabled the existing "
        "provisional/away factors also apply. No side normalization: applied team "
        "means can differ (as with published provisional/away factors); discount "
        "decay also affects effective changes. League offsets, K and transfers stay "
        "published. No g(RD), league RD or volatility estimation.\n",
        "At E=0.5 without inactivity, RD 250→100 takes about 11 games at m=1, "
        "21 at m=0.5 and 41 at m=0.25. Thus slower information shrinkage is "
        "explicitly tested. The wider floor/ratio grid changes this duration too.\n",
        f"Tuning replays use the chronological prefix ({len(short_inputs.games):,} of "
        f"{len(inputs.games):,} games), including intervening differently labelled seasons. "
        "Published prefix equality is exact; selected RD prefixes are checked against "
        "full replays before held-out scoring. Checkpoints and the pre-score frozen "
        "protocol/choices live under gitignored `data/research/elo_glicko/v2/`.\n",
        "Scoring follows the existing research harness: leave-one-year-out win curves "
        "within each requested partition; Form opponent adjustment and Form/FORGE "
        "weights are refit for every selected replay. For major sections Form fits "
        "use the requested partition; the shared within-other-league helper fits "
        "Form feature weights on all other major-league years in the full frame, "
        "including tuning years. This is not a fully chronological "
        "deployment simulation. Intervals are 95% paired bootstraps over individual "
        "games (not series); sections and secondary arms are not multiplicity-adjusted.\n",
        "## Published replay reproduction\n",
        "```text",
        reproduction,
        "```\n",
        "## Tuning\n",
        f"Published objective: {base_objective:.6f}.\n",
        "| Arm | Stage | Parameters (floor, new/floor, growth, information) | Objective |",
        "|---|---|---|---:|",
    ]
    for arm, stage, kw, objective in tuning:
        lines.append(f"| {arm} | {stage} | {coordinates(kw)} | {objective:.6f} |")
    lines += [f"\nOverall tuning winner: **{best_arm}**, `{winners[best_arm][1]}`.\n"]
    for arm in ARMS:
        initial = initial_winners[arm]
        final = winners[arm]
        lines.append(
            f"{arm}: initial winner `{coordinates(initial[1])}` ({initial[0]:.6f}); "
            f"initial boundary coordinates: {', '.join(boundaries(initial[1])) or 'none'}. "
            f"After one extension: `{coordinates(final[1])}` ({final[0]:.6f}); "
            f"remaining outer boundaries: {', '.join(boundaries(final[1], expanded=True)) or 'none'}.\n"
        )
    best_rows = None
    full_timings = []
    for arm, (objective, kw) in winners.items():
        t = time.perf_counter()
        pre = ev.replay(inputs, margin, **kw)
        full_timings.append(time.perf_counter() - t)
        short = ev.replay(short_inputs, margin, **kw)
        np.testing.assert_array_equal(
            short.to_numpy(), pre.reindex(short.index).to_numpy()
        )
        result = sections(inputs, pairs, pre, test)
        rows = comparison(baseline, result)
        lines += [
            f"## Held out: {arm}\n",
            f"Parameters: `{kw}`; tuning objective {objective:.6f}.\n",
        ]
        lines += table(rows)
        lines += [
            "\n### Roster-change slice\n",
            "Either team changed its known five starters since its previous game, "
            "across all competitions; first appearances excluded. Curves and blends "
            "are fit on the full evaluation sections, then sliced.\n",
        ]
        lines += table(comparison(baseline, result, changed))
        if arm == best_arm:
            best_rows = rows
    gains = [r[0] for r in best_rows if r[5] < 0]
    harms = [r[0] for r in best_rows if r[4] > 0]
    paired_times = timing_check(inputs, margin, winners[best_arm][1])
    gate = (
        "Passes the benchmark significance gate"
        if gains and not harms
        else "Fails the benchmark significance gate"
    )
    verdict = (
        "Iterate; do not ship"
        if gains and not harms
        else "Drop this tested design; do not ship"
    )
    lines += [
        "\n## Verdict and limits\n",
        f"**{verdict}. {gate}.** Overall tuning winner's significant gains: "
        f"{', '.join(gains) or 'none'}; significant regressions: {', '.join(harms) or 'none'}. "
        "Shipping requires a significant targeted gain and no significant guarded "
        "regression; secondary-arm results cannot replace the tuning-selected winner. "
        "RD models uncertainty, while the rookie discount models a shifted prior. "
        "A failed replacement need not invalidate the discount. The selected floor "
        "and information multiplier remain at expanded boundaries; iterate on that "
        "unresolved tuning choice before selecting production constants. In normalized "
        "variance units the effective parameters are new/floor, c/floor and "
        "m × floor², so floor and information trade off rather than being independent "
        "mechanisms. No optional league-RD "
        "experiment or full Glicko-2 volatility fit was attempted.\n",
        "V1 also normalized side means, which could change a settled player's "
        "effective K when lineup uncertainty differed. V2 removes that normalization "
        "to enforce the requested per-player weight literally. An initial v2 tuning "
        "attempt retaining normalization was aborted before held-out scoring; its "
        "scores were discarded and the same grid restarted with direct weights.\n",
        "## Runtime\n",
        f"Published full replay: {baseline_time:.2f} s. Selected RD full replays: "
        f"median {np.median(full_timings):.2f} s, range {min(full_timings):.2f}–{max(full_timings):.2f} s. "
        "Tuning-prefix RD replays: "
        f"median {np.median(timings):.2f} s, range {min(timings):.2f}–{max(timings):.2f} s "
        f"({len(timings)} settings). This invocation: {time.perf_counter() - start:.1f} s "
        "(checkpoint reuse, if any, excludes earlier invocation overhead). "
        "VECLIB_MAXIMUM_THREADS=1; concurrent local agents can affect wall times. "
        "No new CI step, dependency, DB rebuild or production fit.\n",
        timing_text(paired_times),
    ]
    lines += [
        "## v1 (flawed: reference above floor)\n",
        "All 24 settings had RD_ref > RD_min, reducing settled-player K to about "
        "8.9 or 5 rather than 20; this confounds uncertainty with a global K reduction. "
        "The original numbers below are preserved for audit and do not establish "
        "that uncertainty itself fails. Reproduce v1 with `player_rd_information=1` "
        "and `player_rd_normalize=True`.\n",
        V1_REPORT.read_text().split("\n", 1)[1].replace("\n##", "\n###"),
    ]
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
