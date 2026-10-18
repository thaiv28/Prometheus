"""
cand_objectives.py: objective counts on top of gold in the live map model.

v1 (`prometheus/live/time_model_v1.json`) calls the blue team's map chance from
the estimated clock, both teams' gold and pre-series Elo. v2 (3x the maps) and
v3 (time-varying weights) tied it (`docs/research/time_model_v2.md`,
`time_model_v3.md`). The live service already receives towers, dragons, barons,
inhibitors and kills from the same Riot feed, so this tests whether those
counts add to gold. Fixed protocol, declared before scoring the test:

- **Data and split.** `train_time_model_v2.partitions()` unchanged: train through
  2024, calibrate January-June 2025, test July 2025 on (feed maps only), clock
  cut to the minutes every partition covers. Each feed row's objective counts
  come from the same feed sample (`objective_rows` repeats `feed_rows`' filter
  and clock in the same order, so row i of it is feed row i of `partitions`'
  data (its feed rows come first, index 0 on); the script stops unless the
  counts match and every row's game id and seconds agree. One map's frozen clock
  repeats a (game, seconds) pair, so a key join would not do.
- **gol.gg rows.** The gol.gg training rows carry no objective counts, so the
  candidate and a refit baseline are both trained on the feed rows of the
  training years only (2024 feed maps); the calibration and test rows are
  already feed-only. The refit baseline uses v1's six features on exactly the
  candidate's rows, so candidate minus baseline isolates the objective inputs.
- **Primary candidate.** v1's six features plus, as blue minus red, towers,
  dragons, barons, inhibitors, kills and a dragon-soul flag (4 or more dragons,
  +1 blue / -1 red / 0), each as x and x * time (time = seconds / 1200, as v1):
  18 columns. **Secondary (labeled, declared now):** v1's six plus towers,
  dragons and barons only, x and x * time: 12 columns. No other variants.
- **Fit.** `train_time_model.fit`: standardized, L2 with C=1, each map weighted
  equally, then v1's calibration layer fit on the calibration partition. No
  tuning after the test is scored.
- **Scoring.** Test rows within v1's supported clock. Per-map log loss,
  candidate minus v1 and candidate minus refit baseline, 95% intervals from the
  paired series bootstrap (`train_time_model.delta`, 2,000 draws, seed 42).
  Slices: minutes 0-10/10-20/20-30/30+; Major league/International/Other.
- **Adoption.** The primary candidate is adopted only when candidate minus v1 on
  all test maps has a 95% interval below zero. The secondary variant and the
  baseline comparison are reported for reading, not for adoption.

    PYTHONPATH=$PWD python scripts/research/cand_objectives.py \\
        --feed data/feed_timelines --report docs/research/cand_objectives.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import (
    INTERNATIONAL,
    MAJORS,
    V1,
    calls,
    ci,
    clock,
    partitions,
    when,
)

from prometheus.live.timeline import FEATURES

ROOT = Path(__file__).resolve().parents[2]
STATS = ("towers", "dragons", "barons", "inhibitors", "kills")
SOUL = 4  # elemental dragons for a soul
PRIMARY = ["towers", "dragons", "barons", "inhibitors", "kills", "soul"]
SECONDARY = ["towers", "dragons", "barons"]


def objective_values(blue, red):
    """Blue minus red counts for one sample, plus the soul flag (+1/-1/0)."""
    out = {k: int(blue[k]) - int(red[k]) for k in STATS}
    out["soul"] = int(blue["dragons"] >= SOUL) - int(red["dragons"] >= SOUL)
    return out


def objective_rows(joined):
    """One row per feed sample that `feed_rows` keeps: game id, seconds and the
    objective differences (same clock and filter as `feed_rows`)."""
    rows = []
    for m in joined:
        seconds = clock(m["samples"], when(m["start"]))
        for s, sec in zip(m["samples"], seconds):
            if sec is None or sec < 0 or s["state"] != "in_game":
                continue
            bg, rg = s["blue"]["gold"], s["red"]["gold"]
            if not bg or not rg or bg <= 0 or rg <= 0:
                continue
            rows.append(
                {
                    "game_id": m["oe_gameid"],
                    "seconds": sec,
                    **objective_values(s["blue"], s["red"]),
                }
            )
    return pd.DataFrame(rows)


def attach(part, objectives, n_feed):
    """`part` (feed rows of `partitions`' data, original index) with objective
    columns: row i of `objectives` is feed row i, checked on game id and seconds."""
    if len(objectives) != n_feed or not part.index.isin(range(n_feed)).all():
        raise ValueError("objective rows do not match the feed rows")
    extra = objectives.loc[part.index]
    if not (
        (extra.game_id.to_numpy() == part.game_id.to_numpy()).all()
        and (extra.seconds.to_numpy() == part.seconds.to_numpy()).all()
    ):
        raise ValueError("objective rows do not match the partition")
    return pd.concat([part, extra.drop(columns=["game_id", "seconds"])], axis=1)


def add_columns(data, names):
    """x and x * time for each objective name; returns the new column names."""
    cols = []
    for name in names:
        data[f"obj_{name}"] = data[name].astype(float)
        data[f"obj_{name}_time"] = data[name].astype(float) * data["time"]
        cols += [f"obj_{name}", f"obj_{name}_time"]
    return cols


def tier(league):
    if league in INTERNATIONAL:
        return "International"
    return "Major league" if league in MAJORS else "Other"


SLICES = (("0–10", 0, 600), ("10–20", 600, 1200), ("20–30", 1200, 1800))


def slices(shared):
    out = [
        (
            f"Minutes {label}",
            ((shared.seconds >= lo) & (shared.seconds < hi)).to_numpy(),
        )
        for label, lo, hi in SLICES + (("30+", 1800, 1e9),)
    ]
    t = shared.league.map(tier)
    return out + [
        (name, (t == name).to_numpy())
        for name in ("Major league", "International", "Other")
    ]


def table(shared, p, control, control_name, name):
    lines = [
        f"| Slice | Maps | {control_name} LL | {name} LL | {name} − {control_name} |",
        "|---|---|---|---|---|",
        f"| All | {shared.game_id.nunique():,} | {metrics(shared, control)['log_loss']:.4f} | "
        f"{metrics(shared, p)['log_loss']:.4f} | {ci(delta(shared, p, control))} |",
    ]
    for label, mask in slices(shared):
        part = shared[mask]
        if part.game_id.nunique() >= 30:
            lines.append(
                f"| {label} | {part.game_id.nunique():,} | {metrics(part, control[mask])['log_loss']:.4f} | "
                f"{metrics(part, p[mask])['log_loss']:.4f} | {ci(delta(part, p[mask], control[mask]))} |"
            )
    return lines


def run(args):
    parts = partitions(args.feed, args.gol)
    objectives = objective_rows(parts["joined"])
    train = parts["train"][parts["train"].source == "feed"]
    n_feed = int((parts["data"].source == "feed").sum())
    train, calibration, test = (
        attach(p, objectives, n_feed)
        for p in (train, parts["calibration"], parts["test"])
    )
    primary = FEATURES + add_columns(train, PRIMARY)
    secondary = (
        FEATURES
        + [f"obj_{n}" for n in SECONDARY]
        + [f"obj_{n}_time" for n in SECONDARY]
    )
    for p in (calibration, test):
        add_columns(p, PRIMARY)

    v1 = json.loads(V1.read_text())
    shared = test[(test.seconds <= v1["supported_seconds"][1]).to_numpy()].copy()
    p1 = calls(v1, shared)
    fits = {
        "baseline": FEATURES,
        "primary": primary,
        "secondary": secondary,
    }
    p = {
        k: score(fit(train, calibration, cols), shared, cols)
        for k, cols in fits.items()
    }
    main_delta = delta(shared, p["primary"], p1)
    adopt = main_delta["interval"][1] < 0

    fitted = fit(train, calibration, primary)
    scaler, base, _ = fitted
    raw = base.coef_[0] / scaler.scale_

    lines = [
        "# Live map model candidate: objectives on top of gold",
        "",
        f"Generated by `scripts/research/cand_objectives.py` on {date.today().isoformat()}. "
        "v2's split (`train_time_model_v2.partitions`), training on its feed rows only (the gol.gg rows "
        f"carry no objectives): train {train.game_id.nunique():,} maps (2024 feed), "
        f"calibrate {calibration.game_id.nunique():,}, test {shared.game_id.nunique():,} "
        f"(rows within v1's 0–{v1['supported_seconds'][1] // 60} minutes). "
        "Primary: v1's six features plus blue − red towers, dragons, barons, inhibitors, kills and a "
        "dragon-soul flag, each as x and x·time (18 columns). Secondary: towers, dragons and barons only "
        "(12 columns). Baseline: v1's six features refit on the same rows. C=1, map weights, v1's calibration.",
        "",
        "Log loss per map (each map's rows weighted equally); negative differences are better; "
        "95% intervals resample whole series.",
        "",
        "## Primary against v1",
        "",
        *table(shared, p["primary"], p1, "v1", "Primary"),
        "",
        f"**Statistical threshold met: {'yes' if adopt else 'no'}; not shipped** (rule: primary − v1 on all maps, interval below zero).",
        "",
        "## Primary against the refit baseline (same rows, v1's features)",
        "",
        *table(shared, p["primary"], p["baseline"], "Baseline", "Primary"),
        "",
        "## Secondary (towers, dragons, barons) against the refit baseline",
        "",
        *table(shared, p["secondary"], p["baseline"], "Baseline", "Secondary"),
        "",
        "## Secondary against v1",
        "",
        *table(shared, p["secondary"], p1, "v1", "Secondary"),
        "",
        "## Refit baseline against v1",
        "",
        *table(shared, p["baseline"], p1, "v1", "Baseline"),
        "",
        "## Calibration on the test",
        "",
        "Expected calibration error, 10 bins, map-weighted (`train_time_model.metrics`).",
        "",
        "| Model | ECE |",
        "|---|---|",
        f"| v1 | {metrics(shared, p1)['ece10']:.4f} |",
        *(
            f"| {k.capitalize()} | {metrics(shared, p[k])['ece10']:.4f} |"
            for k in ("baseline", "primary", "secondary")
        ),
        "",
        "## Primary weights",
        "",
        "Log-odds per unit before calibration (one more tower, dragon, … for blue), "
        "at the start and at 10, 20 and 30 minutes (x + x·time).",
        "",
        "| Input | 0 min | 10 min | 20 min | 30 min |",
        "|---|---|---|---|---|",
    ]
    index = {c: i for i, c in enumerate(primary)}
    for name in PRIMARY:
        a, b = raw[index[f"obj_{name}"]], raw[index[f"obj_{name}_time"]]
        lines.append(
            f"| {name} | "
            + " | ".join(f"{a + b * m * 60 / 1200:+.3f}" for m in (0, 10, 20, 30))
            + " |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Trained on the 2024 feed maps only (the gol.gg rows have no objective counts); the 2025 H2 "
        "test outcomes were seen in the v2 and v3 runs, though nothing here was tuned on them.",
        "- The adoption rule covers the primary set; the secondary set is a declared reading, not a second test.",
        "- Weights are not causal: towers come out slightly negative early because their value is already in gold.",
        "- Feed counts as saved by `feed_timelines.py` (dragons is the length of the feed's dragon list; "
        "inhibitors count destroyed so far, including respawned ones). Retrospective only; "
        "not yet run on the live service's own 10-second frames.",
    ]
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
