"""Fixed, retrospective champion-scaling study; no production changes."""

import json
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd
from cand_objectives import PRIMARY, add_columns, attach, objective_rows
from cand_temporal import momentum
from scipy.special import expit
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LogisticRegression
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import INTERNATIONAL, MAJORS, ci, partitions

from prometheus.live.timeline import STATE_FEATURES

OUT = Path("data/research/live_champ_scaling")
REPORT = Path("docs/research/live_champ_scaling.md")
EPOCH = pd.Timestamp("2014-01-01", tz="UTC")
LAMBDA = 25
CANDIDATES = {
    "primary": (365, False),
    "secondary_a": (730, False),
    "secondary_b": (365, True),
}


def days(values):
    return (
        (
            pd.to_datetime(values, utc=True, format="mixed").dt.floor("D") - EPOCH
        ).dt.total_seconds()
        / 86400
    ).to_numpy()


def history():
    with sqlite3.connect("db/prometheus.db") as connection:
        matches = pd.read_sql(
            "SELECT gameid, year, date, league, teamid, side, "
            "gamelength, result FROM matches",
            connection,
        )
        elo = pd.read_sql(
            "SELECT gameid, teamid, pre_match_elo FROM game_length_elo", connection
        )
        players = pd.read_sql(
            "SELECT gameid, teamid, position, champion FROM match_players "
            "WHERE champion IS NOT NULL AND TRIM(champion) != ''",
            connection,
        )
    valid = matches[matches.gamelength > 0].copy()
    valid["x"] = (
        valid.gamelength
        - valid.groupby(["league", "year"]).gamelength.transform("median")
    ) / 600
    valid = valid.merge(elo, on=["gameid", "teamid"], validate="one_to_one")
    opponent = valid[["gameid", "teamid", "pre_match_elo"]].rename(
        columns={"teamid": "opponent", "pre_match_elo": "opponent_elo"}
    )
    valid = valid.merge(opponent, on="gameid")
    valid = (
        valid[(valid.teamid != valid.opponent)]
        .dropna(subset=["pre_match_elo", "opponent_elo"])
        .copy()
    )
    if valid.duplicated(["gameid", "teamid"]).any():
        raise ValueError("History must have exactly two teams per map")
    valid["day"] = days(valid.date)
    predictor = ((valid.pre_match_elo - valid.opponent_elo) / 100).to_numpy()
    pre = valid.day < days(pd.Series(["2024-01-01"]))[0]
    model = LogisticRegression(fit_intercept=False, max_iter=3000).fit(
        predictor[pre, None], valid.result.to_numpy()[pre]
    )
    valid["r"] = valid.result - expit(predictor * model.coef_[0, 0])
    entities = valid.merge(players, on=["gameid", "teamid"], validate="one_to_many")
    rosters = players.merge(
        matches[["gameid", "teamid", "side"]],
        on=["gameid", "teamid"],
        validate="many_to_one",
    )
    return entities, rosters, float(model.coef_[0, 0])


def entity_column(frame, role):
    frame = frame.copy()
    if role:
        frame = frame[frame.position.notna() & frame.position.str.strip().ne("")].copy()
        frame["entity"] = list(zip(frame.champion, frame.position))
    else:
        frame["entity"] = frame.champion
    return frame


class Slopes:
    """Exponentially factored cumulative moments; search excludes the target day."""

    def __init__(self, data, half_life):
        self.a = 0 if np.isinf(half_life) else np.log(2) / half_life
        self.groups = {}
        for entity, group in data.groupby("entity", sort=False):
            group = group.sort_values("day", kind="stable")
            t, x, r = (group[k].to_numpy() for k in ("day", "x", "r"))
            w = np.exp(self.a * t)
            sums = np.column_stack([w, w * x, w * r, w * x * r, w * x * x]).cumsum(
                axis=0
            )
            self.groups[entity] = (t, np.vstack([np.zeros(5), sums]))

    def get(self, entity, target):
        target = np.asarray(target, dtype=float)
        if entity not in self.groups:
            return (
                np.zeros(target.shape),
                np.zeros(target.shape),
                np.zeros(target.shape, int),
            )
        dates, sums = self.groups[entity]
        n = np.searchsorted(dates, target, side="left")
        moments = sums[n] * np.exp(-self.a * target)[..., None]
        w, wx, wr, wxr, wxx = np.moveaxis(moments, -1, 0)
        denominator = np.where(w > 0, w, 1)
        slope = (wxr - wx * wr / denominator) / (
            np.maximum(0, wxx - wx * wx / denominator) + LAMBDA
        )
        return slope, w, n


def gaps(maps, rosters, estimator, role):
    roster = entity_column(rosters, role)
    joined = maps[["game_id", "date"]].merge(
        roster, left_on="game_id", right_on="gameid"
    )
    joined["day"] = days(joined.date)
    joined["slope"] = 0.0
    for entity, group in joined.groupby("entity", sort=False):
        joined.loc[group.index, "slope"] = estimator.get(entity, group.day)[0]
    joined["signed"] = joined.slope * np.where(joined.side.eq("Blue"), 1, -1)
    counts = joined.groupby(["game_id", "side"]).size().unstack(fill_value=0)
    known = counts.reindex(columns=["Blue", "Red"], fill_value=0).eq(5).all(axis=1)
    values = joined.groupby("game_id").signed.sum().where(known, 0)
    return (
        maps.game_id.map(values).fillna(0).to_numpy(),
        maps.game_id.map(known).fillna(False).astype(bool).to_numpy(),
    )


def slices(test, known):
    league = test.league
    tier = league.map(
        lambda name: (
            name
            if name in {"LPL", "LCK", "LEC", "LCS"}
            else "International"
            if name in INTERNATIONAL
            else "Other majors"
            if name in MAJORS
            else "Other"
        )
    )
    return (
        [("All", np.ones(len(test), bool))]
        + [
            (label, ((test.seconds >= lo) & (test.seconds < hi)).to_numpy())
            for label, lo, hi in [
                ("0–10", 0, 600),
                ("10–20", 600, 1200),
                ("20–30", 1200, 1800),
                ("30+", 1800, np.inf),
            ]
        ]
        + [
            (label, tier.eq(label).to_numpy())
            for label in [
                "LPL",
                "LCK",
                "LEC",
                "LCS",
                "Other majors",
                "International",
                "Other",
            ]
        ]
        + [
            ("Known", known),
            ("Unknown", ~known),
            (
                "2026",
                pd.to_datetime(test.date, utc=True, format="mixed")
                .dt.year.eq(2026)
                .to_numpy(),
            ),
        ]
    )


def main():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    extra = objective_rows(parts["joined"])
    n = int(parts["data"].source.eq("feed").sum())
    frames = [
        momentum(attach(parts[key][parts[key].source == "feed"], extra, n))
        for key in ("train", "calibration", "test")
    ]
    for frame in frames:
        add_columns(frame, PRIMARY)
    train, calibration, test = frames
    test = test[test.seconds <= 2400].copy()
    frames = [train, calibration, test]
    control = score(fit(train, calibration, STATE_FEATURES), test, STATE_FEATURES)
    control_metrics = metrics(test, control)
    if abs(control_metrics["log_loss"] - 0.4675) > 0.003:
        raise RuntimeError(
            f"Control sanity failed: {control_metrics}; stopping before candidates"
        )
    print(f"Control sanity PASS: LL={control_metrics['log_loss']:.6f}", flush=True)
    data, rosters, elo_coef = history()
    maps = pd.concat([frame[["game_id", "date"]] for frame in frames]).drop_duplicates(
        "game_id"
    )
    predictions = test[
        ["game_id", "series", "date", "league", "seconds", "minute", "won"]
    ].copy()
    predictions["control"] = control
    gap_records = maps.copy()
    all_results, fitted_signs, knowns = {}, {}, {}
    for name, (half_life, role) in CANDIDATES.items():
        estimator = Slopes(entity_column(data, role), half_life)
        gap, known = gaps(maps, rosters, estimator, role)
        gap_records[f"{name}_gap"] = gap
        gap_records[f"{name}_gap_known"] = known
        lookup = pd.DataFrame({"gap": gap, "gap_known": known}, index=maps.game_id)
        for frame in frames:
            frame["gap"] = frame.game_id.map(lookup.gap)
            frame["gap_time"] = frame.gap * frame.time
        cols = STATE_FEATURES + ["gap", "gap_time"]
        fitted = fit(train, calibration, cols)
        prob = score(fitted, test, cols)
        predictions[name] = prob
        knowns[name] = test.game_id.map(lookup.gap_known).to_numpy()
        fitted_signs[name] = [
            "+" if v > 0 else "−" if v < 0 else "0" for v in fitted[1].coef_[0][-2:]
        ]
        all_results[name] = {}
        for label, mask in slices(test, knowns[name]):
            all_results[name][label] = (
                delta(test[mask], prob[mask], control[mask]) if mask.any() else None
            )
    primary = all_results["primary"]["All"]
    passed = primary["interval"][1] < 0 and not any(
        result and result["interval"][0] > 0
        for result in all_results["primary"].values()
    )
    predictions.to_csv(OUT / "predictions.csv.gz", index=False)
    gap_records.to_csv(OUT / "gaps.csv", index=False)
    coverage = test[["game_id", "league"]].drop_duplicates().copy()
    coverage["gap_known"] = (
        test.assign(known=knowns["primary"])
        .groupby("game_id")
        .known.first()
        .reindex(coverage.game_id)
        .to_numpy()
    )
    coverage.to_csv(OUT / "coverage.csv", index=False)
    champion_data = entity_column(data, False)
    windows = []
    for lo, hi in [("2022-01-01", "2024-01-01"), ("2024-01-01", "2026-01-01")]:
        a, b = days(pd.Series([lo, hi]))
        window = champion_data[champion_data.day.ge(a) & champion_data.day.lt(b)]
        estimator = Slopes(window, np.inf)
        windows.append(
            {
                entity: estimator.get(entity, np.array([b]))
                for entity in estimator.groups
            }
        )
    eligible = sorted(
        entity
        for entity in windows[0].keys() & windows[1].keys()
        if windows[0][entity][2][0] >= 50 and windows[1][entity][2][0] >= 50
    )
    a, b = (
        np.array([window[entity][0][0] for entity in eligible]) for window in windows
    )
    persistence = {
        "n": len(eligible),
        "pearson": float(pearsonr(a, b).statistic),
        "spearman": float(spearmanr(a, b).statistic),
    }
    estimator = Slopes(champion_data, 365)
    target = days(pd.Series(["2026-10-01"]))
    descriptive = []
    for entity in estimator.groups:
        slope, w, count = estimator.get(entity, target)
        if count[0] >= 30:
            descriptive.append(
                {
                    "entity": entity,
                    "champion": entity,
                    "slope": slope[0],
                    "weighted_games": w[0],
                    "raw_games": int(count[0]),
                }
            )
    descriptive = pd.DataFrame(descriptive).sort_values("slope", ascending=False)
    descriptive.to_csv(OUT / "champion_slopes.csv", index=False)
    summary = {
        "control": control_metrics,
        "results": all_results,
        "signs": fitted_signs,
        "persistence": persistence,
        "pass": bool(passed),
        "elo_coefficient": elo_coef,
        "elapsed_seconds": time.monotonic() - started,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        f"**{'PASS' if passed else 'FAIL'}: primary ΔLL {ci(primary, 6)}; retrospective, research only.**",
        "",
        "# Champion scaling in the live model",
        "",
        "Protocol fixed before scoring: primary champion H=365 days; A champion H=730; "
        "B champion-by-role H=365. No variants selected after scoring. "
        f"Feed train/calibration/test maps: {train.game_id.nunique()}/"
        f"{calibration.game_id.nunique()}/{test.game_id.nunique()}; test ≤40 minutes. "
        "Control uses the deployed 20-feature recipe; candidates add blue-minus-red "
        "summed slopes and gap×time. StandardScaler, L2 C=1, equal map weights, Platt calibration. "
        "Missing ten-champion rosters give zero gap; no rows dropped.",
        "",
        "Residuals subtract a no-intercept pre-2024 Elo logistic fit. Length is centered "
        "on league/year median, divided by 600. Slopes use strictly earlier UTC days, "
        "exponential decay and ridge 25, computed with cumulative moments.",
        "",
        "LL is map-weighted. Δ=candidate−control; 95% paired whole-series bootstrap "
        "intervals use 2,000 draws, seed 42. Pass requires primary All upper bound <0 "
        "and no reported primary slice lower bound >0. Secondaries are descriptive, never adopted. "
        "No multiple-comparison adjustment.",
        "",
        "| Model | LL | Brier | ECE10 | gap / gap_time signs |",
        "|---|---:|---:|---:|---|",
    ]
    for name in ["control", *CANDIDATES]:
        m = metrics(test, predictions[name].to_numpy())
        lines.append(
            f"| {name} | {m['log_loss']:.6f} | {m['brier']:.6f} | {m['ece10']:.6f} | "
            f"{' / '.join(fitted_signs[name]) if name != 'control' else '—'} |"
        )
    lines += [
        "",
        "Signs are standardized logistic coefficients before Platt calibration.",
        "",
        "| Slice | Maps | Primary ΔLL (95% CI) | A ΔLL (95% CI) | B ΔLL (95% CI) |",
        "|---|---:|---|---|---|",
    ]
    for label, mask in slices(test, knowns["primary"]):
        cells = [compact_ci(all_results[name][label]) for name in CANDIDATES]
        lines.append(
            f"| {label} | {test[mask].game_id.nunique()} | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "Known/Unknown use each candidate's roster availability (B also requires roles).",
        "",
        "| Test league | Maps | Missing champion rosters |",
        "|---|---:|---:|",
    ]
    for league, group in coverage.groupby("league"):
        lines.append(f"| {league} | {len(group)} | {int((~group.gap_known).sum())} |")
    lines += [
        "",
        f"Persistence, unweighted 2022–2023 vs 2024–2025, ridge 25, ≥50 games "
        f"in both: n={len(eligible)}, Pearson={persistence['pearson']:.4f}, "
        f"Spearman={persistence['spearman']:.4f}. Weak persistence suggests noise.",
        "",
        "Top/bottom ten as of 2026-10-01 (strictly earlier days), H=365, ≥30 raw games:",
        "",
        "| Entity | Champion name | Slope | Σw | Raw games |",
        "|---|---|---:|---:|---:|",
    ]
    for row in pd.concat([descriptive.head(10), descriptive.tail(10)]).itertuples():
        lines.append(
            f"| {row.entity} | {row.champion} | {row.slope:+.4f} | "
            f"{row.weighted_games:.1f} | {row.raw_games} |"
        )
    lines += [
        "",
        "Limits: July-2025+ outcomes were viewed in earlier studies, so this is "
        "retrospective regardless of the verdict. Oracle's Elixir lacks champions for many "
        "historical LPL games, although every test map here has complete rosters "
        "(the Unknown slice is empty). Game length is an outcome-side quantity used only from earlier games; "
        "league/year centering follows the fixed protocol. Slopes are associations, not causal "
        "champion effects. No market/trading check; no production model changed.",
        "",
        "Reproduce:",
        "```bash",
        "OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_champ_scaling.py",
        "```",
        "",
    ]
    text = "\n".join(lines)
    if len(text.split()) >= 900:
        raise ValueError(f"Report exceeds word budget: {len(text.split())}")
    REPORT.write_text(text)
    print(
        f"{'PASS' if passed else 'FAIL'} primary {ci(primary, 6)}; persistence {persistence}; "
        f"{time.monotonic() - started:.1f}s; wrote {REPORT} and {OUT}"
    )


def compact_ci(result):
    if result is None:
        return "n/a"
    lo, hi = result["interval"]
    return f"{result['delta']:+.6f}[{lo:+.6f},{hi:+.6f}]"


if __name__ == "__main__":
    main()
