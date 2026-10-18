"""Frozen protocol, before scoring (2026-10-17): three added features, one candidate.
Champion-role profiles use strictly earlier UTC days, all available history.
Scaling = shrunk win-above-Elo in >=30 minute games minus <30 minute games
(each denominator n+100). Early lean = mean gold+XP lane gap at 15 / 2000,
shrunk with 50 missing-zero pseudo-games (observed snapshots only).
Team profiles sum five picks; features: blue-minus-red scaling, scaling mean
of the two teams times production logit (strength interaction), early difference.
No damage feature: the DB has total damage share, not physical/magic mix.
Fit 2019..Y-1, test 2021..2026; compare one augmented logistic model to v2
on identical games, series-cluster bootstrap. No tuning or variant selection.
Historical outcomes/lengths/snapshots build profiles, never current game's.
Research only. 2025-26 already viewed during v2 selection.
"""

import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_walkforward as dw

EXTRA = ["scaling", "scaling_strength", "early"]


def profiles(rows):
    rows = rows.copy()
    for name, mask in (
        ("long", rows["gamelength"] >= 1800),
        ("short", rows["gamelength"] < 1800),
    ):
        rows[f"{name}_wae"] = rows["wae"] * mask
        rows[f"{name}_n"] = mask.astype(float)
    rows["early_value"] = rows["early_obs"].fillna(0)
    rows["early_n"] = rows["early_obs"].notna().astype(float)
    vals = ["long_wae", "long_n", "short_wae", "short_n", "early_value", "early_n"]
    prior = dw.prior_days(rows, ["champion", "position"], vals)
    rows["scaling"] = prior[:, 0] / (prior[:, 1] + 100) - prior[:, 2] / (
        prior[:, 3] + 100
    )
    rows["early"] = prior[:, 4] / (prior[:, 5] + 50)
    return rows


def aggregate(rows):
    team = rows.groupby(["gameid", "side"])[["scaling", "early"]].sum()
    blue, red = team.xs("Blue", level="side"), team.xs("Red", level="side")
    out = blue - red
    out["scaling_mean"] = (blue["scaling"] + red["scaling"]) / 2
    return out.reset_index()


def score(games):
    parts, coefficients = [], {}
    base = ["forge_logit", *dw.FEATURES]
    for year in dw.TEST_YEARS:
        train = games[games.year.between(dw.FIT_FROM, year - 1)]
        test = games[games.year == year].copy()
        if test.empty:
            continue
        for name, cols in (("v2", base), ("candidate", [*base, *EXTRA])):
            model = dw._fit(train, cols)
            test[name] = model.predict_proba(test[cols].to_numpy())[:, 1]
            if name == "candidate":
                coefficients[year] = dict(zip(cols, model.coef_[0]))
        parts.append(test)
    return pd.concat(parts, ignore_index=True), coefficients


def report(scored, coefficients, seconds):
    lines = [
        "# Draft composition profiles",
        "",
        "One frozen candidate; protocol in `scripts/research/draft_composition.py`. "
        "Walk-forward fits use 2019 through the preceding year. Differences are candidate minus v2; "
        "95% intervals resample league/day/team-pair series. Negative favours the candidate.",
        "",
        "| Slice | Games | v2 LL | Candidate LL | Difference (95%) |",
        "|---|---:|---:|---:|---|",
    ]
    groups = [*dw.slices(scored), ("before 2025", scored[scored.year < 2025])]
    groups += [(str(year), scored[scored.year == year]) for year in dw.TEST_YEARS]
    for name, frame in groups:
        if frame.empty:
            continue
        a, b, delta, lo, hi = dw.paired(frame, "candidate", "v2")
        lines.append(
            f"| {name} | {len(frame):,} | {b:.6f} | {a:.6f} | {delta:+.6f} ({lo:+.6f} to {hi:+.6f}) |"
        )
    lines += [
        "",
        "## Added-feature coefficients",
        "",
        "| Test year | " + " | ".join(EXTRA) + " |",
        "|---|" + "---:|" * len(EXTRA),
    ]
    for year, coef in coefficients.items():
        lines.append(
            f"| {year} | " + " | ".join(f"{coef[c]:+.5f}" for c in EXTRA) + " |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "Scaling is an observational duration profile: winners affect game length; "
        "it does not identify causal late-game power. Lane snapshots are sparse in LPL; missing champion-role history "
        "is shrunk to zero, not a reason to exclude current LPL games. Damage mix was not implemented because "
        "the built DB lacks physical/magic damage. No production metric, weights or site changed. "
        "All periods are retrospective; 2025-26 helped choose v2. "
        "The production call's own fitted weights are not vintage artifacts.",
        "",
        f"Feature construction and scoring: {seconds:.1f} s (bootstrap reporting excluded); no new CI job or production-build work.",
    ]
    return "\n".join(lines) + "\n"


def base_games():
    """Reuse the frozen production calls; unrated games intentionally lack a call."""
    path = dw.CACHE / "base_games.pkl"
    if path.exists():
        return pd.read_pickle(path)
    rows = dw.player_features(dw.load_rows())
    games = dw.game_table(rows, dw.synergy(rows))
    games = games[games["year"] >= dw.FIT_FROM]
    games = games.merge(pd.read_pickle(dw.CACHE / "forge.pkl"), on="gameid")
    games["forge_logit"] = dw._logit(games["p_forge"])
    games.to_pickle(path)
    return games


def main():
    start = time.monotonic()
    games = base_games()
    rows = dw.load_rows()
    with sqlite3.connect(f"file:{dw.DB_PATH}?mode=ro", uri=True) as conn:
        lengths = pd.read_sql("SELECT gameid, teamid, gamelength FROM matches", conn)
        early = pd.read_sql(
            "SELECT gameid, playerid, teamid, (goldat15-opp_goldat15+xpat15-opp_xpat15)/2000.0 AS early_obs FROM player_stats",
            conn,
        )
    rows = rows.merge(lengths, on=["gameid", "teamid"]).merge(
        early, on=["gameid", "teamid", "playerid"], how="left"
    )
    coverage = rows["early_obs"].notna().mean()
    games = games.merge(aggregate(profiles(rows)), on="gameid")
    games["scaling_strength"] = games["scaling_mean"] * games["forge_logit"]
    games.to_pickle(dw.CACHE / "composition_games.pkl")
    scored, coef = score(games)
    scored.to_pickle(dw.CACHE / "composition_scored.pkl")
    text = report(scored, coef, time.monotonic() - start)
    text += f"\nHistorical player-row lane-snapshot coverage: {coverage:.1%}.\n"
    (dw.ROOT / "docs/research/draft_composition.md").write_text(text)
    print(text, flush=True)


if __name__ == "__main__":
    main()
