"""Audit raw OE snapshots and benchmark in-game probabilities chronologically.

Standalone research; does not change the database or published metrics.
Run: uv run python scripts/audit_snapshots.py
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MINUTES = (10, 15, 20)
ROLES = ("top", "jng", "mid", "bot", "sup")
STATS = ("gold", "xp", "cs", "kills", "deaths", "assists")
LEAGUES = ("LCK", "LPL", "LEC", "LCS", "Worlds", "MSI", "EWC", "FST")
ALIASES = {"NA LCS": "LCS", "LTA N": "LCS", "EU LCS": "LEC", "WLDs": "Worlds"}
FEATURES = {
    "gold": ["total_gold"],
    "scoreboard": ["total_gold", "total_kills"],
    "lanes_no_xp": [f"{r}_{s}" for r in ROLES for s in STATS if s != "xp"],
    "aura_features": [f"{r}_{s}" for r in ROLES for s in STATS],
}
META = ("league", "date", "gamelength", "result")


def game_frames(raw):
    """Count malformed games; retain one blue-oriented row for each valid game.

    Require ten unique side/role pairs, consistent metadata, one winner, and
    different teams. Calculate gaps directly, without trusting opp_* columns.
    A valid roster can still have missing snapshot fields.
    """
    players = raw[raw.position.isin(ROLES)].copy()
    missing_ids = int(players.gameid.isna().sum())
    players = players.dropna(subset=["gameid"])
    players["date"] = pd.to_datetime(players.date, utc=True, errors="coerce")
    players["league"] = players.league.replace(ALIASES)
    numeric = ["gamelength", "result"] + [f"{s}at{m}" for m in MINUTES for s in STATS]
    for col in numeric:
        players[col] = pd.to_numeric(players[col], errors="coerce")
    snapshot_cols = numeric[2:]
    players[snapshot_cols] = players[snapshot_cols].where(
        np.isfinite(players[snapshot_cols]) & (players[snapshot_cols] >= 0)
    )
    group = players.groupby("gameid")
    info = group[list(META)].first()
    consistent = (
        group[["league", "date", "gamelength"]].nunique(dropna=False).eq(1).all(axis=1)
    )
    unique = (
        players.drop_duplicates(["gameid", "side", "position"]).groupby("gameid").size()
    )
    side_roles = (
        players.groupby(["gameid", "side"]).position.nunique().unstack(fill_value=0)
    )
    side_roles = side_roles.reindex(columns=["Blue", "Red"], fill_value=0)
    teams = players.groupby(["gameid", "side"]).teamname.nunique().unstack(fill_value=0)
    teams = teams.reindex(columns=["Blue", "Red"], fill_value=0)
    results = players.groupby(["gameid", "side"]).result.agg(["first", "nunique"])
    wins = results["first"].unstack().reindex(columns=["Blue", "Red"])
    valid = (
        group.size().eq(10)
        & unique.eq(10)
        & side_roles.eq(5).all(axis=1)
        & teams.eq(1).all(axis=1)
        & group.teamname.nunique().eq(2)
        & group.teamname.count().eq(10)
        & consistent
        & info.date.notna()
        & info.gamelength.gt(0)
        & np.isfinite(info.gamelength)
        & wins.isin([0, 1]).all(axis=1)
        & wins.sum(axis=1).eq(1)
        & results["nunique"].groupby("gameid").max().eq(1)
        & group.result.count().eq(10)
    )
    info["valid_roster"] = valid.fillna(False)
    info["won"] = wins.Blue
    info["year"] = info.date.dt.year
    for name, column in (
        ("champions", "champion"),
        ("player_ids", "playerid"),
        ("player_names", "playername"),
    ):
        info[f"has_{name}"] = (
            group[column].count().eq(10) if column in players else False
        )
    kept = players[players.gameid.isin(info.index[info.valid_roster])]
    if "champion" in kept:
        draft = kept.pivot(
            index="gameid", columns=["side", "position"], values="champion"
        )
        for side in ("Blue", "Red"):
            for role in ROLES:
                info[f"{side.lower()}_{role}_champion"] = draft.get(
                    (side, role), pd.Series(dtype=object)
                )
    frames = {}
    for minute in MINUTES:
        wide = kept.pivot(
            index="gameid",
            columns=["side", "position"],
            values=[f"{s}at{minute}" for s in STATS],
        )
        frame = info.copy()
        for role in ROLES:
            for stat in STATS:
                col = f"{stat}at{minute}"
                blue = wide.get((col, "Blue", role), pd.Series(dtype=float))
                red = wide.get((col, "Red", role), pd.Series(dtype=float))
                frame[f"{role}_{stat}"] = blue - red
        for stat in ("gold", "kills"):
            frame[f"total_{stat}"] = frame[[f"{r}_{stat}" for r in ROLES]].sum(
                axis=1, min_count=5
            )
        frames[minute] = frame
    return frames, missing_ids


def load_raw(directory):
    frames = {m: [] for m in MINUTES}
    manifest = []
    missing_ids = 0
    columns = {
        "gameid",
        "teamname",
        "side",
        "position",
        "champion",
        "playerid",
        "playername",
        *META,
    }
    columns.update(f"{s}at{m}" for m in MINUTES for s in STATS)
    for path in sorted(
        directory.glob("*_LoL_esports_match_data_from_OraclesElixir.csv")
    ):
        print(f"Auditing {path.name}", flush=True)
        raw = pd.read_csv(path, usecols=lambda c: c in columns, low_memory=False)
        for col in columns - set(raw.columns):
            raw[col] = np.nan
        result, missing = game_frames(raw)
        missing_ids += missing
        for minute, frame in result.items():
            frames[minute].append(frame)
        manifest.append(
            {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    if not manifest:
        raise ValueError(f"No Oracle's Elixir CSVs found in {directory}")
    duplicates = 0
    for minute in MINUTES:
        frame = pd.concat(frames[minute])
        repeated = frame.index.duplicated(keep=False)
        duplicates = int(frame.index[repeated].nunique())
        # No arbitrary choice between multiple copies of a game.
        frames[minute] = frame[~repeated]
    return frames, {
        "files": manifest,
        "missing_gameid_player_rows": missing_ids,
        "duplicate_gameids_excluded": duplicates,
    }


def audit(frames):
    rows = []
    for minute, frame in frames.items():
        for (year, league), games in frame.groupby(["year", "league"], dropna=False):
            reached = games.gamelength.gt(minute * 60)
            usable = reached & games.valid_roster
            row = {
                "year": year,
                "league": league,
                "minute": minute,
                "games": len(games),
                "ended_by_minute": int((~reached & games.gamelength.notna()).sum()),
                "invalid_roster_or_metadata": int((~games.valid_roster).sum()),
                "reached_minute": int(reached.sum()),
            }
            for field in ("champions", "player_ids", "player_names"):
                row[f"complete_{field}"] = int((usable & games[f"has_{field}"]).sum())
            for model, cols in FEATURES.items():
                complete = usable & games[cols].notna().all(axis=1)
                row[model] = int(complete.sum())
            for stat in STATS:
                row[f"complete_{stat}"] = int(
                    (
                        usable
                        & games[[f"{r}_{stat}" for r in ROLES]].notna().all(axis=1)
                    ).sum()
                )
            rows.append(row)
    return pd.DataFrame(rows)


def temporal_split(games, year):
    """Three calendar years train; preceding year calibrates; test year is untouched."""
    return (
        games[games.year.between(year - 4, year - 2)],
        games[games.year.eq(year - 1)],
        games[games.year.eq(year)],
    )


def losses(y, p):
    p = np.clip(p, 1e-8, 1 - 1e-8)
    return -(y * np.log(p) + (1 - y) * np.log1p(-p))


def scores(y, p):
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(
        np.mean(bins == b) * abs(p[bins == b].mean() - y[bins == b].mean())
        for b in range(10)
        if np.any(bins == b)
    )
    return {
        "n": len(y),
        "log_loss": float(losses(y, p).mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "accuracy": float(np.mean((p >= 0.5) == y)),
        "ece10": float(ece),
    }


def clustered_interval(delta, clusters, repetitions=2000):
    """Paired resampling of league/calendar-day clusters, preserving game weights."""
    groups = (
        pd.DataFrame({"delta": delta, "cluster": np.asarray(clusters)})
        .groupby("cluster")
        .delta.agg(["sum", "count"])
    )
    rng = np.random.default_rng(42)
    draws = rng.integers(0, len(groups), size=(repetitions, len(groups)))
    means = groups["sum"].to_numpy()[draws].sum(axis=1) / groups["count"].to_numpy()[
        draws
    ].sum(axis=1)
    return np.quantile(means, [0.025, 0.975])


def benchmark(frames, years=(2023, 2024, 2025, 2026)):
    predictions, metrics, coefficients = [], [], []
    for minute, frame in frames.items():
        # Same complete cohort for paired comparisons; audit separately reports
        # the larger gold-only/scoreboard populations.
        games = frame[
            frame.valid_roster
            & frame.league.isin(LEAGUES)
            & frame.gamelength.gt(minute * 60)
            & frame[FEATURES["aura_features"]].notna().all(axis=1)
        ]
        for year in years:
            train, calibration, test = temporal_split(games, year)
            if min(len(train), len(calibration), len(test)) < 100:
                continue
            if min(train.won.nunique(), calibration.won.nunique()) < 2:
                continue
            print(
                f"Benchmark {minute}m/{year}: {len(train)} train, {len(calibration)} calibration, {len(test)} test",
                flush=True,
            )
            y = test.won.to_numpy(dtype=int)
            baseline = None
            for name, cols in FEATURES.items():
                model = make_pipeline(
                    StandardScaler(), LogisticRegression(C=1, max_iter=2000)
                )
                model.fit(train[cols], train.won)
                cal = LogisticRegression(C=1e6, max_iter=2000)
                cal.fit(
                    model.decision_function(calibration[cols]).reshape(-1, 1),
                    calibration.won,
                )
                raw_p = model.predict_proba(test[cols])[:, 1]
                p = cal.predict_proba(
                    model.decision_function(test[cols]).reshape(-1, 1)
                )[:, 1]
                if baseline is None:
                    baseline = p
                delta = losses(y, p) - losses(y, baseline)
                clusters = test.league + "/" + test.date.dt.strftime("%Y-%m-%d")
                low, high = clustered_interval(delta, clusters)
                row = {
                    "year": year,
                    "minute": minute,
                    "model": name,
                    "train_n": len(train),
                    "calibration_n": len(calibration),
                    **scores(y, p),
                    "raw_log_loss": scores(y, raw_p)["log_loss"],
                    "delta_gold": float(delta.mean()),
                    "delta_low": low,
                    "delta_high": high,
                }
                metrics.append(row)
                pred = test[["date", "league", "won"]].copy().reset_index()
                pred["minute"], pred["year"], pred["model"] = minute, year, name
                pred["probability"], pred["raw_probability"] = p, raw_p
                predictions.append(pred)
                scaler, fitted = model.steps[0][1], model.steps[1][1]
                coefficients.append(
                    {
                        "minute": minute,
                        "test_year": year,
                        "model": name,
                        "train_years": [year - 4, year - 2],
                        "calibration_year": year - 1,
                        "features": cols,
                        "scale_mean": scaler.mean_.tolist(),
                        "scale_std": scaler.scale_.tolist(),
                        "coef": fitted.coef_[0].tolist(),
                        "intercept": float(fitted.intercept_[0]),
                        "calibration_slope": float(cal.coef_[0, 0]),
                        "calibration_intercept": float(cal.intercept_[0]),
                    }
                )
    if not predictions:
        raise ValueError("Insufficient complete games for chronological evaluation")
    return (
        pd.DataFrame(metrics),
        pd.concat(predictions, ignore_index=True),
        coefficients,
    )


def table(frame):
    """Markdown without the optional tabulate dependency."""

    def fmt(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:.4f}" if not float(value).is_integer() else str(int(value))
        return str(value)

    return "\n".join(
        [
            "| " + " | ".join(frame.columns) + " |",
            "| " + " | ".join("---" for _ in frame.columns) + " |",
        ]
        + [
            "| " + " | ".join(map(fmt, row)) + " |"
            for row in frame.itertuples(index=False, name=None)
        ]
    )


def report(coverage, metrics, predictions, manifest, artifacts):
    recent = coverage[coverage.year.ge(2024) & coverage.league.isin(LEAGUES)]
    final_year = int(metrics.year.max())
    final = metrics[metrics.year.eq(final_year)]
    by_league = []
    for (minute, model, league), games in predictions[
        predictions.year.eq(final_year)
    ].groupby(["minute", "model", "league"]):
        if model in ("gold", "aura_features"):
            by_league.append(
                {
                    "minute": minute,
                    "model": model,
                    "league": league,
                    **scores(games.won.to_numpy(), games.probability.to_numpy()),
                }
            )
    conclusions = []
    for minute in MINUTES:
        gold = final[(final.minute.eq(minute)) & final.model.eq("gold")].iloc[0]
        rich = final[(final.minute.eq(minute)) & final.model.eq("aura_features")].iloc[
            0
        ]
        conclusions.append(
            f"- {minute} minutes: gold alone {gold.accuracy:.1%} accuracy / {gold.log_loss:.4f} log loss; "
            f"AURA features {rich.accuracy:.1%} / {rich.log_loss:.4f}. "
            f"Rich-minus-gold log loss {rich.delta_gold:+.4f} "
            f"(95% interval {rich.delta_low:+.4f} to {rich.delta_high:+.4f})."
        )
    parts = [
        "# Snapshot audit and chronological win-probability baseline",
        "",
        "Research only; estimates current-map outcomes, not series outcomes or trading profitability.",
        "",
        f"## Findings: {final_year} calendar holdout",
        "",
        *conclusions,
        "",
        "These are retrospective prediction benchmarks, not a demonstrated market edge. "
        "The complete-case cohort and league mix can change between years; consult league scores below. "
        "Calibration fitted on the preceding year may worsen next-year log loss; both raw and calibrated scores are retained. "
        "Do not choose a recalibration method using this final holdout.",
        "",
        "## Method",
        "",
        "Raw CSVs are audited before database filtering. A complete game has ten unique side/role pairs, "
        "consistent league/timestamp/duration, two teams and exactly one winner. Missing or negative/nonfinite "
        "snapshot values are unavailable, never imputed. Gaps are blue minus red. Calendar year comes from the "
        "match timestamp, not the season label. A game must last strictly beyond the target minute.",
        "",
        "Each test year uses the three years ending two years earlier for training, and the immediately preceding "
        "year for sigmoid calibration. Example: 2026 uses 2022–2024 training and 2025 calibration. "
        "The scaler and logistic regression (C=1) see training only. The 2023–2025 folds are development "
        "diagnostics; 2026 is the final calendar holdout, scored with fixed features/settings. "
        "No tuning follows these holdout results. 2026 is partial through the last locally downloaded game.",
        "",
        "All models share the complete AURA-feature cohort for paired comparisons, restricted to "
        + ", ".join(LEAGUES)
        + ". "
        "One row per game per minute; each minute has its own model. Whole calendar years separate "
        "training/calibration/test. Explicit series identifiers are unavailable; a series crossing New Year "
        "cannot be guaranteed to stay in one split. Intervals resample league/day clusters, an approximate "
        "series grouping, 2,000 times with seed 42. ECE uses ten equal-width bins and is descriptive.",
        "",
        "## Source inventory",
        "",
        f"{len(manifest['files'])} files; {manifest['missing_gameid_player_rows']} player rows missing game IDs; "
        f"{manifest['duplicate_gameids_excluded']} game IDs repeated across files excluded entirely. "
        f"Latest evaluated match timestamp: {predictions.date.max().isoformat()}.",
        "",
        "File hashes, full coverage, fitted parameters, per-game predictions, calibration bins, and league-specific "
        f"scores are in `{artifacts}` (gitignored).",
        "",
        "## Recent coverage",
        "",
        "Counts are games, not player rows. Reached includes malformed games; invalid overlaps other columns. "
        "Gold requires all ten players’ gold; AURA requires all six stats for all ten. Ended games are "
        "excluded from the minute's prediction population, not treated as missing live observations.",
        "",
        table(
            recent[
                [
                    "year",
                    "league",
                    "minute",
                    "games",
                    "ended_by_minute",
                    "invalid_roster_or_metadata",
                    "reached_minute",
                    "gold",
                    "scoreboard",
                    "aura_features",
                ]
            ]
        ),
        "",
        "### Draft and identity coverage at 10 minutes",
        "",
        table(
            recent[recent.minute.eq(10)][
                [
                    "year",
                    "league",
                    "games",
                    "complete_champions",
                    "complete_player_ids",
                    "complete_player_names",
                ]
            ]
        ),
        "",
        "## Chronological benchmark",
        "",
        "Lower log loss/Brier is better. Negative delta means improvement over calibrated gold alone; "
        "delta_low/high are paired 95% cluster-bootstrap intervals. Raw log loss is before calibration.",
        "",
        table(
            metrics[
                [
                    "year",
                    "minute",
                    "model",
                    "train_n",
                    "calibration_n",
                    "n",
                    "log_loss",
                    "raw_log_loss",
                    "brier",
                    "accuracy",
                    "ece10",
                    "delta_gold",
                    "delta_low",
                    "delta_high",
                ]
            ]
        ),
        "",
        f"## {final_year} holdout by league",
        "",
        "Small international samples are descriptive only; do not interpret their calibration as stable.",
        "",
        table(pd.DataFrame(by_league)),
        "",
        "## Live feature availability",
        "",
        "| Feature | Broadcast feasibility | Historical benchmark |",
        "| --- | --- | --- |",
        "| Team gold difference | Usually on scoreboard; rounded and delayed | Sum of player gold differences; validate against displayed team totals |",
        "| Team kill difference | Usually on scoreboard | Sum of player kills |",
        "| Lane CS and KDA | Often visible; layout/replays may hide them | lanes_no_xp model |",
        "| Individual gold | Not continuously visible | Needed for lane models; requires structured feed or occasional overlay |",
        "| Individual XP | Not consistently visible; level is not exact XP | AURA-feature model is a richer-data reference |",
        "| Champions/players | Match metadata or draft; stable per game | Not fitted in this first benchmark |",
        "| Towers/dragons/barons | Often on scoreboard | Final-game totals exist, but fixed-minute objective values are not used here |",
        "",
        "Feasibility is a collection design assumption, not verified OCR or live feed access. "
        "Historical summed gold is more precise than rounded scoreboard reads; test rounding and extraction noise before deployment.",
        "",
        "## Next work and limits",
        "",
        "Start the collection pilot with team gold, kills, game clock, and match metadata. "
        "Use richer lane/XP models only where a live source supplies those fields. "
        "Investigate snapshot gaps by league; complete-case selection means these results do not establish "
        "performance on missing-data games. Add a strictly historical team-strength prior and draft "
        "features in a new development experiment, with a new untouched evaluation period. "
        "Do not substitute final-game objectives or season-level scores as live inputs. "
        "There are no synchronized market prices, executable fills, fees, or latency measurements here; "
        "this benchmark establishes prediction quality only.",
        "",
    ]
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("docs/snapshot_report.md"))
    parser.add_argument("--artifacts", type=Path, default=Path("data/snapshot_audit"))
    args = parser.parse_args()
    frames, manifest = load_raw(args.raw_dir)
    coverage = audit(frames)
    metrics, predictions, coefficients = benchmark(frames)
    slices, bins = [], []
    for (year, minute, model, league), group in predictions.groupby(
        ["year", "minute", "model", "league"]
    ):
        slices.append(
            {
                "year": year,
                "minute": minute,
                "model": model,
                "league": league,
                **scores(group.won.to_numpy(), group.probability.to_numpy()),
            }
        )
    for (year, minute, model), group in predictions.groupby(
        ["year", "minute", "model"]
    ):
        bucket = np.minimum((group.probability * 10).astype(int), 9)
        for b, rows in group.groupby(bucket):
            bins.append(
                {
                    "year": year,
                    "minute": minute,
                    "model": model,
                    "bin": int(b),
                    "n": len(rows),
                    "mean_probability": rows.probability.mean(),
                    "win_rate": rows.won.mean(),
                }
            )
    args.artifacts.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "coverage": coverage,
        "metrics": metrics,
        "predictions": predictions,
        "league_scores": pd.DataFrame(slices),
        "calibration_bins": pd.DataFrame(bins),
    }.items():
        frame.to_csv(args.artifacts / f"{name}.csv", index=False)
    manifest["models"] = coefficients
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        report(coverage, metrics, predictions, manifest, args.artifacts)
    )
    print(f"Wrote {args.out} and {args.artifacts}")


if __name__ == "__main__":
    main()
