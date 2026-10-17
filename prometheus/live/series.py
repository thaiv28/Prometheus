"""Live chance to win a series: the score so far, the current map's live chance
and FORGE's one-map chance for the maps still to play.

Prometheus's series model draws one per-series chance from a Beta with mean
p_game and within-series correlation rho; maps are independent given it. Maps
already played update that Beta. The current map's own chance comes from the
live model; later maps use the updated Beta.
"""

import math


def map_prior(p_game, rho, wins, losses):
    """Team 0's pre-map chance after `wins`-`losses` in this series: the Beta's
    posterior mean, as the series model updates the one-map chance."""
    kappa = 1 / max(rho, 1e-9) - 1
    return (p_game * kappa + wins) / (kappa + wins + losses)


def map_shift(p_game, rho, wins, losses):
    """Log-odds to add to team 0's live map call for the maps already played
    (`docs/research/series_checkpoint.md`); 0 before the first map."""
    p = min(max(p_game, 1e-4), 1 - 1e-4)
    post = map_prior(p, rho, wins, losses)
    return math.log(post / (1 - post)) - math.log(p / (1 - p))


def _log_beta(a, b):
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def win_from(wins, losses, need, a, b):
    """Chance to reach `need` map wins first from (wins, losses), chance ~ Beta(a, b)."""
    if wins >= need:
        return 1.0
    if losses >= need:
        return 0.0
    need_w, need_l = need - wins, need - losses
    total = 0.0
    for k in range(need_l):
        log_m = _log_beta(a + need_w, b + k) - _log_beta(a, b)
        total += math.comb(need_w - 1 + k, k) * math.exp(log_m)
    return total


def series_chance(p_game, best_of, rho, score, p_map=None):
    """Team 0's chance; `score` is [team 0 maps, team 1 maps]."""
    need = best_of // 2 + 1
    kappa = 1 / max(rho, 1e-9) - 1
    a, b = p_game * kappa + score[0], (1 - p_game) * kappa + score[1]
    if p_map is None:
        return win_from(score[0], score[1], need, a, b)
    return p_map * win_from(score[0] + 1, score[1], need, a + 1, b) + (
        1 - p_map
    ) * win_from(score[0], score[1] + 1, need, a, b + 1)
