"""
evaluate_season_stats.py: How well each season stat describes a team-season.

Season stats are judged differently from forecasts (`evaluate_metrics.py`). A good
season stat is:

- Stable: computed on half of a team's games, it agrees with the other half. Each
  team-season's games are split into two random halves (by game id, so both teams
  in a game land in the same half); the correlation between halves, stepped up to
  the full season with Spearman-Brown, is its reliability. "Games to 0.5" is how
  many games a team needs before the stat is at least half signal.
- Faithful to the season: it agrees with what the team achieved that season
  (win %, and Record, which also accounts for schedule).
- Predictive out of sample: computed on one half, it correlates with win % in the
  other half (the average of both directions). Unlike the same-season fit, a stat
  can't score well here just by restating results.

Only LCK, LPL, LEC and LCS team-seasons are scored. Correlations are taken after
centring each season on its own mean, so era differences don't count as agreement.
Luck should be unstable: a luck stat that repeats is measuring skill.

Usage:
    uv run python scripts/evaluate_season_stats.py [--out docs/season_stats_report.md]
"""

import argparse
import datetime
import hashlib

import numpy as np
import pandas as pd

from prometheus.evaluation import (
    correlation_interval,
    games_for_reliability,
    spearman_brown,
)
from prometheus.matches import team_season_averages
from prometheus.ranking import (
    adjust_for_opponent_elo,
    adjust_for_opponent_record,
    load_glory_games,
)
from prometheus.regression import fit_glory_pipeline
from prometheus.season import (
    MAJORS,
    _team_seasons,
    calibrate_earned,
    fit_record,
    get_record,
    load_season_games,
)
from prometheus.types import GLORY_FEATURES

KEY = ["teamname", "year"]
# Each half needs this many major-league games for the split-half sample.
MIN_HALF_GAMES = 10
# Same-season fit uses every team-season with at least this many games.
MIN_GAMES = 5

STATS = [
    ("win_pct", "Win %"),
    ("glory", "GLORY (opponent-adjusted by Record)"),
    ("glory_raw", "GLORY, unadjusted (old GLORY)"),
    ("glory_elo", "GLORY, adjusted by pre-game Elo (old GLORY+)"),
    ("glorb", "GLORB"),
    ("record", "Record"),
    ("luck", "Luck"),
]


def half_of(gameids):
    """0 or 1 for each game, from a hash of its id (stable across runs)."""
    return gameids.map(lambda g: int(hashlib.md5(str(g).encode()).hexdigest()[:8], 16) % 2)


def _by_half(frame, value):
    """Per team-season `value` on all games and on each half, plus half game counts.

    `value` maps a frame of one subset's per-game rows to a Series indexed by KEY.
    """
    parts = {"full": value(frame)}
    for h in (0, 1):
        sub = frame[frame["half"] == h]
        parts[f"h{h}"] = value(sub)
        parts[f"n{h}"] = sub.groupby(KEY).size()
    return pd.DataFrame(parts)


def glory_stats(games, record):
    """GLORY variants, win % and Luck per team-season, on all games and each half."""
    out = {name: [] for name in ("glory", "glory_raw", "glory_elo", "glorb", "win_pct", "luck")}
    for year, raw in games.items():
        pipeline = fit_glory_pipeline(raw, GLORY_FEATURES)
        scaler = pipeline.steps[0][1]
        variants = {
            "glory": adjust_for_opponent_record(raw, GLORY_FEATURES, record),
            "glory_raw": raw,
            "glory_elo": adjust_for_opponent_elo(raw, GLORY_FEATURES),
        }
        for name, frame in variants.items():
            frame = frame.assign(half=half_of(frame["gameid"]))
            out[name].append(_by_half(frame, lambda d: _predict(pipeline, d)))
        frame = raw.assign(
            half=half_of(raw["gameid"]),
            result=raw["result"].astype(int),
            expected=np.clip(pipeline.predict(raw[GLORY_FEATURES]), 0, 1),
        )
        out["glorb"].append(_by_half(frame, lambda d: _glorb(scaler, d)))
        out["win_pct"].append(_by_half(frame, lambda d: d.groupby(KEY)["result"].mean()))
        # Luck uses the season's calibration of earned win % for every subset.
        season = frame.groupby(KEY).agg(win=("result", "mean"), raw=("expected", "mean"), n=("result", "size"))
        intercept, slope = calibrate_earned(season["win"], season["raw"], season["n"])
        luck = lambda d: d.groupby(KEY)["result"].mean() - (intercept + slope * d.groupby(KEY)["expected"].mean())
        out["luck"].append(_by_half(frame, luck))
    return {name: pd.concat(parts) for name, parts in out.items()}


def _glorb(scaler, games):
    averages = _averages(games)
    return pd.Series(scaler.transform(averages[GLORY_FEATURES]).sum(axis=1), index=averages.set_index(KEY).index)


def _averages(games):
    return team_season_averages(games.drop(columns=["league"]), 0)


def _predict(pipeline, games):
    averages = _averages(games)
    return pd.Series(pipeline.predict(averages[GLORY_FEATURES]), index=averages.set_index(KEY).index)


def record_stats(season_games):
    """Record per team-season, on every game of the season and on each half."""
    parts = []
    for year, season in season_games.groupby("year"):
        season = season.assign(half=half_of(season["gameid"]))
        info = _team_seasons(season).set_index("teamid")
        major = info["league"].isin(MAJORS)
        cols = {}
        for label, sub in (("full", season), ("h0", season[season["half"] == 0]), ("h1", season[season["half"] == 1])):
            rating = fit_record(sub).reindex(info.index)
            cols[label] = rating - rating[major].mean()
            if label != "full":
                counts = pd.concat([sub["teamid"], sub["opp_teamid"]]).value_counts()
                cols[f"n{label[1]}"] = counts.reindex(info.index).fillna(0)
        frame = pd.DataFrame(cols).assign(teamname=info["teamname"], year=year)[major]
        parts.append(frame.groupby(KEY).first())
    return pd.concat(parts)


def _centre(series, years):
    return series - series.groupby(years).transform("mean")


def reliability(table):
    """Split-half reliability, its full-season step-up, and games to 0.5."""
    t = table.dropna(subset=["h0", "h1"])
    t = t[(t["n0"] >= MIN_HALF_GAMES) & (t["n1"] >= MIN_HALF_GAMES)]
    years = t.index.get_level_values("year")
    r = _centre(t["h0"], years).corr(_centre(t["h1"], years))
    lo, hi = correlation_interval(r, len(t))
    per_half = ((t["n0"] + t["n1"]) / 2).mean()
    return {
        "n": len(t),
        "r_half": r,
        "r_half_lo": lo,
        "r_half_hi": hi,
        "full": spearman_brown(r, 2),
        "games_half": per_half,
        "games_50": games_for_reliability(r, per_half),
    }


def other_half(table, win_pct):
    """Correlation of a stat on one half with win % on the other half (both directions)."""
    t = pd.concat([table[["h0", "h1", "n0", "n1"]], win_pct[["h0", "h1"]].add_prefix("win_")], axis=1, join="inner")
    t = t.dropna(subset=["h0", "h1", "win_h0", "win_h1"])
    t = t[(t["n0"] >= MIN_HALF_GAMES) & (t["n1"] >= MIN_HALF_GAMES)]
    years = t.index.get_level_values("year")
    corr = lambda a, b: _centre(t[a], years).corr(_centre(t[b], years))
    return (corr("h0", "win_h1") + corr("h1", "win_h0")) / 2


def fit_with(table, target):
    """Correlation of a stat's full-season value with a target, over shared team-seasons."""
    joined = pd.concat([table["full"].rename("stat"), target.rename("target")], axis=1, join="inner").dropna()
    years = joined.index.get_level_values("year")
    return _centre(joined["stat"], years).corr(_centre(joined["target"], years))


def report(tables):
    games = tables["win_pct"]
    qualified = games.index[(games["n0"] + games["n1"]) >= MIN_GAMES]
    win_pct = tables["win_pct"].loc[qualified, "full"]
    record = tables["record"]["full"].reindex(qualified)
    lines = [
        "| Stat | Split-half r (95% CI) | Full-season reliability | Games to 0.5 | r with other half's win % "
        "| r with win % | r with Record |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for key, label in STATS:
        table = tables[key]
        rel = reliability(table)
        full = table.loc[table.index.intersection(qualified)]
        with_win = "—" if key == "win_pct" else f"{fit_with(full, win_pct):.2f}"
        with_record = "—" if key == "record" else f"{fit_with(full, record):.2f}"
        games_50 = "never" if not np.isfinite(rel["games_50"]) else f"{rel['games_50']:.0f}"
        lines.append(
            f"| {label} | {rel['r_half']:.2f} ({rel['r_half_lo']:.2f} to {rel['r_half_hi']:.2f}) "
            f"| {rel['full']:.2f} | {games_50} | {other_half(table, tables['win_pct']):.2f} | {with_win} | {with_record} |"
        )
    n = reliability(tables["win_pct"])["n"]
    lines += [
        "",
        f"Split-half sample: {n:,} major-league team-seasons with {MIN_HALF_GAMES}+ major-league games in each half "
        f"(about {reliability(tables['win_pct'])['games_half']:.0f} per half). Same-season fit: {len(qualified):,} "
        f"team-seasons with {MIN_GAMES}+ games. Record's halves count games in every league, including international events.",
        "",
        "Reliability near 1 means the stat measures something a team keeps doing; near 0 means it is mostly noise. "
        "Luck is meant to sit near 0. \"Other half's win %\" uses the split-half sample; Record's halves use its own "
        "games, so its value is not strictly comparable. Correlations are within-season (each season centred on its own mean).",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="Also write the report to this Markdown file")
    args = parser.parse_args()

    print("Loading games...")
    games = load_glory_games()
    season_games = load_season_games()
    record_full = get_record(season_games)
    print("Scoring halves...")
    tables = glory_stats(games, record_full)
    tables["record"] = record_stats(season_games)
    text = f"## Season-stat report ({datetime.date.today().isoformat()})\n\n" + report(tables)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
