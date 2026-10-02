"""
evaluate_metrics.py: Backtest how well each team metric predicts game winners.

Rolling monthly backtest. At the first of every month, each metric is computed from
that season's earlier games only, then used to predict every game played that
month. The rating gap between the two teams is turned into a win probability with a
logistic curve fit on the other seasons, and the probabilities are scored.

Test sets:
- Domestic: LCK, LPL, LEC and LCS games.
- International: Worlds, MSI, EWC, First Stand, ... games between teams from two
  different major leagues, predicted from domestic play. This is the only direct
  test of cross-region strength.

Every metric is scored on exactly the same games (both teams need 5+ games that
season before the cutoff), and each is compared with "win % so far this season"
using a paired bootstrap.

Usage:
    uv run python scripts/evaluate_metrics.py [--years 2022 2023] [--out report.md]
    uv run python scripts/evaluate_metrics.py --write-weights   # refresh GlorELO+ weights
    uv run python scripts/evaluate_metrics.py --check-weights   # CI: warn if they moved
"""

import argparse
import datetime
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sqlalchemy import text

from prometheus.evaluation import (
    game_losses,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.glorelo import (
    WEIGHT_TOLERANCE,
    load_weights,
    save_weights,
    weight_changes,
)
from prometheus.matches import get_available_years
from prometheus.ranking import get_glory_ranking
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

MINIMUM_MATCHES = 5
# A cutoff needs this many major-league team-games that season to fit GLORY's weights.
MINIMUM_TRAINING_ROWS = 200
MAJORS = [l.value for l in ALL_MAJOR_LEAGUES]
_IN_MAJORS = ", ".join(repr(l) for l in MAJORS)
_IN_EVENTS = ", ".join(repr(l) for l in MAJORS + INTERNATIONAL_LEAGUES)

# (key, label, inputs). `inputs` are the blue-minus-red gap columns the win curve
# is fit on: None for the blue-side baseline, several columns for a blend.
# "win_pct" is the baseline every other metric is compared with.
METRICS = [
    ("blue_side", "Blue side wins", None),
    ("win_pct", "Win % so far", "win_pct"),
    ("glorb", "GLORB", "glorb"),
    ("glory", "GLORY", "glory"),
    ("glory_plus", "GLORY+", "glory_plus"),
    ("elo", "Elo (as of cutoff)", "elo"),
    ("glorelo", "GlorELO+", ["glory_plus", "elo"]),
    # Lets the GLORY+/Elo balance shift as the season goes on.
    (
        "glorelo_season",
        "GlorELO+ (season-weighted)",
        ["glory_plus", "elo", "glory_plus_x_games", "elo_x_games"],
    ),
    ("elo_live", "Elo (live)", "elo_live"),
    ("glorelo_live", "GlorELO+ (live Elo)", ["glory_plus", "elo_live"]),
]
BASELINE = "win_pct"
LABELS = {key: label for key, label, _ in METRICS}
# Does each blend beat its strongest part on the same games?
BLEND_CHECKS = [
    ("glorelo", "elo"),
    ("glorelo_season", "elo"),
    ("glorelo_live", "elo_live"),
]


def load_games():
    """One row per game in a major league or international event, from blue's side."""
    stmt = f"""
    SELECT b.gameid, b.date, b.year, b.league,
           b.teamid AS blue_id, r.teamid AS red_id,
           b.teamname AS blue, r.teamname AS red, b.result AS won,
           eb.pre_match_elo AS blue_elo_live, er.pre_match_elo AS red_elo_live
    FROM matches b
    JOIN matches r ON r.gameid = b.gameid AND r.side = 'Red'
    LEFT JOIN game_length_elo eb ON eb.gameid = b.gameid AND eb.teamid = b.teamid
    LEFT JOIN game_length_elo er ON er.gameid = r.gameid AND er.teamid = r.teamid
    WHERE b.side = 'Blue' AND b.league IN ({_IN_EVENTS})
    """
    games = pd.read_sql(stmt, get_engine(), parse_dates=["date"])
    games["won"] = games["won"].astype(int)
    return games


def load_results():
    """Every major-league team-game result, for win % so far."""
    stmt = f"SELECT year, date, teamname, result FROM matches WHERE league IN ({_IN_MAJORS})"
    return pd.read_sql(stmt, get_engine(), parse_dates=["date"])


def load_elo_timeline():
    """Each team's Elo after every game, oldest first."""
    stmt = """
    SELECT m.teamname, m.date, e.post_match_elo AS elo
    FROM game_length_elo e
    JOIN matches m ON m.gameid = e.gameid AND m.teamid = e.teamid
    ORDER BY m.date, m.gameid
    """
    return pd.read_sql(text(stmt), get_engine(), parse_dates=["date"])


def month_starts(dates):
    """First of every month from the month after the earliest date to the latest."""
    first = dates.min().to_period("M") + 1
    last = dates.max().to_period("M") + 1
    return [p.to_timestamp() for p in pd.period_range(first, last, freq="M")]


def _scores(year, cutoff, **kwargs):
    df = get_glory_ranking(
        year=year,
        league=ALL_MAJOR_LEAGUES,
        before=cutoff.date(),
        minimum_matches=MINIMUM_MATCHES,
        **kwargs,
    )
    # A team in two major leagues in one season keeps its larger sample's row;
    # rankings are sorted by score, so keep the first (best) as a tie-break.
    return df.drop_duplicates("teamname").set_index("teamname")


def ratings_at(year, cutoff, results, elo_timeline):
    """Every metric's rating for each qualified team, using games before `cutoff`."""
    season = results[(results["year"] == year) & (results["date"] < cutoff)]
    record = season.groupby("teamname")["result"].agg(["mean", "size"])
    record = record[record["size"] >= MINIMUM_MATCHES]

    glory = _scores(year, cutoff)
    ratings = pd.DataFrame(
        {
            "league": glory["league"],
            "glory": glory["score"],
            "glorb": _scores(year, cutoff, baseline=True)["score"],
            "glory_plus": _scores(year, cutoff, opponent_adjusted=True)["score"],
            "win_pct": record["mean"],
            "games": record["size"],
        }
    )
    elo = elo_timeline[elo_timeline["date"] < cutoff].groupby("teamname")["elo"].last()
    ratings["elo"] = elo
    return ratings.dropna()


def backtest(games, results, elo_timeline, years):
    """Predict each month's games from ratings at the start of that month."""
    rows = []
    for year in years:
        season_games = games[games["year"] == year]
        season_results = results[results["year"] == year]
        cutoffs = month_starts(season_results["date"])
        for cutoff, next_cutoff in zip(cutoffs, cutoffs[1:] + [pd.Timestamp.max]):
            window = season_games[
                (season_games["date"] >= cutoff) & (season_games["date"] < next_cutoff)
            ]
            if window.empty:
                continue
            if (season_results["date"] < cutoff).sum() < MINIMUM_TRAINING_ROWS:
                continue
            ratings = ratings_at(year, cutoff, results, elo_timeline)
            window = window.join(ratings.add_prefix("blue_"), on="blue", how="inner")
            window = window.join(ratings.add_prefix("red_"), on="red", how="inner")
            print(f"  {year} {cutoff:%Y-%m}: {len(window)} games")
            rows.append(window)

    frame = pd.concat(rows, ignore_index=True)
    for col in ("glory", "glorb", "glory_plus", "win_pct", "elo", "elo_live"):
        frame[col] = frame[f"blue_{col}"] - frame[f"red_{col}"]
    # How far into the season the game is, as log games played by the less-played team.
    games = np.log(frame[["blue_games", "red_games"]].min(axis=1))
    frame["glory_plus_x_games"] = frame["glory_plus"] * games
    frame["elo_x_games"] = frame["elo"] * games
    frame = frame.dropna(subset=["elo_live"]).reset_index(drop=True)

    frame["test_set"] = None
    frame.loc[frame["league"].isin(MAJORS), "test_set"] = "Domestic"
    cross_region = frame["league"].isin(INTERNATIONAL_LEAGUES) & (
        frame["blue_league"] != frame["red_league"]
    )
    frame.loc[cross_region, "test_set"] = "International"
    return frame.dropna(subset=["test_set"]).reset_index(drop=True)


def score(frame):
    """Per-game losses for every metric, using out-of-year win curves."""
    losses = {}
    for key, _, inputs in METRICS:
        p = out_of_year_probabilities(frame, inputs)
        losses[key] = game_losses(p, frame["won"])
    return losses


def summarize(frame, losses):
    lines = []
    for test_set in ("Domestic", "International"):
        mask = (frame["test_set"] == test_set).to_numpy()
        n = int(mask.sum())
        years = frame.loc[mask, "year"]
        lines.append(f"\n### {test_set}: {n:,} games, {years.min()}–{years.max()}\n")
        lines.append(
            "| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |"
        )
        lines.append("|---|---:|---:|---:|---|")
        base = losses[BASELINE]["log_loss"].to_numpy()[mask]
        for key, label, _ in METRICS:
            l = losses[key][mask]
            if key == BASELINE:
                delta = "baseline"
            else:
                mean, lo, hi = paired_bootstrap(l["log_loss"].to_numpy(), base)
                delta = f"{mean:+.4f} ({lo:+.4f} to {hi:+.4f})"
            lines.append(
                f"| {label} | {l['accuracy'].mean():.1%} | {l['brier'].mean():.4f} "
                f"| {l['log_loss'].mean():.4f} | {delta} |"
            )
        lines.append("")
        for blend, part in BLEND_CHECKS:
            mean, lo, hi = paired_bootstrap(
                losses[blend]["log_loss"].to_numpy()[mask],
                losses[part]["log_loss"].to_numpy()[mask],
            )
            lines.append(
                f"- {LABELS[blend]} vs {LABELS[part]}: log loss "
                f"{mean:+.4f} ({lo:+.4f} to {hi:+.4f})"
            )
    lines.append(
        "\nLower Brier and log loss are better. A negative log-loss delta means the "
        "metric beats win % so far; an interval that excludes 0 is a real difference."
    )
    return "\n".join(lines)


def glorelo_weights(frame):
    """Per-point log-odds weights of the published GlorELO+ (GLORY+ and live Elo).

    Fit on every backtest game. `--write-weights` saves them for `prometheus/glorelo.py`.
    """
    x = frame[["glory_plus", "elo_live"]].to_numpy()
    sd = x.std(axis=0)
    model = LogisticRegression(C=1e6).fit(x / sd, frame["won"])
    glory_plus, elo = model.coef_[0] / sd
    return {"glory_plus_weight": glory_plus, "elo_weight": elo}


def format_weights(weights):
    return (
        f"\nGlorELO+ weights (log-odds per point, all games): "
        f"GLORY_PLUS_WEIGHT = {weights['glory_plus_weight']:.5f}, "
        f"ELO_WEIGHT = {weights['elo_weight']:.5f}"
    )


def check_weights(weights):
    """Compare refit weights with the tracked ones; warn (GitHub annotation) on a big move."""
    tracked = load_weights()
    changes = weight_changes(tracked, weights)
    for key, change in changes.items():
        print(f"{key}: tracked {tracked[key]:.5f}, refit {weights[key]:.5f} ({change:+.1%})")
    moved = [key for key, change in changes.items() if change > WEIGHT_TOLERANCE]
    if moved:
        print(
            f"::warning title=GlorELO+ weights moved::{', '.join(moved)} moved more than "
            f"{WEIGHT_TOLERANCE:.0%} on refit. Run scripts/evaluate_metrics.py "
            "--write-weights and review the backtest."
        )
    return moved


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--years", type=int, nargs="*", help="Seasons to backtest (default: all)"
    )
    parser.add_argument("--out", help="Also write the report to this Markdown file")
    weights_mode = parser.add_mutually_exclusive_group()
    weights_mode.add_argument(
        "--write-weights",
        action="store_true",
        help="Save the refit GlorELO+ weights to prometheus/glorelo_weights.json",
    )
    weights_mode.add_argument(
        "--check-weights",
        action="store_true",
        help="Only refit the GlorELO+ weights and warn if they moved (skips the report)",
    )
    args = parser.parse_args()
    if args.years and (args.write_weights or args.check_weights):
        sys.exit("GlorELO+ weights are fit on every season; drop --years.")

    years = args.years or get_available_years(ALL_MAJOR_LEAGUES)
    print("Loading games...")
    games, results, elo_timeline = load_games(), load_results(), load_elo_timeline()
    print("Backtesting:")
    frame = backtest(games, results, elo_timeline, years)
    weights = glorelo_weights(frame)
    if args.check_weights:
        check_weights(weights)
        return

    report = (
        f"## Metric backtest ({datetime.date.today().isoformat()})\n"
        + summarize(frame, score(frame))
        + format_weights(weights)
    )
    print(report)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
    if args.write_weights:
        save_weights(weights)
        print("Saved GlorELO+ weights to prometheus/glorelo_weights.json")


if __name__ == "__main__":
    main()
