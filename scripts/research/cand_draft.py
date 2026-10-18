"""
cand_draft.py: does the draft add to the in-game map model, and for how long?

v1 (`prometheus/live/time_model_v1.json`) calls blue's map from the estimated
clock, both teams' gold and pre-series Elo. v2 and v3 tied it; the draft score
(`draft_score.py`) helps the pre-match call. This adds the draft's log-odds shift
to v1's six features. Fixed protocol, declared before scoring the test:

- **Data and split.** `train_time_model_v2.partitions()` unchanged: train
  through 2024, calibrate January-June 2025, test July 2025 on (feed maps only).
- **Draft shift.** Per Oracle's Elixir game: the draft model's log-odds minus
  its Elo-only base's log-odds (`draft_score.evaluate`, the definition used
  against Kalshi). Features from strictly earlier games (`draft_score`'s
  cumulative sums exclude the game itself; the 60-day meta window is closed on
  the left). Weights fit on `draft_score.FIT` (2019-2023) only, never on the
  calibration or test periods; the frozen `draft_model_v1.json` (fit through
  2026-10-11, overlapping the test) is not used.
  - **Primary:** `shift_both`, the frozen model's columns (Elo, exp,
    champ_wae, champ_gd15, meta, matchup, synergy), refit on 2019-2023.
  - **Secondary (labeled, not for adoption):** `shift`, round one's four
    draft features only (chosen before any test was viewed; matchup and
    synergy were kept after the pre-match 2025-26 test was seen).
- **Coverage.** A map without a shift (not all ten champions, or no
  game-length Elo for a team, in Oracle's Elixir) is dropped from every
  model's rows in every partition (candidate, refit baseline and v1 alike);
  counts are reported, with the reason from the DB.
- **Model.** v1's features plus `draft` and `draft_time` (draft times v1's
  `time`, seconds / 1200), `train_time_model.fit` (standardized, C=1, each map
  weighted equally, v1's calibration). The refit baseline is the same fit on
  the same rows with v1's six features.
- **Scoring.** Test rows within v1's range. Candidate - v1 and candidate -
  refit baseline, `train_time_model.delta` (per-map log loss, paired series
  bootstrap, 2,000 draws, seed 42); slices minutes 0-10/10-20/20-30/30+ and
  Major league/International/Other (v2's tiers).
- **Adoption.** The primary candidate replaces v1 when candidate - v1 on all
  test maps has a 95% interval below zero. No tuning after the test is viewed.

    uv run python scripts/research/cand_draft.py --feed data/feed_timelines \\
        --report docs/research/cand_draft.md
"""

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_score as ds
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import INTERNATIONAL, MAJORS, V1, calls, ci, partitions

from prometheus.live.timeline import FEATURES

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = FEATURES + ["draft", "draft_time"]
PRIMARY, SECONDARY = "shift_both", "shift"
# Added after the test was viewed (diagnostic, not for adoption): the primary
# shift without its intercept and Elo terms.
DRAFT_ONLY = "draft_only"
LABELS = {
    PRIMARY: "draft + matchup + synergy",
    SECONDARY: "draft (round one)",
    DRAFT_ONLY: "draft + matchup + synergy, draft terms only",
}
MINUTES = (("0–10", 0, 600), ("10–20", 600, 1200), ("20–30", 1200, 1800))
MINUTES += (("30+", 1800, 1e9),)


NOTES = (
    "Matchup and synergy (in the primary shift) were kept after draft_score.py's "
    "pre-match 2025–26 test, which overlaps this test; the round-one shift, chosen "
    "before that, does not meet the rule on its own.",
    "Maps dropped for missing champions are mostly LPL (Oracle's Elixir lacks "
    "champion rows for many LPL games: 418 of 959 from July 2025 in this DB), so "
    "the LPL is under-represented in every partition.",
    "The live service does not compute the draft: Riot's window has each player's "
    "`championId` in `gameMetadata` (kept by `feed.py` as `participant_metadata`) "
    "from about 30 s into the game; a live input needs champion ids mapped to "
    "Oracle's Elixir names, feed players mapped to OE player ids, and each "
    "player's and champion's history read from the DB before the map.",
    "The saved feed timelines have no champions, so this joins the shift by OE "
    "game id; picks as the feed reports them are untested.",
)


def draft_shifts():
    """Per OE game: date and both shifts, weights fit on draft_score.FIT."""
    games = ds.all_games()
    scored, _, coefs = ds.evaluate(games)
    scored[DRAFT_ONLY] = draft_terms(scored, coefs["draft+both"])
    out = scored.set_index("gameid")[["date", PRIMARY, SECONDARY, DRAFT_ONLY]]
    return out, coefs, len(games)


def draft_terms(frame, coef):
    """The draft features' part of a model's log-odds (no intercept, no Elo)."""
    names = [k for k in coef if k not in ("intercept", "elo_logit")]
    return sum(coef[k] * frame[k] for k in names)


def drop_reasons(gameids, db=ds.DB_PATH):
    """Why each OE game has no shift: counts of 'no game-length Elo' (fewer than
    two teams rated) and 'fewer than ten champions'; Elo is checked first."""
    ids = sorted(set(gameids))
    out = {"no game-length Elo": 0, "fewer than ten champions": 0, "other": 0}
    if not ids:
        return out
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        conn.execute("CREATE TEMP TABLE ids (gameid TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO ids VALUES (?)", [(i,) for i in ids])
        elo = dict(
            conn.execute(
                "SELECT i.gameid, COUNT(e.teamid) FROM ids i LEFT JOIN game_length_elo e"
                " ON e.gameid = i.gameid GROUP BY i.gameid"
            ).fetchall()
        )
        champs = dict(
            conn.execute(
                "SELECT i.gameid, COUNT(p.champion) FROM ids i LEFT JOIN player_stats p"
                " ON p.gameid = i.gameid AND p.champion IS NOT NULL AND p.champion != ''"
                " GROUP BY i.gameid"
            ).fetchall()
        )
    for i in ids:
        if elo.get(i, 0) < 2:
            out["no game-length Elo"] += 1
        elif champs.get(i, 0) < 10:
            out["fewer than ten champions"] += 1
        else:
            out["other"] += 1
    return out


def add_draft(frame, shifts, column):
    """`frame`'s rows that have a shift, with `draft` and `draft_time` added."""
    s = shifts[column]
    kept = frame[frame["game_id"].isin(s.index)].copy()
    kept["draft"] = kept["game_id"].map(s).to_numpy(dtype=float)
    kept["draft_time"] = kept["draft"] * kept["time"]
    return kept


def draft_weight(fitted, columns, seconds):
    """Log-odds per unit of draft shift at `seconds`, before calibration."""
    scaler, base, _ = fitted
    raw = dict(zip(columns, base.coef_[0] / scaler.scale_))
    return raw["draft"] + raw["draft_time"] * seconds / 1200


def tier(league):
    if league in INTERNATIONAL:
        return "International"
    return "Major league" if league in MAJORS else "Other"


def slices(shared):
    out = [("All", np.ones(len(shared), bool))]
    out += [
        (
            f"Minutes {label}",
            ((shared.seconds >= lo) & (shared.seconds < hi)).to_numpy(),
        )
        for label, lo, hi in MINUTES
    ]
    tiers = shared.league.map(tier)
    out += [
        (name, (tiers == name).to_numpy())
        for name in ("Major league", "International", "Other")
    ]
    return out


def evaluate(parts, shifts, column, v1):
    """Fit candidate and refit baseline on maps with a shift; score the test."""
    train, calibration, test = (
        add_draft(parts[k], shifts, column) for k in ("train", "calibration", "test")
    )
    cand = fit(train, calibration, COLUMNS)
    refit = fit(train, calibration, FEATURES)
    shared = test[(test.seconds <= v1["supported_seconds"][1]).to_numpy()]
    p = {
        "cand": score(cand, shared, COLUMNS),
        "refit": score(refit, shared, FEATURES),
        "v1": calls(v1, shared),
    }
    rows = []
    for label, mask in slices(shared):
        part = shared[mask]
        if part.game_id.nunique() < 30:
            continue
        ll = {k: metrics(part, v[mask])["log_loss"] for k, v in p.items()}
        rows.append(
            {
                "slice": label,
                "maps": part.game_id.nunique(),
                **ll,
                "vs_v1": delta(part, p["cand"][mask], p["v1"][mask]),
                "vs_refit": delta(part, p["cand"][mask], p["refit"][mask]),
            }
        )
    return {
        "rows": rows,
        "fitted": cand,
        "maps": [x.game_id.nunique() for x in (train, calibration, test)],
        "shared": shared,
    }


def run(args):
    parts = partitions(args.feed, args.gol)
    shifts, coefs, n_games = draft_shifts()
    v1 = json.loads(V1.read_text())
    results = {
        c: evaluate(parts, shifts, c, v1) for c in (PRIMARY, SECONDARY, DRAFT_ONLY)
    }
    primary = results[PRIMARY]
    adopt = primary["rows"][0]["vs_v1"]["interval"][1] < 0

    names = ("Train (to 2024)", "Calibrate (2025 H1)", "Test (2025 H2 on)")
    keys = ("train", "calibration", "test")
    lines = [
        "# Live map model: draft shift as an in-game input",
        "",
        f"Generated by `scripts/research/cand_draft.py` on {date.today().isoformat()}. "
        "Protocol in the script's docstring (fixed before scoring). v2's split "
        "(`train_time_model_v2.partitions`); v1's six features plus the draft shift "
        "and the shift times v1's time (seconds / 1200), C=1, map weights, v1's "
        "calibration.",
        "",
        f"Draft shift: the draft model's log-odds minus its Elo-only base, weights fit on "
        f"{ds.FIT[0]}–{ds.FIT[1]} Oracle's Elixir games only (`draft_score.evaluate`; "
        f"{n_games:,} games with all ten champions and both Elos); the frozen "
        "`draft_model_v1.json` (fit through 2026-10-11) is not used.",
        "",
        "| Partition | Maps | With a shift | Dropped (no shift) | Why dropped |",
        "|---|---|---|---|---|",
    ]
    for name, key, kept in zip(names, keys, primary["maps"]):
        ids = set(parts[key].game_id)
        why = drop_reasons(ids - set(shifts.index))
        why = ", ".join(f"{k} {v:,}" for k, v in why.items() if v)
        lines.append(
            f"| {name} | {len(ids):,} | {kept:,} | {len(ids) - kept:,} | {why} |"
        )
    shift_sd = shifts.loc[
        shifts.index.intersection(primary["shared"].game_id.unique())
    ].std()
    lines += [
        "",
        "Test-map standard deviation of the shift: "
        + ", ".join(
            f"{LABELS[c]} {shift_sd[c]:.3f}" for c in (PRIMARY, SECONDARY, DRAFT_ONLY)
        )
        + " log-odds.",
    ]
    roles = {
        PRIMARY: "Primary",
        SECONDARY: "Secondary (declared, not for adoption)",
        DRAFT_ONLY: "Diagnostic added after viewing the test (not for adoption)",
    }
    for column in (PRIMARY, SECONDARY, DRAFT_ONLY):
        res = results[column]
        role = roles[column]
        lines += [
            "",
            f"## {role}: {LABELS[column]}",
            "",
            "Log loss per map (each map's rows weighted equally) on test rows within "
            "v1's range; negative is better; 95% intervals resample whole series. "
            "Refit: v1's six features fit on the same rows."
            + (
                " The primary shift contains the fitted draft model's own intercept"
                " and Elo terms (its Elo weight differs from the base's); this one"
                " keeps only the draft features' terms, to check the gain is the"
                " draft's."
                if column == DRAFT_ONLY
                else ""
            ),
            "",
            "| Slice | Maps | v1 LL | Refit LL | Candidate LL | Candidate − v1 "
            "| Candidate − refit |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in res["rows"]:
            lines.append(
                f"| {r['slice']} | {r['maps']:,} | {r['v1']:.4f} | {r['refit']:.4f} "
                f"| {r['cand']:.4f} | {ci(r['vs_v1'])} | {ci(r['vs_refit'])} |"
            )
        lines += [
            "",
            "Weight on the shift (log-odds per log-odds of shift, before calibration): "
            + ", ".join(
                f"{m} min {draft_weight(res['fitted'], COLUMNS, m * 60):+.2f}"
                for m in (0, 10, 20, 30, 40)
            )
            + ".",
        ]
    lines += [
        "",
        f"**Adoption rule met: {'yes' if adopt else 'no'}** (primary candidate − v1 on "
        "all maps, interval below zero). Shipping also needs the draft computed live "
        "(not built).",
        "",
        "## Draft weights (fit 2019–2023)",
        "",
        "| Model | " + " | ".join(["intercept", *ds.FROZEN_COLS]) + " |",
        "|---|" + "---:|" * (1 + len(ds.FROZEN_COLS)),
    ]
    for name in ("base", "draft", "draft+both"):
        c = coefs[name]
        cells = [c.get(k) for k in ["intercept", *ds.FROZEN_COLS]]
        lines.append(
            f"| {name} | "
            + " | ".join("" if v is None else f"{v:+.3f}" for v in cells)
            + " |"
        )
    lines += ["", "## Limits", "", *(f"- {n}" for n in NOTES)]
    text = "\n".join(lines) + "\n"
    if args.report:
        args.report.write_text(text)
    print(text)
    return adopt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, default=ROOT / "data" / "feed_timelines")
    parser.add_argument("--gol", type=Path, default=ROOT / "data" / "gol_training")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
