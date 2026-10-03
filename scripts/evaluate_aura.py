"""
evaluate_aura.py: Is AURA's win-probability model calibrated, and does AURA measure the player?

Five parts:

- Calibration. The snapshot model (one logistic weight per role and lane stat) is
  fit on every earlier year and scored on each test year, at 10, 15, 20 and 25
  minutes: log loss, Brier score, AUC and expected calibration error (ECE, the
  games-weighted gap between predicted and actual win % over ten bins). A model
  whose chances are off can't be split into fair shares.
- Player scores, in LCK, LPL, LEC and LCS player-seasons (player, year, role).
  AURA (15-minute term plus a quarter of the team-centred change to 25 minutes)
  is compared with each snapshot's term alone and two baselines: the lane's gold
  gap at 15 minutes (in standard deviations for that role and year) and the
  team's win %.
  - Split-half reliability: each player-season's games split in two by game id;
    the correlation of the halves (10+ games each).
  - Teammates: the correlation, over player-games, of a player's score with the
    average of their four teammates' in the same game. A player stat should not
    simply restate the team.
  - Follows the player: the correlation of a player's season with their next
    season (20+ games each), for players who stayed on a team and players who
    moved. Win % drops sharply for movers, because it is mostly the team's.
- Held-out check, as the AURA change rule asks: AURA against the 15-minute
  term alone with weights fit on earlier years only.
- Do the players add up to the team? Each starter's AURA from one half of a
  team-season, summed over the lineups the team used in the other half, against
  win % in that half; compared with GLORY, win % and the team's own AURA from the
  first half, by a paired bootstrap over team-seasons. Needs GLORY's halves from
  `evaluate_season_stats.py` (imported from this folder).
- Substitutions. Games where exactly one starter changed: does the incoming
  minus outgoing player's AURA so far (earlier games only) predict the result
  beyond Player Elo's expectation, which already rates the new player?

Correlations are within year and role. Differences use a paired bootstrap.

Usage:
    uv run python scripts/evaluate_aura.py [--out docs/aura_report.md]
"""

import argparse
import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from prometheus import aura
from prometheus.elo import get_pregame_elos
from prometheus.evaluation import (
    correlation_interval,
    game_losses,
    half_of,
    paired_correlation_bootstrap,
    spearman_brown,
)
from prometheus.season import MAJORS

FIRST_TEST_YEAR = 2022
MIN_HALF_GAMES = 10
MIN_SEASON_GAMES = 20
KEY = ["playerid", "year", "position"]
SCORES = ["aura"] + [f"aura{m}" for m in aura.MINUTES] + ["gold15", "win"]
LABELS = {"aura": "AURA (15 min + ¼ team-centred change)"}
LABELS |= {f"aura{m}": f"AURA at {m} min only" for m in aura.MINUTES}
LABELS |= {"gold15": "Lane gold gap at 15 min", "win": "Team win %"}
CHOSEN = "aura"
# Held-out check: weights from earlier years only, scored from this year on.
HELD_OUT_FROM = 2017
# A player's AURA from a few games is pulled toward the average lane (0) as if
# this many average games were added.
SHRINK_GAMES = 5
# Substitution test: a player's AURA so far is their last this-many games.
RECENT_GAMES = 50
ROSTER_PREDICTORS = ["roster", "team", "glory", "win_other"]
ROSTER_LABELS = {
    "roster": "Roster AURA (players' AURA, this half's lineups)",
    "team": "Team AURA (the team's own lane sum)",
    "glory": "GLORY",
    "win_other": "Win %",
}


def ece(p, won, bins=10):
    """Expected calibration error over equal-width probability bins."""
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return sum((idx == b).mean() * abs(p[idx == b].mean() - won[idx == b].mean()) for b in range(bins) if (idx == b).any())


def calibration(players):
    """Out-of-year scores at each snapshot, and the 15-minute reliability bins."""
    rows, bins = [], None
    for minute in aura.MINUTES:
        games = aura.game_frame(players, minute)
        test_years = sorted(y for y in games["year"].unique() if y >= FIRST_TEST_YEAR)
        p, won, blue = [], [], []
        for year in test_years:
            train, test = games[games["year"] < year], games[games["year"] == year]
            intercept, weights = aura.fit_aura_weights(train)
            p.append(aura.win_probability(test, intercept, weights))
            won.append(test["won"].to_numpy())
            blue.append(np.full(len(test), train["won"].mean()))
        p, won, blue = np.concatenate(p), np.concatenate(won), np.concatenate(blue)
        rows.append(
            {
                "minute": minute,
                "games": len(won),
                "log_loss": game_losses(p, won)["log_loss"].mean(),
                "blue_ll": game_losses(blue, won)["log_loss"].mean(),
                "brier": game_losses(p, won)["brier"].mean(),
                "auc": roc_auc_score(won, p),
                "ece": ece(p, won),
            }
        )
        if minute == aura.MINUTE:
            frame = pd.DataFrame({"p": p, "won": won, "bin": np.minimum((p * 10).astype(int), 9)})
            bins = frame.groupby("bin").agg(games=("p", "size"), predicted=("p", "mean"), actual=("won", "mean"))
    return pd.DataFrame(rows), bins


def all_scores(players):
    """Every player-game (all leagues) with every score to compare."""
    frame = players[KEY + ["gameid", "teamid", "teamname", "league", "date", "result"]].copy()
    for minute in aura.MINUTES:
        frame[f"aura{minute}"] = aura.snapshot_scores(players, minute)
    frame["aura"] = aura.get_aura(players)["aura"]
    gold = players["gold_15"]
    frame["gold15"] = gold / gold.groupby([players["year"], players["position"]]).transform("std")
    frame["win"] = players["result"].astype(float)
    return frame


def score_frame(scores):
    """Major-league player-games, split into halves by game id."""
    frame = scores[scores["league"].isin(MAJORS)].dropna(subset=[CHOSEN])
    return frame.assign(half=half_of(frame["gameid"]))


def _centre(frame, col):
    return frame[col] - frame.groupby(["year", "position"])[col].transform("mean")


def split_halves(frame, scores=None):
    """Per player-season: each score's mean in each half, centred within year and role."""
    scores = scores or SCORES
    means = frame.groupby(KEY + ["half"])[scores].mean().unstack("half")
    sizes = frame.groupby(KEY + ["half"]).size().unstack("half")
    keep = (sizes[0] >= MIN_HALF_GAMES) & (sizes[1] >= MIN_HALF_GAMES)
    means = means[keep]
    out = pd.DataFrame(index=means.index)
    for s in scores:
        for h in (0, 1):
            out[f"{s}_{h}"] = means[(s, h)]
    out = out.reset_index().dropna()
    for col in out.columns.drop(KEY):
        out[col] = _centre(out, col)
    return out


def teammate_r(frame, score):
    team = frame.groupby(["gameid", "teamid"])[score]
    mates = (team.transform("sum") - frame[score]) / (team.transform("size") - 1)
    return frame[score].corr(mates)


def season_pairs(frame, scores=None):
    """Consecutive player-seasons (same role), each centred within year and role."""
    scores = scores or SCORES
    season = frame.groupby(KEY).agg(
        **{s: (s, "mean") for s in scores},
        games=("gameid", "size"),
        team=("teamname", lambda t: t.mode().iat[0]),
    )
    season = season[season["games"] >= MIN_SEASON_GAMES].reset_index()
    for s in scores:
        season[s] = _centre(season, s)
    following = season.assign(year=season["year"] - 1)
    pairs = season.merge(following, on=KEY, suffixes=("", "_next"))
    return pairs.assign(moved=pairs["team"] != pairs["team_next"])


def _shrunk(total, count, prior=SHRINK_GAMES):
    """A mean pulled toward 0 (the average lane) as if `prior` average games were added."""
    return total / (count + prior)


def roster_table(frame, glory=None, score=CHOSEN):
    """Per team-season half: each predictor from the *other* half, and this half's win %.

    Roster AURA: every starter's AURA in the other half (shrunk; 0 for a player who
    didn't play there), summed over each game's five starters and averaged over the
    team's games in this half. Team AURA: the team's own five-lane sum in the other
    half. GLORY and win %: the other half's values. Rows are (teamname, year, half).
    """
    games = frame.groupby(["teamname", "year", "half"]).agg(n=("gameid", "nunique"), win=("win", "mean"))
    team_games = frame.groupby(["gameid", "teamid", "teamname", "year", "half"])[score].sum().reset_index()
    team_aura = team_games.groupby(["teamname", "year", "half"])[score].mean()
    player = frame.groupby(KEY + ["half"])[score].agg(["sum", "size"])
    player = _shrunk(player["sum"], player["size"])
    rows = []
    for h in (0, 1):
        this = frame[frame["half"] == h]
        other = pd.Series(player.xs(1 - h, level="half"), name="other")
        starters = this.join(other, on=KEY)["other"].fillna(0.0)
        roster = starters.groupby([this["gameid"], this["teamname"], this["year"]]).sum()
        roster = roster.groupby(level=["teamname", "year"]).mean()
        part = pd.DataFrame(
            {
                "win": games.xs(h, level="half")["win"],
                "n": games.xs(h, level="half")["n"],
                "n_other": games.xs(1 - h, level="half")["n"],
                "roster": roster,
                "team": team_aura.xs(1 - h, level="half"),
                "win_other": games.xs(1 - h, level="half")["win"],
            }
        )
        if glory is not None:
            part["glory"] = glory[f"h{1 - h}"]
        rows.append(part.assign(half=h))
    table = pd.concat(rows).dropna()
    table = table[(table["n"] >= MIN_HALF_GAMES) & (table["n_other"] >= MIN_HALF_GAMES)]
    # Keep team-seasons that have both directions, then centre within year.
    both = table.groupby(level=["teamname", "year"])["half"].transform("size") == 2
    table = table[both].reset_index()
    for col in ROSTER_PREDICTORS:
        if col in table:
            table[col] -= table.groupby(["year", "half"])[col].transform("mean")
    table["win"] -= table.groupby(["year", "half"])["win"].transform("mean")
    return table


def _roster_r(table, col):
    return table[col].corr(table["win"])


def roster_bootstrap(table, a, b, n_resamples=2000, seed=0):
    """Paired difference in r with this half's win %, resampling team-seasons (both halves together)."""
    seasons = table[["teamname", "year"]].drop_duplicates().reset_index(drop=True)
    groups = table.groupby(["teamname", "year"]).indices
    keys = list(zip(seasons["teamname"], seasons["year"]))
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_resamples):
        pick = rng.integers(0, len(keys), len(keys))
        sample = table.iloc[np.concatenate([groups[keys[i]] for i in pick])]
        diffs.append(_roster_r(sample, a) - _roster_r(sample, b))
    return _roster_r(table, a) - _roster_r(table, b), np.percentile(diffs, 2.5), np.percentile(diffs, 97.5)


def so_far(players):
    """Add each player's AURA and lane gold gap so far: `<score>_pre` (before the game) and `_post` (after it).

    The shrunk mean of their last `RECENT_GAMES` games, every league; `prior_games`
    counts their earlier games.
    """
    players = players.sort_values(["date", "gameid", "teamid", "position"]).reset_index(drop=True)
    recent = lambda s: s.rolling(RECENT_GAMES, min_periods=1).sum()
    for score in (CHOSEN, "gold15"):
        total = players[score].fillna(0.0).groupby(players["playerid"]).transform(recent)
        count = players[score].notna().astype(float).groupby(players["playerid"]).transform(recent)
        players[f"{score}_post"] = _shrunk(total, count)
        players[f"{score}_pre"] = players[f"{score}_post"].groupby(players["playerid"]).shift().fillna(0.0)
    players["prior_games"] = players.groupby("playerid").cumcount()
    return players


def pregame_gap_r(players, leagues=None):
    """Correlation of the two teams' summed AURA so far (blue minus red) with blue's result."""
    players = so_far(players)
    if leagues is not None:
        players = players[players["league"].isin(leagues)]
    team = players.groupby(["gameid", "side"]).agg(pre=(f"{CHOSEN}_pre", "sum"), won=("win", "first")).unstack("side")
    team = team.dropna()
    return (team[("pre", "Blue")] - team[("pre", "Red")]).corr(team[("won", "Blue")]), len(team)


def substitutions(players, elos):
    """Games where exactly one starter changed from the team's previous game.

    (Two players trading roles changes two roles, so it is never counted.)

    For the incoming and outgoing players, AURA (and the lane gold gap) so far: the
    shrunk mean of their last `RECENT_GAMES` games before this one, every league.
    `surprise` is the result minus Player Elo's expected result (which already
    rates the incoming player).
    """
    players = so_far(players)

    lineups = players.pivot_table(index=["gameid", "teamid"], columns="position", values="playerid", aggfunc="first")
    order = players.drop_duplicates(["gameid", "teamid"])[["gameid", "teamid", "date", "result"]]
    order = order.join(lineups, on=["gameid", "teamid"]).reset_index(drop=True)
    prev = order.groupby("teamid")[["gameid", *aura.ROLES]].shift()
    changed = pd.DataFrame({r: order[r] != prev[r] for r in aura.ROLES})
    one = (changed.sum(axis=1) == 1) & prev["gameid"].notna()
    rows = []
    post = players.set_index(["gameid", "playerid"])
    pre = players.set_index(["gameid", "teamid", "position"])
    for i in np.flatnonzero(one.to_numpy()):
        role = aura.ROLES[int(np.argmax(changed.iloc[i].to_numpy()))]
        g, team, outgoing = order.at[i, "gameid"], order.at[i, "teamid"], prev.at[i, role]
        new = pre.loc[(g, team, role)]
        old = post.loc[(prev.at[i, "gameid"], outgoing)]
        rows.append(
            {
                "gameid": g,
                "teamid": team,
                "league": new["league"],
                "result": order.at[i, "result"],
                "aura_diff": new[f"{CHOSEN}_pre"] - old[f"{CHOSEN}_post"],
                "gold_diff": new["gold15_pre"] - old["gold15_post"],
                "in_games": new["prior_games"],
                "out_games": old["prior_games"] + 1,
            }
        )
    subs = pd.DataFrame(rows).merge(elos, on=["gameid", "teamid"])
    subs["expected"] = 1 / (1 + 10 ** ((subs["opp_elo"] - subs["elo"]) / 400))
    subs["surprise"] = subs["result"].astype(float) - subs["expected"]
    return subs


def _sub_rows(subs, label):
    out = []
    for name, col in (("AURA so far", "aura_diff"), ("Lane gold gap so far", "gold_diff")):
        r = subs[col].corr(subs["surprise"])
        lo, hi = correlation_interval(r, len(subs))
        thirds = pd.qcut(subs[col], 3, labels=False, duplicates="drop")
        by_third = subs.groupby(thirds)["surprise"].mean()
        out.append(
            f"| {label} | {name} | {len(subs):,} | {r:+.3f} ({lo:+.3f} to {hi:+.3f}) "
            f"| {by_third.iloc[0]:+.3f} | {by_third.iloc[-1]:+.3f} |"
        )
    return out


def held_out(players):
    """AURA against the 15-minute term alone, both with weights from earlier years only.

    The AURA change rule's comparison: major-league player-seasons from
    `HELD_OUT_FROM`. Returns rows of numbers and the paired differences.
    """
    frame = players[KEY + ["gameid", "teamid", "teamname", "league", "result"]].copy()
    frame["win"] = players["result"].astype(float)
    frame["aura"] = aura.get_aura(players, earlier_only=True)["aura"]
    frame["aura15"] = aura.snapshot_scores(players, aura.MINUTE, earlier_only=True)
    frame = frame[frame["league"].isin(MAJORS) & (frame["year"] >= HELD_OUT_FROM)].dropna(subset=["aura", "aura15"])
    frame = frame.assign(half=half_of(frame["gameid"]))
    names = ["aura", "aura15"]
    halves, pairs = split_halves(frame, names), season_pairs(frame, names)
    stay, moved = pairs[~pairs["moved"]], pairs[pairs["moved"]]
    roster = roster_table(frame, score="aura")[["teamname", "year", "half", "win", "roster"]].rename(columns={"roster": "aura"})
    roster["aura15"] = roster_table(frame, score="aura15")["roster"].to_numpy()
    rows = {
        n: {
            "split": halves[f"{n}_0"].corr(halves[f"{n}_1"]),
            "mates": teammate_r(frame, n),
            "stay": stay[n].corr(stay[n + "_next"]),
            "moved": moved[n].corr(moved[n + "_next"]),
            "roster": _roster_r(roster, n),
        }
        for n in names
    }
    diffs = {
        "split": paired_correlation_bootstrap((halves["aura_0"], halves["aura_1"]), (halves["aura15_0"], halves["aura15_1"])),
        "moved": paired_correlation_bootstrap((moved["aura"], moved["aura_next"]), (moved["aura15"], moved["aura15_next"])),
        "roster": roster_bootstrap(roster, "aura", "aura15"),
    }
    sizes = (len(halves), len(stay), len(moved), roster[["teamname", "year"]].drop_duplicates().shape[0])
    return rows, diffs, sizes


def held_out_section(result):
    rows, diffs, (n_half, n_stay, n_moved, n_roster) = result
    fmt = lambda d: f"{d[0]:+.3f} ({d[1]:+.3f} to {d[2]:+.3f})"
    lines = [
        "",
        "### Held-out check (the AURA change rule)",
        "",
        f"Both scores with weights fit on every earlier year only, major-league seasons from {HELD_OUT_FROM}: "
        f"{n_half:,} player-seasons (split-half), {n_stay:,} same-team and {n_moved:,} new-team pairs, {n_roster:,} "
        "team-seasons (roster). The team-centred change adds up to zero over a team, so the 15-minute term alone is "
        "also AURA's team-only control.",
        "",
        "| Score | Split-half r | r with teammates | Next season, same team | Next season, new team | Roster r |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for n, label in (("aura", LABELS["aura"]), ("aura15", "AURA at 15 min only")):
        r = rows[n]
        lines.append(f"| {label} | {r['split']:.3f} | {r['mates']:.3f} | {r['stay']:.3f} | {r['moved']:.3f} | {r['roster']:.3f} |")
    lines += [
        "",
        f"AURA minus 15 min only: split-half {fmt(diffs['split'])}; new team {fmt(diffs['moved'])}; roster "
        f"{fmt(diffs['roster'])}; r with teammates {rows['aura']['mates'] - rows['aura15']['mates']:+.3f}.",
    ]
    return lines


def roster_section(table):
    n = table[["teamname", "year"]].drop_duplicates().shape[0]
    lines = [
        "",
        "### Do the players add up to the team?",
        "",
        "Each predictor is taken from one half of a team-season and correlated with win % in the other half (both "
        f"directions pooled, centred within year). {n:,} major-league team-seasons with {MIN_HALF_GAMES}+ games in "
        "each half. Roster AURA uses only players' own AURA, so it follows lineup changes; team AURA is the same "
        "lane sum without crediting players.",
        "",
        "| From the other half | r with this half's win % | Against roster AURA (paired bootstrap) |",
        "|---|---:|---|",
    ]
    for col in ROSTER_PREDICTORS:
        if col not in table:
            continue
        r = _roster_r(table, col)
        if col == "roster":
            vs = "—"
        else:
            d = roster_bootstrap(table, "roster", col)
            vs = f"{d[0]:+.3f} ({d[1]:+.3f} to {d[2]:+.3f})"
        lines.append(f"| {ROSTER_LABELS[col]} | {r:.2f} | {vs} |")
    return lines


def substitution_section(subs, reference=None):
    lines = [
        "",
        "### Substitutions",
        "",
        "Games where exactly one starter differs from the team's previous game, every league. "
        f"Each player's AURA so far is their last {RECENT_GAMES} games before this one, shrunk toward the average "
        f"lane as if {SHRINK_GAMES} average games were added; the difference is incoming minus outgoing. Surprise is "
        "the result minus Player Elo's expected result, which already rates the incoming player, so a positive r "
        "means AURA knows something about the swap that Player Elo doesn't. AURA's weights are fit on the whole "
        "year, a small look-ahead in the weights only.",
        "",
        "| Games | Difference in | Swaps | r with surprise (95% CI) | Surprise, lowest third | Surprise, highest third |",
        "|---|---|---:|---|---:|---:|",
    ]
    if reference is not None:
        lines[4:4] = [
            "",
            f"For reference, the test can see a signal: over all {reference[1]:,} games, the gap between the two "
            f"teams' summed AURA so far correlates {reference[0]:.2f} with the result (major leagues "
            f"{reference[2]:.2f}). Swaps where the AURA difference doesn't predict even the raw result (r "
            f"{subs['aura_diff'].corr(subs['result'].astype(float)):+.3f}) point to how teams choose substitutes "
            f"(rotations, call-ups in games that matter less); mean surprise in swap games is "
            f"{subs['surprise'].mean():+.3f}.",
        ]
    seasoned = subs[(subs["in_games"] >= 10) & (subs["out_games"] >= 10)]
    lines += _sub_rows(subs, "All swaps")
    lines += _sub_rows(seasoned, "Both players 10+ games")
    lines += _sub_rows(subs[subs["league"].isin(MAJORS)], "Major leagues")
    return lines


def report(cal, bins, frame, weights, weight_year, roster=None, subs=None, reference=None, held=None):
    lines = [
        "### Calibration",
        "",
        f"Fit on every earlier year, scored on each year from {FIRST_TEST_YEAR}. Blue-side log loss is the "
        "baseline that only knows blue's win rate.",
        "",
        "| Snapshot | Games | Log loss | Blue-side log loss | Brier | AUC | ECE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in cal.itertuples():
        lines.append(
            f"| {r.minute} min | {r.games:,} | {r.log_loss:.4f} | {r.blue_ll:.4f} | {r.brier:.4f} | {r.auc:.3f} | {r.ece:.4f} |"
        )
    lines += ["", f"At {aura.MINUTE} minutes, by predicted chance:", "", "| Predicted | Games | Mean predicted | Actual |", "|---|---:|---:|---:|"]
    for b, r in bins.iterrows():
        lines.append(f"| {b * 10}–{b * 10 + 10}% | {int(r.games):,} | {r.predicted:.3f} | {r.actual:.3f} |")

    halves = split_halves(frame)
    pairs = season_pairs(frame)
    stay, moved = pairs[~pairs["moved"]], pairs[pairs["moved"]]
    lines += [
        "",
        "### Player scores",
        "",
        "| Score | Split-half r (95% CI) | Full-season reliability | r with teammates (same game) "
        "| Next season, same team | Next season, new team |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for s in SCORES:
        r = halves[f"{s}_0"].corr(halves[f"{s}_1"])
        lo, hi = correlation_interval(r, len(halves))
        mates = "—" if s == "win" else f"{teammate_r(frame, s):.2f}"
        lines.append(
            f"| {LABELS[s]} | {r:.2f} ({lo:.2f} to {hi:.2f}) | {spearman_brown(r, 2):.2f} | {mates} "
            f"| {stay[s].corr(stay[s + '_next']):.2f} | {moved[s].corr(moved[s + '_next']):.2f} |"
        )
    lines += [
        "",
        f"{len(halves):,} player-seasons with {MIN_HALF_GAMES}+ games in each half; {len(stay):,} same-team and "
        f"{len(moved):,} new-team pairs of consecutive seasons with {MIN_SEASON_GAMES}+ games (\"team\" is the team "
        "name the player played most for that year).",
        "",
        f"{LABELS[CHOSEN]} against the others (paired bootstrap, 95% interval):",
        "",
        "| Against | Split-half r | Next season, new team |",
        "|---|---|---|",
    ]
    for s in SCORES:
        if s == CHOSEN:
            continue
        d_half = paired_correlation_bootstrap(
            (halves[f"{CHOSEN}_0"], halves[f"{CHOSEN}_1"]), (halves[f"{s}_0"], halves[f"{s}_1"])
        )
        d_move = paired_correlation_bootstrap(
            (moved[CHOSEN], moved[CHOSEN + "_next"]), (moved[s], moved[s + "_next"])
        )
        fmt = lambda d: f"{d[0]:+.3f} ({d[1]:+.3f} to {d[2]:+.3f})"
        lines.append(f"| {LABELS[s]} | {fmt(d_half)} | {fmt(d_move)} |")

    if held is not None:
        lines += held_out_section(held)
    if roster is not None:
        lines += roster_section(roster)
    if subs is not None:
        lines += substitution_section(subs, reference)
    lines += [
        "",
        f"### {weight_year} weights at {aura.MINUTE} minutes",
        "",
        "Log-odds per unit of the lane gap (own minus lane opponent). The stats overlap (kills and deaths "
        "move gold), so a single weight is not the stat's whole value.",
        "",
        "| Role | " + " | ".join(aura.STATS) + " |",
        "|---|" + "---:|" * len(aura.STATS),
    ]
    for role, w in weights.items():
        lines.append(f"| {role} | " + " | ".join(f"{v:.4f}" for v in w) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="Also write the report to this Markdown file")
    args = parser.parse_args()

    print("Loading player-games...")
    players = aura.load_aura_games()
    print("Calibration...")
    cal, bins = calibration(players)
    print("Player scores...")
    scores = all_scores(players)
    frame = score_frame(scores)
    print("Held-out check...")
    held = held_out(players)
    print("Roster test...")
    glory = None
    try:
        from evaluate_season_stats import glory_stats  # scripts/ is on the path when run as a script
        from prometheus.ranking import load_glory_games
        from prometheus.season import get_record, load_season_games

        glory = glory_stats(load_glory_games(), get_record(load_season_games()))["glory"]
    except ImportError:
        print("GLORY halves unavailable; roster test without GLORY.")
    roster = roster_table(frame, glory)
    print("Substitution test...")
    with_side = scores.join(players[["side"]])
    subs = substitutions(with_side, get_pregame_elos("game_length"))
    r_all, n_all = pregame_gap_r(with_side)
    r_major, _ = pregame_gap_r(with_side, MAJORS)
    games = aura.game_frame(players)
    counts = games["year"].value_counts()
    weight_year = int(counts[counts >= 1000].index.max())  # the newest full year
    _, weights = aura.fit_aura_weights(games[games["year"] == weight_year])
    text = f"## AURA report ({datetime.date.today().isoformat()})\n\n" + report(cal, bins, frame, weights, weight_year, roster, subs, (r_all, n_all, r_major), held)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
