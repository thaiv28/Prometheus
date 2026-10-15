"""Native forecast checks for saved single-offset replays; no new fitting grid."""

import argparse
import time
from pathlib import Path

import elo_tempo_surprise as tempo
import elo_tempo_validation as validation
import elo_variants as ev
import numpy as np
import pandas as pd


def transfer_attribution(losses):
    """Descriptive roster slices, not causal attribution or a new selection grid."""
    players = pd.read_sql(
        """SELECT p.gameid,p.playerid,m.date,e.home_league AS home
        FROM match_players p JOIN matches m ON p.gameid=m.gameid AND p.teamid=m.teamid
        JOIN game_length_elo e ON p.gameid=e.gameid AND p.teamid=e.teamid
        ORDER BY m.date,m.gameid""",
        ev.get_engine(),
    )
    players["appearances"] = players.groupby("playerid").cumcount()
    previous = players.groupby("playerid").home.shift()
    moves = players.home.notna() & previous.notna() & (players.home != previous)
    last = players.appearances.where(moves).groupby(players.playerid).ffill()
    players["recent_move"] = (players.appearances - last).between(0, 9)
    players["rookie"] = players.appearances < 25
    flags = players.groupby("gameid")[["recent_move", "rookie"]].any()
    key = ("Within other leagues", "Elo")
    ids, base = losses["baseline"][key]
    _, candidate = losses["recalibrated_fixed"][key]
    f = flags.reindex(ids).fillna(False)
    labels = np.where(
        f.recent_move,
        "Recent home-league move",
        np.where(f.rookie, "Rookie, no recent move", "Neither"),
    )
    delta = candidate - base
    lines = [
        "## Other-league regression: roster slices",
        "",
        "Descriptive only: either team has a starter within 10 appearances of a known home-league change; "
        "otherwise a starter with fewer than 25 prior appearances; otherwise neither. Groups are disjoint. "
        "Homes and rosters are the actual game's, from the baseline DB. This includes promotions/home relabelling as well as transfers. "
        "It cannot establish which mechanism caused the regression or identify a remedy.",
        "",
        "| Slice | Games | Mean Δ LL | Sum of Δ LL |",
        "|---|---:|---:|---:|",
    ]
    for label in ("Recent home-league move", "Rookie, no recent move", "Neither"):
        keep = labels == label
        lines.append(
            f"| {label} | {int(keep.sum())} | {delta[keep].mean():+.6f} | {delta[keep].sum():+.3f} |"
        )
    return lines + [""]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replays", type=Path, default=Path("data/learned_offsets/replays.pkl")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/learned_offsets_guards.md")
    )
    args = parser.parse_args()
    started = time.perf_counter()
    artifacts = pd.read_pickle(args.replays)
    inputs = ev.load_inputs()
    years = sorted(y for y in inputs.frame.year.unique() if y >= 2022)
    baseline = None
    lines = [
        "# Single-offset replay: native forecast checks",
        "",
        "The saved full replays use the same raw games/rosters, current player update rules and duration curve. "
        "This runner checks downstream domestic, international, cross-league and other-league effects, including refitted Form/FORGE. "
        "It uses existing native out-of-year curves and Form fitting, not the separate earlier-event cross-region scale. "
        "Thus it tests rating-table effects, not proof that a scaled candidate passes every production gate. "
        "No production DB/weights changed. Previously viewed data; this is not a prospective confirmation.",
        "",
    ]
    exported = {}
    for name, artifact in artifacts.items():
        print(f"Native checks {name}", flush=True)
        pre = artifact["records"].set_index(["gameid", "teamid"]).pre_match_elo
        scores = tempo.all_scores(inputs, pre, years)
        exported[name] = scores
        if name == "baseline":
            baseline = scores
            continue
        for key, (ids, _) in scores.items():
            np.testing.assert_array_equal(ids, baseline[key][0])
        lines += [
            f"## {name}",
            "",
            validation.HEADER,
            tempo.comparison(baseline, scores),
            "",
            "Paired dependence sensitivity: team-pair/day clusters.",
            "",
            validation.clustered_comparison(inputs, baseline, scores),
            "",
        ]
    pd.to_pickle(exported, args.replays.parent / "native_losses.pkl")
    lines += transfer_attribution(exported)
    lines += [f"Runtime: {time.perf_counter() - started:.2f} s.", ""]
    args.out.write_text("\n".join(lines))
    print(f"Wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
