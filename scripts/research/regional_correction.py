"""Earlier-event calibration and ridge regional corrections to published Elo.

Research only. No market input to fitting, no production changes. Fixed grid is
selected through 2021, then frozen for 2022+. Per-event parameters use completed
older events only. Corrections stay frozen inside an event; base Elo evolves daily.
"""

import argparse
import hashlib
import json
import math
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import international_markets as diagnostic
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from prometheus import schedule, utils
from prometheus.evaluation import game_losses
from prometheus.types import INTERNATIONAL_LEAGUES

TUNE_END = 2021
# Fixed before scoring: 3 ridge strengths x 3 recency settings; no later grid.
PENALTIES = (1.0, 4.0, 16.0)
HALF_LIVES = (365.0, 1460.0, math.inf)
MIN_TRAIN = 50


def before_day_ratings(queries, timeline, offsets):
    """Production main-roster Elo, including carried offsets, strictly before day."""
    q = queries.copy().reset_index(drop=True)
    q["_order"] = np.arange(len(q))
    q["day"] = pd.to_datetime(q.day).dt.normalize()
    history = timeline.copy()
    history["day"] = pd.to_datetime(history.date).dt.normalize()
    history = history.sort_values(["date", "gameid"]).drop_duplicates(
        ["teamid", "day"], keep="last"
    )
    history = history.drop(columns=["date", "gameid"])
    joined = pd.merge_asof(
        q.sort_values("day"),
        history.sort_values("day"),
        on="day",
        by="teamid",
        allow_exact_matches=False,
    )
    regional = offsets.copy()
    regional["day"] = pd.to_datetime(regional.date).dt.normalize()
    regional = regional.drop_duplicates(["home", "day"], keep="last").drop(
        columns="date"
    )
    known = joined[joined.home.notna()]
    known = pd.merge_asof(
        known.sort_values("day"),
        regional.sort_values("day"),
        on="day",
        by="home",
        allow_exact_matches=False,
    )
    known["elo"] += (known.current_offset - known.saved_offset).fillna(0)
    return known.sort_values("_order").drop(columns="_order")


def metadata_exclusions(cached, games):
    """Event provenance only: never inspect market probabilities or outcomes."""
    excluded, ewc_days = set(), set()
    for r in cached.itertuples():
        day = r.start.date()
        selected = games[
            (games.team == r.ours1)
            & (games.opponent == r.ours2)
            & (games.day >= day - pd.Timedelta(days=1))
            & (games.day <= day + pd.Timedelta(days=1))
        ]
        if (
            selected.empty
            or selected.league.nunique() != 1
            or selected.day.nunique() != 1
        ):
            continue
        league = selected.iloc[0].league
        date = pd.Timestamp(selected.iloc[0].day)
        if any(word in r.event.lower() for word in ("qualifier", "regional finals")):
            excluded.add((league, date))
        elif league == "EWC":
            ewc_days.add(date)
    return excluded, ewc_days


def load_data(market_dir):
    engine = utils.get_engine()
    placeholders = ",".join(f"'{x}'" for x in INTERNATIONAL_LEAGUES)
    games = pd.read_sql(
        f"""SELECT a.gameid, a.date, a.league, a.teamid AS id1,
              b.teamid AS id2, a.teamname AS team1, b.teamname AS team2, a.result AS won
        FROM matches a JOIN matches b ON a.gameid=b.gameid AND b.side='Red'
        WHERE a.side='Blue' AND a.league IN ({placeholders}) ORDER BY a.date,a.gameid""",
        engine,
    )
    timeline = pd.read_sql(
        """SELECT e.teamid, m.gameid, m.date,
        COALESCE(e.main_elo,e.post_match_elo) AS elo, e.home_league AS home,
        e.league_offset AS saved_offset FROM game_length_elo e JOIN matches m
        ON m.gameid=e.gameid AND m.teamid=e.teamid ORDER BY m.date,m.gameid""",
        engine,
    )
    offsets = pd.read_sql(
        """SELECT date, league AS home, league_offset AS current_offset
        FROM game_length_elo_league_offsets ORDER BY rowid""",
        engine,
    )
    # Use all matched market metadata to exclude identified regional qualifiers/finals.
    cached, *_ = pd.read_pickle("data/markets/frames.pkl")
    metadata_games = diagnostic.load_games("2025-12-09")
    drop_keys, ewc_days = metadata_exclusions(cached, metadata_games)
    games["day"] = pd.to_datetime(games.date).dt.normalize()
    # Exact known 2026 EWC main-event window excludes unpriced regional qualifiers too.
    if ewc_days:
        lo, hi = min(ewc_days), max(ewc_days)
        extra = games[
            (games.league == "EWC")
            & (games.day.dt.year == 2026)
            & ~games.day.between(lo, hi)
        ]
        drop_keys.update(zip(extra.league, extra.day))
    games = games[
        ~pd.Series(list(zip(games.league, games.day)), index=games.index).isin(
            drop_keys
        )
    ].reset_index(drop=True)
    queries = pd.concat(
        [
            games[["gameid", "day", f"id{i}"]]
            .rename(columns={f"id{i}": "teamid"})
            .assign(side=i)
            for i in (1, 2)
        ],
        ignore_index=True,
    )
    rated = before_day_ratings(queries, timeline, offsets)
    for i in (1, 2):
        ratings = rated[rated.side == i][["gameid", "elo", "home"]].rename(
            columns={"elo": f"elo{i}", "home": f"home{i}"}
        )
        games = games.merge(ratings, on="gameid", how="left", validate="one_to_one")
    excluded = games[
        games.home1.isna() | games.home2.isna() | (games.home1 == games.home2)
    ].copy()
    games = games[
        games.home1.notna() & games.home2.notna() & (games.home1 != games.home2)
    ].copy()
    games["base_logit"] = schedule.CROSS_REGION_ELO_WEIGHT * (games.elo1 - games.elo2)
    # Metadata-only event blocks. Large breaks split regional qualification from main events.
    games = assign_events(games)
    games["year"] = games.day.dt.year
    games["cluster"] = games.apply(
        lambda r: f"{r.league}|{r.day.date()}|{'|'.join(sorted((r.id1, r.id2)))}",
        axis=1,
    )
    games["weight"] = 1 / games.groupby("cluster").gameid.transform("size")
    games = entry_labels(games)
    market_series = pd.read_csv(
        market_dir / "series.csv", parse_dates=["start", "game_date"]
    )
    market_maps = pd.read_csv(
        market_dir / "map1.csv", parse_dates=["start", "game_date"]
    )
    return (
        games.reset_index(drop=True),
        excluded,
        timeline,
        offsets,
        market_series,
        market_maps,
    )


def entry_labels(games):
    out = games.copy()
    out["entry"] = False
    for _, part in out.groupby("event_id"):
        first = {}
        for r in part.itertuples():
            for team in (r.id1, r.id2):
                first[team] = min(first.get(team, r.day), r.day)
        for idx, r in part.iterrows():
            out.loc[idx, "entry"] = any(first[team] == r.day for team in (r.id1, r.id2))
    return out


def assign_events(games, gap_days=21):
    out = games.sort_values(["day", "date", "gameid"]).copy()
    chunks = {}
    for (league, year), part in out.groupby(["league", out.day.dt.year], sort=False):
        days = part.day.drop_duplicates().sort_values()
        blocks = days.diff().dt.days.gt(gap_days).cumsum()
        for day, block in zip(days, blocks):
            chunks[(league, year, day)] = f"{league}-{year}-{int(block)}"
    out["event_id"] = [chunks[(r.league, r.day.year, r.day)] for r in out.itertuples()]
    return out


@dataclass
class Correction:
    alpha: float
    effects: dict
    penalty: float
    half_life: float
    trained_through: str | None
    n_train: int

    def logit(self, base, home1, home2):
        a = np.array([self.effects.get(x, 0.0) for x in home1])
        b = np.array([self.effects.get(x, 0.0) for x in home2])
        return self.alpha * np.asarray(base) + a - b


def fit(history, cutoff, penalty=4.0, half_life=math.inf, regions=True):
    # Callers must exclude incomplete events; this additionally enforces day cutoff.
    history = history[history.day < pd.Timestamp(cutoff)]
    if len(history) < MIN_TRAIN:
        return Correction(1.0, {}, penalty, half_life, None, len(history))
    vocabulary = sorted(set(history.home1) | set(history.home2)) if regions else []
    mapping = {name: i for i, name in enumerate(vocabulary)}
    x = np.zeros((len(history), len(vocabulary) + 1))
    x[:, 0] = history.base_logit
    for i, r in enumerate(history.itertuples()):
        if regions:
            x[i, 1 + mapping[r.home1]] += 1
            x[i, 1 + mapping[r.home2]] -= 1
    y = history.won.to_numpy(float)
    weight = history.weight.to_numpy(float)
    if np.isfinite(half_life):
        ages = (pd.Timestamp(cutoff) - history.day).dt.days.to_numpy()
        weight *= np.exp2(-ages / half_life)
    initial = np.zeros(x.shape[1])
    initial[0] = 1.0
    # Alpha is regularized toward current Elo; regional effects toward zero.
    regularizer = np.full(x.shape[1], penalty)
    regularizer[0] = 1.0

    def objective(theta):
        z = x @ theta
        delta = theta - initial
        loss = np.sum(weight * (np.logaddexp(0, z) - y * z)) + 0.5 * np.sum(
            regularizer * delta**2
        )
        gradient = x.T @ (weight * (expit(z) - y)) + regularizer * delta
        return loss, gradient

    result = minimize(
        objective,
        initial,
        jac=True,
        method="L-BFGS-B",
        bounds=[(0.25, 4.0)] + [(None, None)] * len(vocabulary),
        options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 500},
    )
    if not result.success:
        raise RuntimeError(result.message)
    # Signed differences plus isotropic ridge identify a zero-sum solution.
    effects = (
        dict(zip(vocabulary, result.x[1:] - result.x[1:].mean())) if regions else {}
    )
    return Correction(
        float(result.x[0]),
        effects,
        penalty,
        half_life,
        str(history.day.max().date()),
        len(history),
    )


def older_events(games, cutoff):
    end = games.groupby("event_id").day.transform("max")
    return games[end < pd.Timestamp(cutoff)]


def event_predictions(games, penalty=4.0, half_life=math.inf, regions=True):
    out = np.full(len(games), np.nan)
    records = []
    for event_id, part in games.groupby("event_id", sort=False):
        cutoff = part.day.min()
        model = fit(older_events(games, cutoff), cutoff, penalty, half_life, regions)
        out[part.index] = expit(model.logit(part.base_logit, part.home1, part.home2))
        records.append(
            {"event_id": event_id, "cutoff": str(cutoff.date()), **model.__dict__}
        )
    return out, records


def loss_delta(frame, candidate, base):
    a = game_losses(candidate, frame.won)["log_loss"]
    b = game_losses(base, frame.won)["log_loss"]
    difference = np.asarray(a - b)
    lo, hi = diagnostic.interval(difference, frame.cluster)
    elo, ehi = diagnostic.interval(difference, frame.event_id)
    return f"{difference.mean():+.4f} [{lo:+.4f}, {hi:+.4f}]; event [{elo:+.4f}, {ehi:+.4f}]"


def game_table(games, candidates):
    lines = [
        "| Slice | Maps | Events | Baseline LL | Candidate | Candidate LL | Δ vs published (series-cluster 95%; event sensitivity) | Δ vs calibration |",
        "|---|---:|---:|---:|---|---:|---|---|",
    ]
    held = games[games.year > TUNE_END]
    major_count = held.home1.isin(schedule.MAJORS).astype(int) + held.home2.isin(
        schedule.MAJORS
    ).astype(int)
    slices = [
        ("2022+ major v major", held[major_count == 2]),
        ("2022+ major v other", held[major_count == 1]),
        ("2022+ other v other", held[major_count == 0]),
    ] + [(f"Year {year}", f) for year, f in held.groupby("year")]
    for label, f in [
        ("2022+ all", games[games.year > TUNE_END]),
        ("2022+ entry", games[(games.year > TUNE_END) & games.entry]),
        ("2022+ later", games[(games.year > TUNE_END) & ~games.entry]),
        ("2022+ senior", games[(games.year > TUNE_END) & (games.league != "WSCI")]),
        ("2026", games[games.year == 2026]),
    ] + slices:
        if not len(f):
            continue
        baseline = game_losses(f.published, f.won)["log_loss"].mean()
        for candidate in candidates:
            score = game_losses(f[candidate], f.won)["log_loss"].mean()
            lines.append(
                f"| {label} | {len(f)} | {f.event_id.nunique()} | {baseline:.4f} | {candidate} | {score:.4f} | "
                f"{loss_delta(f, f[candidate], f.published)} | {loss_delta(f, f[candidate], f.calibration)} |"
            )
    return lines


def market_predictions(frame, games, timeline, offsets, chosen, series):
    frame = frame[frame.cross_region].copy().reset_index(drop=True)
    queries = []
    # Map each name to its ID at the diagnostic's matched game, not today's roster.
    meta = pd.read_sql(
        "SELECT gameid, teamid, teamname FROM matches", utils.get_engine()
    )
    lookup = meta.set_index(["gameid", "teamname"]).teamid
    for idx, row in frame.iterrows():
        for suffix, hours in (("close", 0), ("12h", 12)):
            day = (row.start - pd.Timedelta(hours=hours)).tz_localize(None).normalize()
            for side in (1, 2):
                name = row[f"ours{side}"]
                queries.append(
                    {
                        "index": idx,
                        "suffix": suffix,
                        "side": side,
                        "day": day,
                        "teamid": lookup.loc[(row.first_game, name)],
                    }
                )
    rated = before_day_ratings(pd.DataFrame(queries), timeline, offsets)
    models = {}
    for idx, row in frame.iterrows():
        matched = games[games.gameid == row.first_game]
        if matched.empty:
            raise ValueError(f"No training-event metadata for {row.event_ticker}")
        event_id = matched.iloc[0].event_id
        event_start = games[games.event_id == event_id].day.min()
        for suffix in ("close", "12h"):
            r = rated[(rated["index"] == idx) & (rated.suffix == suffix)].set_index(
                "side"
            )
            cutoff = min(event_start, r.iloc[0].day)
            base = schedule.CROSS_REGION_ELO_WEIGHT * (r.loc[1].elo - r.loc[2].elo)
            # Exact reproduction check against diagnostic's fresh Elo.
            p = float(expit(base))
            rho = schedule.series_rho(r.loc[1].home, r.loc[2].home)
            if series:
                p = schedule.series_probability(p, row.best_of, rho)
            np.testing.assert_allclose(p, row[f"elo_{suffix}"], atol=1e-12, rtol=0)
            for name, penalty, half_life, regions in chosen:
                key = (name, cutoff)
                if key not in models:
                    models[key] = fit(
                        older_events(games, cutoff), cutoff, penalty, half_life, regions
                    )
                model = models[key]
                chance = float(
                    expit(model.logit([base], [r.loc[1].home], [r.loc[2].home])[0])
                )
                if series:
                    chance = schedule.series_probability(chance, row.best_of, rho)
                frame.loc[idx, f"{name}_{suffix}"] = chance
        frame.loc[idx, "event_id"] = event_id
    return frame


def market_table(series, maps, names):
    lines = [
        "| Slice | n | Candidate | LL | Δ vs current Elo (paired series 95%) | Δ vs Kalshi (paired series 95%) |",
        "|---|---:|---|---:|---|---|",
    ]

    def add(label, f, suffix, market):
        if f.empty:
            return
        for name in names:
            loss = game_losses(f[f"{name}_{suffix}"], f.won1)["log_loss"]
            cells = []
            for p in (f[f"elo_{suffix}"], f[market]):
                d = np.asarray(loss - game_losses(p, f.won1)["log_loss"])
                lo, hi = diagnostic.interval(d)
                cells.append(f"{d.mean():+.4f} [{lo:+.4f}, {hi:+.4f}]")
            lines.append(
                f"| {label} | {len(f)} | {name} | {loss.mean():.4f} | {cells[0]} | {cells[1]} |"
            )

    common = series[series.timed & series.market_early.notna()]
    add("12h, common cohort (primary)", common, "12h", "market_early")
    add("Close, common cohort", common, "close", "market_close")
    add("Close, all", series, "close", "market_close")
    for phase, f in series.groupby("phase"):
        add(f"Close: {phase}", f, "close", "market_close")
    for event, f in series.groupby("event"):
        add(f"Close: {event}", f, "close", "market_close")
    add("Map 1 close", maps, "close", "market_close")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--market-dir", type=Path, default=Path("data/international_markets")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/regional_correction_report.md")
    )
    parser.add_argument("--export", type=Path, default=Path("data/regional_correction"))
    args = parser.parse_args()
    started = time.perf_counter()
    games, excluded, timeline, offsets, series, maps = load_data(args.market_dir)
    print(
        f"Loaded {len(games)} eligible maps; {len(excluded)} missing-home/same-region exclusions",
        flush=True,
    )
    games["published"] = expit(games.base_logit)
    games["calibration"], calibration_models = event_predictions(games, regions=False)
    tuning, all_models, chosen = (
        [],
        {"calibration": calibration_models},
        [("calibration", 4.0, math.inf, False)],
    )
    train = games.year <= TUNE_END
    for penalty in PENALTIES:
        for half_life in HALF_LIVES:
            name = f"r{penalty:g}-h{half_life:g}"
            games[name], all_models[name] = event_predictions(games, penalty, half_life)
            loss = game_losses(games.loc[train, name], games.loc[train, "won"])[
                "log_loss"
            ].mean()
            tuning.append(
                {
                    "name": name,
                    "penalty": penalty,
                    "half_life": half_life,
                    "tuning_ll": float(loss),
                }
            )
            print(f"{name}: <=2021 LL {loss:.5f}", flush=True)
    # Separately choose persistent and recency candidates on old events only.
    for label, persistent in (("persistent", True), ("dynamic", False)):
        pool = [r for r in tuning if np.isinf(r["half_life"]) == persistent]
        best = min(pool, key=lambda r: r["tuning_ll"])
        games[label] = games[best["name"]]
        all_models[label] = all_models[best["name"]]
        chosen.append((label, best["penalty"], best["half_life"], True))
    names = [x[0] for x in chosen]
    print(f"Frozen choices: {chosen}", flush=True)
    series = market_predictions(series, games, timeline, offsets, chosen, True)
    maps = market_predictions(maps, games, timeline, offsets, chosen, False)
    lines = [
        "# Regional Elo correction: first development experiment",
        "",
        "Research only; no adoption, DB writes, published weights or live calls changed. "
        "Grid fixed in code before scoring (ridge 1/4/16; half-life 365/1460/infinite days); "
        "persistent and dynamic settings selected through 2021, then frozen for 2022+. "
        "Calibration and regional coefficients are re-fit before each event from completed earlier events only.",
        "",
        "Baseline is the current published cross-region curve on production main-roster Elo before each UTC day. "
        "Current Elo's algorithm/hyperparameters and baseline slope have previously seen later periods. "
        "Candidates fit scale and regional effects on earlier events only; results remain retrospective development evidence.",
        "",
        "Regional effects are ridge-shrunk to zero and sum to zero. Dynamic means an exponential half-life on older evidence, "
        "not a Bayesian uncertainty filter. No team residual or uncertainty integration is implemented. "
        "Map outcomes train a logistic likelihood; each unordered team-pair/day totals weight one to limit series dependence. "
        "One pooled positive scale multiplies Elo's logit; no intercept, so predictions reverse on swapping teams.",
        "",
        "Event blocks are league/year with breaks longer than 21 days. Corrections are frozen at event start; "
        "existing Elo still learns from previous days inside that event. Same-day results never enter that day's forecasts. "
        "Known 2026 qualifier/regional-final days and EWC outside the matched main-event window are excluded using market metadata, "
        "never prices or market outcomes. Other historical event labels inherit OE limitations. "
        "Entry is based on first eligible cross-region game day, not bracket round or every same-region game.",
        "",
        "Training is cross-region international-labelled maps. Same-home-region forecasts and all domestic/non-international routes "
        "are unchanged by construction; this is not a production benchmark-gate run. Series odds keep current rho. "
        "Series format and diagnostic fixture provenance retain their retrospective limitations. "
        "Kalshi fitting inputs are never used. Primary market endpoint is 12h on the fixed cohort; close is separate. "
        "2026 prices cover four previously viewed events and no Worlds. No prospective market-beating claim.",
        "",
        f"Eligible maps: {len(games)}; event blocks: {games.event_id.nunique()}; missing-home/same-region exclusions: {len(excluded)}.",
        "",
        "## Settings chosen through 2021",
        "",
        "| Variant | Ridge | Half-life (days) | Earlier-event tuning LL |",
        "|---|---:|---:|---:|",
    ]
    for name, penalty, half_life, _ in chosen:
        loss = game_losses(games.loc[train, name], games.loc[train, "won"])[
            "log_loss"
        ].mean()
        lines.append(f"| {name} | {penalty:g} | {half_life:g} | {loss:.5f} |")
    lines += [
        "",
        "## Chronological maps",
        "",
        *game_table(games, names),
        "",
        "## Fixed market cohort",
        "",
        *market_table(series, maps, names),
        "",
    ]
    args.export.mkdir(parents=True, exist_ok=True)
    games.to_csv(args.export / "games.csv", index=False)
    series.to_csv(args.export / "series.csv", index=False)
    maps.to_csv(args.export / "map1.csv", index=False)
    excluded.to_csv(args.export / "excluded_games.csv", index=False)

    # Infinity serialized as a string for interoperable provenance.
    def clean(value):
        if isinstance(value, float) and not np.isfinite(value):
            return "infinite"
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value]
        return value

    audit = clean(
        {
            "choices": chosen,
            "grid": tuning,
            "models": all_models,
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "base_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "price_cohort_sha256": hashlib.sha256(
                Path("data/markets/frames.pkl").read_bytes()
            ).hexdigest(),
            "baseline_slope": schedule.CROSS_REGION_ELO_WEIGHT,
            "tune_end": TUNE_END,
            "db_end": str(timeline.date.max()),
        }
    )
    (args.export / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {args.out}, {audit['runtime_seconds']}s", flush=True)


if __name__ == "__main__":
    main()
