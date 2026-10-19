"""Diagnostic: is Elo's compression (c ~ 1.5) the soft game-length score?

Replays plain 1/0 results at several K and prints c per tier (see elo_win_scale.md).

    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_score_compression.py
"""

import sys
import time

import numpy as np

sys.path.insert(0, "scripts/research")
sys.path.insert(0, "scripts")
import elo_new_players as enp
import elo_one_scale as eos
import elo_variants as ev
import evaluate_metrics as em

from prometheus import elo

inputs = ev.load_inputs(verbose=False)
pairs = em.load_pair_games()
years = sorted(inputs.frame.year.unique())
train = [y for y in years if y <= 2021]
w = ev.winner_scores(inputs, ev.game_length_margin())
wbar = w.mean()
print(
    f"mean winner score {wbar:.4f}; predicted compression 1/(2w-1) = {1 / (2 * wbar - 1):.3f}"
)


def replay(margin, K):
    games = inputs.games[ev.ELO_COLUMNS].assign(
        gamelength=ev.winner_scores(inputs, margin)
    )

    def change(**a):
        return ev.margin_elo_change(**a, K=K, expected_slope=eos.S0)

    out, _ = elo.compute_elo_records(
        games, change, rosters=inputs.rosters, other_league_slope=None
    )
    return out.set_index(["gameid", "teamid"])["pre_match_elo"]


binary = lambda g: np.ones(len(g))
for label, margin, ks in (
    ("game length", ev.game_length_margin(), (20,)),
    ("binary 1/0", binary, (8, 10, 12, 14, 16, 20)),
):
    for K in ks:
        t = time.perf_counter()
        pre = replay(margin, K)
        cm, co, cx = eos.calibration(inputs, pairs, pre, train)
        obj = enp.objective(inputs, pairs, pre, train)
        print(
            f"{label:12s} K {K:3d}: train objective {obj:.6f}  c_M {cm:.3f} c_O {co:.3f} c_X {cx:.3f}  ({time.perf_counter() - t:.1f}s)",
            flush=True,
        )
