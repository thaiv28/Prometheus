"""
blue_side.py: should Elo's update, and our calls, know which side a team plays on?

Blue side wins about 54% of games, but published Elo's expected score ignores side
(a blue win earns as much as a red one) and our calls are for a neutral side. Two
parts:

1. **Elo update.** Replays Elo (`elo_variants.replay`) with the expected score
   counting blue's rating `side_advantage` points higher (`compute_elo_records`
   options, off by default). Stored ratings stay neutral, so the backtest curves'
   blue intercept is unchanged; any gain has to come from better ratings. Three
   designs, grids fixed in advance: one advantage everywhere; one per tier (major
   leagues and international events vs every other league); and an advantage
   learned online from earlier games (each tier's moves by `side_rate` times the
   blue team's change, starting at 0). Tuned on 2014–2021 (mean Elo log loss over
   domestic and within-other-league games, as `elo_new_players.py`), reported on
   2022 on against the published Elo (rookie discount on): Elo and FORGE on
   domestic, international, within other leagues and cross-league games.
2. **Is the side known before a match?** Our calls are made before the match, so a
   side term helps only if game 1's side is predictable. Checks against Oracle's
   Elixir: how often the prediction log's Leaguepedia `team1` was blue in game 1, by
   league, and how often the loser of a series game played blue in the next.

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/blue_side.py --out docs/research/blue_side.md
"""

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_new_players as enp
import elo_variants as ev
import evaluate_metrics as em

from prometheus.elo import winner_score
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

TRAIN_LAST = 2021
POINTS = (10, 20, 30, 40)
DESIGNS = {
    "One advantage": [{"side_advantage": a} for a in (*POINTS, 60)],
    "By tier": [
        {"side_advantage": {"major": m, "other": o}} for m in POINTS for o in POINTS
    ],
    "Learned online": [{"side_rate": r} for r in (0.005, 0.01, 0.02, 0.05)],
}
MAJOR_EVENTS = {l.value for l in ALL_MAJOR_LEAGUES} | set(INTERNATIONAL_LEAGUES)
# Games of one series: same two teams, each within this long of the last.
SERIES_GAP = pd.Timedelta(hours=12)


# --- part 1 --------------------------------------------------------------------------


def update_scale_advantage(inputs):
    """Blue's mean actual score in the update (game-length scored) by tier, and the
    Elo points that score corresponds to on the 400-point curve."""
    g = inputs.games
    s = winner_score(g["gamelength"].to_numpy(dtype=float))
    blue_won = (g["side"] == "Blue").to_numpy() == g["result"].astype(bool).to_numpy()
    blue_score = np.where(blue_won, s, 1 - s)
    tier = np.where(g["league"].isin(MAJOR_EVENTS), "major", "other")
    rows = []
    for t in ("major", "other"):
        m = blue_score[tier == t].mean()
        rows.append((t, int((tier == t).sum()), m, 400 * math.log10(m / (1 - m))))
    return rows


def sections(inputs, pairs, pre, years):
    """Per-game log loss of every section on `years`."""
    s = ev.score(inputs, pre, years=years)
    _, oth = enp.other_losses(pairs, pre, years)
    _, cr = enp.cross_losses(pairs, pre, years)
    _, of = enp.other_forge_losses(inputs, pairs, pre, years)
    return {
        "Elo, domestic": s.log_loss("elo_live", "Domestic"),
        "Elo, international": s.log_loss("elo_live", "International"),
        "FORGE, domestic": s.log_loss("forge", "Domestic"),
        "FORGE, international": s.log_loss("forge", "International"),
        "Elo, other leagues": oth,
        "FORGE, other leagues": of,
        "Elo, cross-league": cr,
    }


def part_one(lines):
    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    years = sorted(inputs.frame["year"].unique())
    train = [y for y in years if y <= TRAIN_LAST]
    test = [y for y in years if y > TRAIN_LAST]
    margin = ev.game_length_margin()
    base_pre = inputs.baseline()

    lines += [
        "### Blue's score in the update\n",
        "Blue's mean actual score in Elo's update (a win scores 0.65–1.0 by game "
        "length) over every game, and the gap on the 400-point curve it amounts to.\n",
        "| Tier | Games | Blue's mean score | Elo points |",
        "|---|---:|---:|---:|",
    ]
    for t, n, m, pts in update_scale_advantage(inputs):
        lines.append(f"| {t} | {n:,} | {m:.4f} | {pts:+.1f} |")

    lines += [
        "\n### Tuning\n",
        f"Objective: mean Elo log loss over domestic and within-other-league games, "
        f"{train[0]}–{train[-1]}.\n",
        "| Design | Best parameters | Train objective | Published |",
        "|---|---|---:|---:|",
    ]
    base_obj = enp.objective(inputs, pairs, base_pre, train)
    chosen = {}
    for design, grid in DESIGNS.items():
        scored = []
        for params in grid:
            pre = ev.replay(inputs, margin, **params)
            scored.append((enp.objective(inputs, pairs, pre, train), params))
            print(f"  {design} {params}: {scored[-1][0]:.5f}", flush=True)
        best_obj, best = min(scored, key=lambda t: t[0])
        chosen[design] = best
        lines.append(f"| {design} | {best} | {best_obj:.5f} | {base_obj:.5f} |")

    base = sections(inputs, pairs, base_pre, test)
    names = list(base)
    lines += [
        f"\n### Held out, {test[0]}–{test[-1]}\n",
        "Δ is variant minus published log loss (negative is better), paired "
        "bootstrap 95% interval over games.\n",
        "| Design | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
        "| Published (log loss) | "
        + " | ".join(f"{base[n].mean():.4f}" for n in names)
        + " |",
    ]
    for design, params in chosen.items():
        var = sections(inputs, pairs, ev.replay(inputs, margin, **params), test)
        cells = []
        for n in names:
            assert len(var[n]) == len(base[n])
            cells.append(enp._delta(var[n], base[n]))
        lines.append(f"| {design} {params} | " + " | ".join(cells) + " |")
    lines.append(
        "\nGames: " + ", ".join(f"{n} {len(base[n]):,}" for n in names) + ".\n"
    )


# --- part 2 --------------------------------------------------------------------------


def load_sided_games():
    """One row per game: date, league, blue and red team names and ids, blue won."""
    stmt = """
    SELECT b.gameid, b.date, b.league, b.teamname AS blue, r.teamname AS red,
           b.teamid AS blue_id, r.teamid AS red_id, b.result AS blue_won
    FROM matches b JOIN matches r ON r.gameid = b.gameid AND r.side = 'Red'
    WHERE b.side = 'Blue'
    ORDER BY b.date, b.gameid
    """
    g = pd.read_sql(stmt, get_engine())
    g["date"] = pd.to_datetime(g["date"])
    return g


def series_games(g):
    """`g` with series and game number: consecutive games of one pair of teams
    within `SERIES_GAP` of each other."""
    g = g.copy()
    g["pair"] = [
        tuple(sorted(x)) for x in zip(g["blue_id"].astype(str), g["red_id"].astype(str))
    ]
    g = g.sort_values(["date", "gameid"]).reset_index(drop=True)
    gap = g.groupby("pair")["date"].diff()
    g["series"] = (gap.isna() | (gap > SERIES_GAP)).groupby(g["pair"]).cumsum()
    g["game"] = g.groupby(["pair", "series"]).cumcount() + 1
    return g


def loser_side(g):
    """For every later game of a series, whether the previous game's loser is blue."""
    prev = g.groupby(["pair", "series"]).shift()
    later = g[g["game"] > 1].copy()
    p = prev.loc[later.index]
    loser = np.where(p["blue_won"].astype(bool), p["red_id"], p["blue_id"])
    later["loser_blue"] = later["blue_id"].to_numpy() == loser
    later["tier"] = np.where(later["league"].isin(MAJOR_EVENTS), "major", "other")
    later["year"] = later["date"].dt.year
    return later


def team1_blue(g, log_path):
    """Logged matches (Leaguepedia team1/team2) matched to game 1 in Oracle's
    Elixir: same two team names, first game within a day after the start."""
    matches = json.loads(Path(log_path).read_text())["matches"]
    firsts = g[g["game"] == 1]
    by_names = {}
    for row in firsts.itertuples(index=False):
        by_names.setdefault(frozenset((row.blue, row.red)), []).append(row)
    rows = []
    for m in matches:
        if not m.get("ours1") or not m.get("ours2") or m.get("winner") is None:
            continue
        start = pd.Timestamp(m["start"]).tz_localize(None)
        cands = [
            r
            for r in by_names.get(frozenset((m["ours1"], m["ours2"])), [])
            if start - pd.Timedelta(hours=6) <= r.date <= start + pd.Timedelta(days=1)
        ]
        if not cands:
            continue
        first = min(cands, key=lambda r: r.date)
        rows.append(
            {
                "league": m["league"],
                "event": m["event"],
                "playoffs": "playoff" in m["event"].lower()
                or "knockout" in m["event"].lower(),
                "team1_blue": first.blue == m["ours1"],
            }
        )
    return pd.DataFrame(rows)


def part_two(lines, log_path):
    g = series_games(load_sided_games())
    later = loser_side(g[g["date"].dt.year >= 2016])
    lines += [
        "### Does the loser play blue next?\n",
        "Later games of a series (Bo3/Bo5, grouped by teams and a 12-hour gap), "
        "share where the previous game's loser is on blue.\n",
        "| Year | Major games | Loser on blue | Other games | Loser on blue |",
        "|---|---:|---:|---:|---:|",
    ]
    for year, df in later.groupby("year"):
        maj, oth = df[df.tier == "major"], df[df.tier == "other"]
        lines.append(
            f"| {year} | {len(maj):,} | {maj['loser_blue'].mean():.1%} "
            f"| {len(oth):,} | {oth['loser_blue'].mean():.1%} |"
        )

    t1 = team1_blue(g, log_path)
    lines += [
        "\n### Is Leaguepedia's team1 blue in game 1?\n",
        f"Prediction-log matches matched to game 1 in Oracle's Elixir: {len(t1):,}.\n",
        "| League | Matches | team1 blue | Playoff matches | team1 blue |",
        "|---|---:|---:|---:|---:|",
    ]
    for league, df in sorted(t1.groupby("league"), key=lambda kv: -len(kv[1])):
        if len(df) < 10:
            continue
        po = df[df["playoffs"]]
        po_cell = f"{po['team1_blue'].mean():.1%}" if len(po) else "–"
        lines.append(
            f"| {league} | {len(df)} | {df['team1_blue'].mean():.1%} | {len(po)} "
            f"| {po_cell} |"
        )
    small = t1.groupby("league").filter(lambda d: len(d) < 10)
    if len(small):
        lines.append(
            f"| Leagues with under 10 | {len(small)} | {small['team1_blue'].mean():.1%} | | |"
        )
    lines.append(f"| All | {len(t1)} | {t1['team1_blue'].mean():.1%} | | |\n")

    lines += [
        "### How much would the later games' sides move a series call?\n",
        "Game 1 neutral; in each later game the previous game's loser is on blue with "
        "chance q, and blue adds d log-odds. Change in the favourite's series chance "
        "against no side term.\n",
        "| Best of | Game chance | d 0.13, q 0.92 | d 0.13, q 0.21 | d 0.20, q 0.92 |",
        "|---|---:|---:|---:|---:|",
    ]
    for best_of in (3, 5):
        for p in (0.6, 0.7, 0.8):
            base = loser_picks_series(p, best_of, 0.0, 0.5)
            cells = [
                f"{loser_picks_series(p, best_of, d, q) - base:+.4f}"
                for d, q in ((0.13, 0.92), (0.13, 0.21), (0.20, 0.92))
            ]
            lines.append(f"| {best_of} | {p:.1f} | " + " | ".join(cells) + " |")
    lines.append("")
    return t1, later


def loser_picks_series(p, best_of, d, q):
    """Series chance for a team with game chance `p` on a neutral side, when in every
    game after the first the previous game's loser is on blue with chance `q` and
    blue adds `d` log-odds."""
    need = best_of // 2 + 1
    base = math.log(p / (1 - p))

    def game(on_blue_chance):
        return on_blue_chance / (1 + math.exp(-(base + d))) + (1 - on_blue_chance) / (
            1 + math.exp(-(base - d))
        )

    def win(a, b, won_last):
        if a == need:
            return 1.0
        if b == need:
            return 0.0
        pa = p if won_last is None else game(1 - q if won_last else q)
        return pa * win(a + 1, b, True) + (1 - pa) * win(a, b + 1, False)

    return win(0, 0, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--log", type=Path, default=Path("data/predictions.json"))
    ap.add_argument("--skip-elo", action="store_true", help="part 2 only")
    args = ap.parse_args()
    lines = [
        f"## Blue side in Elo and our calls ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/blue_side.py`.\n",
    ]
    if not args.skip_elo:
        lines.append("## Part 1: side in Elo's update\n")
        part_one(lines)
    lines.append("## Part 2: is the side known before a match?\n")
    part_two(lines, args.log)
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)


if __name__ == "__main__":
    main()
