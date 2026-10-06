"""
evaluate_metrics.py: Backtest how well each forecast predicts game winners.

Only forecasts are scored here; season stats (GLORY, Record, Luck) are judged by
`evaluate_season_stats.py` instead. "As of cutoff" ratings are taken at the first
of every month and used for that month's games; "live" ratings are each game's
pre-game rating. The rating gap between the two teams is turned into a win
probability with a logistic curve fit on the other seasons, and the probabilities
are scored. Form's weights are also fit on the other seasons.

Test sets:
- Domestic: LCK, LPL, LEC and LCS games.
- International: Worlds, MSI, EWC, First Stand, ... games between teams from two
  different major leagues, predicted from domestic play. This is the only direct
  test of cross-region strength.
- Cross-league, every league: games at any event (EMEA Masters, cups, promotion,
  international) between teams whose home leagues differ, the home being the
  league a team played most that season. Scored with Elo (live) only, as the site
  forecasts these games; it is the benchmark for league offsets below the majors.

Every forecast is scored on exactly the same games (both teams need 5+ games that
season before the month starts), and each is compared with "win % so far this
season" using a paired bootstrap.

Usage:
    uv run python scripts/evaluate_metrics.py [--years 2022 2023] [--out report.md]
    uv run python scripts/evaluate_metrics.py --write-weights   # refresh Form and FORGE weights
    uv run python scripts/evaluate_metrics.py --check-weights   # CI: warn if they moved
"""

import argparse
import datetime
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sqlalchemy import text

from prometheus import form
from prometheus.elo import calculate_game_length_elo_change, compute_elo_records, load_elo_games
from prometheus.evaluation import (
    cross_league_games,
    elo_as_of,
    game_losses,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.forge import (
    WEIGHT_TOLERANCE,
    load_weights,
    save_weights,
    weight_changes,
)
from prometheus.matches import get_available_years
from prometheus.types import ALL_MAJOR_LEAGUES, GLORY_FEATURES, INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

MINIMUM_MATCHES = 5
# A month is scored once its season has this many major-league team-games before it.
MINIMUM_TRAINING_ROWS = 200
MAJORS = [l.value for l in ALL_MAJOR_LEAGUES]
_IN_MAJORS = ", ".join(repr(l) for l in MAJORS)
_IN_EVENTS = ", ".join(repr(l) for l in MAJORS + INTERNATIONAL_LEAGUES)

# (key, label, inputs). `inputs` are the blue-minus-red gap columns the win curve
# is fit on: None for the blue-side baseline, several columns for a blend, and
# FORGE for the published forecast (see `forge_probabilities`).
# "win_pct" is the baseline every other forecast is compared with.
FORGE = "forge"
METRICS = [
    ("blue_side", "Blue side wins", None),
    ("win_pct", "Win % so far", "win_pct"),
    ("elo", "Elo (as of cutoff)", "elo"),
    ("elo_live", "Elo (live)", "elo_live"),
    ("team_elo_live", "Team Elo, no player ratings (live)", "team_elo_live"),
    ("form", "Form (live)", "form"),
    ("forge", "FORGE (live)", FORGE),
]
BASELINE = "win_pct"
LABELS = {key: label for key, label, _ in METRICS}
# Does each blend beat its strongest part on the same games?
BLEND_CHECKS = [("forge", "elo_live"), ("form", "elo_live"), ("elo_live", "team_elo_live")]
# Domestic games where player ratings should matter most: early in a season, and
# soon after a team changed a starter. Elo (player-built) is compared with team Elo.
ROSTER_SLICE_GAMES = 10


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


def load_cross_league():
    """Every cross-league game (see `cross_league_games`) with each side's pre-game Elo."""
    stmt = """
    SELECT m1.gameid, m1.year, m1.league, m1.teamid, m2.teamid AS opponent_teamid,
           m1.result AS won, e1.pre_match_elo - e2.pre_match_elo AS elo_live
    FROM matches m1
    JOIN matches m2 ON m2.gameid = m1.gameid AND m1.teamid < m2.teamid
    JOIN game_length_elo e1 ON e1.gameid = m1.gameid AND e1.teamid = m1.teamid
    JOIN game_length_elo e2 ON e2.gameid = m2.gameid AND e2.teamid = m2.teamid
    """
    games = pd.read_sql(stmt, get_engine())
    games["won"] = games["won"].astype(int)
    return cross_league_games(games, INTERNATIONAL_LEAGUES, MAJORS)


def summarize_cross_league(games):
    """Elo (live) on every cross-league game, by which leagues met."""
    losses = game_losses(out_of_year_probabilities(games, "elo_live"), games["won"])
    lines = [
        f"\n### Cross-league, every league: {len(games):,} games, {games['year'].min()}–{games['year'].max()}\n",
        "Elo (live) on games between teams from two home leagues at any event; "
        "the home is the league a team played most that season.\n",
        "| Teams | Games | Accuracy | Brier | Log loss |",
        "|---|---:|---:|---:|---:|",
    ]
    international = games["league"].isin(INTERNATIONAL_LEAGUES)
    for label, mask in (
        ("All", pd.Series(True, index=games.index)),
        ("Major v major", games["kind"] == "major v major"),
        ("Major v other", games["kind"] == "major v other"),
        ("Other v other", games["kind"] == "other v other"),
        ("At an international event", international),
        ("At any other event (EMEA Masters, cups, promotion)", ~international),
    ):
        l = losses[mask.to_numpy()]
        lines.append(
            f"| {label} | {len(l):,} | {l['accuracy'].mean():.1%} | {l['brier'].mean():.4f} "
            f"| {l['log_loss'].mean():.4f} |"
        )
    return "\n".join(lines) + "\n"


def load_results():
    """Every major-league team-game result, for win % so far."""
    stmt = f"SELECT year, date, league, teamname, result FROM matches WHERE league IN ({_IN_MAJORS})"
    return pd.read_sql(stmt, get_engine(), parse_dates=["date"])


def load_elo_timeline():
    """Each team's Elo after every game, and the league-offset history, oldest first."""
    stmt = """
    SELECT m.teamname, m.date, e.post_match_elo AS elo, e.home_league, e.league_offset
    FROM game_length_elo e
    JOIN matches m ON m.gameid = e.gameid AND m.teamid = e.teamid
    ORDER BY m.date, m.gameid
    """
    timeline = pd.read_sql(text(stmt), get_engine(), parse_dates=["date"])
    offsets = pd.read_sql(
        "SELECT date, league, league_offset FROM game_length_elo_league_offsets ORDER BY rowid",
        get_engine(),
        parse_dates=["date"],
    )
    return timeline, offsets


def load_team_elo():
    """Pre-game Elo with each team as one unit (no player ratings), for comparison."""
    records, _ = compute_elo_records(load_elo_games(), calculate_game_length_elo_change)
    return records.set_index(["gameid", "teamid"])["pre_match_elo"]


def load_roster_context():
    """Per team-game: games played that season before it, and games since a starter changed.

    A starter change is any game whose five players differ from the team's previous game.
    """
    stmt = """
    SELECT m.gameid, m.teamid, m.year, m.date, group_concat(p.playerid, ',') AS players
    FROM matches m JOIN (SELECT * FROM match_players ORDER BY playerid) p
        ON p.gameid = m.gameid AND p.teamid = m.teamid
    GROUP BY m.gameid, m.teamid
    ORDER BY m.date, m.gameid
    """
    rows = pd.read_sql(stmt, get_engine())
    rows["season_game"] = rows.groupby(["teamid", "year"]).cumcount()
    changed = rows["players"] != rows.groupby("teamid")["players"].shift()
    changed &= rows.groupby("teamid").cumcount() > 0
    block = changed.groupby(rows["teamid"]).cumsum()
    since = rows.groupby([rows["teamid"], block]).cumcount()
    # Before a team's first change there is no change to count from.
    rows["since_change"] = since.where(block > 0, np.inf)
    return rows.set_index(["gameid", "teamid"])[["season_game", "since_change"]]


def month_starts(dates):
    """First of every month from the month after the earliest date to the latest."""
    first = dates.min().to_period("M") + 1
    last = dates.max().to_period("M") + 1
    return [p.to_timestamp() for p in pd.period_range(first, last, freq="M")]


def ratings_at(year, cutoff, results, elo_timeline):
    """As-of-cutoff ratings for each qualified team, using games before `cutoff`."""
    season = results[(results["year"] == year) & (results["date"] < cutoff)]
    record = season.groupby("teamname").agg(
        win_pct=("result", "mean"),
        games=("result", "size"),
        # The major league it played most this season so far.
        league=("league", lambda l: l.value_counts().index[0]),
    )
    ratings = record[record["games"] >= MINIMUM_MATCHES].copy()
    # The rating the site would have shown that day, league-offset moves included.
    ratings["elo"] = elo_as_of(*elo_timeline, cutoff)
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
    team_elo = load_team_elo()
    context = load_roster_context()
    for side in ("blue", "red"):
        key = pd.MultiIndex.from_arrays([frame["gameid"], frame[f"{side}_id"]])
        frame[f"{side}_team_elo_live"] = team_elo.reindex(key).to_numpy()
        for col in ("season_game", "since_change"):
            frame[f"{side}_{col}"] = context[col].reindex(key).to_numpy()
    for col in ("season_game", "since_change"):
        frame[col] = np.minimum(frame[f"blue_{col}"], frame[f"red_{col}"])
    for col in ("win_pct", "elo", "elo_live", "team_elo_live"):
        frame[col] = frame[f"blue_{col}"] - frame[f"red_{col}"]
    frame = frame.dropna(subset=["elo_live"]).reset_index(drop=True)

    frame["test_set"] = None
    frame.loc[frame["league"].isin(MAJORS), "test_set"] = "Domestic"
    cross_region = frame["league"].isin(INTERNATIONAL_LEAGUES) & (
        frame["blue_league"] != frame["red_league"]
    )
    frame.loc[cross_region, "test_set"] = "International"
    return frame.dropna(subset=["test_set"]).reset_index(drop=True)


def form_states():
    """Every team's pre-game Form state for every game (opponent-adjusted stats)."""
    return form.form_states(form.opponent_adjust(form.load_form_games()))


def _state_gaps(frame, states):
    """Blue-minus-red pre-game state gaps for each frame game (one column per stat)."""
    pre = states.set_index(["gameid", "teamid"])[[f"pre_{f}" for f in GLORY_FEATURES]]
    blue = pre.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["blue_id"]])).to_numpy()
    red = pre.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["red_id"]])).to_numpy()
    return blue - red


def add_form(frame, states):
    """Add each game's league-relative Form gap, with Form weights fit out of year.

    For each season, Form's weights come from domestic games in every other season,
    so no game is scored with weights that saw it.
    """
    gaps = _state_gaps(frame, states)
    domestic = (frame["test_set"] == "Domestic").to_numpy()
    won = frame["won"].to_numpy()
    score = np.full(len(states), np.nan)
    for year in sorted(states["year"].unique()):
        train = domestic & (frame["year"] != year).to_numpy()
        weights = dict(zip(GLORY_FEATURES, form.fit_form_weights(gaps[train], won[train])))
        rows = (states["year"] == year).to_numpy()
        score[rows] = form.scores(states[rows], weights)
    relative = pd.Series(form.league_relative(states, score), index=pd.MultiIndex.from_frame(states[["gameid", "teamid"]]))
    blue = relative.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["blue_id"]])).to_numpy()
    red = relative.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["red_id"]])).to_numpy()
    return frame.assign(form=blue - red)


def forge_probabilities(frame):
    """The published FORGE: Elo + Form within a league, Elo alone across leagues.

    Same-league games use a curve on the Elo and Form gaps fit on same-league games;
    cross-league games use a curve on the Elo gap fit on every game.
    """
    same = (frame["blue_league"] == frame["red_league"]).to_numpy()
    p = out_of_year_probabilities(frame, "elo_live")
    within = frame[same].reset_index(drop=True)
    p[same] = out_of_year_probabilities(within, ["elo_live", "form"]).to_numpy()
    return p


def score(frame):
    """Per-game losses for every metric, using out-of-year win curves."""
    losses = {}
    for key, _, inputs in METRICS:
        p = forge_probabilities(frame) if inputs == FORGE else out_of_year_probabilities(frame, inputs)
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
    domestic = frame["test_set"] == "Domestic"
    lines.append("\n### Player-built Elo vs team Elo, where rosters matter\n")
    lines.append("| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |")
    lines.append("|---|---:|---:|---:|---|")
    n = ROSTER_SLICE_GAMES
    for label, mask in (
        ("All", domestic),
        (f"Either team in its first {n} games of the season", domestic & (frame["season_game"] < n)),
        (f"Either team within {n} games of a starter change", domestic & (frame["since_change"] < n)),
    ):
        mask = mask.to_numpy()
        team = losses["team_elo_live"]["log_loss"].to_numpy()[mask]
        player = losses["elo_live"]["log_loss"].to_numpy()[mask]
        mean, lo, hi = paired_bootstrap(player, team)
        lines.append(
            f"| {label} | {int(mask.sum()):,} | {team.mean():.4f} | {player.mean():.4f} "
            f"| {mean:+.4f} ({lo:+.4f} to {hi:+.4f}) |"
        )
    lines.append(
        "\nLower Brier and log loss are better. A negative log-loss delta means the "
        "metric beats win % so far; an interval that excludes 0 is a real difference."
    )
    return "\n".join(lines)


def _slopes(x, won):
    """Per-unit logistic slopes (with an intercept for the blue side)."""
    x = np.asarray(x, dtype=float).reshape(len(won), -1)
    sd = x.std(axis=0)
    model = LogisticRegression(C=1e6).fit(x / sd, won)
    return model.coef_[0] / sd


def published_weights(frame, states):
    """Form and FORGE weights for the site, fit on every backtest game.

    Returns:
        (form_weights, forge_weights). Form: log-odds per unit of each stat's gap,
        fit on domestic games. FORGE: elo_weight and form_weight (same-league
        games) and cross_region_elo_weight (every game).
    """
    gaps = _state_gaps(frame, states)
    domestic = (frame["test_set"] == "Domestic").to_numpy()
    form_weights = dict(zip(GLORY_FEATURES, form.fit_form_weights(gaps[domestic], frame["won"].to_numpy()[domestic])))
    relative = pd.Series(
        form.league_relative(states, form.scores(states, form_weights)),
        index=pd.MultiIndex.from_frame(states[["gameid", "teamid"]]),
    )
    blue = relative.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["blue_id"]])).to_numpy()
    red = relative.reindex(pd.MultiIndex.from_arrays([frame["gameid"], frame["red_id"]])).to_numpy()
    same = (frame["blue_league"] == frame["red_league"]).to_numpy()
    won = frame["won"].to_numpy()
    elo_w, form_w = _slopes(np.c_[frame["elo_live"].to_numpy()[same], (blue - red)[same]], won[same])
    (cross_w,) = _slopes(frame["elo_live"].to_numpy(), won)
    return form_weights, {"elo_weight": elo_w, "form_weight": form_w, "cross_region_elo_weight": cross_w}


def format_weights(forge):
    return (
        "\nFORGE weights (log-odds per point): "
        + ", ".join(f"{k} = {v:.5f}" for k, v in forge.items())
        + f". Form: half-life {form.HALF_LIFE} games, carry {form.CARRY}, prior {form.PRIOR_GAMES} games."
    )


def _tracked_and_refit(form_weights, forge):
    tracked = {**load_weights(), **{f"form_{k}": v for k, v in form.load_weights()["weights"].items()}}
    refit = {**forge, **{f"form_{k}": v for k, v in form_weights.items()}}
    return tracked, refit


def check_weights(form_weights, forge):
    """Compare refit weights with the tracked ones; warn (GitHub annotation) on a big move."""
    tracked, weights = _tracked_and_refit(form_weights, forge)
    changes = weight_changes(tracked, weights)
    for key, change in changes.items():
        print(f"{key}: tracked {tracked[key]:.5f}, refit {weights[key]:.5f} ({change:+.1%})")
    # Only the blend weights can raise a warning: some Form stat weights are near
    # zero, so their relative changes are noise. They are printed above for review.
    moved = [
        key for key, change in changes.items()
        if not key.startswith("form_") and change > WEIGHT_TOLERANCE
    ]
    if moved:
        print(
            f"::warning title=Forecast weights moved::{', '.join(moved)} moved more than "
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
        help="Save the refit Form and FORGE weights (prometheus/form_weights.json, forge_weights.json)",
    )
    weights_mode.add_argument(
        "--check-weights",
        action="store_true",
        help="Only refit the Form and FORGE weights and warn if they moved (skips the report)",
    )
    args = parser.parse_args()
    if args.years and (args.write_weights or args.check_weights):
        sys.exit("Forecast weights are fit on every season; drop --years.")

    years = args.years or get_available_years(ALL_MAJOR_LEAGUES)
    print("Loading games...")
    games, results, elo_timeline = load_games(), load_results(), load_elo_timeline()
    states = form_states()
    print("Backtesting:")
    frame = add_form(backtest(games, results, elo_timeline, years), states)
    form_weights, weights = published_weights(frame, states)
    if args.check_weights:
        check_weights(form_weights, weights)
        return

    report = (
        f"## Metric backtest ({datetime.date.today().isoformat()})\n"
        + summarize(frame, score(frame))
        + summarize_cross_league(load_cross_league())
        + format_weights(weights)
    )
    print(report)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
    if args.write_weights:
        save_weights(weights)
        form.save_weights(form_weights)
        print("Saved weights to prometheus/forge_weights.json and prometheus/form_weights.json")


if __name__ == "__main__":
    main()
