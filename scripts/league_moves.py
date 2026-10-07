"""
league_moves.py: convert a player's Elo on a move between leagues by their standing in
the old league instead of by league offsets, then retest linking leagues at
non-international cross-league games (EMEA Masters, cups, promotion).

Published Elo keeps a moving player's rating plus offset: a player at 1,450 in an ERL is
1,450 in the LEC. Linking ERLs at EMEA Masters moved their offsets and those offsets came
into the majors with promoted players, hurting major-league forecasts (work log
2026-10-06). The variant here gives a mover the new league's active average plus
`move_weight` times their distance from the old league's active average, so offsets no
longer travel with players and only decide team-versus-team calls across leagues.

Fixed before the run: move_weight 1 (no tuning), link shares 0.25 and 0.5 (the earlier
test's values), scope all moves or only moves touching a non-major league. Scored like
`evaluate_metrics.py`: domestic and international (Elo and FORGE), cross-league in every
league, and within other leagues (per-league curves), each paired against published Elo.

    uv run python scripts/league_moves.py --out docs/league_moves_report.md

On macOS set VECLIB_MAXIMUM_THREADS=1.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from prometheus.evaluation import (
    cross_league_games,
    game_losses,
    other_league_games,
    out_of_year_league_probabilities,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.types import INTERNATIONAL_LEAGUES

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_variants as ev  # noqa: E402
import evaluate_metrics as em  # noqa: E402

MAJORS = tuple(em.MAJORS)
VARIANTS = {
    "Standing, every move": dict(move="standing"),
    "Standing, moves touching a non-major league": dict(move="standing", move_scope="minor"),
    "Offsets + links 0.25 (earlier test)": dict(link_share=0.25),
    "Standing, every move + links 0.25": dict(move="standing", link_share=0.25),
    "Standing, non-major moves + links 0.25": dict(move="standing", move_scope="minor", link_share=0.25),
    "Standing, every move + links 0.5": dict(move="standing", link_share=0.5),
    "Standing, non-major moves + links 0.5": dict(move="standing", move_scope="minor", link_share=0.5),
    "Links 0.25, team ratings only": dict(link_share=0.25, link_teams_only=True),
    "Links 0.5, team ratings only": dict(link_share=0.5, link_teams_only=True),
}


def pair_frame(inputs):
    g = inputs.games
    return pd.DataFrame({
        "gameid": g["gameid"], "year": g["year"], "league": g["league"],
        "teamid": g["teamid"], "opponent_teamid": g["opponent_teamid"], "won": g["result"].astype(int),
    })


def with_gap(frame, pre):
    a = pre.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["teamid"]])).to_numpy()
    b = pre.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["opponent_teamid"]])).to_numpy()
    return frame.assign(elo_live=a - b)


def losses(inputs, cross, other, pre):
    """Per-game log loss on each test set for one replay."""
    s = ev.score(inputs, pre)
    out = {}
    for metric in ("elo_live", "forge"):
        for test_set in ev.TEST_SETS:
            mask = s.mask(test_set)
            out[(metric, test_set)] = (
                s.losses[metric]["log_loss"].to_numpy()[mask],
                s.games["year"].to_numpy()[mask],
            )
    c = with_gap(cross, pre)
    cl = game_losses(out_of_year_probabilities(c, "elo_live"), c["won"])["log_loss"].to_numpy()
    for kind in ("all", "major v major", "major v other", "other v other"):
        mask = np.ones(len(c), bool) if kind == "all" else (c["kind"] == kind).to_numpy()
        out[("cross", kind)] = (cl[mask], c["year"].to_numpy()[mask])
    intl = c["league"].isin(INTERNATIONAL_LEAGUES).to_numpy()
    out[("cross", "at internationals")] = (cl[intl], c["year"].to_numpy()[intl])
    out[("cross", "at other events")] = (cl[~intl], c["year"].to_numpy()[~intl])
    o = with_gap(other, pre)
    ol = game_losses(out_of_year_league_probabilities(o), o["won"])["log_loss"].to_numpy()
    out[("within other", "all")] = (ol, o["year"].to_numpy())
    return out


ROWS = [
    ("elo_live", "Domestic"), ("elo_live", "International"), ("forge", "Domestic"), ("forge", "International"),
    ("cross", "all"), ("cross", "major v major"), ("cross", "major v other"), ("cross", "other v other"),
    ("cross", "at internationals"), ("cross", "at other events"), ("within other", "all"),
]


def cell(base, var, since=None):
    (b, years), (v, _) = base, var
    if since:
        b, v = b[years >= since], v[years >= since]
    mean, lo, hi = paired_bootstrap(v, b)
    flag = " **" if (hi < 0 or lo > 0) else ""
    return f"{v.mean():.4f} ({mean:+.4f}, {lo:+.4f} to {hi:+.4f}){flag}"


def table(base, results, since=None):
    labels = list(results)
    lines = ["| Test set | n | Published | " + " | ".join(labels) + " |", "|---|---:|---:|" + "---|" * len(labels)]
    for key in ROWS:
        b, years = base[key]
        n = int((years >= since).sum()) if since else len(b)
        pub = b[years >= since].mean() if since else b.mean()
        cells = [cell(base[key], results[l][key], since) for l in labels]
        lines.append(f"| {key[0]}: {key[1]} | {n:,} | {pub:.4f} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    parser.add_argument("--only", nargs="*", help="variant labels to run")
    args = parser.parse_args()
    t = time.time()
    inputs = ev.load_inputs()
    pairs = pair_frame(inputs)
    cross = cross_league_games(pairs, INTERNATIONAL_LEAGUES, list(MAJORS))
    other = other_league_games(pairs, INTERNATIONAL_LEAGUES, list(MAJORS))
    print(f"inputs {time.time() - t:.0f} s; cross-league {len(cross):,}, within other {len(other):,}")
    base = losses(inputs, cross, other, inputs.baseline())
    results = {}
    for label, kw in VARIANTS.items():
        if args.only and label not in args.only:
            continue
        t = time.time()
        pre = ev.replay(inputs, ev.game_length_margin(), majors=MAJORS, **kw)
        results[label] = losses(inputs, cross, other, pre)
        print(f"{label}: {time.time() - t:.0f} s")
    text = ["# League moves by standing\n", __doc__.split("Usage")[0].strip(), "",
            "Each cell: log loss (variant − published, paired 95% interval); ** = interval excludes 0.\n",
            "## Every season\n", table(base, results), "\n## 2022 on\n", table(base, results, since=2022), ""]
    out = "\n".join(text)
    print(out)
    if args.out:
        Path(args.out).write_text(out)


if __name__ == "__main__":
    main()
