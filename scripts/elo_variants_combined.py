"""
elo_variants_combined.py: combined / learned margins of victory and Elo update settings.

Tests, with the `elo_variants.py` harness, multi-stat margins for player-built Elo and
the update rule itself. Every free parameter, every standardisation and every learned
weight comes from seasons up to 2021 only; each candidate is then compared with the
published Elo (game-length margin, K=20) on 2022 onwards. The best candidate is picked
by its TRAINING objective (domestic Elo-live log loss on 2014–2021), not by held-out.

Candidates (all squashed into the winner's score with `bounded`, upper 1.0):
    1a. Dominance index, learned: weights of z(gold diff), z(kill diff), z(tower diff),
        z(shortness) from a logistic model of each team's NEXT game (on training years),
        with plain-Elo (score 1 for every win) pre-match gap as an offset.
    1b. Dominance index, first principal component of the four z-scores (training games).
    2.  Equal-weight z composite of the four.
    3.  Published game-length margin with its lower bound, center and steepness re-tuned.
    4a. K re-tuned with the published margin.
    4b. K re-tuned with the best composite (its squash fixed from step 1/2).
    5.  Asymmetric: the game-length score, plus a bonus only when the composite is extreme.

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/elo_variants_combined.py \
        --out docs/elo_variants_combined.md
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_variants as ev  # noqa: E402

FEATURES = ["gold", "kills", "towers", "short"]
SQUASH_GRID = {"scale": [0.5, 1.0, 2.0], "center": [-0.5, 0.0, 0.5], "lower": [0.55, 0.65, 0.75]}
GL_GRID = {"lower_bound": [0.55, 0.65, 0.75], "center": [25 * 60, 30 * 60, 35 * 60], "steepness": [2, 3, 5]}
K_GRID = [12, 16, 20, 24, 28, 32, 40]
ASYM_GRID = {"threshold": [1.0, 1.5, 2.0], "bonus": [0.05, 0.1, 0.2]}


def raw_features(games):
    """Winner-perspective margins: gold, kill and tower differences and shortness (-seconds)."""
    return pd.DataFrame({
        "gold": games["w_totalgold"] - games["l_totalgold"],
        "kills": games["w_kills"] - games["l_kills"],
        "towers": games["w_towers"] - games["l_towers"],
        "short": -games["gamelength"].astype(float),
    })


class Standardizer:
    """z-scores with mean and sd from training-year games only."""

    def __init__(self, games, train_mask):
        x = raw_features(games)[train_mask]
        self.mean, self.sd = x.mean(), x.std()

    def z(self, games):
        return (raw_features(games) - self.mean) / self.sd


def logistic_offset(X, y, offset, iters=50, ridge=1e-6):
    """Logistic regression with an offset (Newton / IRLS). Returns [intercept, coefs...]."""
    X = np.column_stack([np.ones(len(X)), X])
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = offset + X @ beta
        p = 1 / (1 + np.exp(-eta))
        w = p * (1 - p)
        grad = X.T @ (y - p) - ridge * beta
        hess = (X * w[:, None]).T @ X + ridge * np.eye(len(beta))
        step = np.linalg.solve(hess, grad)
        beta += step
        if np.abs(step).max() < 1e-9:
            break
    return beta


def learned_weights(inputs, std, train_years):
    """Weights of the four z-margins for predicting each team's next game beyond plain Elo.

    Plain Elo (every win scores 1.0, K=20) gives each next game's pre-match gap, used as
    an offset; a team's margin enters signed (+ for the winner, - for the loser). Only
    pairs where both games are in training years are used.
    """
    g = inputs.games
    plain = ev.replay(inputs, lambda games: np.ones(len(games)))
    z = std.z(g).to_numpy()
    rows = []
    for team, opp in (("teamid", "opponent_teamid"), ("opponent_teamid", "teamid")):
        won = g["result"].astype(bool).to_numpy() if team == "teamid" else ~g["result"].astype(bool).to_numpy()
        key = pd.MultiIndex.from_arrays([g["gameid"], g[team]])
        okey = pd.MultiIndex.from_arrays([g["gameid"], g[opp]])
        rows.append(pd.DataFrame({
            "team": g[team].to_numpy(), "date": g["date"].to_numpy(), "order": np.arange(len(g)),
            "year": g["year"].to_numpy(), "won": won.astype(float),
            "gap": plain.reindex(key).to_numpy() - plain.reindex(okey).to_numpy(),
            **{f: np.where(won, 1, -1) * z[:, i] for i, f in enumerate(FEATURES)},
        }))
    tg = pd.concat(rows).sort_values(["team", "order"]).reset_index(drop=True)
    nxt = tg.groupby("team")[["won", "gap", "year"]].shift(-1)
    data = tg.assign(next_won=nxt["won"], next_gap=nxt["gap"], next_year=nxt["year"]).dropna()
    data = data[data["year"].isin(train_years) & data["next_year"].isin(train_years)]
    offset = data["next_gap"].to_numpy() * np.log(10) / 400
    beta = logistic_offset(data[FEATURES].to_numpy(), data["next_won"].to_numpy(), offset)
    return pd.Series(beta[1:], index=FEATURES), len(data)


def pca_weights(z_train):
    vals, vecs = np.linalg.eigh(np.cov(z_train.to_numpy().T))
    w = vecs[:, -1]
    w = w if w.sum() > 0 else -w
    return pd.Series(w, index=FEATURES), vals[-1] / vals.sum()


def composite_fn(std, weights, train_mask, games):
    """Composite = z @ weights, rescaled to unit sd on training games. Returns f(games)."""
    zt = std.z(games)[train_mask] @ weights
    sd = zt.std()
    return lambda g: (std.z(g) @ weights).to_numpy() / sd


def squash_margin(comp):
    def make(scale, center, lower):
        return ev.with_fallback(lambda g: ev.bounded(comp(g), scale, center, lower, 1.0))
    return make


def asym_margin(comp):
    gl = ev.game_length_margin()

    def make(threshold, bonus):
        def m(g):
            c = comp(g)
            s = np.asarray(gl(g), dtype=float)
            out = np.where(c > threshold, np.minimum(1.0, s + bonus), s)
            return np.where(np.isnan(c), s, out)
        return m
    return make


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    t0 = time.time()
    inputs = ev.load_inputs()
    train, test = ev.split_years(inputs.frame["year"].unique())
    g = inputs.games
    train_mask = g["year"].isin(train).to_numpy()
    std = Standardizer(g, train_mask)
    z_train = std.z(g)[train_mask].dropna()
    corr = z_train.corr()

    w_learn, n_learn = learned_weights(inputs, std, train)
    w_pca, pca_share = pca_weights(z_train)
    w_eq = pd.Series(1.0, index=FEATURES)
    print("learned weights", w_learn.round(4).to_dict(), n_learn)
    print("pca weights", w_pca.round(4).to_dict(), round(pca_share, 3))

    comps = {
        "1a. Dominance, learned (next game)": composite_fn(std, w_learn, train_mask, g),
        "1b. Dominance, first PC": composite_fn(std, w_pca, train_mask, g),
        "2. Equal-weight z composite": composite_fn(std, w_eq, train_mask, g),
    }

    results = {}  # label -> HeldOut
    n_points = 0
    for label, comp in comps.items():
        results[label] = ev.held_out(inputs, squash_margin(comp), SQUASH_GRID, label)
        n_points += len(ev.param_grid(SQUASH_GRID))
        print(results[label].row, flush=True)

    results["3. Game length, re-tuned shape"] = ev.held_out(
        inputs, ev.game_length_margin, GL_GRID, "3. Game length, re-tuned shape")
    n_points += len(ev.param_grid(GL_GRID))

    results["4a. K, published margin"] = ev.held_out(
        inputs, lambda: ev.game_length_margin(), {"K": K_GRID}, "4a. K, published margin")
    n_points += len(K_GRID)

    comp_labels = list(comps)
    best_comp = min(comp_labels, key=lambda l: results[l].tuning["objective"].iloc[0])
    squash = results[best_comp].params
    make = squash_margin(comps[best_comp])
    label4b = f"4b. K, with {best_comp.split('. ')[1]}"
    results[label4b] = ev.held_out(inputs, lambda: make(**squash), {"K": K_GRID}, label4b)
    n_points += len(K_GRID)

    results["5. Asymmetric (bonus for extreme composite)"] = ev.held_out(
        inputs, asym_margin(comps[best_comp]), ASYM_GRID, "5. Asymmetric (bonus for extreme composite)")
    n_points += len(ev.param_grid(ASYM_GRID))

    base_train = ev.score(inputs, inputs.baseline(), years=train, forge=False).log_loss("elo_live", "Domestic").mean()
    best = min(results, key=lambda l: results[l].tuning["objective"].iloc[0])
    d = ev.deltas(inputs.baseline_scores(test), results[best].scores)

    lines = [
        "# Elo margin variants: combined / learned margins and update settings",
        "",
        f"Script: `scripts/elo_variants_combined.py` (harness `scripts/elo_variants.py`). "
        f"Runtime {(time.time() - t0) / 60:.1f} min.",
        "",
        "## Protocol",
        "",
        f"- Tuning seasons {train[0]}–{train[-1]}; held-out seasons {test[0]}–{test[-1]}. Everything learned "
        "(z-score means and sds, learned and PCA weights, composite sd, every grid choice) uses training "
        "seasons only. Objective: domestic Elo-live log loss on training seasons (curves fit only on them).",
        "- Features (winner minus loser): gold, kills, towers; shortness = minus game length. Coverage of all "
        "three stats is ~100% every season; missing stats fall back to the game-length score.",
        "- Composites are rescaled to unit sd on training games, then squashed with "
        "`bounded(c, scale, center, lower, upper=1.0)` over "
        f"{SQUASH_GRID} ({len(ev.param_grid(SQUASH_GRID))} points).",
        f"- 1a learned weights: logistic model of each team's next game (both in training seasons, "
        f"{n_learn:,} team-games), offset by plain Elo's pre-match gap (every win scores 1.0, K=20), "
        "margins signed + for the winner, − for the loser. Weights (per z): "
        + ", ".join(f"{k} {v:+.3f}" for k, v in w_learn.items()) + ".",
        f"- 1b first principal component of the four z-scores ({pca_share:.0%} of variance): "
        + ", ".join(f"{k} {v:+.3f}" for k, v in w_pca.items()) + ".",
        "- Training correlations of the z-scores: " + ", ".join(
            f"{a}/{b} {corr.loc[a, b]:.2f}" for i, a in enumerate(FEATURES) for b in FEATURES[i + 1:]) + ".",
        f"- 3 re-tunes the published logistic in game length: {GL_GRID} (upper bound 1.0).",
        f"- 4a tunes K over {K_GRID} with the published margin; 4b the same K grid with the composite "
        f"that did best on training ({best_comp}, squash {squash} fixed).",
        f"- 5 keeps the game-length score and adds `bonus` (capped at 1.0) only when that composite "
        f"exceeds `threshold` sds: {ASYM_GRID}.",
        f"- {len(results)} candidates, {n_points} parameter points evaluated on training seasons. "
        "Δ = variant minus baseline (published Elo, game length, K=20) on the same held-out games, "
        "paired bootstrap 95% interval; Δ < 0 is better.",
        "",
        "## Held-out results (2022 onward), every candidate",
        "",
        "Training objective = domestic Elo-live log loss on " f"{train[0]}–{train[-1]} "
        f"(baseline {base_train:.5f}).",
        "",
        "| Candidate | Chosen params | Train obj. |",
        "|---|---|---:|",
    ]
    for label, r in results.items():
        lines.append(f"| {label} | {r.params} | {r.tuning['objective'].iloc[0]:.5f} |")
    lines += ["", ev.COMPARE_HEADER]
    for label, r in results.items():
        lines.append(r.row.replace(f"{label} {r.params}", label))

    dom, intl = d.loc[("elo_live", "Domestic")], d.loc[("elo_live", "International")]
    fdom, fintl = d.loc[("forge", "Domestic")], d.loc[("forge", "International")]
    meets = dom["hi"] < 0 and not intl["lo"] > 0
    lines += [
        "",
        "## Verdict",
        "",
        f"Best by training objective: **{best}** with {results[best].params} "
        f"(train {results[best].tuning['objective'].iloc[0]:.5f} vs baseline {base_train:.5f}).",
        "",
        f"Held out: Elo live domestic Δ {dom['delta']:+.4f} ({dom['lo']:+.4f} to {dom['hi']:+.4f}), "
        f"international Δ {intl['delta']:+.4f} ({intl['lo']:+.4f} to {intl['hi']:+.4f}); "
        f"FORGE domestic Δ {fdom['delta']:+.4f} ({fdom['lo']:+.4f} to {fdom['hi']:+.4f}), "
        f"international Δ {fintl['delta']:+.4f} ({fintl['lo']:+.4f} to {fintl['hi']:+.4f}).",
        "",
        ("Meets the significance rule (domestic Elo-live interval below 0, international not "
         "significantly worse)." if meets else
         "Does **not** meet the significance rule (domestic Elo-live interval must lie entirely below 0 "
         "with international not significantly worse)."),
        f" With {len(results)} candidates (and {n_points} tuned points) the intervals are not corrected "
        "for multiple comparisons, so a single marginal pass would be weak evidence.",
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
