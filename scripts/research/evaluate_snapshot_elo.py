"""Pre-match Elo ablation for in-game models; development 2023–2025 only.

Run: .venv/bin/python scripts/research/evaluate_snapshot_elo.py
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import evaluate_champions as champions
from prometheus import elo
from prometheus.utils import get_engine

snapshots = champions.snapshots
VARIANTS = {
    "stats": ("stats", False, "stats"),
    "stats_elo": ("stats", True, "stats"),
    "champions": ("champions", False, "champions"),
    "champions_elo": ("champions", True, "champions"),
}


def frame_hash(frame):
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()


def load_ratings(end_year=2025):
    """Replay existing Elo unchanged in memory through the requested year."""
    games = elo.load_elo_games()
    games["date"] = pd.to_datetime(games.date, utc=True)
    games = games[games.date.dt.year.le(end_year)].copy()
    if not games.date.is_monotonic_increasing or games.gameid.duplicated().any():
        raise ValueError("Elo replay must contain unique games in chronological order")
    game_ids = set(games.gameid)
    rosters = {
        key: value for key, value in elo.load_rosters().items() if key[0] in game_ids
    }
    records, _ = elo.compute_elo_records(
        games, elo.calculate_game_length_elo_change, rosters=rosters
    )
    saved = elo.get_pregame_elos("game_length")[["gameid", "teamid", "elo"]]
    check = records.merge(saved, on=["gameid", "teamid"], validate="one_to_one")
    error = float((check.pre_match_elo - check.elo).abs().max())
    if len(check) != len(records) or error > 1e-8:
        raise ValueError(
            f"Saved pre-match Elo disagrees with chronological replay: {error}"
        )
    metadata = pd.read_sql(
        "SELECT gameid, teamid, side, date, result, gamelength FROM matches",
        get_engine(),
    )
    metadata = metadata[metadata.gameid.isin(games.gameid)]
    metadata["date"] = pd.to_datetime(metadata.date, utc=True)
    ratings = orient_ratings(records, metadata)
    roster_rows = pd.DataFrame(
        [
            (game, team, "|".join(players))
            for (game, team), players in sorted(rosters.items())
        ],
        columns=["gameid", "teamid", "players"],
    )
    audit = {
        "elo_games": len(games),
        "records": len(records),
        "saved_rating_max_difference": error,
        "tied_timestamp_games": int(games.date.duplicated(keep=False).sum()),
        "games_sha256": frame_hash(games),
        "rosters_sha256": frame_hash(roster_rows),
        "pre_match_records_sha256": frame_hash(records),
        "algorithm": {
            "starting_elo": elo.STARTING_ELO,
            "league_share": elo.LEAGUE_SHARE,
            "active_days": elo.ACTIVE_DAYS,
            "K": 20,
        },
    }
    return ratings, audit


def orient_ratings(records, metadata):
    """Match both sides by immutable game/team IDs; never read post-match Elo."""
    joined = metadata.merge(
        records[["gameid", "teamid", "pre_match_elo"]],
        on=["gameid", "teamid"],
        validate="one_to_one",
    )
    if joined.duplicated(["gameid", "side"]).any():
        raise ValueError("Duplicate game/side ratings")
    blue = joined[joined.side.eq("Blue")].set_index("gameid")
    red = joined[joined.side.eq("Red")].set_index("gameid")
    result = blue[["date", "result", "gamelength"]].rename(
        columns={"date": "elo_date", "result": "elo_won", "gamelength": "elo_length"}
    )
    result["elo_gap"] = blue.pre_match_elo - red.pre_match_elo.reindex(blue.index)
    return result


def attach_ratings(frame, ratings):
    joined = frame.join(ratings, validate="one_to_one")
    valid = (
        joined.date.eq(joined.elo_date)
        & joined.won.eq(joined.elo_won)
        & joined.gamelength.eq(joined.elo_length)
        & np.isfinite(joined.elo_gap)
    )
    joined["elo_available"] = valid
    joined.loc[~valid, "elo_gap"] = np.nan
    return joined


def evaluate(frames, ratings, variants=None):
    variants = VARIANTS if variants is None else variants
    predictions, parameters, coverage = [], [], []
    for minute, frame in frames.items():
        cohort = frame[
            frame.valid_roster
            & frame.league.isin(snapshots.LEAGUES)
            & frame.gamelength.gt(minute * 60)
            & frame[snapshots.FEATURES["aura_features"]].notna().all(axis=1)
            & frame.year.le(2025)
        ]
        cohort = cohort[
            cohort[champions.DRAFT_COLS].notna().all(axis=1)
            & cohort[champions.DRAFT_COLS].ne("").all(axis=1)
        ]
        cohort = attach_ratings(cohort, ratings)
        for year, part in cohort.groupby("year"):
            coverage.append(
                {
                    "minute": minute,
                    "year": int(year),
                    "snapshot_draft_complete": len(part),
                    "elo_complete": int(part.elo_available.sum()),
                }
            )
        cohort = cohort[cohort.elo_available]
        for year in champions.YEARS:
            train, calibration, test = snapshots.temporal_split(cohort, year)
            if min(len(train), len(calibration), len(test)) < 100:
                continue
            print(
                f"Elo {minute}m/{year}: {len(train)} train, {len(calibration)} calibrate, {len(test)} evaluate",
                flush=True,
            )
            for base in ("gold", "aura_features"):
                for name, (fit_variant, add_elo, _) in variants.items():
                    columns = list(snapshots.FEATURES[base]) + (
                        ["elo_gap"] if add_elo else []
                    )
                    p, raw, fitted = champions.fit_predict(
                        train, calibration, test, columns, fit_variant
                    )
                    pred = test[["date", "league", "won", "elo_gap"]].reset_index()
                    pred["minute"], pred["year"], pred["base"], pred["variant"] = (
                        minute,
                        year,
                        base,
                        name,
                    )
                    pred["probability"], pred["raw_probability"] = p, raw
                    predictions.append(pred)
                    parameters.append(
                        {
                            "minute": minute,
                            "year": year,
                            "base": base,
                            "variant": name,
                            "train_n": len(train),
                            "calibration_n": len(calibration),
                            **fitted,
                        }
                    )
    if not predictions:
        raise ValueError("Insufficient matched rating coverage")
    return pd.concat(predictions, ignore_index=True), parameters, pd.DataFrame(coverage)


def score(predictions, annual=False, variants=None):
    variants = VARIANTS if variants is None else variants
    rows = []
    keys = ["minute", "base"] + (["year"] if annual else [])
    for key, group in predictions.groupby(keys):
        for variant, part in group.groupby("variant"):
            control = variants[variant][2]
            reference = (
                group[group.variant.eq(control)].set_index("gameid").loc[part.gameid]
            )
            y, p = part.won.to_numpy(), part.probability.to_numpy()
            delta = snapshots.losses(y, p) - snapshots.losses(
                y, reference.probability.to_numpy()
            )
            low, high = snapshots.clustered_interval(
                delta, part.league + "/" + part.date.dt.strftime("%Y-%m-%d")
            )
            rows.append(
                {
                    **dict(zip(keys, key)),
                    "variant": variant,
                    **snapshots.scores(y, p),
                    "raw_log_loss": snapshots.scores(
                        y, part.raw_probability.to_numpy()
                    )["log_loss"],
                    "control": control,
                    "delta_base": float(delta.mean()),
                    "delta_low": low,
                    "delta_high": high,
                }
            )
    return pd.DataFrame(rows)


def report(pooled, annual, coverage, audit):
    candidates = pooled[pooled.variant.str.endswith("_elo")]
    finding = (
        "Every Elo addition improves pooled log loss, with all paired 95% intervals below zero."
        if candidates.delta_high.lt(0).all()
        else "Elo improvements are mixed; inspect paired intervals before selecting a candidate."
    )
    yearly = annual[annual.variant.str.endswith("_elo")]
    if yearly.delta_base.lt(0).all():
        finding += " Every annual comparison also improves in point estimate."
    finding += " Keep stats+Elo as a development candidate; champion additions remain exploratory. Calibration is not uniformly improved. No production adoption or fresh validation is claimed."
    return "\n".join(
        [
            "# Pre-match Elo and in-game win probability",
            "",
            "Exploratory 2023–2025 development folds; 2026 excluded. Lower log loss is better.",
            "",
            "## Finding",
            "",
            finding,
            "",
            "## Protocol",
            "",
            "Add blue-minus-red pre-match Elo as one standardized numeric feature. Gold and 30-lane-stat bases each compare stats vs stats+Elo (C=1) and champions vs champions+Elo (C=0.1). Each pair has identical complete snapshot/draft/Elo games and regularization. Champion effects are by role, with no lane pairs or state interactions. Separate models at 10/15/20 minutes learn separate Elo weights. No hyperparameter search.",
            "",
            "Three training calendar years, the next year for sigmoid calibration, then the evaluation year. Scaling, champion vocabulary and coefficients use training only. Report calibrated and raw scores. Paired 95% intervals resample league/day clusters, 2,000 draws, seed 42, without multiplicity adjustment.",
            "",
            "## Elo provenance",
            "",
            f"Existing player/roster-aware, game-length-weighted Elo replayed unchanged in memory through 2025: {audit['elo_games']} games. Pre-match ratings reproduce all stored records with maximum difference {audit['saved_rating_max_difference']:.3g}. Ratings are captured before updating from the current game result or length. Joins use game/team IDs and blue/red sides; raw snapshot date, winner and duration must match DB metadata. Missing or mismatched ratings are excluded from every comparison, never imputed.",
            "",
            f"{audit['tied_timestamp_games']} historical games share timestamps; the existing replay breaks ties by game ID. Match timestamps are the archive ordering, not a verified feed of result availability. Elo algorithm constants were established in prior research; these folds are not an untouched evaluation of their selection. No DB writes or published metric changes.",
            "",
            "## Pooled results",
            "",
            snapshots.table(pooled),
            "",
            "## Annual results",
            "",
            snapshots.table(annual),
            "",
            "## Coverage",
            "",
            snapshots.table(coverage),
            "",
            "## Limits and decision",
            "",
            "Inspect annual consistency, raw versus calibrated scores and uncertainty before choosing a candidate. These viewed folds support development, not final validation or market profitability. Any candidate needs new untouched matches and synchronized live inputs/prices. Ratings reflect starters; live inference needs the confirmed lineup. Earlier series maps may inform later maps when results are available, but archive timestamps alone do not prove availability. Complete-case league coverage remains uneven.",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("docs/research/snapshot_elo_report.md"))
    parser.add_argument("--artifacts", type=Path, default=Path("data/snapshot_elo"))
    args = parser.parse_args()
    ratings, audit = load_ratings()
    frames, manifest = snapshots.load_raw(args.raw_dir)
    predictions, parameters, coverage = evaluate(frames, ratings)
    pooled, annual = score(predictions), score(predictions, annual=True)
    args.artifacts.mkdir(parents=True, exist_ok=True)
    for name, data in {
        "predictions": predictions,
        "pooled": pooled,
        "metrics": annual,
        "coverage": coverage,
        "pregame_ratings": ratings.reset_index(),
    }.items():
        data.to_csv(args.artifacts / f"{name}.csv", index=False)
    manifest.update(
        {
            "purpose": "pre-match Elo exploratory ablation; 2026 excluded",
            "years": champions.YEARS,
            "elo_audit": audit,
            "elo_source_sha256": hashlib.sha256(
                Path(elo.__file__).read_bytes()
            ).hexdigest(),
            "models": parameters,
        }
    )
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.write_text(report(pooled, annual, coverage, audit))
    print(f"Wrote {args.out} and {args.artifacts}")


if __name__ == "__main__":
    main()
