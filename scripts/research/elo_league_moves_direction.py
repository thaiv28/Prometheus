"""
elo_league_moves_direction.py: should a player who moves between a major and another
league count less (moving up) or more (moving down) than the offsets say?

Published Elo keeps a moving player's rating, converted through the two leagues'
offsets. Residual checks on 2016 on (work log 2026-10-12) found teams with players who
moved into a major in their last 30 games do worse than Elo expects (z −2.7), and teams
with players who moved down from a major do better (z +3.9). This replays published Elo
(rookie discount on; `elo_variants.replay`) with the `compute_elo_records` options
`move_up_penalty` U, `move_down_bonus` V and `move_games` N, fixed in advance:

- **Stored** (N 0): a player moving into a major (`elo.MAJOR_LEAGUES`, the four) from
  another league loses U points of their rating; one moving from a major down gains V.
- **Fading over 30 / 60 games**: the same change counts only toward team ratings,
  fading linearly to nothing over the player's next N games (not stored, like the
  rookie discount).

U and V each in {0, 25, 50, 75, 100}. Tuning objective, fixed in advance: mean Elo log
loss over domestic (major-league), within-other-league and cross-league games up to
2021, games-weighted. Held out (2022 on), each design's best against published Elo on
the same games: Elo and FORGE domestic and international (`elo_variants.score`), within
other leagues Elo on per-league curves and FORGE (Elo + Form), and cross-league Elo
by kind. The market benchmark is run separately on DBs built with the chosen variant
(`--write-db`).

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_league_moves_direction.py --out docs/research/elo_league_moves_direction.md
    uv run python scripts/research/elo_league_moves_direction.py --write-db '{"move_up_penalty": 50}'
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_new_players as enp
import elo_variants as ev
import evaluate_metrics as em

from prometheus import elo
from prometheus.evaluation import paired_bootstrap

TRAIN_LAST = 2021
STEPS = (0, 25, 50, 75, 100)
DESIGNS = {
    name: [
        {"move_up_penalty": u, "move_down_bonus": v, "move_games": n}
        for u in STEPS
        for v in STEPS
        if u or v
    ]
    for name, n in (
        ("Stored", 0),
        ("Fading over 30 games", 30),
        ("Fading over 60 games", 60),
    )
}
CROSS_KINDS = ("all", "major v major", "major v other", "other v other")


def objective(inputs, pairs, pre, years):
    dom = ev.score(inputs, pre, years=years, forge=False).log_loss(
        "elo_live", "Domestic"
    )
    _, oth = enp.other_losses(pairs, pre, years)
    _, cross = enp.cross_losses(pairs, pre, years)
    return np.concatenate([dom, oth, cross]).mean()


def cross_by_kind(pairs, pre, years):
    games, losses = enp.cross_losses(pairs, pre, years)
    out = {"all": losses}
    for kind in CROSS_KINDS[1:]:
        out[kind] = losses[(games["kind"] == kind).to_numpy()]
    return out


def sections(inputs, pairs, pre, years):
    """Held-out log losses per section (arrays, one per game)."""
    s = ev.score(inputs, pre, years=years)
    out = {
        f"{name}, {test_set.lower()}": s.log_loss(metric, test_set)
        for metric, name in (("elo_live", "Elo"), ("forge", "FORGE"))
        for test_set in ("Domestic", "International")
    }
    out["Elo, other leagues"] = enp.other_losses(pairs, pre, years)[1]
    out["FORGE, other leagues"] = enp.other_forge_losses(inputs, pairs, pre, years)[1]
    for kind, losses in cross_by_kind(pairs, pre, years).items():
        out[f"Elo, cross-league {kind}"] = losses
    return out


def _cell(variant, base):
    mean, lo, hi = paired_bootstrap(variant, base)
    star = " **" if lo > 0 or hi < 0 else ""
    return f"{mean:+.4f} ({lo:+.4f} to {hi:+.4f}){star}"


def write_db(params):
    """Rebuild the Elo tables with `params` on top of the published options."""
    original = elo.compute_elo_records

    def patched(*args, **kwargs):
        return original(*args, **{**params, **kwargs})

    elo.compute_elo_records = patched
    try:
        elo.bootstrap_elo("game_length")
    finally:
        elo.compute_elo_records = original


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--write-db", help="JSON options: rebuild the DB's Elo with them")
    args = ap.parse_args()
    if args.write_db is not None:
        write_db(json.loads(args.write_db))
        return

    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    years = sorted(inputs.frame["year"].unique())
    train = [y for y in years if y <= TRAIN_LAST]
    test = [y for y in years if y > TRAIN_LAST]
    margin = ev.game_length_margin()
    base_pre = ev.replay(inputs, margin)

    lines = [
        f"## League moves by direction ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/elo_league_moves_direction.py`. Tuned on "
        f"{train[0]}–{train[-1]} (objective: mean Elo log loss over domestic, "
        "within-other-league and cross-league games), reported on "
        f"{test[0]}–{test[-1]}. Δ is variant minus published Elo (rookie discount on) "
        "log loss, negative is better, paired bootstrap over games; ** marks an "
        "interval that excludes 0.\n",
        "### Tuning\n",
        "| Design | Best parameters | Train objective | Published |",
        "|---|---|---:|---:|",
    ]
    base_obj = objective(inputs, pairs, base_pre, train)
    chosen = {}
    for design, grid in DESIGNS.items():
        scored = []
        for params in grid:
            pre = ev.replay(inputs, margin, **params)
            scored.append((objective(inputs, pairs, pre, train), params))
            print(f"  {design} {params}: {scored[-1][0]:.5f}", flush=True)
        best_obj, best = min(scored, key=lambda t: t[0])
        chosen[design] = best
        lines.append(f"| {design} | {best} | {best_obj:.5f} | {base_obj:.5f} |")

    base = sections(inputs, pairs, base_pre, test)
    variants = {
        f"{design} {params}": sections(
            inputs, pairs, ev.replay(inputs, margin, **params), test
        )
        for design, params in chosen.items()
    }
    lines += [
        "\n### Held out\n",
        "| Section | n | Published | " + " | ".join(variants) + " |",
        "|---|---:|---:|" + "---|" * len(variants),
    ]
    for section, b in base.items():
        cells = []
        for v in variants.values():
            assert len(v[section]) == len(b), section
            cells.append(_cell(v[section], b))
        lines.append(
            f"| {section} | {len(b):,} | {b.mean():.4f} | " + " | ".join(cells) + " |"
        )
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)


if __name__ == "__main__":
    main()
