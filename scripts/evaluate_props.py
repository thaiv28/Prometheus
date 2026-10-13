"""
evaluate_props.py: How well the prop projections (`prometheus/props.py`) forecast a
player's kills, assists, deaths, CS and fantasy points, before any book's lines.

Every projection uses only earlier games, with the states before the series'
first map (as a line set before the series would). Each stat's half-life and
prior are chosen on 2022-2023 with models fit on games through 2021 (the grid's
best for that stat), fixed, then the models are refit on games through 2023 and
scored on 2024 onward. A held-out check compares the chosen settings with one
half-life for every stat. Only LCK, LPL, LEC, LCS
and international games are scored (where the lines are); every league's games
train the models.

Scores, lower is better:
- log score: minus the log of the probability given to the actual count;
- RPS (ranked probability score, the CRPS of a count) and, for fantasy points, CRPS.
Each is compared with baselines on the same rows by a paired bootstrap over
matches: the league-and-role average, the player's last 10 games, the player's
season so far (each a negative binomial with a dispersion fit per role), the
player's shrunk rate alone, and the model without the result mixture.

Calibration: P(over) at a stand-in line (the last-10 mean rounded down plus a
half), against how often the player went over, with its ECE.

Series: the total over maps 1-2 (Bo3 and Bo5), maps 1-3 of a Bo5, and maps 1-3 of
a Bo3 as played (map 3 counts when it happens; the model weighs the series
lengths by the Elo chance, the baseline by how often Bo3s went to three maps in
the training years). Best-of is inferred from the final score, as on game logs.

Usage:
    uv run python scripts/evaluate_props.py [--out docs/props_report.md]
    uv run python scripts/evaluate_props.py --write-weights   # also refit on every game into props_weights.json
    uv run python scripts/evaluate_props.py --dump DIR        # CI only (compare_benchmarks.py): the published
                                                              # settings, no tuning or report
"""

import argparse
import datetime
import json
import os

import numpy as np
import pandas as pd

from prometheus import props
from prometheus.evaluation import ece, paired_bootstrap
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

SCORED = [league.value for league in ALL_MAJOR_LEAGUES] + list(INTERNATIONAL_LEAGUES)
TUNE_END, VALID_END, TEST_START = 2021, 2023, 2024
GRID = [(h, n0) for h in (4, 8, 16, 32) for n0 in (3, 10)]
CHUNK = 5000


def add_baseline_states(g):
    """Pre-game last-10 and season-so-far means of each stat and of fantasy points
    (NaN with fewer than 3 earlier games: the pace then stands in)."""
    out = g.copy()
    out["fantasy"] = props.fantasy_points(out)
    out["pace_fantasy"] = sum(props.FANTASY[s] * out[f"pace_{s}"] for s in props.STATS)
    for stat in list(props.STATS) + ["fantasy"]:
        last10 = _pregame(
            out, ["playerid"], stat, lambda r: r.rolling(10, min_periods=3)
        )
        out[f"l10_{stat}"] = last10.fillna(out[f"pace_{stat}"])
        season = _pregame(
            out, ["playerid", "year"], stat, lambda r: r.expanding(min_periods=3)
        )
        out[f"ssn_{stat}"] = season.fillna(out[f"pace_{stat}"])
    return out


def _pregame(g, keys, col, window):
    """A windowed mean of `col` within `keys`, over earlier rows only."""
    running = window(g.groupby(keys, sort=False)[col]).mean()
    running = running.reset_index(level=list(range(len(keys))), drop=True).sort_index()
    return running.groupby([g[k] for k in keys], sort=False).shift()


def prepared(settings, games):
    g = props.add_stat_states(games, settings)
    g = add_baseline_states(g)
    g["p_fantasy"] = sum(props.FANTASY[s] * g[f"p_{s}"] for s in props.STATS)
    return props.series_start_states(g)


def chunks(n):
    for start in range(0, n, CHUNK):
        yield slice(start, min(start + CHUNK, n))


def model_scores(model, g, stat):
    """Per-row log score and RPS of the model's one-map projection."""
    logs, rpss, over = [], [], []
    for sl in chunks(len(g)):
        part = g.iloc[sl]
        pmf, _, _ = props.game_pmf(model, part, stat)
        logs.append(props.log_score(pmf, part[stat]))
        rpss.append(props.rps(pmf, part[stat]))
        over.append(props.prob_over(pmf, np.floor(part[f"l10_{stat}"]) + 0.5))
    return np.concatenate(logs), np.concatenate(rpss), np.concatenate(over)


def role_alphas(train, stat, mean_col):
    return {
        role: props._alpha(
            train.loc[train["position"] == role, stat].to_numpy(float),
            train.loc[train["position"] == role, mean_col]
            .clip(lower=0.05)
            .to_numpy(float),
        )
        for role in props.ROLES
    }


def baseline_scores(train, g, stat, mean_col):
    alphas = role_alphas(train, stat, mean_col)
    logs, rpss, over = [], [], []
    for sl in chunks(len(g)):
        part = g.iloc[sl]
        pmf = props.nb_pmf(
            part[mean_col].clip(lower=0.05),
            part["position"].map(alphas),
            props.SUPPORT[stat],
        )
        logs.append(props.log_score(pmf, part[stat]))
        rpss.append(props.rps(pmf, part[stat]))
        over.append(props.prob_over(pmf, np.floor(part[f"l10_{stat}"]) + 0.5))
    return np.concatenate(logs), np.concatenate(rpss), np.concatenate(over)


def fantasy_model_crps(model, g):
    out = []
    for sl in chunks(len(g)):
        part = g.iloc[sl]
        mw, sw, ml, sl_ = model.fantasy(part)
        p = model.win_chance(part)
        out.append(
            props.normal_mixture_crps([(p, mw, sw), (1 - p, ml, sl_)], part["fantasy"])
        )
    return np.concatenate(out)


def fantasy_baseline_crps(train, g, mean_col):
    sd = {
        role: float(
            np.std(
                train.loc[train["position"] == role, "fantasy"]
                - train.loc[train["position"] == role, mean_col]
            )
        )
        for role in props.ROLES
    }
    out = []
    for sl in chunks(len(g)):
        part = g.iloc[sl]
        s = part["position"].map(sd).to_numpy()
        out.append(
            props.normal_mixture_crps(
                [(np.ones(len(part)), part[mean_col].to_numpy(), s)], part["fantasy"]
            )
        )
    return np.concatenate(out)


def match_keys(g):
    """One id per match (both teams' series), for clustered bootstraps."""
    first = g.groupby("gameid")["series"].transform("min")
    return first.groupby(g["series"]).transform("min").to_numpy()


def clustered(loss, keys):
    return pd.Series(loss).groupby(keys).mean().to_numpy()


def compare(loss_a, loss_b, keys):
    mean, lo, hi = paired_bootstrap(
        clustered(loss_a, keys), clustered(loss_b, keys), n_resamples=1000
    )
    return mean, lo, hi


def tune(games):
    """Pick each stat's (half-life, prior games): the grid's best one-map log score
    for that stat on 2022-2023."""
    rows = []
    for halflife, prior_games in GRID:
        g = prepared(props.uniform(halflife, prior_games), games)
        train = g[g["year"] <= TUNE_END]
        valid = g[
            (g["year"] > TUNE_END) & (g["year"] <= VALID_END) & g["league"].isin(SCORED)
        ]
        model = props.fit(train, props.uniform(halflife, prior_games))
        total = {
            stat: model_scores(model, valid, stat)[0].mean() for stat in props.STATS
        }
        rows.append(
            {
                "halflife": halflife,
                "prior_games": prior_games,
                **total,
                "sum": sum(total.values()),
            }
        )
        print(rows[-1])
    table = pd.DataFrame(rows)
    settings = {}
    for stat in props.STATS:
        best = table.loc[table[stat].idxmin()]
        settings[stat] = (int(best["halflife"]), int(best["prior_games"]))
    return settings, table


HALFLIFE_CHECK = (4, 8, 16, 32, 64)


def halflife_check(games, settings, prior_games=3):
    """Do the chosen settings hold up on the held-out years? They and one half-life
    for every stat (prior `prior_games`) are fit through 2023 and scored on 2024 on,
    one map and over series (Bo3 maps 1-2, Bo5 maps 1-3), paired against the
    chosen settings."""
    scored = {}
    variants = {"chosen": settings} | {
        h: props.uniform(h, prior_games) for h in HALFLIFE_CHECK
    }
    for name, variant in variants.items():
        g = prepared(variant, games)
        train = g[g["year"] <= VALID_END]
        test = g[(g["year"] >= TEST_START) & g["league"].isin(SCORED)].reset_index(
            drop=True
        )
        model = props.fit(train, variant)
        q3 = three_map_share(train)
        out = {"keys": match_keys(test)}
        for stat in props.STATS:
            out[stat] = model_scores(model, test, stat)[0]
        for label, maps, best_of in (("Bo3 1-2", 2, 3), ("Bo5 1-3", 3, 5)):
            rows = series_rows(test, maps, best_of)
            out[f"{label} keys"] = match_keys(rows)
            for stat in ("kills", "assists"):
                out[f"{label} {stat}"] = series_scores(
                    model, train, rows, stat, maps, best_of, q3
                )["model_log"]
        scored[name] = out
        print(f"{name} scored")
    base = scored["chosen"]
    cols = list(props.STATS) + [
        f"{lab} {st}" for lab in ("Bo3 1-2", "Bo5 1-3") for st in ("kills", "assists")
    ]
    lines = [
        "| Half-life | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for name, out in scored.items():
        cells = []
        for col in cols:
            keys = (
                out[col.rsplit(" ", 1)[0] + " keys"]
                if col not in props.STATS
                else out["keys"]
            )
            if name == "chosen":
                cells.append(f"{out[col].mean():.4f}")
            else:
                cells.append(fmt_ci(*compare(out[col], base[col], keys), digits=4))
        label = "Chosen per stat" if name == "chosen" else f"{name} for every stat"
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


# ---------------------------------------------------------------- series


def series_rows(g, maps, best_of):
    """One row per player per series of the given best-of whose first `maps` maps
    the player all played (or every map, when the series ended sooner), with the
    total of each stat over those maps and the states before map 1."""
    bo = 2 * np.maximum(g["series_wins"], g["series_losses"]) - 1
    tie = g["series_wins"] == g["series_losses"]
    g = g[(bo == best_of) & ~tie & (g["map"] <= maps)]
    played = np.minimum(g["series_wins"] + g["series_losses"], maps)
    counted = g.groupby(["series", "playerid"])["map"].transform("size")
    g = g[counted == played]
    totals = g.groupby(["series", "playerid"])[list(props.STATS) + ["fantasy"]].sum()
    first = g.groupby(["series", "playerid"]).first()
    first[list(props.STATS) + ["fantasy"]] = totals
    first["maps_played"] = g.groupby(["series", "playerid"]).size()
    return first.reset_index()


def three_map_share(train):
    s = train.drop_duplicates("series")
    bo3 = s[
        (np.maximum(s["series_wins"], s["series_losses"]) == 2)
        & (s["series_wins"] != s["series_losses"])
    ]
    return float(((bo3["series_wins"] + bo3["series_losses"]) == 3).mean())


def series_scores(model, train, rows, stat, maps, best_of, q3):
    """Model and last-10 baseline log score and RPS on series totals."""
    alphas = role_alphas(train, stat, f"l10_{stat}")
    out = {
        "model_log": [],
        "model_rps": [],
        "base_log": [],
        "base_rps": [],
        "model_over": [],
        "base_over": [],
    }
    for sl in chunks(len(rows)):
        part = rows.iloc[sl]
        _, win, loss = props.game_pmf(model, part, stat)
        p = model.win_chance(part)
        pmf = props.series_pmf(win, loss, p, best_of, maps)
        base1 = props.nb_pmf(
            part[f"l10_{stat}"].clip(lower=0.05),
            part["position"].map(alphas),
            props.SUPPORT[stat],
        )
        # The baseline's series length: guaranteed maps, or a Bo3's third map at the
        # training years' rate.
        if best_of == 3 and maps == 3:
            two = _sum_pmf(base1, 2, props.SUPPORT[stat] * 3)
            three = _sum_pmf(base1, 3, props.SUPPORT[stat] * 3)
            base = (1 - q3) * two + q3 * three
        else:
            base = _sum_pmf(base1, maps, props.SUPPORT[stat] * maps)
        line = (
            np.floor(
                part[f"l10_{stat}"]
                * (2.0 if maps == 2 else (2 + q3 if best_of == 3 else 3.0))
            )
            + 0.5
        )
        y = part[stat]
        out["model_log"].append(props.log_score(pmf, y))
        out["model_rps"].append(props.rps(pmf, y))
        out["base_log"].append(props.log_score(base, y))
        out["base_rps"].append(props.rps(base, y))
        out["model_over"].append(props.prob_over(pmf, line))
        out["base_over"].append(props.prob_over(base, line))
        out.setdefault("went_over", []).append((y > line).to_numpy())
    return {k: np.concatenate(v) for k, v in out.items()}


def _sum_pmf(pmf, k, support):
    f = np.fft.rfft(pmf, n=support)
    return np.clip(np.fft.irfft(f**k, n=support), 0.0, None)


def series_fantasy(model, train, rows, maps, best_of, q3):
    sd = {
        role: float(
            np.std(
                train.loc[train["position"] == role, "fantasy"]
                - train.loc[train["position"] == role, "l10_fantasy"]
            )
        )
        for role in props.ROLES
    }
    m_crps, b_crps = [], []
    for sl in chunks(len(rows)):
        part = rows.iloc[sl]
        mw, sw, ml, sl_ = model.fantasy(part)
        p = model.win_chance(part)
        parts = props.series_normal(mw, sw, ml, sl_, p, best_of, maps)
        m_crps.append(props.normal_mixture_crps(parts, part["fantasy"]))
        mean1, s1 = part["l10_fantasy"].to_numpy(), part["position"].map(sd).to_numpy()
        if best_of == 3 and maps == 3:
            base = [
                (np.full(len(part), 1 - q3), 2 * mean1, np.sqrt(2) * s1),
                (np.full(len(part), q3), 3 * mean1, np.sqrt(3) * s1),
            ]
        else:
            base = [(np.ones(len(part)), maps * mean1, np.sqrt(maps) * s1)]
        b_crps.append(props.normal_mixture_crps(base, part["fantasy"]))
    return np.concatenate(m_crps), np.concatenate(b_crps)


# ---------------------------------------------------------------- report


def markdown_table(df):
    head = "| " + " | ".join(df.columns) + " |"
    rule = "|" + "---|" * len(df.columns)
    body = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in df.itertuples(index=False)
    ]
    return "\n".join([head, rule] + body)


def fmt_ci(mean, lo, hi, digits=4):
    return f"{mean:+.{digits}f} ({lo:+.{digits}f} to {hi:+.{digits}f})"


DUMP_SERIES = (("Bo3 maps 1-2", 2, 3), ("Bo5 maps 1-3", 3, 5))


def dump_scores(games, settings, out_dir):
    """The CI benchmark (compare_benchmarks.py): the published settings fit through
    2023, each held-out row's log score, one map per stat and the series totals
    lines are set on (kills and assists). One row per measure and unit, with the
    match (the series' first map) for a clustered bootstrap. Kept lean for CI time:
    no baselines, no tuning, and one-map scores without full distributions."""
    g = props.series_start_states(props.add_stat_states(games, settings))
    train = g[g["year"] <= VALID_END]
    test = g[(g["year"] >= TEST_START) & g["league"].isin(SCORED)].reset_index(
        drop=True
    )
    test["fantasy"] = props.fantasy_points(test)
    model = props.fit(train, settings)
    first = test.groupby("series")["gameid"].transform("first")
    match = test.assign(m=first).groupby("gameid")["m"].transform("min")
    parts = []
    for stat in props.STATS:
        parts.append(
            pd.DataFrame(
                {
                    "measure": f"map {stat}",
                    "unit": test["gameid"] + "|" + test["playerid"],
                    "match": match,
                    "loss": props.game_log_score(model, test, stat),
                }
            )
        )
    match_of = dict(zip(test["gameid"], match, strict=False))
    start_of = test.groupby("series")["gameid"].first()
    for label, maps, best_of in DUMP_SERIES:
        rows = series_rows(test, maps, best_of)
        start = rows["series"].map(start_of)
        for stat in ("kills", "assists"):
            losses = []
            for sl in chunks(len(rows)):
                part = rows.iloc[sl]
                _, win, loss = props.game_pmf(model, part, stat)
                pmf = props.series_pmf(win, loss, model.win_chance(part), best_of, maps)
                losses.append(props.log_score(pmf, part[stat]))
            parts.append(
                pd.DataFrame(
                    {
                        "measure": f"{label} {stat}",
                        "unit": start + "|" + rows["playerid"],
                        "match": start.map(match_of),
                        "loss": np.concatenate(losses),
                    }
                )
            )
    os.makedirs(out_dir, exist_ok=True)
    pd.concat(parts, ignore_index=True).round({"loss": 6}).to_csv(
        os.path.join(out_dir, "scores.csv.gz"), index=False
    )


def write_weights(games, settings, path=props.WEIGHTS_PATH):
    """Refit on every game (every league, every year) and save the model."""
    g = props.series_start_states(props.add_stat_states(games, settings))
    model = props.fit(g, settings)
    with open(path, "w") as f:
        json.dump(model.to_dict(), f, indent=1)
        f.write("\n")
    print(f"Wrote {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="write the Markdown report here")
    parser.add_argument(
        "--write-weights",
        action="store_true",
        help="refit on every game into props_weights.json",
    )
    parser.add_argument(
        "--dump",
        help="CI only: the published settings' held-out scores into DIR, no report",
    )
    args = parser.parse_args()

    games = props.load_prop_games()
    if args.dump:
        dump_scores(games, props.load_model().settings, args.dump)
        return
    settings, grid = tune(games)
    print(f"chosen settings: {settings}")

    g = prepared(settings, games)
    train = g[g["year"] <= VALID_END]
    test = g[(g["year"] >= TEST_START) & g["league"].isin(SCORED)].reset_index(
        drop=True
    )
    model = props.fit(train, settings)
    flat = props.fit(train, settings, result_term=False)
    keys = match_keys(test)
    chosen = ", ".join(f"{stat} {h} and {p}" for stat, (h, p) in settings.items())

    lines = [
        "# Prop projections: report",
        "",
        f"Generated {datetime.date.today()} by `scripts/evaluate_props.py`. Half-life "
        f"and prior games per stat ({chosen}), each the best on 2022-2023 (grid "
        "below); models fit on every league's games through 2023; scored on "
        f"{len(test):,} player-maps of LCK, LPL, LEC, LCS and international events from "
        f"2024 on ({test['gameid'].nunique():,} games, {len(np.unique(keys)):,} matches). "
        "Each projection uses the states before its series' first map. Lower is better; "
        "Δ is the model minus the other, with a 95% interval from a bootstrap over matches.",
        "",
        "## One map",
        "",
        "| Stat | Model log score | Model RPS | vs league-role avg | vs last 10 | vs season | vs player rate | vs no result term |",
        "|---|---|---|---|---|---|---|---|",
    ]
    calib = []
    for stat in props.STATS:
        m_log, m_rps, m_over = model_scores(model, test, stat)
        f_log, _, _ = model_scores(flat, test, stat)
        cells = []
        for col in (f"pace_{stat}", f"l10_{stat}", f"ssn_{stat}", f"p_{stat}"):
            b_log, _, b_over = baseline_scores(train, test, stat, col)
            cells.append(fmt_ci(*compare(m_log, b_log, keys), digits=3))
            if col == f"l10_{stat}":
                went = (test[stat] > np.floor(test[col]) + 0.5).to_numpy()
                calib.append(
                    (
                        stat,
                        m_over.mean(),
                        b_over.mean(),
                        went.mean(),
                        ece(m_over, went),
                        ece(b_over, went),
                    )
                )
        cells.append(fmt_ci(*compare(m_log, f_log, keys), digits=3))
        lines.append(
            f"| {stat} | {m_log.mean():.3f} | {m_rps.mean():.3f} | "
            + " | ".join(cells)
            + " |"
        )
        print(lines[-1])

    m_crps = fantasy_model_crps(model, test)
    cells = [
        fmt_ci(
            *compare(m_crps, fantasy_baseline_crps(train, test, col), keys), digits=3
        )
        for col in ("pace_fantasy", "l10_fantasy", "ssn_fantasy", "p_fantasy")
    ]
    lines += [
        "",
        "Fantasy points (DraftKings Pick6 scoring: kill 3, assist 2, death −1, CS 0.02), CRPS:",
        "",
        "| Model CRPS | vs league-role avg | vs last 10 | vs season | vs player rate |",
        "|---|---|---|---|---|",
        f"| {m_crps.mean():.3f} | " + " | ".join(cells) + " |",
        "",
        "## Calibration at a stand-in line (last-10 mean rounded down, plus a half)",
        "",
        "| Stat | Model P(over) | Last-10 P(over) | Went over | Model ECE | Last-10 ECE |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {s} | {a:.3f} | {b:.3f} | {c:.3f} | {d:.3f} | {e:.3f} |"
        for s, a, b, c, d, e in calib
    ]

    q3 = three_map_share(train)
    lines += [
        "",
        "## Series totals",
        "",
        f"Bo3s in the training years went to a third map {q3:.0%} of the time (the baseline's rate). "
        "Baseline: the last-10 mean per map, summed over the maps. Stand-in line: the baseline's mean rounded down plus a half.",
        "",
        "| Maps | Stat | Player-series | Model log score | Δ log vs last 10 | Δ RPS vs last 10 | Model ECE | Last-10 ECE |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, maps, best_of in (
        ("1-2 (Bo3)", 2, 3),
        ("1-2 (Bo5)", 2, 5),
        ("1-3 (Bo3, as played)", 3, 3),
        ("1-3 (Bo5)", 3, 5),
    ):
        rows = series_rows(test, maps, best_of)
        if rows.empty:
            continue
        rkeys = match_keys(rows)
        for stat in props.STATS:
            s = series_scores(model, train, rows, stat, maps, best_of, q3)
            lines.append(
                f"| {label} | {stat} | {len(rows):,} | {s['model_log'].mean():.3f} | "
                f"{fmt_ci(*compare(s['model_log'], s['base_log'], rkeys), digits=3)} | "
                f"{fmt_ci(*compare(s['model_rps'], s['base_rps'], rkeys), digits=3)} | "
                f"{ece(s['model_over'], s['went_over']):.3f} | {ece(s['base_over'], s['went_over']):.3f} |"
            )
            print(lines[-1])
        m_c, b_c = series_fantasy(model, train, rows, maps, best_of, q3)
        lines.append(
            f"| {label} | fantasy (CRPS) | {len(rows):,} | {m_c.mean():.3f} | "
            f"{fmt_ci(*compare(m_c, b_c, rkeys), digits=3)} | | | |"
        )

    lines += [
        "",
        "## Tuning grid (2022-2023, one-map log score)",
        "",
        markdown_table(grid.round(4)),
        "",
        "## Held out: per-stat settings against one half-life for every stat",
        "",
        "Log score on 2024 on (models fit through 2023), one map and the series totals "
        "lines are set on. First row: the chosen settings; the others: the difference "
        "from them (below 0 beats them), with a 95% interval over matches.",
        "",
        *halflife_check(games, settings),
        "",
    ]
    report = "\n".join(lines)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
    print(report)
    if args.write_weights:
        write_weights(games, settings)


if __name__ == "__main__":
    main()
