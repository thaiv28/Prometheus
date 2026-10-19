"""Exploratory follow-up to elo_one_scale.py (designed after viewing its results).

Elo with game-length scores predicts the expected *score*, compressed toward .5
by about 2w-1 (w: mean winner score), so every tier needs a fitted win curve.
Here ratings live on the win-probability scale instead: the update expects the
game-length score a win chance P = sigmoid(s0 * gap) implies,
E = .5 + m * (P - .5), with m = 2 * mean winner score - 1 from training years.
Then P itself should be a calibrated forecast with no fitted curve.

Grid fixed before scoring: K_M in {24, 32, 40} x K_O in {24, 32, 40, 48}, share .5,
selected on the training objective (refit curves, as elo_one_scale stage 1).
Held out: the chosen replay's no-curve forecast and refit forecast against the
published replay's refit forecast, series-clustered paired intervals.

    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_win_scale.py
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_new_players as enp
import elo_one_scale as eos
import elo_variants as ev
import evaluate_metrics as em

from prometheus import elo
from prometheus.evaluation import paired_bootstrap, series_ids
from prometheus.types import INTERNATIONAL_LEAGUES

KMS, KOS = (24, 32, 40), (24, 32, 40, 48)


def replay(inputs, scores, m, km, ko, share=0.5):
    games = inputs.games[ev.ELO_COLUMNS].assign(gamelength=scores)
    major_or_event = games.league.isin([*em.MAJORS, *INTERNATIONAL_LEAGUES])
    ks = iter(np.where(major_or_event, km, ko))

    def change(elo, opponent_elo, game_length, result, **_):
        actual = game_length if result else 1 - game_length
        p = 1 / (1 + np.exp(-eos.S0 * (elo - opponent_elo)))
        return next(ks) * (actual - (0.5 + m * (p - 0.5)))

    out, _ = elo.compute_elo_records(
        games,
        change,
        rosters=inputs.rosters,
        other_league_slope=None,
        league_share=share,
    )
    return out.set_index(["gameid", "teamid"])["pre_match_elo"]


def fmt(d):
    return f"{d[0]:+.5f} ({d[1]:+.5f} to {d[2]:+.5f})"


def main():
    start = time.perf_counter()
    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    years = sorted(inputs.frame.year.unique())
    train = [y for y in years if y <= 2021]
    test = [y for y in years if y > 2021]
    scores = ev.winner_scores(inputs, ev.game_length_margin())
    in_train = inputs.games.year.isin(train).to_numpy()
    m = 2 * scores[in_train].mean() - 1
    print(f"m = {m:.4f} (training mean winner score {scores[in_train].mean():.4f})")
    best = None
    for km in KMS:
        for ko in KOS:
            pre = replay(inputs, scores, m, km, ko)
            obj = enp.objective(inputs, pairs, pre, train)
            c = eos.calibration(inputs, pairs, pre, train)
            print(
                f"K_M {km} K_O {ko}: train objective {obj:.6f}; c_M {c[0]:.3f} c_O {c[1]:.3f} c_X {c[2]:.3f}",
                flush=True,
            )
            if best is None or obj < best[0]:
                best = (obj, km, ko, pre)
    obj, km, ko, chosen = best
    print(f"chosen K_M {km} K_O {ko} (train {obj:.6f})")
    published = ev.replay(inputs, ev.game_length_margin())
    print(
        "published train objective",
        f"{enp.objective(inputs, pairs, published, train):.6f}",
    )
    c = eos.calibration(inputs, pairs, chosen, test)
    print(f"held-out c: chosen c_M {c[0]:.3f} c_O {c[1]:.3f} c_X {c[2]:.3f}")
    P = eos.held_losses(inputs, pairs, published, test, published=True)
    C = eos.held_losses(inputs, pairs, chosen, test)
    print(
        "\n| Section | Metric | Games | C refit − P refit | C no curve − P refit | C no curve − C refit |"
    )
    print("|---|---|---:|---|---|---|")
    for key in P:
        pg, pl, _ = P[key]
        cg, cl, cn = C[key]
        assert np.array_equal(pg.gameid.to_numpy(), cg.gameid.to_numpy())
        clusters = series_ids(
            pg.date, pg.teamid.astype(str), pg.opponent_teamid.astype(str)
        )
        a = paired_bootstrap(cl, pl, clusters=clusters)
        b = paired_bootstrap(cn, pl, clusters=clusters) if cn is not None else None
        d = paired_bootstrap(cn, cl, clusters=clusters) if cn is not None else None
        print(
            f"| {key[0]} | {key[1]} | {len(pl):,} | {fmt(a)} | {fmt(b) if b else '—'} | {fmt(d) if d else '—'} |"
        )
    print(f"\n{time.perf_counter() - start:.0f}s")


if __name__ == "__main__":
    main()
