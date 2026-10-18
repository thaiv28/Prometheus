"""
cand_map_elo.py: the live map model with Elo from just before each map.

v1 (`prometheus/live/time_model_v1.json`) takes Elo from before the series, as
the live page has it (no rating updates between maps). The series-checkpoint
research (`docs/research/series_checkpoint.md`) found about half of the series
lead's effect is Elo moving after each map. This tests putting that movement into
the in-game model. Fixed protocol, declared before scoring the test:

- **Data and split.** `train_time_model_v2.partitions` unchanged: train through
  2024, calibrate January-June 2025, test July 2025 on (feed maps only). Rows
  are joined on the Oracle's Elixir game id (`game_id`) to that map's
  `game_length_elo.pre_match_elo` for the blue and red team (OE sides). Rows of
  a map without both values are dropped from every fit and score alike.
- **Primary candidate.** v1's six features (`timeline.features`) with the
  per-map Elo (`pre_match_elo`) in place of pre-series Elo, refit with
  `train_time_model.fit` (C=1, each map weighted equally, calibration on 2025
  H1).
- **Secondary variant (declared up front).** What the live service could
  compute itself: pre-series Elo plus, for each finished map of the series, the
  team-level `elo.calculate_game_length_elo_change` (default parameters) from
  the running ratings, that map's result and game length, zero-sum. It omits the
  player-level parts of the rating (provisional and away factors, rookie
  discount, roster changes, league offsets at international events); how far it
  is from `pre_match_elo` is reported.
- **Controls.** v1 as shipped, and a refit baseline: the same fit on the same
  rows with pre-series Elo, which isolates the input.
- **Report.** Test log loss per map, paired series bootstrap (`delta`): each
  variant minus v1 and minus the refit baseline; slices minutes 0-10/10-20/
  20-30/30+, Major league/International/Other (v2's MAJORS/INTERNATIONAL), and
  map 1 vs maps 2+ (map number in the OE series).
- **Adoption.** The primary candidate is adopted when its all-maps test log
  loss minus v1's has a 95% interval below zero. The secondary is reported for
  production feasibility; it is held to the same rule. No tuning after viewing
  the test.

    PYTHONPATH=. python scripts/research/cand_map_elo.py \\
        --feed data/feed_timelines --report docs/research/cand_map_elo.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import INTERNATIONAL, MAJORS, V1, calls, ci, partitions

from prometheus.elo import calculate_game_length_elo_change
from prometheus.live.timeline import FEATURES, features

ROOT = Path(__file__).resolve().parents[2]


def service_elo(g, change=calculate_game_length_elo_change):
    """{(gameid, teamname): (own, opp)}: pre-series Elo plus each earlier map's
    team-level update in the same series (what the live service could apply).

    `g` has one row per team-game with gameid, teamname, series (per team),
    elo_pre, opp_elo_pre, gamelength and result; rows in time order.
    """
    out = {}
    for _, rows in g.groupby("series", sort=False):
        own = opp = None
        for r in rows.itertuples():
            if own is None:
                own, opp = float(r.elo_pre), float(r.opp_elo_pre)
            out[(r.gameid, r.teamname)] = (own, opp)
            d = change(
                elo=own,
                opponent_elo=opp,
                game_length=int(r.gamelength),
                result=int(r.result),
            )
            own, opp = own + d, opp - d
    return out


def map_table(g):
    """Per OE game: blue/red per-map Elo, service Elo, map number in the series."""
    g = g.dropna(subset=["elo_pre", "opp_elo_pre"])
    svc = service_elo(g)
    blue = g[g.side == "Blue"].drop_duplicates("gameid")
    table = pd.DataFrame(
        {
            "game_id": blue.gameid.to_numpy(),
            "map_blue": blue.elo_pre.to_numpy(dtype=float),
            "map_red": blue.opp_elo_pre.to_numpy(dtype=float),
            "k": blue.k.to_numpy(dtype=int),
        }
    )
    pairs = [svc[(r.gameid, r.teamname)] for r in blue.itertuples()]
    table["svc_blue"] = [p[0] for p in pairs]
    table["svc_red"] = [p[1] for p in pairs]
    return table.set_index("game_id")


def with_elo(data, blue, red, prefix):
    """Add v1's feature columns under `prefix` from the given Elo columns."""
    x = np.array(
        [
            features(float(s), float(bg), float(rg), float(be), float(re))
            for s, bg, rg, be, re in zip(
                data.seconds, data.blue_gold, data.red_gold, data[blue], data[red]
            )
        ]
    )
    names = [f"{prefix}{n}" for n in FEATURES]
    for i, name in enumerate(names):
        data[name] = x[:, i]
    return names


def tier(league):
    if league in INTERNATIONAL:
        return "International"
    return "Major league" if league in MAJORS else "Other"


def run(args):
    parts = partitions(args.feed, args.gol)
    table = map_table(parts["g"])
    frames = {}
    dropped = {}
    for name in ("train", "calibration", "test"):
        d = parts[name].join(table, on="game_id")
        ok = d[["map_blue", "map_red", "svc_blue", "svc_red"]].notna().all(axis=1)
        dropped[name] = int(d.loc[~ok, "game_id"].nunique())
        frames[name] = d[ok].copy()
    train, calibration, test = frames["train"], frames["calibration"], frames["test"]

    # Input diagnostics (no outcomes): the pre-series Elo the rows carry, against
    # per-map Elo, and the service's update against per-map Elo, on maps 2+.
    maps = pd.concat(frames.values()).drop_duplicates("game_id")
    gap = lambda a, b: (maps[a] - maps[b]).to_numpy()
    later = (maps.k > 1).to_numpy()
    pre_vs_map = np.abs(gap("blue_elo", "red_elo") - gap("map_blue", "map_red"))
    svc_vs_map = np.abs(gap("svc_blue", "svc_red") - gap("map_blue", "map_red"))
    gol_first = maps[(maps.source == "gol") & (maps.k == 1)]
    gol_later = maps[(maps.source == "gol") & (maps.k > 1)]

    cols = {}
    for key, (b, r) in {
        "base": ("blue_elo", "red_elo"),
        "map": ("map_blue", "map_red"),
        "svc": ("svc_blue", "svc_red"),
    }.items():
        for d in (train, calibration, test):
            cols[key] = with_elo(d, b, r, f"{key}_")
    p = {}
    for key, names in cols.items():
        p[key] = score(fit(train, calibration, names), test, names)

    v1 = json.loads(V1.read_text())
    in_v1 = (test.seconds <= v1["supported_seconds"][1]).to_numpy()
    shared = test[in_v1]
    p = {k: v[in_v1] for k, v in p.items()}
    p["v1"] = calls(v1, shared)

    head = delta(shared, p["map"], p["v1"])
    adopt = head["interval"][1] < 0
    svc_head = delta(shared, p["svc"], p["v1"])

    tiers = shared.league.map(tier)
    slices = [("All", np.ones(len(shared), bool))]
    slices += [
        (
            f"Minutes {label}",
            ((shared.seconds >= lo) & (shared.seconds < hi)).to_numpy(),
        )
        for label, lo, hi in (
            ("0–10", 0, 600),
            ("10–20", 600, 1200),
            ("20–30", 1200, 1800),
            ("30+", 1800, 1e9),
        )
    ]
    slices += [
        (name, (tiers == name).to_numpy())
        for name in ("Major league", "International", "Other")
    ]
    slices += [
        ("Map 1", (shared.k == 1).to_numpy()),
        ("Maps 2+", (shared.k > 1).to_numpy()),
    ]

    def table_rows(key):
        out = []
        for label, mask in slices:
            part = shared[mask]
            if part.game_id.nunique() < 30:
                continue
            out.append(
                f"| {label} | {part.game_id.nunique():,} | "
                f"{metrics(part, p['v1'][mask])['log_loss']:.4f} | "
                f"{metrics(part, p['base'][mask])['log_loss']:.4f} | "
                f"{metrics(part, p[key][mask])['log_loss']:.4f} | "
                f"{ci(delta(part, p[key][mask], p['v1'][mask]))} | "
                f"{ci(delta(part, p[key][mask], p['base'][mask]))} |"
            )
        return out

    header = [
        "| Slice | Maps | v1 LL | Baseline LL | Candidate LL | − v1 | − baseline |",
        "|---|---|---|---|---|---|---|",
    ]
    lines = [
        "# Live map model with Elo from before each map",
        "",
        f"Generated by `scripts/research/cand_map_elo.py` on {date.today().isoformat()}. "
        "v2's data and split (`docs/research/time_model_v2.md`): "
        f"train {train.game_id.nunique():,} maps, calibrate {calibration.game_id.nunique():,}, "
        f"test {test.game_id.nunique():,} (dropped without per-map Elo: "
        f"{', '.join(f'{k} {v}' for k, v in dropped.items())}). "
        "v1's six features, C=1, map weights, v1's calibration layer. "
        "Baseline: the same refit with pre-series Elo. Log loss per map, negative is better; "
        "95% intervals resample whole series.",
        "",
        "## Inputs",
        "",
        f"Maps 2+ ({later.sum():,} of {len(maps):,} maps): Elo gap, pre-series minus per-map, "
        f"median absolute {np.median(pre_vs_map[later]):.1f} points "
        f"(90th percentile {np.percentile(pre_vs_map[later], 90):.1f}). "
        "Service update minus per-map: median absolute "
        f"{np.median(svc_vs_map[later]):.2f} points (90th percentile "
        f"{np.percentile(svc_vs_map[later], 90):.2f}; within 1 point "
        f"{np.mean(svc_vs_map[later] <= 1):.0%}).",
        "",
        "gol.gg rows (train only) carry the gol dataset's Elo; its gap equals the per-map "
        f"gap within 0.01 on {np.mean(np.abs((gol_later.blue_elo - gol_later.red_elo) - (gol_later.map_blue - gol_later.map_red)) < 0.01):.0%} "
        f"of its maps 2+ ({len(gol_later):,}) and "
        f"{np.mean(np.abs((gol_first.blue_elo - gol_first.red_elo) - (gol_first.map_blue - gol_first.map_red)) < 0.01):.0%} "
        f"of its maps 1 ({len(gol_first):,}).",
        "",
        "## Primary: per-map Elo (`pre_match_elo`)",
        "",
        *header,
        *table_rows("map"),
        "",
        f"**Adopted: {'yes' if adopt else 'no'}** (rule: candidate − v1, all maps, "
        f"95% interval below zero; {ci(head)}).",
        "",
        "## Secondary: pre-series Elo plus the service's own update after each map",
        "",
        *header,
        *table_rows("svc"),
        "",
        f"Same rule: {'met' if svc_head['interval'][1] < 0 else 'not met'} ({ci(svc_head)}).",
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
