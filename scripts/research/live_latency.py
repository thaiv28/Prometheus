"""Offline fixed-rule lag comparison and fight/objective veto; no production change."""

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import live_trading as trading

el = trading.el
FORWARD_START = pd.Timestamp("2026-10-20", tz="UTC")


def before_holdout(data):
    """Exclude forward maps before either fitting or scoring."""
    return {
        **data,
        "maps": [m for m in data["maps"] if pd.Timestamp(m["start"]) < FORWARD_START],
    }


def add_veto(rows, data):
    """Join flags to prepared calls by exact map/source sample identity.

    prepare's arrival is sample source + lag; this avoids rounding two source
    samples onto a shared minute. Compare adjacent original samples, including
    ones excluded by the model or entry filters, resetting at every map.
    For duplicate source timestamps, map_calls selects the last raw sample.
    """
    fields = data["fields"]["teams"]
    kills = fields.index("kills")
    objectives = [
        fields.index(k) for k in ("towers", "inhibitors", "barons", "dragons")
    ]
    flags = []
    for m in data["maps"]:
        previous = None
        for sample in m["samples"]:
            teams = sample["teams"]
            veto = False
            if previous is not None:
                counters = [team[kills] for team in teams + previous]
                kill_change = (
                    all(v is not None for v in counters)
                    and sum(t[kills] for t in teams) - sum(t[kills] for t in previous)
                    >= 2
                )
                objective_change = any(
                    a[k] is not None and b[k] is not None and a[k] != b[k]
                    for a, b in zip(teams, previous)
                    for k in objectives
                )
                veto = bool(kill_change or objective_change)
            flags.append(
                {
                    "game": m["game"],
                    "arrival": pd.Timestamp(m["start"])
                    + pd.Timedelta(seconds=sample["t"])
                    + pd.Timedelta(seconds=data["lag"]),
                    "veto": veto,
                }
            )
            previous = teams
    flags = pd.DataFrame(flags).drop_duplicates(["game", "arrival"], keep="last")
    # Resolve the exact raw sample, then use prepare's game/minute call keys.
    meta = rows[["game", "minute", "arrival"]].merge(
        flags, on=["game", "arrival"], how="left", validate="one_to_one"
    )
    assert meta.veto.notna().all(), "Prepared call has no raw sample"
    return rows.merge(
        meta[["game", "minute", "veto"]], on=["game", "minute"], validate="one_to_one"
    )


def paired(a_data, b_data, a_bets, b_bets):
    """B minus A, $1 all-in per entry; zero for maps without an entry."""
    a = pd.DataFrame(
        [{"game": m["game"], "series": m["series"]} for m in a_data["maps"]]
    )
    b = pd.DataFrame(
        [{"game": m["game"], "series": m["series"]} for m in b_data["maps"]]
    )
    common = a.merge(b, on="game", validate="one_to_one", suffixes=("", "_b"))
    if common.empty:
        raise ValueError("No common maps")
    assert common.series.equals(common.series_b), (
        "Series identity differs across builds"
    )
    for name, bets in (("a", a_bets), ("b", b_bets)):
        profit = pd.Series(
            (bets.win / trading.effective_cost(bets.price) - 1).to_numpy(),
            index=bets.game,
        )
        common[name] = common.game.map(profit).fillna(0)
    common["delta"] = common.b - common.a
    grouped = common.groupby("series").delta.agg(["sum", "count"])
    rng = np.random.default_rng(0)
    draw = rng.integers(0, len(grouped), (2000, len(grouped)))
    means = grouped["sum"].to_numpy()[draw].sum(axis=1) / grouped["count"].to_numpy()[
        draw
    ].sum(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return {
        "maps": len(common),
        "sum": common.delta.sum(),
        "mean": common.delta.mean(),
        "lo": lo,
        "hi": hi,
    }


def describe(bets):
    stats = trading.summary(bets)
    valid = bets[bets.clv.notna()]
    lo, hi = trading.cluster_ci(valid, valid.clv)
    return {
        "bets": stats["bets"],
        "ROI (95% CI)": "—"
        if bets.empty
        else f"{stats['roi']:+.1%} [{stats['lo']:+.1%}, {stats['hi']:+.1%}]",
        "CLV cents (95% CI)": "—"
        if valid.empty
        else f"{100 * valid.clv.mean():+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]",
        "CLV n": len(valid),
    }


def loss(rows):
    p = np.clip(rows.blend, 1e-6, 1 - 1e-6)
    values = -(rows.won * np.log(p) + (1 - rows.won) * np.log1p(-p))
    return rows.assign(loss=values).groupby("game").loss.mean().mean()


def pair_row(label, value):
    return {
        "B − A": label,
        "maps": value["maps"],
        "total profit $": f"{value['sum']:+.3f}",
        "mean $/map (95% CI)": f"{value['mean']:+.4f} [{value['lo']:+.4f}, {value['hi']:+.4f}]",
        "interval includes zero": "yes" if value["lo"] <= 0 <= value["hi"] else "no",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--data-a", type=Path)
    parser.add_argument("--data-b", type=Path)
    parser.add_argument("--data", type=Path, help="veto input; defaults to data-a")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/research/live_latency.md"
    )
    parser.add_argument("--lag-unavailable", default="Lag comparison not requested.")
    args = parser.parse_args(argv)
    if not (args.data or args.data_a):
        parser.error("--data or --data-a is required")
    if args.data_b and not args.data_a:
        parser.error("--data-b requires --data-a")
    cache, provenance = {}, []

    def load(path):
        path = path.resolve()
        if path not in cache:
            raw = el.load_data(path)
            if path == el.DATA.resolve():
                assert all(
                    pd.Timestamp(m["start"]) < FORWARD_START for m in raw["maps"]
                ), "Pinned input extends into forward holdout"
            data = before_holdout(raw)
            assert all(pd.Timestamp(m["start"]) < FORWARD_START for m in data["maps"])
            prepared, skipped = trading.prepare(data, args.db)
            rows, _ = trading.walk_forward(add_veto(prepared, data))
            cache[path] = data, rows
            provenance.append(
                f"`{path.name}`: lag {data['lag']} s; {len(data['maps'])} input maps, {rows.game.nunique()} scored maps, {len(rows)} rows; {skipped} Elo skips; {len(raw['maps']) - len(data['maps'])} forward maps excluded; SHA256 `{hashlib.sha256(path.read_bytes()).hexdigest()}`."
            )
        return cache[path]

    policy_rows, comparisons = [], []
    if args.data_b:
        da, ra = load(args.data_a)
        db, rb = load(args.data_b)
        assert {m["game"] for m in da["maps"]} == {m["game"] for m in db["maps"]}, (
            "Lag builds must contain the same maps"
        )
        for window in (30, 21):
            ba, bb = [
                trading.select(r, forecast="blend", window=window, edge=0.05)
                for r in (ra, rb)
            ]
            for label, data, rows, bets in (("A", da, ra, ba), ("B", db, rb, bb)):
                policy_rows.append(
                    {
                        "policy": f"{label}: lag {data['lag']}s / {window}s window",
                        **describe(bets),
                        "blend log loss": f"{loss(rows):.6f}",
                    }
                )
            comparisons.append(
                pair_row(
                    f"lag {db['lag']} − {da['lag']}s / {window}s window",
                    paired(da, db, ba, bb),
                )
            )
    data, rows = load(args.data or args.data_a)
    if data["lag"] != 21:
        raise ValueError("Veto study requires lag-21 data via --data")
    base = trading.select(rows, forecast="blend", window=30, edge=0.05)
    veto = trading.select(rows[~rows.veto], forecast="blend", window=30, edge=0.05)
    # Removed original entries, including those replaced by later entries.
    removed = base[base.veto]
    veto_stats = [
        {"policy": label, **describe(b)}
        for label, b in (
            ("No veto", base),
            ("Veto", veto),
            ("Original bets vetoed", removed),
        )
    ]
    difference = paired(data, data, base, veto)
    comparisons.append(pair_row("veto − no veto", difference))
    includes = difference["lo"] <= 0 <= difference["hi"]
    verdict = (
        f"The fixed fight/objective veto changes entries from {len(base)} to {len(veto)}; "
        f"its paired profit difference is ${difference['sum']:+.3f}, "
        f"mean ${difference['mean']:+.4f}/map (95% series-bootstrap ${difference['lo']:+.4f} to ${difference['hi']:+.4f}). "
        + (
            "The interval includes zero; improvement is inconclusive. "
            if includes
            else (
                "The veto reduced profit; the interval excludes zero on this reused history. "
                if difference["hi"] < 0
                else "The veto increased profit; the interval excludes zero on this reused history. "
            )
        )
        + (
            "Lag comparisons below describe the fixed policies; paired intervals state whether zero is included. "
            if args.data_b
            else args.lag_unavailable + " "
        )
        + "No published metric or production behaviour changes."
    )
    report = [
        "# Live-map delay and fight-veto research — 2026-10-23",
        "",
        verdict,
        "",
        "## Fixed policies and results",
        "",
        "Earlier-only monthly blend, first qualifying entry per map at minutes 5–30; valid objectives, non-flat feed, latest trade ≤10 s, ≥2 trades spanning ≤1 cent in the stability window, ≥5-cent after-fee edge. $1 all-in per bet, 7% quadratic fee rounded up to $0.0001 per contract. Production analogue: `signals.py` persists the first qualifying candidate; `live_map.py` also checks actual books and feed freshness. Research retains tape costs.",
        "",
        *(
            [
                trading.markdown_table(pd.DataFrame(policy_rows)),
                "",
                "Blend log loss averages all eligible scored 5–30-minute rows within each map, then equally across maps, before entry filters.",
                "",
            ]
            if policy_rows
            else []
        ),
        "Veto at lag 21 s, 30-second stability window:",
        "",
        trading.markdown_table(pd.DataFrame(veto_stats)),
        "",
        "Veto removes a sample if total kills rose ≥2 since the immediately previous sample of that map, or either team's towers/inhibitors/barons/dragons changed. First samples are retained. Missing counter pairs cannot establish a change. Filter before entry selection; later samples may enter. Original bets vetoed includes entries replaced later.",
        "",
        trading.markdown_table(pd.DataFrame(comparisons)),
        "",
        "Policy ROI and CLV intervals reuse `live_trading.cluster_ci` (2,000 whole-series draws). CLV is backed-side trade price 120 s after arrival minus entry price, in cents. Paired profit uses all common input maps (zero without a bet, including unscored training maps); 2,000 whole-series resamples, seed 0, give the mean per-map difference interval. Total differences are sums of $1-outlay profits, not ROI differences.",
        "",
        "## Limits",
        "",
        "Minute samples cannot reproduce production's 10-second frames or a precise post-fight cooldown. Trade tapes are not books: no asks, depth, fills, or executable exits. Reused history: the 30-second rule itself was chosen on this history; intervals do not adjust for selection or repeated comparisons. No conclusions use maps starting 2026-10-20 or later; these are removed before fitting and scoring, with a pinned-input assertion.",
        "",
        "Measured receipt ages: BLG–MKOI median 25.6 s (204 receipts; p90 29.0), KC–MVK map 3 median 22.1 s (161; p90 26.3); floor about 20 s from the Riot embargo. Ten-second polling adds about 5 s average wait. A 21-vs-26 s comparison is a fixed-lag sensitivity, not a reconstruction of variable receipt times. Stress: an extra 1–5 cents of executable cost can consume the apparent edge; this analysis does not simulate fills or select a stress threshold.",
        "",
        "## Inputs and reproduction",
        "",
        *provenance,
        "",
        f"DB SHA256 `{hashlib.sha256(args.db.read_bytes()).hexdigest()}`. No new CI job or production workload; research runs offline.",
        "",
        "```bash",
        "UV_NO_SYNC=1 uv run python scripts/research/live_latency.py --db db/prometheus.db \\",
        *(
            [
                f"  --data-a {args.data_a} --data-b {args.data_b}"
                + (f" --data {args.data}" if args.data else "")
            ]
            if args.data_b
            else [f"  --data {args.data or args.data_a}"]
        ),
        "```",
        "",
        "Real candidates: `uv run python scripts/live_markouts.py --root data/live` reads backups pulled with `scripts/live_data.py pull`. It prints delivery status and backed-side mid minus original ask at 30/60/120 s, using the first quote at/after each horizon and showing its delay. Bo1 uses match-level series quotes. Missing horizons stay blank; summaries count available observations. Candidate markouts are neither fills nor after-fee returns; pre-match fills require the private ledger and are out of scope. No local worker backups were available for this run.",
        "",
    ]
    args.out.write_text("\n".join(report))
    print(trading.markdown_table(pd.DataFrame(veto_stats)))
    print(trading.markdown_table(pd.DataFrame(comparisons)))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
