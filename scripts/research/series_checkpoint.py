"""
series_checkpoint.py: does the series score help the live model once gold is known?

The live model (`prometheus/live/time_model_v1.json`) calls a map from the clock,
both teams' gold and their Elo from before the series; it ignores the maps already
played. Pre-game, maps of a series are not independent
(`docs/research/series_independence.md`): a map won raises the next map's chance.
This checks whether that survives at Oracle's Elixir's gold checkpoints (0, 10,
15, 20 and 25 minutes), on maps 2 and later of every clean Bo3 and Bo5
(`series_independence.load`).

Two candidates, both scored on 2025-2026 (hard fearless; after the model's
2022-2023 training and 2024 calibration years):

- **Fitted lead.** Log-odds = a * logit(live call) + b * lead, refit per
  checkpoint on 2018-2024 (lead = maps won minus lost before this one).
- **Beta prior.** No fitting: shift the live call's log-odds by the change the
  series model already makes to the pre-game chance (the Beta posterior mean
  with `schedule.SERIES_RHO`), at every checkpoint.

Log-loss changes are per map (maps 2+), against the live call refit with the
same `a` (so recalibration alone isn't counted as a series gain); 95% intervals
resample whole series.

Usage:
    uv run python scripts/research/series_checkpoint.py --out docs/research/series_checkpoint.md
"""

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
from series_independence import DB, ROOT, load

from prometheus.live.timeline import START_GOLD, predict
from prometheus.schedule import SERIES_RHO

MODEL = ROOT / "prometheus" / "live" / "time_model_v1.json"
RAW = ROOT / "data" / "raw"
MINUTES = (0, 10, 15, 20, 25)
FIT_YEARS = (2018, 2024)
TEST_YEARS = (2025, 2026)
SEED = 42
BOOT = 1000


def checkpoint_gold():
    """goldat10..25 for every team-game from the raw Oracle's Elixir files."""
    cols = [
        "gameid",
        "teamid",
        "position",
        "goldat10",
        "goldat15",
        "goldat20",
        "goldat25",
    ]
    frames = []
    for path in sorted(RAW.glob("*_LoL_esports_match_data_from_OraclesElixir.csv")):
        year = int(path.name[:4])
        if year < FIT_YEARS[0]:
            continue
        d = pd.read_csv(path, usecols=cols, low_memory=False)
        frames.append(d[d["position"] == "team"].drop(columns="position"))
    return pd.concat(frames).drop_duplicates(["gameid", "teamid"])


def rows(g, s, gold, model):
    """One row per map and checkpoint: result, lead before it, live call, Beta shift."""
    g = g[g["series"].isin(s.index)].copy()
    first = g.groupby("series").first()
    g["e1"] = g["series"].map(first["elo_pre"])
    g["e2"] = g["series"].map(first["opp_elo_pre"])
    g["won_before"] = g.groupby("series")["result"].cumsum() - g["result"]
    g["lead"] = 2 * g["won_before"] - (g["k"] - 1)
    g = g.merge(gold, on=["gameid", "teamid"], how="left").merge(
        gold.rename(columns=lambda c: c if c == "gameid" else f"opp_{c}"),
        left_on=["gameid", "opp_id"],
        right_on=["gameid", "opp_teamid"],
        how="left",
    )
    g = g.dropna(subset=["e1", "e2", "elo_pre", "opp_elo_pre"])
    g = g.join(s[["major", "bo", "p"]].rename(columns={"p": "p1"}), on="series")

    # The series model's pre-game chance for this map, and its log-odds shift from
    # the pre-series chance (game 1's call), as `live/series.py` updates it.
    rho = np.where(g["major"], SERIES_RHO[True], SERIES_RHO[False])
    kappa = 1 / rho - 1
    p1 = np.clip(g["p1"].to_numpy(dtype=float), 1e-4, 1 - 1e-4)
    post = (p1 * kappa + g["won_before"]) / (kappa + g["k"] - 1)
    g["shift"] = logit(post) - logit(p1)

    out = []
    for minute in MINUTES:
        if minute == 0:
            mine = theirs = np.full(len(g), float(START_GOLD))
        else:
            mine = g[f"goldat{minute}"].to_numpy(dtype=float)
            theirs = g[f"opp_goldat{minute}"].to_numpy(dtype=float)
        ok = np.isfinite(mine) & np.isfinite(theirs) & (mine > 0) & (theirs > 0)
        d = g[ok].copy()
        mine, theirs = mine[ok], theirs[ok]
        blue = (d["side"] == "Blue").to_numpy()
        # q: Elo from before the series (the live page); q_map: from before this map.
        for col, (c1, c2) in {
            "q": ("e1", "e2"),
            "q_map": ("elo_pre", "opp_elo_pre"),
        }.items():
            e1, e2 = d[c1].to_numpy(float), d[c2].to_numpy(float)
            q = np.array(
                [
                    predict(
                        model,
                        minute * 60,
                        *map(float, (a, b, x, y) if bl else (b, a, y, x)),
                    )
                    for a, b, x, y, bl in zip(mine, theirs, e1, e2, blue)
                ]
            )
            d[col] = np.clip(np.where(blue, q, 1 - q), 1e-6, 1 - 1e-6)
        d["gold_diff"] = mine - theirs
        d["minute"] = minute
        out.append(d)
    keep = [
        "series",
        "year",
        "k",
        "result",
        "lead",
        "shift",
        "q",
        "q_map",
        "gold_diff",
        "elo_pre",
        "opp_elo_pre",
        "minute",
        "major",
        "bo",
    ]
    return pd.concat(out)[keep]


def log_loss(p, y):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def fit(X, y):
    return LogisticRegression(C=1e6, max_iter=1000).fit(X, y)


def series_ci(diff, series, rng):
    """Mean of `diff` per map and a 95% interval resampling whole series."""
    by = pd.DataFrame({"d": diff, "s": series}).groupby("s")["d"].agg(["sum", "size"])
    sums, sizes = by["sum"].to_numpy(), by["size"].to_numpy()
    idx = rng.integers(0, len(by), size=(BOOT, len(by)))
    boot = sums[idx].sum(axis=1) / sizes[idx].sum(axis=1)
    return diff.mean(), *np.percentile(boot, [2.5, 97.5])


def evaluate(d, rng, call="q"):
    """Per checkpoint: maps, the fitted lead's coefficient, and both candidates' LL change."""
    out = []
    for minute, m in d.groupby("minute"):
        later = m[m["k"] >= 2]
        train = later[later["year"].between(*FIT_YEARS)]
        test = later[later["year"].between(*TEST_YEARS)]
        if len(train) < 200 or len(test) < 100:
            continue
        x_tr, x_te = logit(train[call]).to_numpy(), logit(test[call]).to_numpy()
        y_tr, y_te = train["result"].to_numpy(), test["result"].to_numpy()
        base = fit(x_tr[:, None], y_tr)
        lead = fit(np.c_[x_tr, train["lead"]], y_tr)
        p_base = base.predict_proba(x_te[:, None])[:, 1]
        p_lead = lead.predict_proba(np.c_[x_te, test["lead"]])[:, 1]
        # The Beta prior moves the raw live call, so it is compared with the raw call.
        p_beta = expit(x_te + test["shift"].to_numpy())
        ll_raw = log_loss(test[call].to_numpy(), y_te)
        coef = []
        groups = train.groupby("series").indices
        keys = list(groups)
        for _ in range(200):
            pick = np.concatenate(
                [groups[keys[i]] for i in rng.integers(0, len(keys), len(keys))]
            )
            coef.append(
                fit(
                    np.c_[x_tr[pick], train["lead"].to_numpy()[pick]], y_tr[pick]
                ).coef_[0][1]
            )
        out.append(
            {
                "minute": minute,
                "train": len(train),
                "test": len(test),
                "lead_coef": lead.coef_[0][1],
                "lead_lo": np.percentile(coef, 2.5),
                "lead_hi": np.percentile(coef, 97.5),
                "ll_raw": ll_raw.mean(),
                "fitted": series_ci(
                    log_loss(p_lead, y_te) - log_loss(p_base, y_te),
                    test["series"].to_numpy(),
                    rng,
                ),
                "beta": series_ci(
                    log_loss(p_beta, y_te) - ll_raw, test["series"].to_numpy(), rng
                ),
            }
        )
    return out


def ci(t, digits=4):
    m, lo, hi = t
    return f"{m:+.{digits}f} ({lo:+.{digits}f} to {hi:+.{digits}f})"


def table(results):
    lines = [
        "| Minute | Maps fit / scored | Lead coefficient (log-odds per map) | Fitted lead, LL change | Beta prior, LL change |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['minute']} | {r['train']:,} / {r['test']:,} | {r['lead_coef']:+.3f} "
            f"({r['lead_lo']:+.3f} to {r['lead_hi']:+.3f}) | {ci(r['fitted'])} | {ci(r['beta'])} |"
        )
    return "\n".join(lines)


def refit_check(d, rng):
    """Is the live model short of data? Its call (Elo from before each map) against a
    gold-diff + Elo-diff logistic refit per checkpoint on every OE map of the fit years."""
    lines = [
        "| Teams | Minute | Maps fit / scored | Live call LL | Refit minus live call |",
        "|---|---|---|---|---|",
    ]
    for major in (True, False):
        for minute in MINUTES[1:]:
            m = d[(d["minute"] == minute) & (d["major"] == major)]
            X = np.c_[m["gold_diff"] / 1000, (m["elo_pre"] - m["opp_elo_pre"]) / 100]
            tr = m["year"].between(*FIT_YEARS).to_numpy()
            te = m["year"].between(*TEST_YEARS).to_numpy()
            y = m["result"].to_numpy()[te]
            live = log_loss(m["q_map"].to_numpy()[te], y)
            refit = log_loss(
                fit(X[tr], m["result"].to_numpy()[tr]).predict_proba(X[te])[:, 1], y
            )
            diff = series_ci(refit - live, m["series"].to_numpy()[te], rng)
            lines.append(
                f"| {'Major' if major else 'Other'} | {minute} | {tr.sum():,} / {te.sum():,} | "
                f"{live.mean():.4f} | {ci(diff)} |"
            )
    return "\n".join(lines)


def report(d, slices):
    n_maps = d[d["minute"] == 0]
    parts = [
        "# Series score at gold checkpoints",
        "",
        f"Generated by `scripts/research/series_checkpoint.py` on {date.today().isoformat()}. "
        f"{n_maps['series'].nunique():,} clean Bo3 and Bo5 series, {len(n_maps):,} maps "
        f"({(n_maps['k'] >= 2).sum():,} of them map 2 or later), {FIT_YEARS[0]}–{TEST_YEARS[1]}. "
        "One side per map. The live call is `time_model_v1` with Elo from before the series, "
        "as the live page uses it; 0 minutes is its pre-map call.",
        "",
        f"Fitted on maps 2+ of {FIT_YEARS[0]}–{FIT_YEARS[1]}, scored on maps 2+ of "
        f"{TEST_YEARS[0]}–{TEST_YEARS[1]}. LL change is log loss per map against the live call "
        "(the fitted lead against the live call refit alone; the Beta prior against the raw "
        "call); negative is better. 95% intervals resample whole series. Maps that ended "
        "before a checkpoint drop out of it.",
    ]
    for title, d_slice, call in slices:
        parts += [
            "",
            f"## {title}",
            "",
            table(evaluate(d_slice, np.random.default_rng(SEED), call)),
        ]
    parts += [
        "",
        "## Live model against a checkpoint refit",
        "",
        "All maps (not only map 2+). The live model was fit on 1,778 full timelines; the "
        "refit uses Oracle's Elixir's gold at one checkpoint, gold difference and Elo "
        "difference only. Negative means the refit is better.",
        "",
        refit_check(d, np.random.default_rng(SEED)),
    ]
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    model = json.loads(MODEL.read_text())
    with sqlite3.connect(DB) as con:
        g, s = load(con)
    s = s[s["clean"] & (s["year"] >= FIT_YEARS[0])]
    d = rows(g, s, checkpoint_gold(), model)
    text = report(
        d,
        [
            ("All clean leagues", d, "q"),
            ("Both teams from major leagues", d[d["major"]], "q"),
            ("Other", d[~d["major"]], "q"),
            ("Best of 5", d[d["bo"] == 5], "q"),
            # Elo already moves after each map; is the lead more than that update?
            ("All clean leagues, Elo from before each map", d, "q_map"),
            (
                "Both teams from major leagues, Elo from before each map",
                d[d["major"]],
                "q_map",
            ),
        ],
    )
    if args.out:
        args.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
