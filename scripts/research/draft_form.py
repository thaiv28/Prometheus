"""Frozen protocol (2026-10-17), before scoring: one v2 augmentation with three
player-comfort features summed blue minus red: log1p exponentially decayed
champion games; log1p days since last champion game capped at 365 (unseen=365);
champion share of all player's exponentially decayed games (denominator n+5).
Choose decay half-life from {30,90,180} days on 2020 log loss after fitting 2019
only, then freeze it for every 2021..2026 test year. Models fit 2019..Y-1.
All history excludes the entire current UTC day. Primary candidate-v2 paired
series bootstrap on same games, required league/year/pre-2025 slices. No result
above Elo variant (exploratory-only in handoff), no further variant selection.
Research only; v2 selection already viewed 2025-26.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_walkforward as dw

EXTRA = ["decayed_exp", "recency", "share"]
HALF_LIVES = (30, 90, 180)


def comfort(rows, half_life):
    """Causal daily state, preserving row order and seeing no same-day updates."""
    rows = rows.copy()
    output = np.zeros((len(rows), 3))
    # Iterate per player, batching a whole UTC day before updating champion state.
    for _, player in rows.groupby("playerid", sort=False):
        counts, last = {}, {}
        total, previous = 0.0, None
        for day, block in player.groupby("day", sort=True):
            if previous is not None:
                decay = 2 ** (-(day - previous).days / half_life)
                total *= decay
                counts = {c: n * decay for c, n in counts.items()}
            for idx, champ in zip(block.index, block.champion):
                n = counts.get(champ, 0.0)
                gap = min((day - last[champ]).days, 365) if champ in last else 365
                output[idx] = [np.log1p(n), np.log1p(gap), n / (total + 5)]
            for champ, count in block.champion.value_counts().items():
                counts[champ] = counts.get(champ, 0.0) + count
                last[champ] = day
            total += len(block)
            previous = day
    rows[EXTRA] = output
    return rows


def aggregate(rows):
    teams = rows.groupby(["gameid", "side"])[EXTRA].sum()
    return (
        teams.xs("Blue", level="side") - teams.xs("Red", level="side")
    ).reset_index()


def choose_half_life(games_by_half):
    """Selection is explicitly restricted to fit/development years <=2020."""
    cols = ["forge_logit", *dw.FEATURES, *EXTRA]
    losses = {}
    for half, games in games_by_half.items():
        model = dw._fit(games[games.year == 2019], cols)
        dev = games[games.year == 2020]
        p = model.predict_proba(dev[cols].to_numpy())[:, 1]
        losses[half] = float(dw.game_losses(p, dev.won)["log_loss"].mean())
    return min(losses, key=losses.get), losses


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


def report(scored, coef, half, losses, seconds):
    lines = [
        "# Draft player-on-champion recency",
        "",
        "Protocol fixed in `scripts/research/draft_form.py`. "
        "Three half-lives compared only on 2020 (fit 2019); one augmentation scored on test years. "
        "Candidate minus v2, 95% league/day/team-pair series bootstrap; negative favours recency.",
        "",
        f"Selected half-life: {half} days. 2020 development log losses: "
        + ", ".join(f"{k}d {v:.6f}" for k, v in losses.items())
        + ".",
        "",
        "| Slice | Games | v2 LL | Candidate LL | Difference (95%) |",
        "|---|---:|---:|---:|---|",
    ]
    groups = [*dw.slices(scored), ("before 2025", scored[scored.year < 2025])]
    groups += [(str(y), scored[scored.year == y]) for y in dw.TEST_YEARS]
    for name, frame in groups:
        if frame.empty:
            continue
        a, b, d, lo, hi = dw.paired(frame, "candidate", "v2")
        lines.append(
            f"| {name} | {len(frame):,} | {b:.6f} | {a:.6f} | {d:+.6f} ({lo:+.6f} to {hi:+.6f}) |"
        )
    lines += [
        "",
        "## Added-feature coefficients",
        "",
        "| Test year | " + " | ".join(EXTRA) + " |",
        "|---|" + "---:|" * len(EXTRA),
    ]
    for year, values in coef.items():
        lines.append(
            f"| {year} | " + " | ".join(f"{values[c]:+.5f}" for c in EXTRA) + " |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "Professional games only; this does not measure practice or solo queue. "
        "The three correlated features are assessed jointly, not individually selected after test scoring. "
        "Unseen champions use capped 365-day recency; inactivity decays both numerator and denominator. "
        "No result-above-Elo exploratory candidate was tried. All periods retrospective; 2025-26 were "
        "viewed for v2 selection, and production-call weights are not vintage artifacts. "
        "No production metric, weights or site changed.",
        "",
        f"Feature construction and scoring: {seconds:.1f} s (bootstrap reporting excluded); no production-build work or CI job added.",
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
    rows = dw.load_rows().reset_index(drop=True)
    variants = {}
    for half in HALF_LIVES:
        print(f"comfort half-life {half}", flush=True)
        variants[half] = games.merge(aggregate(comfort(rows, half)), on="gameid")
    half, losses = choose_half_life(variants)
    variants[half].to_pickle(dw.CACHE / "form_games.pkl")
    scored, coef = score(variants[half])
    scored.to_pickle(dw.CACHE / "form_scored.pkl")
    text = report(scored, coef, half, losses, time.monotonic() - start)
    (dw.ROOT / "docs/research/draft_form.md").write_text(text)
    print(text, flush=True)


if __name__ == "__main__":
    main()
