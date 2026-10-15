"""Check production/artifact parity on the fixed international research cohort.

Run after international_markets.py, regional_correction.py and the offline export.
Prices/outcomes and earlier-only fits are reused; no network or refitting.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import regional_correction as rc

from prometheus import regional_calibration as calibration
from prometheus import schedule
from prometheus.evaluation import game_losses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/research/regional_calibration_validation.md"),
    )
    args = parser.parse_args()
    saved = pd.read_csv("data/regional_correction/games.csv")
    runtime = np.array(
        [
            calibration.probability(
                r.published,
                r.elo1 - r.elo2,
                r.home1,
                r.home2,
                at=r.day,
                event=r.league,
                event_day=r.day,
            )
            for r in saved.itertuples(index=False)
        ]
    )
    np.testing.assert_allclose(runtime, saved.persistent, atol=1e-12, rtol=0)
    lines = [
        "# Regional calibration production validation",
        "",
        "Production probabilities reproduce the original persistent two-layer experiment within 1e-12 on every eligible map and priced forecast. No numeric setting was selected again for production.",
        "",
        f"Map parity: {len(saved):,} maps. Artifact: {len(calibration.load()['snapshots'])} frozen snapshots; latest trained through {calibration.snapshot()['trained_through']}.",
        "",
        "| 2022+ slice | Maps | Elo LL | Calibrated LL | Delta (series-cluster 95%; event sensitivity) |",
        "|---|---:|---:|---:|---|",
    ]
    saved["runtime"] = runtime
    for label, f in [
        ("All", saved[saved.year >= 2022]),
        (
            "Major v major",
            saved[
                (saved.year >= 2022)
                & saved.home1.isin(schedule.MAJORS)
                & saved.home2.isin(schedule.MAJORS)
            ],
        ),
        ("2026", saved[saved.year == 2026]),
    ]:
        b = game_losses(f.published, f.won)["log_loss"].mean()
        h = game_losses(f.runtime, f.won)["log_loss"].mean()
        lines.append(
            f"| {label} | {len(f)} | {b:.6f} | {h:.6f} | {rc.loss_delta(f, f.runtime, f.published)} |"
        )
    _, _, timeline, offsets, _, _ = rc.load_data(Path("data/international_markets"))
    lines += [
        "",
        "## Fixed priced cohort",
        "",
        "| Kind / cutoff | Calls | Maximum probability error |",
        "|---|---:|---:|",
    ]
    for kind in ("series", "map1"):
        frame = pd.read_csv(
            f"data/regional_correction/{kind}.csv", parse_dates=["start"]
        )
        queries = []
        for i, row in frame.iterrows():
            for suffix, hours in (("close", 0), ("12h", 12)):
                cutoff = (
                    (row.start - pd.Timedelta(hours=hours))
                    .tz_localize(None)
                    .normalize()
                )
                for side in (1, 2):
                    game = saved[saved.gameid == row.first_game].iloc[0]
                    teamid = game.id1 if row[f"ours{side}"] == game.team1 else game.id2
                    queries.append(
                        {
                            "index": i,
                            "suffix": suffix,
                            "side": side,
                            "day": cutoff,
                            "teamid": teamid,
                        }
                    )
        rated = rc.before_day_ratings(pd.DataFrame(queries), timeline, offsets)
        for suffix in ("close", "12h"):
            actual = []
            for i, row in frame.iterrows():
                r = rated[(rated["index"] == i) & (rated.suffix == suffix)].set_index(
                    "side"
                )
                p = calibration.probability(
                    0.5,
                    r.loc[1].elo - r.loc[2].elo,
                    r.loc[1].home,
                    r.loc[2].home,
                    at=r.loc[1].day,
                    event=row.league,
                    title=row.event,
                    event_day=row.start,
                )
                if kind == "series":
                    p = schedule.series_probability(
                        p,
                        row.best_of,
                        schedule.series_rho(r.loc[1].home, r.loc[2].home),
                    )
                actual.append(p)
            np.testing.assert_allclose(
                actual, frame[f"persistent_{suffix}"], atol=1e-12, rtol=0
            )
            error = np.max(
                np.abs(np.asarray(actual) - frame[f"persistent_{suffix}"].to_numpy())
            )
            lines.append(f"| {kind} / {suffix} | {len(frame)} | {error:.2g} |")
    series = pd.read_csv("data/regional_correction/series.csv")
    lines += ["", "Primary market endpoint and closing comparison:", ""]
    common = series[series.timed & series.market_early.notna()]
    for label, part, suffix, market in [
        ("12h timed common cohort", common, "12h", "market_early"),
        ("All closing series", series, "close", "market_close"),
    ]:
        scores = [
            game_losses(part[column], part.won1)["log_loss"].mean()
            for column in (f"persistent_{suffix}", f"elo_{suffix}", market)
        ]
        lines.append(
            f"- {label} ({len(part)}): calibrated LL {scores[0]:.6f}, "
            f"Elo {scores[1]:.6f}, Kalshi {scores[2]:.6f}."
        )
    lines += [
        "",
        "The original paired market comparisons span zero. This is evidence of historical forecast improvement, not evidence of beating Kalshi.",
        "",
        "## Scope and limits",
        "",
        "Only cross-home fixtures in recognized international events are calibrated. Domestic, same-home international, EMEA Masters, promotion and other cross-league competitions retain their existing methods. An unrestricted exploratory application worsened non-international cross-league LL by +0.01595; that scope was rejected. See the [native benchmark comparison](regional_calibration_benchmarks.md) for every adoption guard.",
        "",
        "The broad 2022+ international gain is significant under both series and event resampling. Major-v-major and 2026-only gains remain within noise. Historical event boundaries, current Elo development and the viewed later seasons make this retrospective evidence. The fixed market cohort covers four events through September 30, no actual Worlds. A prospective untouched market holdout remains necessary.",
        "",
        "Runtime loads committed coefficients, never fits. Historical snapshots admit only earlier completed events, freeze through known event boundaries, and use UTC forecast-day cutoffs. The deployment artifact deliberately retains the last evaluated pre-event fit (October 2), rather than learning from an incomplete tournament. Old saved calls remain frozen; future calls record artifact version, snapshot and training cutoff. REGIONAL_CALIBRATION=0 disables the overlay.",
    ]
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Parity passed; wrote {args.out}")


if __name__ == "__main__":
    main()
