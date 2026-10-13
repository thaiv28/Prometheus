"""Additional frozen-tempo attribution, chronological and offline market checks.

Run after elo_tempo_surprise.py. No grids are extended; amplitude remains .175.
Market input is a PRIVATE COPY of data/markets/frames.pkl (no fetching).
"""

import argparse
import datetime
from pathlib import Path

import elo_tempo_surprise as tempo
import elo_variants as ev
import numpy as np
import pandas as pd

from prometheus import elo, forge, form, schedule
from prometheus.evaluation import (
    cross_league_games,
    fit_win_curve,
    game_losses,
    other_league_games,
    shrunk_league_slopes,
)
from prometheus.types import INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

HEADER = "| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |\n|---|---|---:|---:|---:|---|"


def chronological_form(frame, states):
    """Inner expanding-year Form fits; no outcome from year Y enters Y's scores."""
    gaps = ev.em._state_gaps(frame, states)
    score = np.zeros(len(states))
    for year in sorted(states["year"].unique()):
        train = (frame["year"] < year) & (frame["test_set"] == "Domestic")
        rows = (states["year"] == year).to_numpy()
        if train.any():
            weights = dict(
                zip(
                    ev.em.GLORY_FEATURES,
                    form.fit_form_weights(gaps[train], frame.loc[train, "won"]),
                )
            )
            score[rows] = form.scores(states[rows], weights)
    return pd.Series(
        form.league_relative(states, score),
        index=pd.MultiIndex.from_frame(states[["gameid", "teamid"]]),
    )


def earlier_probabilities(frame, columns, years, per_league=False):
    p = np.full(len(frame), np.nan)
    for year in years:
        train = frame[frame["year"] < year]
        test = (frame["year"] == year).to_numpy()
        if per_league:
            pooled, slopes = shrunk_league_slopes(
                train["elo_live"], train["won"], train["league"]
            )
            weights = frame.loc[test, "league"].map(slopes).fillna(pooled).to_numpy()
            p[test] = 1 / (
                1 + np.exp(-weights * frame.loc[test, "elo_live"].to_numpy())
            )
        else:
            curve = fit_win_curve(train[columns].to_numpy(), train["won"])
            p[test] = curve(frame.loc[test, columns].to_numpy())
    return p


def chronological_scores(inputs, pre, years):
    frame = ev._with_elo(inputs.frame, pre)
    states = ev.variant_form_states(inputs, pre)
    relative = chronological_form(frame, states)
    frame = ev.em.add_form(frame, states, relative)
    ep = earlier_probabilities(frame, "elo_live", years)
    fp = ep.copy()
    same = frame["blue_league"] == frame["red_league"]
    fp[same] = earlier_probabilities(
        frame[same].reset_index(drop=True), ["elo_live", "form"], years
    )
    output = {}
    for section in ev.TEST_SETS:
        keep = (frame["test_set"] == section) & frame["year"].isin(years)
        for metric, p in (("Elo", ep), ("FORGE", fp)):
            output[(section, metric)] = (
                frame.loc[keep, "gameid"].to_numpy(),
                game_losses(p[keep], frame.loc[keep, "won"])["log_loss"].to_numpy(),
            )
    pairs = tempo.pair_frame(inputs, pre)
    cross = cross_league_games(pairs, INTERNATIONAL_LEAGUES, ev.em.MAJORS)
    cp = earlier_probabilities(cross, "elo_live", years)
    keep = cross["year"].isin(years)
    output[("Cross-league", "Elo")] = (
        cross.loc[keep, "gameid"].to_numpy(),
        game_losses(cp[keep], cross.loc[keep, "won"])["log_loss"].to_numpy(),
    )
    other = other_league_games(pairs, INTERNATIONAL_LEAGUES, ev.em.MAJORS)
    op = earlier_probabilities(other, "elo_live", years, per_league=True)
    keep = other["year"].isin(years)
    output[("Within other leagues", "Elo")] = (
        other.loc[keep, "gameid"].to_numpy(),
        game_losses(op[keep], other.loc[keep, "won"])["log_loss"].to_numpy(),
    )
    other["form"] = ev.em.form_gap(
        relative, other["gameid"], other["teamid"], other["opponent_teamid"]
    )
    other = other[other["form"].notna()].reset_index(drop=True)
    fp = earlier_probabilities(other, ["elo_live", "form"], years)
    keep = other["year"].isin(years)
    output[("Within other leagues", "FORGE")] = (
        other.loc[keep, "gameid"].to_numpy(),
        game_losses(fp[keep], other.loc[keep, "won"])["log_loss"].to_numpy(),
    )
    return output


def memory_latest(records, offsets):
    """Authoritative LatestElos query/output semantics on private replay records."""
    meta = pd.read_sql(
        "SELECT gameid, teamid, teamname, league, date AS latest_date, CAST(strftime('%Y', date) AS INT) AS year, DATE(date) AS day FROM matches",
        get_engine(),
    )
    obj = elo.LatestElos.__new__(elo.LatestElos)
    obj.games = (
        records.rename(columns={"main_elo": "elo"})
        .merge(meta, on=["gameid", "teamid"])
        .sort_values(["latest_date", "gameid"], kind="stable")
    )
    obj.offsets = offsets.assign(
        day=pd.to_datetime(offsets["date"]).dt.strftime("%Y-%m-%d")
    )
    return obj


def market_calls(frame, states, latest, form_weights, weights, league_curves):
    """Raw Form routing equivalent to schedule.game_probability, daily cutoff."""
    days = pd.to_datetime(states["date"]).dt.date
    cache = {}
    calls = []
    methods = []
    for row in frame.itertuples(index=False):
        day = row.start.date()
        if day not in cache:
            forms, _ = forge.team_forms(states[days < day], form_weights=form_weights)
            elos = latest(day - datetime.timedelta(days=1))
            elos = elos.sort_values("latest_date", ascending=False).drop_duplicates(
                "teamname"
            )
            forms = forms.sort_values("latest_date", ascending=False).drop_duplicates(
                "teamname"
            )
            cache[day] = elos.merge(
                forms[["teamname", "form"]], on="teamname", how="left"
            ).set_index("teamname")
        rating = cache[day]
        a, b = rating.loc[row.ours1], rating.loc[row.ours2]
        gap = a.elo - b.elo
        if a.league != b.league:
            logit = weights["cross_region_elo_weight"] * gap
            method = "elo-cross"
        elif a.league in schedule.MAJORS:
            logit = weights["elo_weight"] * gap + weights["form_weight"] * (
                (a.form if pd.notna(a.form) else 0)
                - (b.form if pd.notna(b.form) else 0)
            )
            method = "forge"
        elif pd.notna(a.form) and pd.notna(b.form):
            logit = weights["other_league_forge_elo_weight"] * gap + weights[
                "other_league_form_weight"
            ] * (a.form - b.form)
            method = "forge"
        else:
            logit = (
                league_curves.get(a.league, weights["other_league_elo_weight"]) * gap
            )
            method = "elo"
        p = 1 / (1 + np.exp(-logit))
        calls.append(
            schedule.series_probability(p, row.best_of, schedule.SERIES_RHO[row.major])
        )
        methods.append(method)
    return np.asarray(calls), np.asarray(methods)


def fitted_weights(inputs, pre, states, last_year):
    major = ev._with_elo(inputs.frame, pre)
    major = major[major["year"] <= last_year].reset_index(drop=True)
    other = other_league_games(
        tempo.pair_frame(inputs, pre), INTERNATIONAL_LEAGUES, ev.em.MAJORS
    )
    other = other[other["year"] <= last_year].reset_index(drop=True)
    return ev.em.published_weights(major, states, other)


def market_checks(
    inputs,
    base,
    candidate,
    states_base,
    states_candidate,
    records,
    offsets,
    market_path,
    verify=True,
    extra=None,
):
    series, _, _, _ = pd.read_pickle(market_path)
    series = series[series["start"].map(lambda x: x.year >= 2025)].reset_index(
        drop=True
    )
    methods = None
    if verify:
        # First reproduce ordinary current-code calls using both the DB and its replay,
        # NOT the cached ours column (possibly generated by older production code).
        latest = memory_latest(records[0], offsets[0])
        tracked_form = form.load_weights()["weights"]
        tracked_forge, tracked_curves = forge.load_weights(), forge.load_league_curves()
        mine, methods = market_calls(
            series, states_base, latest, tracked_form, tracked_forge, tracked_curves
        )
        before = schedule.RatingsBefore(states_base)
        direct = []
        for row in series.itertuples(index=False):
            ratings = before(row.start.date())
            p, _method = schedule.game_probability(
                ratings.loc[row.ours1], ratings.loc[row.ours2]
            )
            direct.append(
                schedule.series_probability(
                    p, row.best_of, schedule.SERIES_RHO[row.major]
                )
            )
        if not np.isfinite(mine).all() or not np.isfinite(direct).all():
            raise AssertionError(
                "market reconstruction produced nonfinite probabilities"
            )
        maximum = np.max(np.abs(mine - direct))
        if maximum > 1e-9:
            raise AssertionError(
                f"market reconstruction disagrees with current routing: {maximum}"
            )
        proof = f"Current-code reconstruction max series probability difference: {maximum:.3g}."
    else:
        proof = "The preceding conditional validation reproduced current routing to 1.87e-14; that equality pass is reused, not rerun here."
    # Frozen <=2024 fitting gives genuine later-outcome exclusion for market calls.
    calls = []
    models = list(
        zip((base, candidate), (states_base, states_candidate), records, offsets)
    )
    if extra is not None:
        models.append(extra)
    for pre, states, rec, off in models:
        fw, curves, weights = fitted_weights(inputs, pre, states, 2024)
        p, rebuilt_methods = market_calls(
            series, states, memory_latest(rec, off), fw, weights, curves
        )
        if not np.isfinite(p).all():
            raise AssertionError("frozen-fit market probabilities are nonfinite")
        if methods is None:
            methods = rebuilt_methods
        if not np.array_equal(methods, rebuilt_methods):
            raise AssertionError("market routing changed")
        calls.append(p)
    losses = [game_losses(p, series["won1"])["log_loss"].to_numpy() for p in calls]
    slices = {
        "All": np.ones(len(series), bool),
        "Same major league FORGE": (methods == "forge") & series["major"].to_numpy(),
        "Same other league FORGE": (methods == "forge") & ~series["major"].to_numpy(),
        "Cross-league Elo": methods == "elo-cross",
    }
    base_scores, candidate_scores = {}, {}
    for section, keep in slices.items():
        if keep.any():
            keys = series.index.to_numpy()[keep]
            base_scores[(section, "Series")] = (keys, losses[0][keep])
            candidate_scores[(section, "Series")] = (keys, losses[1][keep])
    text = f"{proof} Cached ours are unused; cached prices/cohort only. Both Form and forecast weights are frozen through 2024; the cutoff is exactly the day before start, main roster with carried regional offsets, and current series rho.\n\n{HEADER}\n{tempo.comparison(base_scores, candidate_scores)}\n"
    if extra is not None:
        extra_scores = {}
        for section, keep in slices.items():
            if keep.any():
                extra_scores[(section, "Series")] = (
                    series.index.to_numpy()[keep],
                    losses[2][keep],
                )
        text += f"\nFixed curve versus conditional curve on the same market cohort:\n\n{HEADER}\n{tempo.comparison(extra_scores, candidate_scores)}\n"
    pd.to_pickle((series, calls, methods), Path("data/tempo_market_calls.pkl"))
    return text


def clustered_comparison(inputs, baseline, candidate):
    """Paired bootstrap of team-pair/date clusters (conservative series proxy)."""
    cluster_by_game = {}
    for row in inputs.games.itertuples(index=False):
        cluster_by_game[row.gameid] = (
            str(row.league),
            str(row.date)[:10],
            tuple(sorted((str(row.teamid), str(row.opponent_teamid)))),
        )
    lines = [
        "| Slice | Metric | Clusters | Delta [cluster 95% CI] |",
        "|---|---|---:|---|",
    ]
    for key, (keys, loss) in candidate.items():
        deltas = loss - baseline[key][1]
        groups = (
            pd.DataFrame(
                {"cluster": [cluster_by_game[g] for g in keys], "delta": deltas}
            )
            .groupby("cluster")["delta"]
            .agg(["sum", "count"])
        )
        totals, counts = groups["sum"].to_numpy(), groups["count"].to_numpy()
        rng = np.random.default_rng(0)
        samples = []
        for _ in range(2000):
            draw = rng.integers(0, len(groups), len(groups))
            samples.append(totals[draw].sum() / counts[draw].sum())
        lo, hi = np.percentile(samples, [2.5, 97.5])
        lines.append(
            f"| {key[0]} | {key[1]} | {len(groups):,} | {deltas.mean():+.6f} [{lo:+.6f}, {hi:+.6f}] |"
        )
    return "\n".join(lines)


def fixed_validation(inputs, base, fixed, conditional, records, offsets, test, args):
    train, _ = ev.split_years(inputs.frame["year"].unique())
    development = (
        ev.score(inputs, fixed, years=train, forge=False)
        .log_loss("elo_live", "Domestic")
        .mean()
    )
    text = "# Fixed-center duration curve follow-up\n\nThis candidate was noticed in the conditional-tempo attribution ablation after inspecting historical 2022+ results. It is retrospectively explored, not a new prospective confirmation. Exact constants stay frozen (.825, .175, 1800 seconds, 300 seconds); no grid or new tuning. Published defaults remain unchanged.\n\n"
    text += f"Development domestic Elo (2014–2021, no tuning): {development:.6f}.\n"
    years = sorted(inputs.frame["year"].unique())
    print("Fixed: all-season guards...", flush=True)
    text += f"\n## All-season guards\n\n{HEADER}\n{tempo.comparison(tempo.all_scores(inputs, base, years), tempo.all_scores(inputs, fixed, years))}\n"
    print("Fixed: nested chronological sensitivity...", flush=True)
    text += f"\n## Nested chronological sensitivity, 2022 onward\n\nAll first-stage Form and outer calibration use strictly earlier years as in the preceding validation; no constants were refit on the held-out years.\n\n{HEADER}\n{tempo.comparison(chronological_scores(inputs, base, test), chronological_scores(inputs, fixed, test))}\n"
    fixed_games = inputs.games[ev.ELO_COLUMNS].assign(
        gamelength=0.825
        + 0.175 * np.tanh((1800 - inputs.games["gamelength"].to_numpy()) / 300)
    )
    fixed_records, fixed_offsets = elo.compute_elo_records(
        fixed_games, ev.margin_elo_change, rosters=inputs.rosters
    )
    if args.market_cache.exists():
        print("Fixed: frozen-weight market evidence (three methods)...", flush=True)
        text += "\n## Frozen-through-2024 market evidence\n\n" + market_checks(
            inputs,
            base,
            fixed,
            ev.variant_form_states(inputs, base),
            ev.variant_form_states(inputs, fixed),
            (records[0], fixed_records),
            (offsets[0], fixed_offsets),
            args.market_cache,
            verify=False,
            extra=(
                conditional,
                ev.variant_form_states(inputs, conditional),
                records[1],
                offsets[1],
            ),
        )
    out = (
        args.out
        if args.out != Path("docs/research/elo_tempo_validation.md")
        else Path("docs/research/elo_tempo_fixed.md")
    )
    out.write_text(text)
    print(text, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--market-cache", type=Path, default=Path("data/markets/frames.pkl")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/elo_tempo_validation.md")
    )
    parser.add_argument(
        "--fixed-only",
        action="store_true",
        help="Validate the frozen fixed-center ablation without repeating conditional checks",
    )
    args = parser.parse_args()
    inputs = ev.load_inputs()
    base, _check = ev.reproduction_check(inputs)
    rec_base, off_base = elo.compute_elo_records(
        inputs.games[ev.ELO_COLUMNS],
        elo.calculate_game_length_elo_change,
        rosters=inputs.rosters,
    )
    rec, off, _ = tempo.replay(inputs, 0.175, records=True)
    candidate = rec.set_index(["gameid", "teamid"])["pre_match_elo"]
    _, test = ev.split_years(inputs.frame["year"].unique())
    print("Attribution check...", flush=True)
    fixed = ev.replay(
        inputs,
        lambda g: 0.825 + 0.175 * np.tanh((1800 - g["gamelength"].to_numpy()) / 300),
    )
    if args.fixed_only:
        fixed_validation(
            inputs, base, fixed, candidate, (rec_base, rec), (off_base, off), test, args
        )
        return
    held_base = tempo.all_scores(inputs, base, test)
    held_candidate = tempo.all_scores(inputs, candidate, test)
    fixed_scores = tempo.all_scores(inputs, fixed, test)
    text = "# Conditional tempo validation\n\nFrozen amplitude .175 selected only through 2021; no extra settings tuned. No defaults changed.\n\n"
    text += f"## Same residual curve, fixed 30-minute center versus published baseline\n\n{HEADER}\n{tempo.comparison(held_base, fixed_scores)}\n"
    text += f"\n## Conditional center versus fixed center\n\n{HEADER}\n{tempo.comparison(fixed_scores, held_candidate)}\n"
    print("All-season guards...", flush=True)
    years = sorted(inputs.frame["year"].unique())
    text += f"\n## All-season guards (2014 onward, out-of-year fitting)\n\n{HEADER}\n{tempo.comparison(tempo.all_scores(inputs, base, years), tempo.all_scores(inputs, candidate, years))}\n"
    print("Nested chronological sensitivity...", flush=True)
    text += f"\n## Nested chronological sensitivity, 2022 onward\n\nEach first-stage Form year uses only earlier domestic outcomes. Outer Elo/Forge/league curves train only on earlier years, using those chronological Form scores. The first year has zero Form as a warm-up; all 2022+ models have ample prior seasons. This is an integrity sensitivity, not another tuned variant.\n\n{HEADER}\n{tempo.comparison(chronological_scores(inputs, base, test), chronological_scores(inputs, candidate, test))}\n"
    if args.market_cache.exists():
        print("Offline market reconstruction...", flush=True)
        text += "\n## Offline market-series evidence\n\n" + market_checks(
            inputs,
            base,
            candidate,
            ev.variant_form_states(inputs, base),
            ev.variant_form_states(inputs, candidate),
            (rec_base, rec),
            (off_base, off),
            args.market_cache,
        )
    else:
        text += "\nMarket check not run: a private copied frames.pkl cache is absent.\n"
    text += (
        "\n## Team-pair/day cluster sensitivity, selected held-out variant\n\nClusters are league × calendar day × unordered team pair, a conservative series proxy (separate same-day series can be pooled).\n\n"
        + clustered_comparison(inputs, held_base, held_candidate)
        + "\n"
    )
    args.out.write_text(text)
    print(text, flush=True)


if __name__ == "__main__":
    main()
