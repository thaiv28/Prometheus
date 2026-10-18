"""Fixed follow-up protocol, declared before scoring this wave.

Same split: train through 2024, calibrate 2025 H1, test from July 2025.
Feed primary: objectives + original four-feature draft shift (weights <=2023),
versus identical-row objectives-only model. Missing drafts have zero shift;
no rows are dropped. Secondary: matchup/synergy draft (overlapping selection),
and causal three-minute momentum added to objectives. No hyperparameter tuning.
Raw/global/four-time-bucket calibration of objectives is diagnostic only.

Role phase A: OE checkpoints 10/15/20/25, major/international leagues, exact
same train/cal/test dates. One model per checkpoint. Primary adds five role
gold and CS gaps to v1's six gold/Elo/time features; secondary adds XP gaps
(XP is not level). Complete ten-player cohorts, same rows for all controls,
only games still running at each checkpoint. Compare to checkpoint-refit and
v1; pooled scoring weights each map equally and bootstraps whole series.
No current-game duration feature (duration only determines checkpoint existence).

All results retrospective on a reused test; no model is shipped. No network.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cand_draft import draft_shifts
from cand_objectives import PRIMARY, add_columns, attach, objective_rows, table
from cand_temporal import bucket, momentum
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import V1, calls, ci, partitions

from prometheus import utils
from prometheus.live.timeline import FEATURES, features

ROLES = ("top", "jng", "mid", "bot", "sup")
MINUTES = (10, 15, 20, 25)
LEAGUES = (
    "LCK",
    "LPL",
    "LEC",
    "LCS",
    "LTA",
    "LTA S",
    "LCP",
    "CBLOL",
    "Worlds",
    "MSI",
    "EWC",
    "FST",
)


def draft_columns(frame, shifts, column):
    out = frame.copy()
    out["draft_known"] = out.game_id.isin(shifts.index)
    out["draft"] = out.game_id.map(shifts[column]).fillna(0.0)
    out["draft_time"] = out.draft * out.time
    return out


def calibration_calls(fitted, calibration, test, columns):
    scaler, base, _ = fitted
    zc = base.decision_function(scaler.transform(calibration[columns]))
    zt = base.decision_function(scaler.transform(test[columns]))
    timed = np.empty(len(test))
    for b in range(4):
        cm = bucket(calibration.seconds.to_numpy()) == b
        tm = bucket(test.seconds.to_numpy()) == b
        if not tm.any():
            continue
        local = calibration[cm]
        w = 1 / local.groupby("game_id").game_id.transform("size").to_numpy()
        w *= len(w) / w.sum()
        cal = LogisticRegression(C=1e6, max_iter=3000).fit(
            zc[cm, None], local.won, sample_weight=w
        )
        timed[tm] = cal.predict_proba(zt[tm, None])[:, 1]
    return expit(zt), timed


def export(fitted, columns):
    scaler, base, cal = fitted
    return {
        "features": columns,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": base.coef_[0].tolist(),
        "intercept": float(base.intercept_[0]),
        "calibration_slope": float(cal.coef_[0, 0]),
        "calibration_intercept": float(cal.intercept_[0]),
        "train_before": "2025-01-01",
        "calibration_before": "2025-07-01",
        "research_only": True,
    }


def feed_run(parts, args, shifts):
    extra = objective_rows(parts["joined"])
    n = int((parts["data"].source == "feed").sum())
    frames = [
        momentum(attach(parts[k][parts[k].source == "feed"], extra, n))
        for k in ("train", "calibration", "test")
    ]
    objcols = FEATURES + add_columns(frames[0], PRIMARY)
    for f in frames[1:]:
        add_columns(f, PRIMARY)
    train, calibration, test = frames
    v1 = json.loads(V1.read_text())
    test = test[test.seconds <= v1["supported_seconds"][1]].copy()
    baseline = fit(train, calibration, objcols)
    control = score(baseline, test, objcols)
    results = {"Objectives": control, "v1": calls(v1, test)}
    lines = [
        "# Objectives follow-up: draft, momentum and calibration",
        "",
        "Retrospective reused test; unchanged split and C=1; equal-map losses and paired "
        "series-bootstrap intervals. Negative differences are better. No production model changes.",
        "",
        f"Train {train.game_id.nunique():,}, calibration {calibration.game_id.nunique():,}, "
        f"test {test.game_id.nunique():,} feed maps. Draft gaps are zero when unavailable; "
        "all models keep all rows. Primary uses the original draft features; matchup/synergy "
        "is secondary because its selection overlaps the test.",
        "",
    ]
    for name, column in [
        ("Primary: original draft", "shift"),
        ("Secondary: draft with interactions", "shift_both"),
    ]:
        tr, ca, te = [
            draft_columns(f, shifts, column) for f in (train, calibration, test)
        ]
        cols = objcols + ["draft", "draft_time"]
        model = fit(tr, ca, cols)
        p = score(model, te, cols)
        results[name] = p
        (args.out / (column + "_model.json")).write_text(
            json.dumps(export(model, cols), indent=2)
        )
        lines += [
            f"## {name} versus objectives",
            "",
            *table(te, p, control, "Objectives", "Combined"),
            "",
        ]
        for label, mask in [
            ("Known draft", te.draft_known.to_numpy()),
            ("Missing draft", ~te.draft_known.to_numpy()),
        ]:
            lines += [
                f"{label}: {te[mask].game_id.nunique():,} maps; "
                f"combined − objectives {ci(delta(te[mask], p[mask], control[mask]))}.",
                "",
            ]
    cols = objcols + ["momentum", "momentum_time"]
    p = score(fit(train, calibration, cols), test, cols)
    results["Objectives + momentum"] = p
    lines += [
        "## Secondary: momentum versus objectives",
        "",
        *table(test, p, control, "Objectives", "Momentum"),
        "",
    ]
    raw, timed = calibration_calls(baseline, calibration, test, objcols)
    results.update({"Objectives raw": raw, "Objectives bucketed": timed})
    lines += [
        "## Objective calibration diagnostics",
        "",
        "| Model | LL | ECE |",
        "|---|---:|---:|",
    ]
    for name, prob in [
        ("Global", control),
        ("Raw", raw),
        ("Fixed time buckets", timed),
    ]:
        m = metrics(test, prob)
        lines.append(f"| {name} | {m['log_loss']:.4f} | {m['ece10']:.4f} |")
    for name, prob in [("Raw", raw), ("Fixed time buckets", timed)]:
        lines += [
            "",
            f"## {name} versus global objective calibration (diagnostic)",
            "",
            *table(test, prob, control, "Global", name),
        ]
    lines += ["", "## Combined models versus v1", ""]
    for name in ("Primary: original draft", "Objectives + momentum"):
        lines += [
            f"### {name}",
            "",
            *table(test, results[name], results["v1"], "v1", name),
            "",
        ]
    lines += [
        "## Calibration across all feed candidates",
        "",
        "| Model | LL | ECE |",
        "|---|---:|---:|",
    ]
    for name, prob in results.items():
        m = metrics(test, prob)
        lines.append(f"| {name} | {m['log_loss']:.4f} | {m['ece10']:.4f} |")
    lines += [
        "",
        "## Limits",
        "",
        "The test is reused and intervals are unadjusted for multiple comparisons. "
        "Objective counts include cumulative inhibitors and an approximate soul flag. "
        "The original draft shift avoids the later interaction-feature selection, but "
        "still comes from earlier exploratory work. Missing picks concentrate in LPL. "
        "No participant-feed or production-frame validation; no trading-profit claim.",
        "",
    ]
    (args.report / "cand_followups.md").write_text("\n".join(lines))
    prediction = test[["game_id", "series", "seconds", "won", "league"]].copy()
    for name, p in results.items():
        prediction[name] = p
    prediction.to_csv(args.out / "feed_predictions.csv", index=False)
    (args.out / "objectives_model.json").write_text(
        json.dumps(export(baseline, objcols), indent=2)
    )
    print("Feed follow-ups complete", flush=True)


def checkpoint_frame(players, games, minute):
    """Ten complete, valid role-side rows; exact player totals and blue-red gaps."""
    stats = ("gold", "cs", "xp")
    cols = [f"{s}at{minute}" for s in stats]
    p = players.copy()
    valid = np.isfinite(p[cols]).all(axis=1) & p[cols].ge(0).all(axis=1)
    p = p[valid & p.position.isin(ROLES) & p.side.isin(("Blue", "Red"))]
    count = p.groupby("gameid").size()
    unique = p.drop_duplicates(["gameid", "side", "position"]).groupby("gameid").size()
    ids = count.index[(count == 10) & (unique.reindex(count.index) == 10)]
    p = p[p.gameid.isin(ids)]
    if p.empty:
        return pd.DataFrame()
    wide = p.pivot(index="gameid", columns=["side", "position"], values=cols)
    b = games[(games.side == "Blue") & games.league.isin(LEAGUES)].set_index("gameid")
    r = games[games.side == "Red"].set_index("gameid")
    b = b.loc[b.index.intersection(wide.index)].copy()
    b["blue_gold"] = wide.loc[
        b.index, [(f"goldat{minute}", "Blue", role) for role in ROLES]
    ].sum(axis=1)
    b["red_gold"] = wide.loc[
        b.index, [(f"goldat{minute}", "Red", role) for role in ROLES]
    ].sum(axis=1)
    b["blue_elo"] = b.series_elo
    b["red_elo"] = r.series_elo.reindex(b.index)
    b = b[
        (b.gamelength > minute * 60) & b[["blue_elo", "red_elo"]].notna().all(axis=1)
    ].copy()
    if b.empty:
        return pd.DataFrame()
    b["game_id"] = b.index
    b["won"] = b.result.astype(int)
    b["seconds"] = minute * 60
    b["series"] = [
        "|".join([*sorted((a, c)), str(d)[:10]])
        for a, c, d in zip(b.teamname, b.opp, b.date)
    ]
    x = np.array(
        [
            features(
                minute * 60, row.blue_gold, row.red_gold, row.blue_elo, row.red_elo
            )
            for row in b.itertuples()
        ]
    )
    for i, name in enumerate(FEATURES):
        b[name] = x[:, i]
    for role in ROLES:
        for stat in stats:
            b[f"{role}_{stat}"] = (
                wide[(f"{stat}at{minute}", "Blue", role)]
                - wide[(f"{stat}at{minute}", "Red", role)]
            ).reindex(b.index)
    return b.reset_index(drop=True)


def role_run(parts, args):
    cols = ", ".join(f"p.{s}at{m}" for m in MINUTES for s in ("gold", "cs", "xp"))
    # Snapshot-only fields; no full-game player totals or opponent-derived shortcuts.
    players = pd.read_sql(
        f"SELECT p.gameid, p.position, m.side, {cols} FROM player_stats p JOIN matches m ON m.gameid=p.gameid AND m.teamid=p.teamid",
        utils.get_engine(),
    )
    lines = [
        "# Role leads phase A: exact OE checkpoints",
        "",
        "Same chronological split; one C=1 calibrated model per minute. Primary adds role "
        "gold and CS gaps to the six-feature gold/Elo control. Secondary adds XP gaps; XP "
        "is a proxy for progression, not a level measurement. All models share complete "
        "ten-player rows. Pregame Elo is fixed at the series start. No feed participant data "
        "or interpolation is used. This is phase A evidence, not live validation.",
        "",
        "| Minute | Train | Calibrate | Test | Control LL | Role gold/CS LL | Difference (95%) | +XP LL | Difference (95%) |",
        "|---|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    records = []
    v1 = json.loads(V1.read_text())
    rolecols = FEATURES + [f"{r}_{s}" for r in ROLES for s in ("gold", "cs")]
    xpcols = rolecols + [f"{r}_xp" for r in ROLES]
    for minute in MINUTES:
        data = checkpoint_frame(players, parts["g"], minute)
        if data.empty:
            raise ValueError(f"No complete snapshot games at minute {minute}")
        dates = pd.to_datetime(data.date)
        train = data[dates < "2025-01-01"]
        ca = data[(dates >= "2025-01-01") & (dates < "2025-07-01")]
        te = data[dates >= "2025-07-01"].copy()
        predictions = [
            score(fit(train, ca, cols), te, cols)
            for cols in (FEATURES, rolecols, xpcols)
        ]
        base, role, xp = predictions
        loss = [metrics(te, p)["log_loss"] for p in predictions]
        lines.append(
            f"| {minute} | {len(train):,} | {len(ca):,} | {len(te):,} | {loss[0]:.4f} | {loss[1]:.4f} | {ci(delta(te, role, base))} | {loss[2]:.4f} | {ci(delta(te, xp, base))} |"
        )
        pred = te[["game_id", "series", "seconds", "won", "league"]].copy()
        pred["Control"], pred["Role"], pred["XP"], pred["v1"] = (
            base,
            role,
            xp,
            calls(v1, te),
        )
        records.append(pred)
        print(f"Role checkpoint {minute} complete", flush=True)
    pooled = pd.concat(records, ignore_index=True)
    lines += [
        "",
        "## Pooled, equal map weights",
        "",
        *table(
            pooled, pooled.Role.to_numpy(), pooled.Control.to_numpy(), "Control", "Role"
        ),
        "",
        "## Secondary XP versus same-row control",
        "",
        *table(
            pooled, pooled.XP.to_numpy(), pooled.Control.to_numpy(), "Control", "XP"
        ),
        "",
        "## Role gold/CS versus frozen v1 on exact checkpoints",
        "",
        *table(pooled, pooled.Role.to_numpy(), pooled.v1.to_numpy(), "v1", "Role"),
        "",
        "## Limits",
        "",
        "Retrospective reused test and multiple comparisons. This pool differs from feed "
        "timelines and has substantial LPL snapshot missingness. The four-checkpoint "
        "result cannot establish gain over objectives or continuous-time performance. "
        "Checkpoint survival selects different populations at each minute. No participant "
        "recollection was started and no live model changed.",
        "",
    ]
    (args.report / "cand_role_leads.md").write_text("\n".join(lines))
    pooled.to_csv(args.out / "role_predictions.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, default=Path("data/feed_timelines"))
    parser.add_argument("--gol", type=Path, default=Path("data/gol_training"))
    parser.add_argument(
        "--out", type=Path, default=Path("data/research/live_followups")
    )
    parser.add_argument("--report", type=Path, default=Path("docs/research"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    parts = partitions(args.feed, args.gol)
    print("Partitions loaded", flush=True)
    shifts, _, _ = draft_shifts()
    print("Historical draft shifts loaded", flush=True)
    feed_run(parts, args, shifts)
    role_run(parts, args)


if __name__ == "__main__":
    main()
