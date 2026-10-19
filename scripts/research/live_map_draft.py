"""Compare draft-v2 trading on the fixed cohort; no network, DB writes or orders.

OE drafts provide a research coverage proxy, NOT live API identity or receipt
availability. Missing/ambiguous map joins retain exact parent blend output.
No hyperparameter, entry rule or sizing is tuned by this comparison.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import live_trading as research

from prometheus import live_map
from prometheus.live import draft, timeline


def candidate_rows(data, db, games):
    model = json.loads(live_map.DRAFT_MODEL.read_text())
    rows, _ = research.prepare(data, db)
    hist = research.el.team_history(
        sorted({n for m in data["maps"] for n in m["teams"]}), db
    )
    elo = research.el.EloBefore(hist)
    predictions, covered = [], 0
    for m in data["maps"]:
        blue, red = [m["teams"][m["blue"]], m["teams"][1 - m["blue"]]]
        start = pd.Timestamp(m["start"]).tz_localize(None)
        hits = games[
            games.blue.eq(blue)
            & games.red.eq(red)
            & (games.date - start).abs().le(pd.Timedelta(minutes=10))
        ]
        if len(hits) != 1:
            continue
        hit = hits.iloc[0]
        if hit.year < 2025:
            raise ValueError("Draft prior must precede every target year")
        covered += 1
        page = research.el.page_for(m, data["fields"]["teams"])
        packet = {
            "status": "ready",
            "ready_at": m["start"],
            "model": draft.fingerprint(model),
            "shift": draft.prior_shift(
                {k: float(hit[k]) for k in draft.FEATURES}, float(hit.p_forge), model
            ),
        }
        ratings = [{"elo": elo(n, m["start"][:10])} for n in m["teams"]]
        if any(r["elo"] is None for r in ratings):
            continue
        _, calls = timeline.timeline_calls(
            page, model, ratings, start=m["start"], draft=packet
        )
        predictions.extend(
            {"game": m["game"], "minute": c["minute"], "candidate": c["p"]}
            for c in calls
        )
    rows = rows.merge(
        pd.DataFrame(predictions),
        on=["game", "minute"],
        how="left",
        validate="one_to_one",
    )
    rows["parent"] = rows.p
    rows["p"] = rows.candidate.fillna(rows.p)
    return rows, covered


def compare(head, base):
    if list(zip(head.game, head.minute)) != list(zip(base.game, base.minute)):
        raise ValueError("Mismatched evaluation rows")

    def loss(p):
        p = np.clip(p, 1e-8, 1 - 1e-8)
        return -(head.won * np.log(p) + (1 - head.won) * np.log(1 - p))

    delta = loss(head.blend) - loss(base.blend)
    maps = (
        head.assign(delta=delta)
        .groupby(["game", "series"], as_index=False)
        .delta.mean()
    )
    result = {
        "map_delta": float(maps.delta.mean()),
        "map_ci": research.cluster_ci(maps, maps.delta),
        "slices": {},
    }
    groups = {
        "early": head.minute.lt(10),
        "mid": head.minute.between(10, 20, inclusive="left"),
        "late": head.minute.ge(20),
    }
    groups.update(
        {str(league): head.league.eq(league) for league in sorted(head.league.unique())}
    )
    for name, mask in groups.items():
        selected = (
            head.loc[mask]
            .assign(delta=delta[mask])
            .groupby(["game", "series"], as_index=False)
            .delta.mean()
        )
        result["slices"][name] = {
            "maps": len(selected),
            "delta": float(selected.delta.mean()),
            "ci": research.cluster_ci(selected, selected.delta),
        }
    result["improvement_gate"] = result["map_ci"][1] < 0 and all(
        s["ci"][0] <= 0 for s in result["slices"].values()
    )
    result["baseline"] = research.summary(research.select(base, window=30))
    result["draft"] = research.summary(research.select(head, window=30))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--games", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--artifact",
        type=Path,
        help="Export a REVIEW candidate even if the improvement gate fails",
    )
    args = parser.parse_args()
    started = time.perf_counter()
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(args.data) != research.PIN:
        raise ValueError("Unrecognized pinned cohort")
    if (
        digest(args.games)
        != json.loads(live_map.DRAFT_MODEL.read_text())["input_sha256"]["games"]
    ):
        raise ValueError("Unrecognized frozen draft feature table")
    games = pd.read_pickle(args.games)
    rows, covered = candidate_rows(research.el.load_data(args.data), args.db, games)
    head, fits = research.walk_forward(rows)
    base, _ = research.walk_forward(rows.assign(p=rows.parent))
    # Production retains the original artifact for absent/ambiguous API drafts.
    head.loc[head.candidate.isna(), "blend"] = base.loc[head.candidate.isna(), "blend"]
    result = compare(head, base)
    result.update(
        {
            "covered_maps": covered,
            "test_maps": head.game.nunique(),
            "test_series": head.series.nunique(),
            "calls": len(head),
            "seconds": time.perf_counter() - started,
            "availability": "OE draft proxy; no measured API coverage or receipts",
        }
    )
    artifact = {
        "version": live_map.VERSION,
        "model_sha256": digest(live_map.DRAFT_MODEL),
        "parent_blend_sha256": digest(live_map.ARTIFACT),
        "input_sha256": digest(args.data),
        "games_sha256": digest(args.games),
        "db_sha256": digest(args.db),
        "market_input": "last_trade",
        "series_shift": False,
        "availability": result["availability"],
        "improvement_gate": result["improvement_gate"],
        "snapshots": fits,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    head.to_pickle(args.out_dir / "rows.pkl")
    (args.out_dir / "comparison.json").write_text(
        json.dumps(result, indent=2, default=float) + "\n"
    )
    if args.artifact:
        args.artifact.write_text(json.dumps(artifact, indent=2, default=float) + "\n")
    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
