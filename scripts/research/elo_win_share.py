"""elo_win_share.py: individual in-game credit in player-built Elo.

Fixed before held-out scoring: gold, XP, CS and equal gold+XP z-score at 15/20m,
plus AURA (earlier_only=True); lambda 0/.025/.05/.10. Role scaling uses strictly
prior calendar years (at least 100 observations per role); no current-year fit.
Tune games-weighted domestic + within-other Elo loss through 2021, as
elo_new_players.py. Select once, then report 2022+ with refitted out-of-year
Elo/FORGE curves and Form weights using the existing harness. No DB writes.

w = max(0, .2 + lambda * result_sign * (z - team_mean)), normalized.
Both complete five-player sides are required; otherwise the whole game falls
back to equal shares. At lambda=0 replay is exactly published. The engine
renormalizes after published rookie/away multipliers to preserve their total
move; with identical multipliers m this is (m * raw_change) * 5 * w.

Usage: VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_win_share.py --out docs/research/elo_win_share.md
"""

import argparse
import datetime
import functools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_new_players as enp
import elo_variants as ev
import evaluate_metrics as em

from prometheus import aura, elo
from prometheus.evaluation import (
    game_losses,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.player_tables import PlayerTables

LAMBDAS = (0.025, 0.05, 0.10)
SIGNALS = tuple(f"{s}_{m}" for m in (15, 20) for s in ("gold", "xp", "cs", "combo")) + (
    "aura",
)


def standardize_prior(players, values):
    """Role means/SD from earlier years only; first/thin years fall back."""
    out = pd.Series(np.nan, index=players.index)
    for year in sorted(players.year.unique()):
        prior = players.year < year
        stats = (
            values[prior]
            .groupby(players.loc[prior, "position"])
            .agg(["mean", "std", "count"])
        )
        rows = players.year == year
        roles = players.loc[rows, "position"]
        mean = roles.map(stats["mean"])
        scale = roles.map(stats["std"]).where(roles.map(stats["count"]) >= 100)
        out.loc[rows] = (values[rows].to_numpy() - mean.to_numpy()) / scale.replace(
            0, np.nan
        ).to_numpy()
    return out


def signal_values(players):
    out = {}
    for m in (15, 20):
        for s in ("gold", "xp", "cs"):
            out[f"{s}_{m}"] = standardize_prior(players, players[f"{s}_{m}"])
        combo = (out[f"gold_{m}"] + out[f"xp_{m}"]) / 2
        # Both components already role-standardized with prior data.
        out[f"combo_{m}"] = combo
    out["aura"] = standardize_prior(
        players, aura.get_aura(players, earlier_only=True)["aura"]
    )
    return out


def make_shares(players, values, strength):
    """Return complete game shares and eligible game IDs; never partial imputation."""
    frame = players[["gameid", "teamid", "playerid", "position", "result"]].copy()
    frame["z"] = values
    frame = frame[np.isfinite(frame.z)]
    sides = frame.groupby(["gameid", "teamid"])
    valid = (
        (sides.playerid.transform("size") == 5)
        & (sides.playerid.transform("nunique") == 5)
        & (sides.position.transform("nunique") == 5)
    )
    full = frame[valid].copy()
    games = full.groupby("gameid")
    full = full[
        (games.playerid.transform("size") == 10)
        & (games.playerid.transform("nunique") == 10)
    ].copy()
    centered = full.z - full.groupby(["gameid", "teamid"]).z.transform("mean")
    full["w"] = (0.2 + strength * (2 * full.result - 1) * centered).clip(lower=0)
    full["w"] /= full.groupby(["gameid", "teamid"]).w.transform("sum")
    shares = {}
    for row in full.itertuples():
        shares.setdefault((row.gameid, row.teamid), {})[row.playerid] = row.w
    return shares, set(full.gameid)


def roster_flags(inputs):
    previous, seen = {}, set()
    changed, formed = set(), set()
    for row in inputs.games.itertuples():
        for team in (row.teamid, row.opponent_teamid):
            roster = frozenset(inputs.rosters.get((row.gameid, team), ()))
            if team in previous and roster != previous[team]:
                changed.add(row.gameid)
            if team not in previous and roster & seen:
                formed.add(row.gameid)
            previous[team] = roster
        for team in (row.teamid, row.opponent_teamid):
            seen.update(inputs.rosters.get((row.gameid, team), ()))
    return changed, formed


def losses(inputs, pairs, pre, years):
    scores = ev.score(inputs, pre, years=years)
    out = {}
    for metric, title in [("elo_live", "Elo"), ("forge", "FORGE")]:
        for section in ev.TEST_SETS:
            mask = scores.mask(section)
            out[f"{title}, {section.lower()}"] = (
                scores.games[mask],
                scores.log_loss(metric, section),
            )
    for label, fn in [
        ("Elo, other leagues", enp.other_losses),
        ("FORGE, other leagues", enp.other_forge_losses),
        ("Elo, cross-league", enp.cross_losses),
    ]:
        out[label] = (
            fn(inputs, pairs, pre, years) if "FORGE" in label else fn(pairs, pre, years)
        )
    return out


def comparison(lines, base, variant, selected=None):
    lines += [
        "| Section | Games | Published loss | Variant loss | Δ log loss (95% CI) |",
        "|---|---:|---:|---:|---|",
    ]
    for label, (games, b) in base.items():
        vg, v = variant[label]
        assert games.gameid.tolist() == vg.gameid.tolist()
        mask = (
            np.ones(len(b), dtype=bool)
            if selected is None
            else games.gameid.isin(selected).to_numpy()
        )
        if mask.any():
            lines.append(
                f"| {label} | {mask.sum():,} | {b[mask].mean():.5f} | {v[mask].mean():.5f} | {enp._delta(v[mask], b[mask])} |"
            )


def player_records(inputs, shares=None):
    games = inputs.games[ev.ELO_COLUMNS].copy()
    games["gamelength"] = ev.winner_scores(inputs, ev.game_length_margin())
    return elo.compute_elo_records(
        games,
        functools.partial(ev.margin_elo_change, K=20),
        rosters=inputs.rosters,
        player_records=True,
        win_share=shares,
    )[2]


def move_check(players, base, variant, lines):
    """Frozen individual rating at transfer vs new team's subsequent results.

    One row per transfer/future game. Fit separate curves out of year, as the
    harness does. Bootstrap mean losses per move so repeated outcomes within a
    move are not independent. This is predictive association, not causal credit.
    """
    meta = players[["gameid", "teamid", "playerid", "date", "year", "result"]]
    b = meta.merge(base, on=["gameid", "teamid", "playerid"]).sort_values(
        ["date", "gameid"]
    )
    v = variant.set_index(["gameid", "teamid", "playerid"]).pre_match_elo
    b["variant"] = v.reindex(
        pd.MultiIndex.from_frame(b[["gameid", "teamid", "playerid"]])
    ).to_numpy()
    # Opponent strength in that game from the other team's starters.
    team = (
        b.groupby(["gameid", "teamid"])
        .pre_match_elo.mean()
        .rename("team_elo")
        .reset_index()
    )
    opp = team.merge(team, on="gameid", suffixes=("", "_opp"))
    opp = opp[opp.teamid != opp.teamid_opp].set_index(["gameid", "teamid"]).team_elo_opp
    games = b.drop_duplicates(["gameid", "teamid"])
    timelines = {
        t: g.reset_index(drop=True) for t, g in games.groupby("teamid", sort=False)
    }
    present = set(zip(b.gameid, b.teamid, b.playerid))
    previous, events = {}, []
    for row in b.itertuples():
        old = previous.get(row.playerid)
        previous[row.playerid] = row.teamid
        if old is None or old == row.teamid:
            continue
        future = timelines[row.teamid]
        idx = future.index[future.gameid == row.gameid][0]
        for j, game in enumerate(future.iloc[idx : idx + 20].itertuples(), 1):
            # Stop at a subsequent departure by this player, rather than crediting a team they left.
            if (game.gameid, row.teamid, row.playerid) not in present:
                break
            events.append(
                (
                    f"{row.gameid}:{row.playerid}",
                    row.year,
                    j,
                    game.result,
                    row.pre_match_elo - opp.loc[(game.gameid, row.teamid)],
                    row.variant - opp.loc[(game.gameid, row.teamid)],
                )
            )
    f = pd.DataFrame(events, columns=["move", "year", "n", "won", "equal", "share"])
    lines += [
        "\n### Player transfer check\n",
        "Frozen individual pre-game rating at the move minus the published opponent rating predicts the destination team’s first 10/20 games while the player remains. Separate out-of-year curves on 2022+; paired bootstrap over move-average losses. Players may move repeatedly; this is an association check, with overlapping team outcomes, not an independent causal test.\n",
        "| Window | Moves | Player-games | Δ log loss (95% CI) |",
        "|---|---:|---:|---|",
    ]
    for window in (10, 20):
        sample = f[(f.year > 2021) & (f.n <= window)].reset_index(drop=True)
        ll = {}
        for name in ("equal", "share"):
            ll[name] = game_losses(
                out_of_year_probabilities(sample, name), sample.won
            ).log_loss
        aggregate = pd.DataFrame(ll).groupby(sample.move).mean()
        lines.append(
            f"| {window} | {len(aggregate):,} | {len(sample):,} | {enp._delta(aggregate.share, aggregate.equal)} |"
        )


def spread(players, base, variant, lines):
    meta = players[["gameid", "teamid", "playerid", "position", "year", "date"]]
    last = players.sort_values(["date", "gameid"]).drop_duplicates(
        ["teamid", "year", "position"], keep="last"
    )
    # All five must be from the same final game, not five different season-end starters.
    final_games = last.sort_values(["date", "gameid"]).drop_duplicates(
        ["teamid", "year"], keep="last"
    )[["gameid", "teamid"]]
    lines += [
        "\n### Season-end teammate spread\n",
        "Last actual lineup per team/calendar year, 2022+. Deviations from that lineup’s mean (offset cancels); role means and SD expose rating drift, including inherited transfer differences.\n",
        "| Role | Lineups | Equal mean | Share mean | Equal SD | Share SD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    frames = []
    for records in (base, variant):
        f = meta.merge(records, on=["gameid", "teamid", "playerid"]).merge(
            final_games, on=["gameid", "teamid"]
        )
        f = f[f.year > 2021].copy()
        f["dev"] = f.post_match_elo - f.groupby(
            ["gameid", "teamid"]
        ).post_match_elo.transform("mean")
        frames.append(f)
    for role in aura.ROLES:
        b, v = [f[f.position == role].dev for f in frames]
        lines.append(
            f"| {role} | {len(b):,} | {b.mean():+.2f} | {v.mean():+.2f} | {b.std():.2f} | {v.std():.2f} |"
        )
    for name, f in zip(("Equal", "Share"), frames):
        ranges = f.groupby(["gameid", "teamid"]).post_match_elo.agg(
            lambda x: x.max() - x.min()
        )
        lines.append(
            f"\n{name}: median teammate range {ranges.median():.2f}, 90th percentile {ranges.quantile(0.9):.2f} Elo."
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("docs/research/elo_win_share.md"))
    args = ap.parse_args()
    inputs = ev.load_inputs()
    pairs = em.load_pair_games()
    base, reproduction = ev.reproduction_check(inputs)
    # Use current-code baseline even if DB classification was older.
    t = time.perf_counter()
    base = ev.replay(inputs, ev.game_length_margin())
    baseline_seconds = time.perf_counter() - t
    print(reproduction, flush=True)
    tables = PlayerTables(stats=aura.STATS, minutes=aura.MINUTES)
    players = aura.load_aura_games(tables=tables)
    print(f"Loaded {len(players):,} snapshot player rows", flush=True)
    values = signal_values(players)
    years = sorted(inputs.frame.year.unique())
    train, test = [y for y in years if y <= 2021], [y for y in years if y > 2021]
    base_obj = enp.objective(inputs, pairs, base, train)
    best = (base_obj, "equal", 0)
    best_nonzero = (float("inf"), None, None)
    tuning, times, coverage = [], [], {}
    for signal in SIGNALS:
        for strength in LAMBDAS:
            shares, eligible = make_shares(players, values[signal], strength)
            coverage[signal] = eligible
            t = time.perf_counter()
            pre = ev.replay(inputs, ev.game_length_margin(), win_share=shares)
            times.append(time.perf_counter() - t)
            objective = enp.objective(inputs, pairs, pre, train)
            row = (objective, signal, strength)
            tuning.append(row)
            if objective < best[0]:
                best = row
            if objective < best_nonzero[0]:
                best_nonzero = row
            print(
                f"{signal} lambda={strength}: {objective:.7f}; replay {times[-1]:.2f}s",
                flush=True,
            )
    # Never inspect held-out alternatives after this selection.
    objective, signal, strength = best
    shares = (
        None if signal == "equal" else make_shares(players, values[signal], strength)[0]
    )
    pre = (
        base
        if shares is None
        else ev.replay(inputs, ev.game_length_margin(), win_share=shares)
    )
    lines = [
        f"# Player Elo win share ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/elo_win_share.py`. Research only; no published defaults, DB or fitted weight files changed.\n",
        "## Fixed protocol\n",
        __doc__.split("Usage:")[0].strip() + "\n",
        "Training uses seasons ≤2021; held out 2022–2026 (partial final year). This is retrospective: prior experiments have viewed these years. Harness curves use other years within the requested split, not strictly earlier years; AURA and contribution scaling alone use strictly earlier years. Paired intervals resample games unless stated otherwise; they do not correct for correlated series or prior research.\n",
        "## Reproduction and runtime\n",
        reproduction + "\n",
        f"Published replay {baseline_seconds:.2f}s; share replay median {np.median(times):.2f}s, range {min(times):.2f}–{max(times):.2f}s ({len(inputs.games):,} games). Offline only; no CI/build job added.\n",
        "## Tuning\n",
        f"Equal control: {base_obj:.7f}. Selected **{signal}, λ={strength}**, objective {objective:.7f}. Best nonzero (training only): {best_nonzero}.\n",
        "| Signal | λ | Training objective |",
        "|---|---:|---:|",
    ]
    lines += [f"| {s} | {l} | {o:.7f} |" for o, s, l in tuning]
    print(f"Selected {best}; scoring held out", flush=True)
    b_losses, v_losses = (
        losses(inputs, pairs, base, test),
        losses(inputs, pairs, pre, test),
    )
    lines += ["\n## Held out: selected configuration\n"]
    comparison(lines, b_losses, v_losses)
    changed, formed = roster_flags(inputs)
    for title, mask in [
        (
            "Roster change or formed from experienced players (primary)",
            changed | formed,
        ),
        ("Roster changed since previous game", changed),
        ("New team with experienced players", formed),
        (
            "No immediate roster change (history can still differ)",
            set(inputs.games.gameid) - changed - formed,
        ),
    ]:
        lines += [f"\n### {title}\n"]
        comparison(lines, b_losses, v_losses, mask)
    bp = player_records(inputs)
    vp = bp if shares is None else player_records(inputs, shares)
    # All roster rows, including games missing snapshot data, for diagnostics.
    all_players = tables.roster.merge(tables.matches, on=["gameid", "teamid"])
    spread(all_players, bp, vp, lines)
    print("Transfer check", flush=True)
    move_check(all_players, bp, vp, lines)
    lines += [
        "\n## Coverage\n",
        "Eligible complete ten-player games after prior-year scaling. Denominator: every Elo replay game; all other games use equal shares. DB snapshot ingestion already excludes partial games, so coverage is not raw-field availability alone.\n",
    ]
    for col in ("year", "league"):
        lines += [
            f"\n### By {col}\n",
            "| Group | Games | " + " | ".join(SIGNALS) + " |",
            "|---|---:|" + "---:|" * len(SIGNALS),
        ]
        for key, group in inputs.games.groupby(col, sort=True):
            cells = [f"{group.gameid.isin(coverage[s]).mean():.1%}" for s in SIGNALS]
            lines.append(f"| {key} | {len(group):,} | " + " | ".join(cells) + " |")
    lines += [
        "\n## Interpretation and limits\n",
        "The fixed-roster invariance claim needs qualification: published provisional and away multipliers differ across starters. Renormalizing the weighted steps preserves each update’s baseline total at the same pre-game state. Across a full replay, transfers, league-average rookie starts and international offsets propagate differences even into games without an immediate roster change. Role-specific earlier-year scales prevent scale differences alone from allocating all credit to one role; season-end role drift is reported rather than assumed absent.\n",
        "Shares use match result to orient credit, not the sign of Elo change: a heavy favorite can lose Elo in a long win. Clipping prevents reversing a player’s underlying move. AURA uses its earlier-only snapshot fits, with the existing late-snapshot fallback; no same-year AURA weights enter the updates. Contribution data from the current match affects only subsequent predictions.\n",
    ]
    # Derive verdict from the seven standard sections and the primary slice, with no hand-selected alternatives.
    results = []
    target = []
    for label, (g, b) in b_losses.items():
        v = v_losses[label][1]
        results.append(paired_bootstrap(v, b))
        mask = g.gameid.isin(changed | formed).to_numpy()
        target.append(paired_bootstrap(v[mask], b[mask]))
    gain = any(r[2] < 0 for r in results)
    target_gain = any(r[2] < 0 for r in target)
    harm = any(r[1] > 0 for r in results)
    verdict = (
        "ITERATE offline: the standard forecast significant-gain/no-significant-harm gate passes. "
        + (
            "The primary roster-change slice also improves. "
            if target_gain
            else "No primary roster-change section improves significantly. "
        )
        + "The player-transfer check must support individual-credit attribution before adoption; "
        "investigate persistent cross-league effects separately. Keep published equal shares."
        if gain and not harm
        else "DROP this fixed design: it does not clear the standard forecast significant-gain/no-significant-harm rule; keep published equal shares."
    )
    lines.append(verdict)
    args.out.write_text("\n".join(lines) + "\n")
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
