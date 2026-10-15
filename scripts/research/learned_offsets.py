"""Full player-Elo replay with one fitted regional offset, research only.

Uses the unmodified production replay via a local DataFrame iterator and its float
mapping factory. Replacement sets league_share=0; only the fitted offset exists.
Offsets fit on completed earlier international events, at day-end, so they affect
subsequent games, transfers, rookies and every team's future rating. No DB writes.
"""

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import ClassVar
from unittest import mock

import international_markets as diagnostic
import numpy as np
import pandas as pd
import regional_correction as rc
from scipy.optimize import minimize
from scipy.special import expit

from prometheus import elo, schedule
from prometheus.evaluation import game_losses

PENALTY = 4.0  # Persistent setting from <=2021; no new grid/tuning.
MODES = (
    "baseline",
    "scale_only",
    "replacement_fixed",
    "replacement_scaled",
    "recalibrated_fixed",
)


def fit_offsets(history, learn_scale, prior_offsets=None):
    if len(history) < rc.MIN_TRAIN:
        return 1.0, {}
    names = sorted(set(history.home1) | set(history.home2))
    index = {name: i for i, name in enumerate(names)}
    x = np.zeros((len(history), len(names)))
    for i, r in enumerate(history.itertuples()):
        x[i, index[r.home1]] += 1
        x[i, index[r.home2]] -= 1
    base = history.base_logit.to_numpy(float)
    y = history.won.to_numpy(float)
    # Fit only finished events: final map counts are available at this point.
    weights = 1 / history.groupby("cluster").gameid.transform("size").to_numpy(float)
    if learn_scale:
        x = np.column_stack((base, x))
        initial = np.zeros(x.shape[1])
        initial[0] = 1.0
        regularizer = np.full(x.shape[1], PENALTY)
        regularizer[0] = 1.0
        offset = 0.0
        bounds = [(0.25, 4.0)] + [(None, None)] * len(names)
    else:
        initial = np.array(
            [
                schedule.CROSS_REGION_ELO_WEIGHT * (prior_offsets or {}).get(name, 0.0)
                for name in names
            ]
        )
        initial -= initial.mean()
        regularizer = np.full(x.shape[1], PENALTY)
        offset = base
        bounds = [(None, None)] * len(names)

    def objective(theta):
        z = offset + x @ theta
        delta = theta - initial
        loss = np.sum(weights * (np.logaddexp(0, z) - y * z)) + 0.5 * np.sum(
            regularizer * delta**2
        )
        gradient = x.T @ (weights * (expit(z) - y)) + regularizer * delta
        return loss, gradient

    result = minimize(
        objective,
        initial,
        jac=True,
        method="L-BFGS-B",
        bounds=bounds,
        options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 500},
    )
    if not result.success:
        raise RuntimeError(result.message)
    alpha = float(result.x[0]) if learn_scale else 1.0
    delta = result.x[1:] if learn_scale else result.x
    # Store one offset in Elo points. No additive correction remains in forecasting.
    regional = (delta - delta.mean()) / (schedule.CROSS_REGION_ELO_WEIGHT * alpha)
    return alpha, dict(zip(names, regional))


class ReplayGames(pd.DataFrame):
    _metadata: ClassVar[list[str]] = ["policy"]

    def itertuples(self, index=True, name="Pandas"):
        for row in super().itertuples(index=index, name=name):
            self.policy.before(row)
            yield row
            # Native replay has finished the game's player updates and records.
            self.policy.after(row)


class OffsetPolicy:
    def __init__(self, games, event_games, mode):
        self.mode = mode
        self.offsets = None
        self.home = {}
        self.counts = {}
        self.homes = {}
        self.current = None
        self.observations = []
        self.offset_records = []
        self.scale_records = []
        self.audit = []
        self.alpha = 1.0
        self.event_map = event_games.set_index("gameid").event_id.to_dict()
        self.event_end = event_games.groupby("event_id").day.max().to_dict()
        self.last_day_game = (
            games.assign(day=pd.to_datetime(games.date).dt.normalize())
            .groupby("day")
            .gameid.last()
            .to_dict()
        )
        self.last_completed = frozenset()

    def mapping(self, factory, *args, **kwargs):
        out = defaultdict(factory, *args, **kwargs)
        if factory is float:
            if self.offsets is not None:
                raise AssertionError(
                    "Replay created more than one regional offset mapping"
                )
            self.offsets = out
        return out

    def before(self, row):
        self.current = row
        if row.league not in elo.INTERNATIONAL_LEAGUES:
            year = pd.Timestamp(row.date).year
            for team in (row.teamid, row.opponent_teamid):
                if (team, year) not in self.counts:
                    self.counts[(team, year)] = (
                        {self.home[team]: 1} if team in self.home else {}
                    )
                counts = self.counts[(team, year)]
                counts[row.league] = counts.get(row.league, 0) + 1
                if counts[row.league] > counts.get(self.home.get(team), 0):
                    self.home[team] = row.league

        for team in (row.teamid, row.opponent_teamid):
            self.homes[(row.gameid, team)] = self.home.get(team)

    def change(self, **kwargs):
        row = self.current
        # Inputs are captured before the native replay updates any player.
        event_id = self.event_map.get(row.gameid)
        home1, home2 = self.home.get(row.teamid), self.home.get(row.opponent_teamid)
        if event_id and home1 and home2 and home1 != home2:
            gap = kwargs["elo"] - kwargs["opponent_elo"]
            if self.mode.startswith("replacement") or self.mode == "recalibrated_fixed":
                gap -= self.offsets[home1] - self.offsets[home2]
            day = pd.Timestamp(row.date).normalize()
            self.observations.append(
                {
                    "gameid": row.gameid,
                    "day": day,
                    "event_id": event_id,
                    "home1": home1,
                    "home2": home2,
                    "base_logit": schedule.CROSS_REGION_ELO_WEIGHT * gap,
                    "won": row.result,
                    "cluster": f"{row.league}|{day}|{'|'.join(sorted((row.teamid, row.opponent_teamid)))}",
                }
            )
        return elo.calculate_game_length_elo_change(**kwargs)

    def after(self, row):
        if self.mode == "baseline":
            return
        day = pd.Timestamp(row.date).normalize()
        if row.gameid != self.last_day_game[day]:
            return
        completed = frozenset(k for k, v in self.event_end.items() if v <= day)
        if completed == self.last_completed:
            return
        self.last_completed = completed
        history = pd.DataFrame(
            [r for r in self.observations if r["event_id"] in completed]
        )
        if history.empty or len(history) < rc.MIN_TRAIN:
            return
        if self.mode == "scale_only":
            history["weight"] = 1 / history.groupby("cluster").gameid.transform("size")
            calibration = rc.fit(history, day + pd.Timedelta(days=1), regions=False)
            alpha, values = calibration.alpha, {}
        else:
            alpha, values = fit_offsets(
                history,
                self.mode == "replacement_scaled",
                dict(self.offsets) if self.mode == "recalibrated_fixed" else None,
            )
        self.alpha = alpha
        self.scale_records.append({"day": day, "alpha": alpha})
        for league, value in values.items():
            self.offsets[league] = value
            self.offset_records.append(
                {
                    "gameid": row.gameid,
                    "date": row.date,
                    "league": league,
                    "league_offset": value,
                }
            )
        self.audit.append(
            {
                "available_from": str((day + pd.Timedelta(days=1)).date()),
                "trained_through": str(history.day.max().date()),
                "n_train": len(history),
                "alpha": alpha,
                "offsets": values,
                "completed_events": sorted(completed),
            }
        )


def replay(games, rosters, events, mode):
    policy = OffsetPolicy(games, events, mode)
    wrapped = ReplayGames(games)
    wrapped.policy = policy
    with mock.patch.object(elo, "defaultdict", policy.mapping):
        records, offsets = elo.compute_elo_records(
            wrapped,
            policy.change,
            rosters=rosters,
            league_share=0.0 if mode.startswith("replacement") else elo.LEAGUE_SHARE,
        )
    # Independently tracked home-league logic must match native replay exactly.
    for row in records.itertuples(index=False):
        assert policy.homes[(row.gameid, row.teamid)] == row.home_league
    if policy.offset_records:
        offsets = pd.concat(
            [offsets, pd.DataFrame(policy.offset_records)], ignore_index=True
        ).sort_values("date", kind="stable")
        # Learned records at a day's last game supersede native zero-share records.
        offsets = offsets.drop_duplicates(["date", "league"], keep="last")
    return records, offsets, policy


def memory_tables(records, offsets, metadata):
    timeline = records.rename(
        columns={
            "main_elo": "elo",
            "home_league": "home",
            "league_offset": "saved_offset",
        }
    )
    timeline = timeline[["gameid", "teamid", "elo", "home", "saved_offset"]].merge(
        metadata[["gameid", "teamid", "date"]],
        on=["gameid", "teamid"],
        validate="one_to_one",
    )
    regional = offsets.rename(
        columns={"league": "home", "league_offset": "current_offset"}
    )
    return timeline, regional[["date", "home", "current_offset"]]


def alpha_at(policy, day):
    available = [
        r["alpha"] for r in policy.scale_records if r["day"] < pd.Timestamp(day)
    ]
    return available[-1] if available else 1.0


def game_calls(frame, timeline, offsets, policy):
    queries = pd.concat(
        [
            frame[["gameid", "day", f"id{i}"]]
            .rename(columns={f"id{i}": "teamid"})
            .assign(side=i)
            for i in (1, 2)
        ],
        ignore_index=True,
    )
    rated = rc.before_day_ratings(queries, timeline, offsets)
    wide = rated.pivot(index="gameid", columns="side", values="elo")
    gap = wide.loc[frame.gameid, 1].to_numpy() - wide.loc[frame.gameid, 2].to_numpy()
    alpha = np.array([alpha_at(policy, day) for day in frame.day])
    return expit(schedule.CROSS_REGION_ELO_WEIGHT * alpha * gap)


def market_calls(frame, metadata, timeline, offsets, policy, series):
    f = frame[frame.cross_region].copy().reset_index(drop=True)
    lookup = metadata.set_index(["gameid", "teamname"]).teamid
    queries = []
    for idx, r in f.iterrows():
        for suffix, hours in (("close", 0), ("12h", 12)):
            day = (r.start - pd.Timedelta(hours=hours)).tz_localize(None).normalize()
            for side in (1, 2):
                queries.append(
                    {
                        "index": idx,
                        "suffix": suffix,
                        "side": side,
                        "day": day,
                        "teamid": lookup.loc[(r.first_game, r[f"ours{side}"])],
                    }
                )
    rated = rc.before_day_ratings(pd.DataFrame(queries), timeline, offsets)
    for idx in f.index:
        for suffix in ("close", "12h"):
            r = rated[(rated["index"] == idx) & (rated.suffix == suffix)].set_index(
                "side"
            )
            p = float(
                expit(
                    schedule.CROSS_REGION_ELO_WEIGHT
                    * alpha_at(policy, r.iloc[0].day)
                    * (r.loc[1].elo - r.loc[2].elo)
                )
            )
            if series:
                rho = schedule.series_rho(r.loc[1].home, r.loc[2].home)
                p = schedule.series_probability(p, f.loc[idx, "best_of"], rho)
            f.loc[idx, f"{policy.mode}_{suffix}"] = p
    return f


def overlay_controls(events):
    """Isolate the original forecast-only gain from scale changes and replay feedback."""
    out = events.copy()
    for learn_scale, name in ((False, "overlay_fixed"), (True, "overlay_scaled")):
        out[name] = np.nan
        for _, part in out.groupby("event_id", sort=False):
            cutoff = part.day.min()
            alpha, corrections = fit_offsets(
                rc.older_events(events, cutoff), learn_scale
            )
            shift = np.array(
                [
                    corrections.get(a, 0.0) - corrections.get(b, 0.0)
                    for a, b in zip(part.home1, part.home2)
                ]
            )
            out.loc[part.index, name] = expit(
                alpha
                * (
                    part.base_logit.to_numpy()
                    + schedule.CROSS_REGION_ELO_WEIGHT * shift
                )
            )
    return out


def table(
    frame, names, col="won", baseline="baseline", cluster="cluster", event="event_id"
):
    interval_kind = "series-cluster" if cluster else "paired series"
    market_column = " | Δ vs Kalshi (paired series 95%)" if "Kalshi" in frame else ""
    lines = [
        f"| Model | n | LL | Δ vs existing Elo ({interval_kind} 95%) | Event-cluster sensitivity{market_column} |",
        "|---|---:|---:|---|---|" + ("---|" if market_column else ""),
    ]
    for name in names:
        loss = game_losses(frame[name], frame[col])["log_loss"]
        diff = np.asarray(loss - game_losses(frame[baseline], frame[col])["log_loss"])
        lo, hi = diagnostic.interval(diff, frame[cluster] if cluster else None)
        a, b = diagnostic.interval(diff, frame[event])
        market_cells = ""
        if market_column:
            delta = np.asarray(loss - game_losses(frame.Kalshi, frame[col])["log_loss"])
            ml, mh = diagnostic.interval(delta)
            market_cells = f" {delta.mean():+.4f} [{ml:+.4f}, {mh:+.4f}] |"
        lines.append(
            f"| {name} | {len(frame)} | {loss.mean():.4f} | {diff.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | [{a:+.4f}, {b:+.4f}] |"
            + market_cells
        )
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/learned_offsets_report.md")
    )
    parser.add_argument("--export", type=Path, default=Path("data/learned_offsets"))
    args = parser.parse_args()
    started = time.perf_counter()
    events, _, _, _, series, maps = rc.load_data(Path("data/international_markets"))
    games = elo.load_elo_games()
    rosters = elo.load_rosters()
    meta = pd.read_sql(
        "SELECT gameid,teamid,teamname,date,league,result FROM matches",
        rc.utils.get_engine(),
    )
    db = (
        pd.read_sql(
            "SELECT gameid,teamid,pre_match_elo FROM game_length_elo",
            rc.utils.get_engine(),
        )
        .set_index(["gameid", "teamid"])
        .pre_match_elo
    )
    artifacts = {}
    timing = {}
    fit_audits = {}
    native = {}
    for mode in MODES:
        t = time.perf_counter()
        records, offsets, policy = replay(games, rosters, events, mode)
        timing[mode] = round(time.perf_counter() - t, 3)
        print(f"{mode} replay: {timing[mode]}s; fits {len(policy.audit)}", flush=True)
        if mode == "baseline":
            actual = records.set_index(["gameid", "teamid"]).pre_match_elo
            np.testing.assert_allclose(
                actual.sort_index(), db.sort_index(), atol=1e-9, rtol=0
            )
        timeline, regional = memory_tables(records, offsets, meta)
        events[mode] = game_calls(events, timeline, regional, policy)
        for target, is_series in ((series, True), (maps, False)):
            called = market_calls(target, meta, timeline, regional, policy, is_series)
            if mode == "baseline":
                for suffix in ("close", "12h"):
                    np.testing.assert_allclose(
                        called[f"baseline_{suffix}"],
                        called[f"elo_{suffix}"],
                        atol=1e-12,
                        rtol=0,
                    )
            for suffix in ("close", "12h"):
                target.loc[target.cross_region, f"{mode}_{suffix}"] = called[
                    f"{mode}_{suffix}"
                ].to_numpy()
        # Native pre-game scores with identical frozen probability scale expose downstream effects.
        paired = records.set_index(["gameid", "teamid"]).pre_match_elo
        native[mode] = (paired, policy)
        fit_audits[mode] = policy.audit
        artifacts[mode] = {"records": records, "offsets": offsets}
    lines = [
        "# One learned regional offset: full Elo replay",
        "",
        "Research only. Production compute_elo_records is unmodified; an iterator observes games and an isolated mapping factory exposes its single offset table. "
        "Replacement uses league_share=0 and overwrites that table with fitted offsets. Every player update, rookie baseline, transfer conversion and later team rating is replayed with the new offsets. "
        "No post-hoc regional term is added to probabilities.",
        "",
        "Ridge 4 and persistent history are inherited from the <=2021 experiment; no new tuning/grid. Fixed-scale replacement holds the published cross-region slope constant. "
        "Scaled replacement fits that slope alongside offsets. Scale-only keeps ordinary offsets and learns probability scaling independently. "
        "Recalibrated-fixed retains ordinary game-by-game updates, then fits absolute offsets shrunk toward the current offset table, "
        "overwriting that same table at completed events. It is a single-state follow-up, fixed ridge 4 and fixed probability scale, specified after the replacement result; "
        "not an untouched confirmation or a new grid. Player update expectations retain the published 400-point curve in every arm.",
        "",
        "Fits use only completed eligible older event blocks, at the end of a UTC day; new offsets/scales are available the next day. "
        "All historical fitting inputs are actual pre-game starter ratings. Evaluation uses production main-roster ratings before each UTC day; this distinction is common to the replay controls. "
        "Each finished pair/day contributes total weight one. Event provenance/coverage and inherited baseline hindsight limits are those of regional_correction.py. "
        "The same raw games/rosters and fixed priced cohort are used in every arm; Kalshi prices/results never enter fitting. No uncertainty/team-effect term.",
        "",
        "Baseline native pre-game ratings reproduce the private DB within 1e-9. Every saved cross-region series/map call at both cutoffs reproduces the previous diagnostic within 1e-12. "
        "Intervals are paired by team-pair/day and by event for map results. Market intervals pair series; four events remain weak evidence. "
        "Research does not constitute a native production adoption-gate run or a prospective market edge.",
        "",
        "## 2022+ day-before maps",
        "",
    ]
    events = overlay_controls(events)
    expected, _ = rc.event_predictions(events, penalty=PENALTY, half_life=math.inf)
    np.testing.assert_allclose(events.overlay_scaled, expected, atol=1e-8, rtol=0)
    held = events[events.year > rc.TUNE_END]
    lines += [
        "## Forecast-only attribution controls",
        "",
        "These preserve original player/offset histories and never feed corrections into updates. "
        "They isolate probability scale and distinguish an equivalent folded prediction from a replacement learning rule. "
        "The scaled overlay reproduces the previous persistent correction within 1e-8. "
        "Replacing offset learning also changes replay feedback and fits on native pre-game rather than day-start inputs; "
        "the difference cannot be attributed solely to replay feedback.",
        "",
        *table(held, ("baseline", "overlay_fixed", "overlay_scaled")),
        "",
    ]
    for label, f in (
        ("All", held),
        ("Entry", held[held.entry]),
        ("Later", held[~held.entry]),
        (
            "Major v major",
            held[held.home1.isin(schedule.MAJORS) & held.home2.isin(schedule.MAJORS)],
        ),
    ):
        lines += [f"### {label}", "", *table(f, MODES), ""]
    for year, f in held.groupby("year"):
        lines += [f"### {year}", "", *table(f, MODES), ""]
    lines += [
        "## Fixed market cohort",
        "",
        "The 12h comparison is primary; common rows have prices at both cutoffs.",
        "",
    ]
    cross = series[series.cross_region].copy()
    cross["event_id"] = cross.event
    common = cross[cross.timed & cross.market_early.notna()].copy()
    for suffix, market, label, f in (
        ("12h", "market_early", "12h", common),
        ("close", "market_close", "Close, common", common),
        ("close", "market_close", "Close, all", cross),
    ):
        part = f.copy()
        for mode in MODES:
            part[mode] = part[f"{mode}_{suffix}"]
        part["Kalshi"] = part[market]
        lines += [
            f"### {label}",
            "",
            *table(part, [*MODES, "Kalshi"], col="won1", cluster=None),
            "",
        ]
    args.export.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.export / "games.csv", index=False)
    series.to_csv(args.export / "series.csv", index=False)
    maps.to_csv(args.export / "map1.csv", index=False)
    # Full records and offsets preserve attribution and support native guards next.
    pd.to_pickle(artifacts, args.export / "replays.pkl")
    audit = {
        "fits": fit_audits,
        "timing": timing,
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "penalty": PENALTY,
        "probability_slope": schedule.CROSS_REGION_ELO_WEIGHT,
        "base_commit": "36a1e6e",
    }
    (args.export / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {args.out}, total {audit['runtime_seconds']}s", flush=True)


if __name__ == "__main__":
    main()
