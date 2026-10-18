"""Fixed protocol, written before test scoring (2026-10-17).

One primary candidate: v2 plus patch_meta, local_meta, priority; no tuning or
variant search. Patch meta = (current-patch WAE + .5 previous-patch WAE) /
(current count + .5 previous count + 50), champion-role, earlier UTC days only.
Previous patch means the numeric predecessor observed BEFORE the day, not a
future vocabulary. local_meta is a 60-day champion-role WAE in the same league,
shrink 50. Priority is current plus half previous patch's historical pick+ban
count for the picked champion, divided by similarly weighted maps + 20.
Missing patches/bans fall back to zero. All five roles summed blue-minus-red.
Keep v2's original four features. Fit 2019..Y-1 and test Y=2021..2026 using the
same logistic settings and games as v2; bootstrap whole series via v2.paired.
Report patch first three observed calendar days separately. These are historical
OE patch labels, not verified game-day publication times. 2025-26 already viewed
in choosing v2; earlier test years reported independently. Research only.
"""

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import draft_walkforward as dw

EXTRA = ["patch_meta", "local_meta", "priority"]


def raw_metadata():
    """Read only patch/bans, retaining team rows, in bounded chunks."""
    parts = []
    cols = ["gameid", "position", "patch", *[f"ban{i}" for i in range(1, 6)]]
    for path in sorted((ROOT / "data" / "raw").glob("*.csv")):
        for chunk in pd.read_csv(path, usecols=cols, dtype=str, chunksize=100000):
            chunk = chunk[chunk["position"] == "team"].copy()
            parts.append(chunk)
    teams = pd.concat(parts, ignore_index=True)
    patch = teams.groupby("gameid")["patch"].first().rename("patch")
    bans = teams.melt(id_vars="gameid", value_vars=cols[3:], value_name="champion")
    bans = bans.dropna(subset=["champion"])[["gameid", "champion"]]
    return patch, bans


def _patch_key(value):
    try:
        return tuple(int(x) for x in str(value).split("."))
    except ValueError:
        return None


def features(rows, patch, bans):
    """Read a day's state, then update it; same-day outcomes never enter."""
    rows = rows.merge(patch, on="gameid", how="left")
    local = (
        rows.groupby(["champion", "position", "league", "day"])[["wae", "one"]]
        .sum()
        .reset_index()
    )
    parts = []
    for _, group in local.groupby(["champion", "position", "league"], sort=False):
        group = group.sort_values("day").set_index("day")
        sums = group[["wae", "one"]].rolling("60D", closed="left").sum().fillna(0)
        parts.append(
            group[["champion", "position", "league"]].assign(
                local_meta=sums.wae / (sums.one + 50)
            )
        )
    rows = rows.merge(
        pd.concat(parts).reset_index(),
        on=["champion", "position", "league", "day"],
        how="left",
    )
    game_bans = defaultdict(list)
    for gameid, champion in bans.itertuples(index=False, name=None):
        game_bans[gameid].append(champion)
    sums, counts, popularity, maps = (
        defaultdict(float),
        defaultdict(float),
        defaultdict(float),
        defaultdict(float),
    )
    seen, first = set(), {}
    out = []
    for day, group in rows.groupby("day", sort=True):
        current_patches = {_patch_key(p) for p in group.patch.dropna()} - {None}
        available = seen
        for record in group.itertuples():
            p = _patch_key(record.patch)
            previous = max(
                (x for x in available if p is not None and x < p), default=None
            )
            key = (p, record.champion, record.position)
            prev = (previous, record.champion, record.position)
            value = (
                (sums[key] + 0.5 * sums[prev]) / (counts[key] + 0.5 * counts[prev] + 50)
                if p
                else 0
            )
            priority = (
                (
                    popularity[p, record.champion]
                    + 0.5 * popularity[previous, record.champion]
                )
                / (maps[p] + 0.5 * maps[previous] + 20)
                if p
                else 0
            )
            first.setdefault((record.league, p), day)
            early = (day - first[record.league, p]).days < 3 if p else False
            out.append((record.Index, value, priority, early))
        for record in group.itertuples(index=False):
            p = _patch_key(record.patch)
            if p is None:
                continue
            key = (p, record.champion, record.position)
            sums[key] += record.wae
            counts[key] += 1
            popularity[p, record.champion] += 1
        for gameid, game in group.groupby("gameid", sort=False):
            p = _patch_key(game.patch.iloc[0])
            if p is not None:
                maps[p] += 1
                for champion in game_bans[gameid]:
                    popularity[p, champion] += 1
        seen |= current_patches
    values = pd.DataFrame(
        out, columns=["index", "patch_meta", "priority", "early_patch"]
    ).set_index("index")
    return rows.join(values)


def add_game_features(games, rows, names):
    side = rows.groupby(["gameid", "side"])[names].sum().unstack("side")
    for name in names:
        games[name] = games.gameid.map(side[name]["Blue"] - side[name]["Red"])
    return games


def score(games, names):
    parts, coefs = [], []
    for year in dw.TEST_YEARS:
        train = games[games.year.between(dw.FIT_FROM, year - 1)]
        test = games[games.year == year].copy()
        if test.empty:
            continue
        for label, cols in (
            ("v2", ["forge_logit", *dw.FEATURES]),
            ("candidate", ["forge_logit", *dw.FEATURES, *names]),
        ):
            model = dw._fit(train, cols)
            test[label] = model.predict_proba(test[cols].to_numpy())[:, 1]
            if label == "candidate":
                coefs.append(
                    (
                        year,
                        dict(
                            zip(
                                ["intercept", *cols],
                                [model.intercept_[0], *model.coef_[0]],
                            )
                        ),
                    )
                )
        parts.append(test)
    return pd.concat(parts, ignore_index=True), coefs


def report(scored, coefs, elapsed):
    lines = [
        "# Draft meta: fixed walk-forward candidate",
        "",
        __doc__.strip(),
        "",
        f"Feature construction/scoring: {elapsed:.1f} seconds (cached FORGE; bootstrap reporting excluded). One candidate, no exploratory variants.",
        "",
        "| Slice | Games | v2 LL | Candidate LL | Candidate − v2 (series-bootstrap 95%) |",
        "|---|---:|---:|---:|---|",
    ]
    slices = [
        *dw.slices(scored),
        ("before 2025", scored[scored.year < 2025]),
        *[(str(y), scored[scored.year == y]) for y in dw.TEST_YEARS],
    ]
    if "early_patch" in scored:
        slices += [
            ("first three patch days", scored[scored.early_patch]),
            ("later patch days", scored[~scored.early_patch]),
        ]
    for name, frame in slices:
        if frame.empty:
            continue
        a, b, d, lo, hi = dw.paired(frame, "candidate", "v2")
        lines.append(
            f"| {name} | {len(frame):,} | {b:.5f} | {a:.5f} | {d:+.5f} ({lo:+.5f} to {hi:+.5f}) |"
        )
    lines += [
        "",
        "## Fitted added-feature weights",
        "",
        "| Year | " + " | ".join(EXTRA) + " |",
        "|---|" + "---:|" * len(EXTRA),
    ]
    for year, coef in coefs:
        lines.append(
            f"| {year} | " + " | ".join(f"{coef[x]:+.4f}" for x in EXTRA) + " |"
        )
    lines += [
        "",
        "Limits: patch labels are historical OE metadata; publication timing is unverified. Priority uses pick/ban frequency, not within-draft pick order. FORGE upstream weights were fit using years included here. No prospective or trading-edge claim.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/research/draft_meta.md"
    )
    args = parser.parse_args()
    start = time.monotonic()
    print("Loading rows and raw patch/bans", flush=True)
    rows = dw.load_rows()
    patch, bans = raw_metadata()
    rows = features(rows, patch, bans)
    print("Building v2 features", flush=True)
    rows = dw.player_features(rows)
    games = dw.game_table(rows, dw.synergy(rows))
    games = add_game_features(games, rows, EXTRA)
    games["early_patch"] = games.gameid.map(
        rows.groupby("gameid").early_patch.max()
    ).fillna(False)
    games = games.merge(pd.read_pickle(dw.CACHE / "forge.pkl"), on="gameid")
    games["forge_logit"] = dw._logit(games.p_forge)
    games = games[games.year >= dw.FIT_FROM].copy()
    games.to_pickle(ROOT / "data/research/draft_v2/meta_games.pkl")
    print("Scoring frozen candidate", flush=True)
    scored, coefs = score(games, EXTRA)
    target = ROOT / "data/research/draft_meta"
    target.mkdir(parents=True, exist_ok=True)
    scored.to_pickle(target / "scored.pkl")
    args.out.write_text(report(scored, coefs, time.monotonic() - start))
    print(args.out, flush=True)


if __name__ == "__main__":
    main()
