"""Fixed, retrospective team/player late-game study; no production changes."""

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

OUT = Path("data/research/live_late_teams")
REPORT = Path("docs/research/live_late_teams.md")
EPOCH = pd.Timestamp("2014-01-01", tz="UTC")
LAMBDA = 25.0
CANDIDATES = {
    "team_180": ("team", 180),
    "team_90": ("team", 90),
    "team_365": ("team", 365),
    "player_180": ("player", 180),
}


def days(values):
    return (
        (pd.to_datetime(values, utc=True, format="mixed").dt.floor("D") - EPOCH)
        / pd.Timedelta(days=1)
    ).to_numpy()


def history():
    with sqlite3.connect("file:db/prometheus.db?mode=ro", uri=True) as db:
        matches = pd.read_sql(
            "SELECT gameid, year, date, league, teamid, teamname, side, "
            "gamelength, result FROM matches",
            db,
        )
        elo = pd.read_sql(
            "SELECT gameid, teamid, pre_match_elo FROM game_length_elo", db
        )
        players = pd.read_sql(
            "SELECT gameid, teamid, position, playerid, playername FROM match_players",
            db,
        )
    assert not matches.duplicated(["gameid", "side"]).any()
    assert not elo.duplicated(["gameid", "teamid"]).any()
    matches["day"] = days(matches.date)
    valid_length = matches.gamelength > 0
    median = matches.loc[valid_length].groupby(["league", "year"]).gamelength.median()
    matches["x"] = (
        matches.gamelength
        - pd.MultiIndex.from_frame(matches[["league", "year"]]).map(median).to_numpy()
    ) / 600
    g = matches.merge(elo, on=["gameid", "teamid"], validate="one_to_one")
    opponents = g[["gameid", "side", "pre_match_elo"]].copy()
    opponents["side"] = opponents.side.map({"Blue": "Red", "Red": "Blue"})
    g = g.merge(opponents, on=["gameid", "side"], suffixes=("", "_opp"))
    g = g[(g.gamelength > 0)].dropna(
        subset=["pre_match_elo", "pre_match_elo_opp", "x", "result", "day"]
    )
    difference = ((g.pre_match_elo - g.pre_match_elo_opp) / 100).to_numpy()
    before = g.day < days(pd.Series(["2024-01-01"]))[0]
    model = LogisticRegression(fit_intercept=False, C=1, max_iter=3000).fit(
        difference[before, None], g.result.to_numpy()[before]
    )
    g["r"] = g.result - expit(difference * model.coef_[0, 0])
    team = g.rename(columns={"teamid": "entity", "teamname": "name"})
    player = players.merge(
        g[["gameid", "teamid", "day", "x", "r"]],
        on=["gameid", "teamid"],
        validate="many_to_one",
    ).rename(columns={"playerid": "entity", "playername": "name"})
    for frame in (team, player):
        frame.dropna(subset=["entity"], inplace=True)
        frame.drop(
            frame.index[frame.entity.astype(str).str.strip().eq("")], inplace=True
        )
        assert not frame.duplicated(["gameid", "entity"]).any()
    return matches, players, {"team": team, "player": player}, float(model.coef_[0, 0])


class Slopes:
    """Exponentially factored cumulative moments, queried strictly before day D."""

    def __init__(self, frame, half_life):
        self.a = 0 if np.isinf(half_life) else np.log(2) / half_life
        self.groups = {}
        for entity, rows in frame.groupby("entity", sort=False):
            rows = rows.sort_values("day", kind="stable")
            t, x, r = (rows[k].to_numpy(dtype=float) for k in ("day", "x", "r"))
            w = np.exp(self.a * t)
            moments = np.column_stack([w, w * x, w * r, w * x * r, w * x * x])
            sums = np.vstack([np.zeros(5), moments.cumsum(axis=0)])
            self.groups[entity] = (t, sums)

    def query(self, entity, target):
        target = np.asarray(target, dtype=float)
        if entity not in self.groups:
            return np.zeros_like(target), np.zeros_like(target), np.zeros_like(target)
        dates, cumulative = self.groups[entity]
        count = np.searchsorted(dates, target, side="left")
        sums = cumulative[count] * np.exp(-self.a * target)[..., None]
        w, x, r, xr, xx = sums.T
        safe = np.where(w > 0, w, 1)
        slope = (xr - x * r / safe) / (np.maximum(xx - x * x / safe, 0) + LAMBDA)
        return slope, w, count


def check_estimator(frame):
    """Direct weighted formula checks, including same-day exclusion and no history."""
    estimator = Slopes(frame, 180)
    entity = frame.entity.iloc[0]
    rows = frame[frame.entity == entity]
    targets = np.array([rows.day.min(), rows.day.median(), rows.day.max() + 1])
    got, _, _ = estimator.query(entity, targets)
    expected = []
    for target in targets:
        past = rows[rows.day < target]
        if past.empty:
            expected.append(0)
            continue
        w = 0.5 ** ((target - past.day.to_numpy()) / 180)
        x, r = past.x.to_numpy(), past.r.to_numpy()
        expected.append(
            ((w * x * r).sum() - (w * x).sum() * (w * r).sum() / w.sum())
            / ((w * x * x).sum() - (w * x).sum() ** 2 / w.sum() + LAMBDA)
        )
    np.testing.assert_allclose(got, expected, atol=1e-10)


def memberships(matches, players, kind):
    if kind == "team":
        rows = matches[["gameid", "side", "teamid"]].rename(
            columns={"teamid": "entity"}
        )
        size = 1
    else:
        rows = players.merge(
            matches[["gameid", "teamid", "side"]],
            on=["gameid", "teamid"],
            validate="many_to_one",
        ).rename(columns={"playerid": "entity"})
        size = 5
    rows = rows.dropna(subset=["entity"])
    rows = rows[rows.entity.astype(str).str.strip().ne("")]
    result = {}
    for gid, group in rows.groupby("gameid", sort=False):
        blue = group.loc[group.side == "Blue", "entity"].tolist()
        red = group.loc[group.side == "Red", "entity"].tolist()
        if len(blue) == len(red) == size and len(set(blue + red)) == 2 * size:
            result[gid] = [(e, 1) for e in blue] + [(e, -1) for e in red]
    return result


def gaps(maps, members, estimator):
    requests = []
    known = maps.game_id.isin(members).to_numpy()
    for i, row in enumerate(maps.itertuples()):
        for entity, sign in members.get(row.game_id, []):
            requests.append((i, entity, sign, row.day))
    result = np.zeros(len(maps))
    if requests:
        requests = pd.DataFrame(requests, columns=["i", "entity", "sign", "day"])
        for entity, rows in requests.groupby("entity", sort=False):
            values, _, _ = estimator.query(entity, rows.day.to_numpy())
            np.add.at(result, rows.i.to_numpy(), values * rows.sign.to_numpy())
    return result, known


def descriptive(frame):
    windows = []
    for lo, hi in (("2022-01-01", "2024-01-01"), ("2024-01-01", "2026-01-01")):
        start, end = days(pd.Series([lo, hi]))
        rows = frame[(frame.day >= start) & (frame.day < end)]
        est = Slopes(rows, np.inf)
        windows.append(
            pd.DataFrame(
                [
                    (entity, *[v[0] for v in est.query(entity, [end])])
                    for entity in est.groups
                ],
                columns=["entity", "slope", "weight", "count"],
            ).set_index("entity")
        )
    paired = windows[0].join(windows[1], lsuffix="_a", rsuffix="_b")
    paired = paired[(paired.count_a >= 50) & (paired.count_b >= 50)]
    persistence = {"n": len(paired)}
    persistence.update(
        pearson=float(pearsonr(paired.slope_a, paired.slope_b).statistic),
        spearman=float(spearmanr(paired.slope_a, paired.slope_b).statistic),
    )
    cutoff = days(pd.Series(["2026-10-01"]))[0]
    past = frame[frame.day < cutoff]
    names = past.sort_values("day", kind="stable").groupby("entity")["name"].last()
    est = Slopes(past, 180)
    table = pd.DataFrame(
        [
            (entity, names.loc[entity], *[v[0] for v in est.query(entity, [cutoff])])
            for entity in est.groups
        ],
        columns=["entity", "name", "slope", "weight", "count"],
    )
    table = table[table["count"] >= 30].sort_values("slope", ascending=False)
    return persistence, table.head(10), table.tail(10).iloc[::-1]


def slice_masks(test, known):
    league = test.league
    special = {"LPL", "LCK", "LEC", "LCS"}
    masks = {"All": np.ones(len(test), dtype=bool)}
    for label, lo, hi in (
        ("0–10", 0, 600),
        ("10–20", 600, 1200),
        ("20–30", 1200, 1800),
        ("30+", 1800, np.inf),
    ):
        masks[label] = ((test.seconds >= lo) & (test.seconds < hi)).to_numpy()
    for name in ("LPL", "LCK", "LEC", "LCS"):
        masks[name] = league.eq(name).to_numpy()
    masks["Other majors"] = league.isin(MAJORS - special - INTERNATIONAL).to_numpy()
    masks["International"] = league.isin(INTERNATIONAL).to_numpy()
    masks["Other"] = (~league.isin(MAJORS | INTERNATIONAL)).to_numpy()
    masks["Known"] = known
    masks["Unknown"] = ~known
    masks["2026"] = pd.to_datetime(test.date, utc=True).dt.year.eq(2026).to_numpy()
    return masks


def compact_ci(result):
    lo, hi = result["interval"]
    return f"{result['delta']:+.5f}[{lo:+.5f},{hi:+.5f}]"


def main():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    extra = objective_rows(parts["joined"])
    n = int((parts["data"].source == "feed").sum())
    frames = [
        momentum(attach(parts[k][parts[k].source == "feed"], extra, n))
        for k in ("train", "calibration", "test")
    ]
    for frame in frames:
        add_columns(frame, PRIMARY)
    train, calibration, test = frames
    test = test[test.seconds <= 2400].copy()
    frames = [train, calibration, test]
    assert len(STATE_FEATURES) == 20
    control = score(fit(train, calibration, STATE_FEATURES), test, STATE_FEATURES)
    control_metrics = metrics(test, control)
    if abs(control_metrics["log_loss"] - 0.4675) > 0.003:
        message = f"STOP: control LL {control_metrics['log_loss']:.6f} outside 0.4675 ± 0.003; candidate scoring not run."
        REPORT.write_text(message + "\n")
        raise RuntimeError(message)
    print(f"Control sanity PASS: LL={control_metrics['log_loss']:.6f}", flush=True)
    matches, players, histories, elo_coef = history()
    for frame in histories.values():
        check_estimator(frame)
    maps = (
        pd.concat([f[["game_id", "date"]] for f in frames])
        .drop_duplicates("game_id")
        .reset_index(drop=True)
    )
    maps["day"] = days(maps.date)
    predictions = test[
        ["game_id", "series", "date", "league", "seconds", "minute", "won"]
    ].copy()
    predictions["control"] = control
    results = {"control": control_metrics}
    slice_results = {}
    coverage = {}
    coefficients = {}
    member_sets = {kind: memberships(matches, players, kind) for kind in histories}
    for name, (kind, half_life) in CANDIDATES.items():
        gap, known = gaps(
            maps,
            member_sets[kind],
            Slopes(histories[kind], half_life),
        )
        lookup = pd.DataFrame({"gap": gap, "known": known}, index=maps.game_id)
        for frame in frames:
            frame["gap"] = frame.game_id.map(lookup.gap)
            frame["gap_time"] = frame.gap * frame.time
            frame["gap_known"] = frame.game_id.map(lookup.known)
        columns = STATE_FEATURES + ["gap", "gap_time"]
        fitted = fit(train, calibration, columns)
        p = score(fitted, test, columns)
        predictions[name] = p
        results[name] = metrics(test, p)
        coefficients[name] = fitted[1].coef_[0][-2:].tolist()
        slice_results[name] = {}
        for label, mask in slice_masks(test, test.gap_known.to_numpy()).items():
            subset = test[mask]
            slice_results[name][label] = {
                "maps": int(subset.game_id.nunique()),
                "result": delta(subset, p[mask], control[mask]) if mask.any() else None,
            }
        coverage[name] = {
            k: {
                "maps": int(f.game_id.nunique()),
                "known": int(f.loc[f.gap_known, "game_id"].nunique()),
            }
            for k, f in zip(("train", "calibration", "test"), frames)
        }
        test[["game_id", "gap", "gap_known"]].drop_duplicates().to_csv(
            OUT / f"{name}_gaps.csv", index=False
        )
    predictions.to_csv(OUT / "predictions.csv.gz", index=False)
    primary = slice_results["team_180"]
    harms = [
        label
        for label, v in primary.items()
        if v["result"] and v["result"]["interval"][0] > 0
    ]
    passed = primary["All"]["result"]["interval"][1] < 0 and not harms
    descriptions = {k: descriptive(v) for k, v in histories.items()}
    summary = {
        "metrics": results,
        "slices": slice_results,
        "coverage": coverage,
        "coefficients": coefficients,
        "elo_coefficient": elo_coef,
        "passed": passed,
        "persistence": {k: v[0] for k, v in descriptions.items()},
    }
    (OUT / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        f"{'PASS' if passed else 'FAIL'}: primary team H=180 {ci(primary['All']['result'], 6)} log loss; research only.",
        "",
        "# Live late-game teams and players",
        "",
        "Protocol fixed before scoring: primary team H=180 days; secondary A team H=90, B team H=365, C players H=180. "
        "Feed train 2024, calibration 2025 H1, test July 2025 onward through 40 minutes. "
        "Control: deployed 20-feature objective/momentum recipe refit; candidates add gap and gap×time. "
        "StandardScaler, L2 logistic C=1, equal map weights, calibration-only Platt layer.",
        "",
        "History: pre-2024 no-intercept Elo logistic residual; league-year median-centered length/600. "
        "Centered slope, ridge 25; earlier UTC days, exponential cumulative moments. "
        "Side score: one team slope or five player slopes. Missing IDs/rosters: zero gap, rows retained. "
        "Unseen entities: zero slopes; require ten distinct player IDs.",
        "",
        f"Control sanity PASS (LL {control_metrics['log_loss']:.6f}; expected 0.4675±0.003). "
        + "; ".join(
            f"{k}: {f.game_id.nunique()} maps/{len(f)} rows"
            for k, f in zip(("train", "calibration", "test"), frames)
        )
        + ".",
        "",
        "| Model | LL | Brier | ECE10 | gap/gap×time signs |",
        "|---|---|---|---|---|",
    ]
    for name, values in results.items():
        signs = (
            "/".join(
                "+" if v > 0 else "−" if v < 0 else "0" for v in coefficients[name]
            )
            if name in coefficients
            else "—"
        )
        lines.append(
            f"| {name} | {values['log_loss']:.6f} | {values['brier']:.6f} | {values['ece10']:.6f} | {signs} |"
        )
    lines += [
        "",
        "Per-map LL delta versus control; 95% paired whole-series bootstrap, 2,000 draws, seed 42. Negative favors candidate. "
        "Cells: delta [interval]; empty slices are N/A. Known/unknown is candidate-specific.",
        "",
        "| Slice (maps: team/player) | Primary | A | B | C |",
        "|---|---|---|---|---|",
    ]
    for label in primary:
        counts = (
            f"{primary[label]['maps']}/{slice_results['player_180'][label]['maps']}"
        )
        cells = [
            compact_ci(slice_results[name][label]["result"])
            if slice_results[name][label]["result"]
            else "N/A"
            for name in CANDIDATES
        ]
        lines.append(f"| {label} ({counts}) | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Pass requires the primary all-map interval below zero and no reported slice interval above zero. "
        f"Harm slices: {', '.join(harms) or 'none'}. Secondaries are descriptive, never adopted.",
        "",
        "Coverage (known/total maps; train, calibration, test): "
        + "; ".join(
            f"{name} "
            + ", ".join(f"{v['known']}/{v['maps']}" for v in coverage[name].values())
            for name in ("team_180", "player_180")
        )
        + ".",
        "",
        "Persistence: unweighted 2022–2023 versus 2024–2025 slopes, ridge 25, ≥50 games in each window.",
        "",
        "| Entity | n | Pearson | Spearman |",
        "|---|---|---|---|",
    ]
    for kind, (persistence, _top, _bottom) in descriptions.items():
        lines.append(
            f"| {kind} | {persistence['n']} | {persistence['pearson']:.4f} | {persistence['spearman']:.4f} |"
        )
    lines += [
        "",
        "As of 2026-10-01, H=180, ≥30 earlier raw games; latest earlier names. Counts: weighted/raw.",
    ]
    for kind, (_, top, bottom) in descriptions.items():
        lines += [
            "",
            f"| {kind} top 10 | Slope | Games | {kind} bottom 10 | Slope | Games |",
            "|---|---|---|---|---|---|",
        ]
        for a, b in zip(top.itertuples(), bottom.itertuples()):
            lines.append(
                f"| {a.name} | {a.slope:+.4f} | {a.weight:.1f}/{a.count:.0f} | {b.name} | {b.slope:+.4f} | {b.weight:.1f}/{b.count:.0f} |"
            )
        top.to_csv(OUT / f"{kind}_top.csv", index=False)
        bottom.to_csv(OUT / f"{kind}_bottom.csv", index=False)
    lines += [
        "",
        "Limits: retrospective test previously viewed in earlier studies; no multiple-comparison adjustment. "
        "LPL champion coverage gaps in Oracle's Elixir also limit player-history/roster coverage. "
        "Game length is an outcome-side quantity used only from earlier games; league-year centering uses the specified full-year median. "
        "Weak persistence suggests noise rather than a stable trait. No market/trading check; no production changes.",
        "",
        "Reproduce:",
        "```bash",
        "OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_late_teams.py",
        "```",
    ]
    report = "\n".join(lines) + "\n"
    assert len(report.split()) < 900, len(report.split())
    REPORT.write_text(report)
    print(
        json.dumps(
            {
                "verdict": "PASS" if passed else "FAIL",
                "primary": primary["All"],
                "persistence": summary["persistence"],
                "seconds": round(time.monotonic() - started, 1),
            }
        )
    )


if __name__ == "__main__":
    main()
