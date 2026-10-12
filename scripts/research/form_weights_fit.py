"""
form_weights_fit.py: how should Form's stat weights be fit?

Form scores a team's recency-weighted stat state with 12 logistic weights, fit
unpenalised (C=1e6) on blue-minus-red state gaps in domestic major-league games,
and the same weights score every league. Several stats move together (first
dragon and dragon rate, first herald and herald rate, barons and turrets), and
three weights come out negative. This tests four designs, each on the forecast
backtest's games with the FORGE blend fit out of year:

- **(a) Ridge**: an L2 penalty on the standardised gaps, C in `CS`.
- **(b) Fewer stats**: drop the first-objective flags, or keep only gold and the
  per-10 rates (`FEATURE_SETS`), at every C in `CS`.
- **(c) Other-league weights**: non-major leagues get weights fit on games inside
  non-major leagues (every C and stat set), or a blend of those with the major
  weights (`BLENDS`).
- **(d) Pooled**: one set fit on major and other-league games together, for the
  majors, for the other leagues, or both.

Tuning, fixed in advance: Form weights for season Y are fit on the seasons up to
`TRAIN_LAST` except Y, and the FORGE curves on those seasons only. The major-league
weights are chosen by domestic FORGE log loss up to `TRAIN_LAST`; then the
non-major weights by FORGE log loss within other leagues up to `TRAIN_LAST`, with
the major choice fixed. Held out (2022 on): weights fit on every other season, as
the published backtest does, for both the current fit and the variant; paired
bootstrap over games.

Usage:
    uv run python scripts/research/form_weights_fit.py --out docs/research/form_weights_fit.md
"""

import argparse
import datetime
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_metrics as em

from prometheus import form
from prometheus.evaluation import (
    game_losses,
    other_league_games,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.types import ALL_MAJOR_LEAGUES, GLORY_FEATURES, INTERNATIONAL_LEAGUES

TRAIN_LAST = 2021
CS = (1e6, 1.0, 0.1, 0.01)
FIRST_FLAGS = ("firstherald", "firstdragon", "firstbaron", "firsttower")
FEATURE_SETS = {
    "all": tuple(GLORY_FEATURES),
    "no first flags": tuple(f for f in GLORY_FEATURES if f not in FIRST_FLAGS),
    "gold + rates": (
        "gpm",
        "kills_per_10",
        "turrets_per_10",
        "baron_per_10",
        "dragon_per_10",
        "heralds_per_10",
        "visionscore_per_10",
    ),
}
BLENDS = (0.25, 0.5, 0.75)
MAJORS = {league.value for league in ALL_MAJOR_LEAGUES}
# (source, C, feature set): source is "major" (domestic major-league games),
# "other" (games inside one non-major league) or "pooled" (both).
CURRENT = ("major", 1e6, "all")


def _fmt(spec):
    if spec is None:
        return "the majors' weights"
    if spec[0] == "blend":
        _, lam, fit, _ = spec
        return f"{lam:.2f} × ({_fmt(fit)}) + {1 - lam:.2f} × the majors' weights"
    source, c, feats = spec
    c_text = "unpenalised" if c >= 1e6 else f"C={c:g}"
    return f"{source}, {c_text}, {feats}"


class Fits:
    """Form weights per (spec, held-out season, phase), cached."""

    def __init__(self, frame, other, states):
        self.states = states
        self.years = sorted(states["year"].unique())
        index = {f: i for i, f in enumerate(GLORY_FEATURES)}
        self.cols = {k: [index[f] for f in v] for k, v in FEATURE_SETS.items()}
        dom = (frame["test_set"] == "Domestic").to_numpy()
        pre = states.set_index(["gameid", "teamid"])[
            [f"pre_{f}" for f in GLORY_FEATURES]
        ]

        def gaps(g, a, b):
            x = pre.reindex(pd.MultiIndex.from_arrays([g["gameid"], g[a]])).to_numpy()
            y = pre.reindex(pd.MultiIndex.from_arrays([g["gameid"], g[b]])).to_numpy()
            return x - y

        major_gaps = em._state_gaps(frame, states)[dom]
        other_gaps = gaps(other, "teamid", "opponent_teamid")
        ok = ~np.isnan(other_gaps).any(axis=1)
        self.data = {
            "major": (
                major_gaps,
                frame["won"].to_numpy()[dom],
                frame["year"].to_numpy()[dom],
            ),
            "other": (
                other_gaps[ok],
                other["won"].to_numpy()[ok],
                other["year"].to_numpy()[ok],
            ),
        }
        self.data["pooled"] = tuple(
            np.concatenate([self.data["major"][i], self.data["other"][i]])
            for i in range(3)
        )
        self.cache = {}

    def weights(self, spec, year, phase):
        key = (spec, year, phase)
        if key in self.cache:
            return self.cache[key]
        if spec[0] == "blend":
            _, lam, fit, major = spec
            o, m = self.weights(fit, year, phase), self.weights(major, year, phase)
            w = {f: lam * o.get(f, 0.0) + (1 - lam) * m.get(f, 0.0) for f in m}
        else:
            source, c, feats = spec
            x, won, years = self.data[source]
            train = years != year
            if phase == "tune":
                train &= years <= TRAIN_LAST
            cols = self.cols[feats]
            coef = form.fit_form_weights(x[train][:, cols], won[train], C=c)
            w = dict(zip(FEATURE_SETS[feats], coef))
        self.cache[key] = w
        return w

    def relative(self, major_spec, other_spec, phase):
        """League-relative pre-game Form for every state row (Series by gameid,
        teamid): major homes scored with `major_spec`, others with `other_spec`
        (None: the major weights)."""
        score = np.full(len(self.states), np.nan)
        for year in self.years:
            rows = (self.states["year"] == year).to_numpy()
            sub = self.states[rows]
            other = (
                None if other_spec is None else self.weights(other_spec, year, phase)
            )
            score[rows] = form.scores(
                sub,
                self.weights(major_spec, year, phase),
                other_weights=other,
                majors=MAJORS,
            )
        return pd.Series(
            form.league_relative(self.states, score),
            index=pd.MultiIndex.from_frame(self.states[["gameid", "teamid"]]),
        )


def section_losses(frame, other, relative, years):
    """Per-game log losses on `years` (curves fit within `years`): domestic FORGE,
    international FORGE, domestic Form alone, FORGE within other leagues."""
    f = em.add_form(
        frame[frame["year"].isin(years)].reset_index(drop=True), None, relative
    )
    forge = game_losses(em.forge_probabilities(f), f["won"])["log_loss"].to_numpy()
    form_alone = game_losses(out_of_year_probabilities(f, "form"), f["won"])[
        "log_loss"
    ].to_numpy()
    dom = (f["test_set"] == "Domestic").to_numpy()
    intl = (f["test_set"] == "International").to_numpy()
    o = other[other["year"].isin(years)]
    o = o.assign(
        form=em.form_gap(relative, o["gameid"], o["teamid"], o["opponent_teamid"])
    )
    o = o[o["form"].notna()].reset_index(drop=True)
    oth = game_losses(out_of_year_probabilities(o, ["elo_live", "form"]), o["won"])[
        "log_loss"
    ].to_numpy()
    return {
        "Domestic FORGE": (forge[dom], f.loc[dom, "year"].to_numpy()),
        "International FORGE": (forge[intl], f.loc[intl, "year"].to_numpy()),
        "Domestic Form alone": (form_alone[dom], f.loc[dom, "year"].to_numpy()),
        "Other leagues FORGE": (oth, o["year"].to_numpy()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="Write the report to this Markdown file")
    args = parser.parse_args()

    print("Loading games...")
    games, results, timeline = (
        em.load_games(),
        em.load_results(),
        em.load_elo_timeline(),
    )
    states = em.form_states()
    frame = em.backtest(
        games, results, timeline, em.get_available_years(ALL_MAJOR_LEAGUES)
    )
    other = other_league_games(em.load_pair_games(), INTERNATIONAL_LEAGUES, MAJORS)
    fits = Fits(frame, other, states)
    all_years = sorted(set(frame["year"]) | set(other["year"]))
    tune_years = [y for y in all_years if y <= TRAIN_LAST]
    held_years = [y for y in all_years if y > TRAIN_LAST]

    def tune_score(major_spec, other_spec, section):
        rel = fits.relative(major_spec, other_spec, "tune")
        return section_losses(frame, other, rel, tune_years)[section][0].mean()

    designs = {
        "(a) Ridge": [("major", c, "all") for c in CS[1:]],
        "(b) Fewer stats": [
            ("major", c, k) for k in FEATURE_SETS if k != "all" for c in CS
        ],
        "(d) Pooled": [("pooled", c, k) for k in FEATURE_SETS for c in CS],
    }
    print("Tuning major-league weights...")
    major_scores = {}
    for spec in itertools.chain(*designs.values(), [CURRENT]):
        if spec not in major_scores:
            major_scores[spec] = tune_score(spec, None, "Domestic FORGE")
            print(f"  {_fmt(spec)}: {major_scores[spec]:.5f}")
    best = {name: min(specs, key=major_scores.get) for name, specs in designs.items()}
    best_major = min([CURRENT, *major_scores], key=major_scores.get)

    print("Tuning non-major weights...")
    separate = [("other", c, k) for k in FEATURE_SETS for c in CS]
    other_scores = {None: tune_score(best_major, None, "Other leagues FORGE")}
    for spec in separate + [("pooled", c, k) for k in FEATURE_SETS for c in CS]:
        other_scores[spec] = tune_score(best_major, spec, "Other leagues FORGE")
        print(f"  {_fmt(spec)}: {other_scores[spec]:.5f}")
    best_sep = min(separate, key=other_scores.get)
    for lam in BLENDS:
        spec = ("blend", lam, best_sep, best_major)
        other_scores[spec] = tune_score(best_major, spec, "Other leagues FORGE")
        print(f"  {_fmt(spec)}: {other_scores[spec]:.5f}")
    best_other = min(other_scores, key=other_scores.get)
    best_c = min([s for s in other_scores if s is not None], key=other_scores.get)

    print("Held out...")
    base = section_losses(
        frame, other, fits.relative(CURRENT, None, "held"), held_years
    )
    variants = {
        f"(a) Ridge: {_fmt(best['(a) Ridge'])}": (best["(a) Ridge"], None),
        f"(b) Fewer stats: {_fmt(best['(b) Fewer stats'])}": (
            best["(b) Fewer stats"],
            None,
        ),
        f"(c) Other-league weights: {_fmt(best_c)}": (CURRENT, best_c),
        f"(d) Pooled, every league: {_fmt(best['(d) Pooled'])}": (
            best["(d) Pooled"],
            None,
        ),
        f"Chosen: majors {_fmt(best_major)}; other leagues {_fmt(best_other)}": (
            best_major,
            best_other,
        ),
    }
    held = {
        label: section_losses(frame, other, fits.relative(m, o, "held"), held_years)
        for label, (m, o) in variants.items()
    }

    shown = {
        "Current": CURRENT,
        "Ridge, C=0.1": ("major", 0.1, "all"),
        "Ridge, C=0.01": ("major", 0.01, "all"),
        "Pooled": ("pooled", 1e6, "all"),
        "Other leagues only": ("other", 1e6, "all"),
    }
    # Fit on every season (`year` 0 leaves none out), as the published weights are.
    fitted = {k: fits.weights(v, 0, "held") for k, v in shown.items()}

    sections = list(base)
    lines = [
        f"## Form's stat weights ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/form_weights_fit.py`. Tuned on seasons up to "
        f"{TRAIN_LAST} (Form weights and FORGE curves fit on those seasons only, each "
        "season left out of its own weights); held out on 2022 on, with weights fit on "
        "every other season as the published backtest does. Δ is variant minus the "
        "current fit (unpenalised, 12 stats, major-league games, every league), paired "
        "bootstrap over games; negative is better.\n",
        "### Tuning: major-league weights (domestic FORGE log loss, ≤ 2021)\n",
        "| Weights | Log loss |",
        "|---|---:|",
    ]
    for spec, v in sorted(major_scores.items(), key=lambda kv: kv[1]):
        mark = " (current)" if spec == CURRENT else ""
        lines.append(f"| {_fmt(spec)}{mark} | {v:.5f} |")
    lines += [
        f"\nChosen for the majors: {_fmt(best_major)}.\n",
        "### Tuning: non-major weights (FORGE within other leagues, ≤ 2021, majors as chosen)\n",
        "| Weights | Log loss |",
        "|---|---:|",
    ]
    for spec, v in sorted(other_scores.items(), key=lambda kv: kv[1]):
        lines.append(f"| {_fmt(spec)} | {v:.5f} |")
    lines += [
        f"\nChosen for other leagues: {_fmt(best_other)}.\n",
        "### Held out (2022 on)\n",
        "| Design | " + " | ".join(sections) + " |",
        "|---|" + "---|" * len(sections),
        "| Current (log loss) | "
        + " | ".join(f"{base[s][0].mean():.4f}" for s in sections)
        + " |",
    ]
    for label, res in held.items():
        cells = []
        for s in sections:
            mean, lo, hi = paired_bootstrap(res[s][0], base[s][0])
            cells.append(f"{mean:+.4f} ({lo:+.4f} to {hi:+.4f})")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.append(
        "\nGames: " + ", ".join(f"{s} {len(base[s][0]):,}" for s in sections) + "."
    )
    lines += [
        "\n### Weights fit on every season (log-odds per unit of stat gap)\n",
        "| Stat | " + " | ".join(fitted) + " |",
        "|---|" + "---:|" * len(fitted),
    ]
    for f in GLORY_FEATURES:
        lines.append(
            f"| {f} | " + " | ".join(f"{w[f]:+.4f}" for w in fitted.values()) + " |"
        )
    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).write_text(report)


if __name__ == "__main__":
    main()
