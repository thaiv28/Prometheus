"""
train_time_model_v2.py: refit the live map model with Riot feed timelines.

v1 (`prometheus/live/time_model_v1.json`, `train_time_model.py`) was fit on 1,778
gol.gg maps. This adds every map `feed_timelines.py` saved, joined to Oracle's
Elixir for the result and Elo, and keeps v1's features, fit and calibration
(`train_time_model.fit`). Fixed protocol, declared before scoring:

- **Rows.** Feed maps: one row per minute sample, the clock estimated as the
  live page does (seconds since 2,500/2,500 gold, paused samples removed); Elo
  from before the series (as the live page has it). gol.gg maps through 2024
  (exact minutes), unless the feed has the same map.
- **Partitions.** Train through 2024; calibrate January-June 2025; test July
  2025 on (feed maps only, so the test is what the live page sees).
- **Adoption.** v2 replaces v1 when its log loss on the test maps is lower with
  a 95% series-bootstrap interval below zero. The series shift
  (`live.series.map_shift`) is then checked on the test's maps 2+ with the
  adopted model.

    uv run python scripts/research/train_time_model_v2.py \\
        --feed data/feed_timelines --gol data/gol_training \\
        --out data/research/time_model_v2 --report docs/research/time_model_v2.md
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_time_model import delta, fit, metrics, score
from train_time_model import load as load_gol

from prometheus import gamelog
from prometheus.form import load_states
from prometheus.live.series import map_shift
from prometheus.live.timeline import FEATURES, features, predict
from prometheus.schedule import series_rho

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "prometheus" / "live" / "time_model_v1.json"
TRAIN_END = "2025-01-01"
CALIBRATION_END = "2025-07-01"
JOIN_MINUTES = 10  # feed start vs Oracle's Elixir game time
CLOSE_SECONDS = 180  # within this, one team's name is enough
STEP = 60  # feed_timelines.STEP
MAJORS = {"LCK", "LPL", "LEC", "LCS", "LTA N", "LTA S", "LTA", "CBLOL", "LCP"}
INTERNATIONAL = {"Worlds", "MSI", "FST", "EWC"}


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def normal(name):
    name = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    for word in ("esports", "gaming", "team", "club"):
        name = name.replace(word, "")
    return name


def same_team(riot, oe):
    """Loose name match: one normalized name inside the other, or the code."""
    a, b = normal(riot.get("name")), normal(oe)
    code = normal(riot.get("code"))
    return bool(a and b and (a in b or b in a)) or bool(code and code == b)


def clock(samples, start):
    """Estimated seconds per sample (None while paused).

    The feed marks pauses (`gameState` "paused", one frozen frame repeated); a
    sample whose own ten seconds kept flat gold counts too. Each pause runs from
    its first paused sample to the next in-game one (to within a sample).
    """
    out, paused, since = [], 0.0, None
    for s in samples:
        t = when(s["at"])
        if s.get("state") == "paused" or s["flat"]:
            since = since or t
            out.append(None)
            continue
        if since is not None:
            paused += (t - since).total_seconds()
            since = None
        out.append((t - start).total_seconds() - paused)
    return out


def team_games():
    """Both sides of every OE game: date, names, side, result, series, and the
    series' first-map Elo and FORGE call (what the live page has before map 1)."""
    g = gamelog.add_series(gamelog.add_calls(gamelog.load_team_games(), load_states()))
    g = g.sort_values(["when", "gameid"], kind="mergesort")
    first = g.groupby("series").first()
    g["series_elo"] = g["series"].map(first["elo_pre"])
    g["series_p"] = g["series"].map(first["p"])
    g["k"] = g.groupby("series").cumcount() + 1
    return g


def join(maps, g):
    """(rows, report): feed maps with OE's result and pre-series Elo."""
    g = g.dropna(subset=["series_elo"]).copy()
    g["t"] = pd.to_datetime(g["date"])  # UTC, naive
    by_time = g.sort_values("t")
    times = by_time["t"].to_numpy()
    joined, why = [], {}
    for m in maps:
        if m.get("error") or not m.get("start"):
            key = m.get("error") or "no start"
            why[key] = why.get(key, 0) + 1
            continue
        start = pd.Timestamp(when(m["start"])).tz_convert(None)
        lo = np.searchsorted(
            times, (start - pd.Timedelta(minutes=JOIN_MINUTES)).to_datetime64()
        )
        hi = np.searchsorted(
            times, (start + pd.Timedelta(minutes=JOIN_MINUTES)).to_datetime64()
        )
        near = by_time.iloc[lo:hi]
        # getEventDetails' sides are not reliable (often swapped); the feed's
        # blueTeam frames and Oracle's Elixir's sides agree, so match the pair
        # either way round and take the sides from Oracle's Elixir.
        a, b = m["teams"]
        hits = []
        for gameid, rows in near.groupby("gameid"):
            sides = {r.side: r for r in rows.itertuples()}
            if not {"Blue", "Red"} <= set(sides):
                continue
            blue_name, red_name = sides["Blue"].teamname, sides["Red"].teamname
            gap = abs((sides["Blue"].t - start).total_seconds())
            both = (same_team(a, blue_name) and same_team(b, red_name)) or (
                same_team(b, blue_name) and same_team(a, red_name)
            )
            # A renamed team (sponsor names) still matches when the start times
            # agree to within minutes and the other team's name matches.
            one = gap <= CLOSE_SECONDS and any(
                same_team(t, n) for t in (a, b) for n in (blue_name, red_name)
            )
            if both or one:
                hits.append((gap, gameid, sides))
        if len(hits) != 1:
            key = "no OE game" if not hits else "several OE games"
            why[key] = why.get(key, 0) + 1
            continue
        _, gameid, sides = hits[0]
        b, r = sides["Blue"], sides["Red"]
        blue_id = m.get("blue_id")
        if blue_id and blue_id not in {t["id"] for t in m["teams"]}:
            why["feed blue team not in match"] = (
                why.get("feed blue team not in match", 0) + 1
            )
            continue
        joined.append(
            dict(
                m,
                oe_gameid=gameid,
                won=int(b.result),
                blue_elo=float(b.series_elo),
                red_elo=float(r.series_elo),
                series_key=f"{min(b.teamname, r.teamname)}|{max(b.teamname, r.teamname)}|{b.date[:10]}",
                k=int(b.k),
                gamelength=int(b.gamelength),
                year=int(b.year),
                date=b.date,
            )
        )
    return joined, why


def series_before(g):
    """{(gameid, team): (maps won, maps lost) earlier in its series}, from every OE map."""
    out = {}
    for _, rows in g.groupby("series"):
        won = lost = 0
        for r in rows.itertuples():
            out[(r.gameid, r.teamname)] = (won, lost)
            won += int(r.result)
            lost += 1 - int(r.result)
    return out


def feed_rows(joined):
    rows, errors = [], []
    for m in joined:
        start = when(m["start"])
        seconds = clock(m["samples"], start)
        valid = [x for x in seconds if x is not None]
        if valid:
            errors.append(valid[-1] - m["gamelength"])
        for s, sec in zip(m["samples"], seconds):
            if sec is None or sec < 0 or s["state"] != "in_game":
                continue
            bg, rg = s["blue"]["gold"], s["red"]["gold"]
            if not bg or not rg or bg <= 0 or rg <= 0:
                continue
            rows.append(
                {
                    "game_id": m["oe_gameid"],
                    "series": m["series_key"],
                    "year": m["year"],
                    "date": m["date"],
                    "league": m["league"],
                    "seconds": sec,
                    "blue_gold": bg,
                    "red_gold": rg,
                    "blue_elo": m["blue_elo"],
                    "red_elo": m["red_elo"],
                    "won": m["won"],
                    "source": "feed",
                }
            )
    return pd.DataFrame(rows), np.array(errors)


def gol_rows(source, feed_ids):
    data, _, _ = load_gol(source)
    data = data[(data["year"] <= 2024) & ~data["game_id"].isin(feed_ids)].copy()
    data["seconds"] = data["minute"] * 60.0
    data["source"] = "gol"
    return data.drop(columns=["gol_id", "minute"])


def add_features(data):
    x = np.array(
        [
            features(
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
            )
            for r in data.itertuples()
        ]
    )
    for i, name in enumerate(FEATURES):
        data[name] = x[:, i]
    data["minute"] = (data["seconds"] // 60).astype(int)
    return data


def model_json(fitted, high, years):
    scaler, base, cal = fitted
    return {
        "schema": "time_gold_elo_v1",
        "features": FEATURES,
        "supported_seconds": [0, high * 60],
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": base.coef_[0].tolist(),
        "intercept": float(base.intercept_[0]),
        "calibration_slope": float(cal.coef_[0, 0]),
        "calibration_intercept": float(cal.intercept_[0]),
        "mode": "research",
        "version": 2,
        "trained_years": years,
        "calibration_period": [TRAIN_END, CALIBRATION_END],
        "test_from": CALIBRATION_END,
        "sources": [
            "feed.lolesports.com timelines (estimated clock)",
            "gol.gg timelines through 2024",
        ],
        "subminute_validated": False,
    }


def calls(model, data):
    return np.array(
        [
            predict(
                model,
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
            )
            for r in data.itertuples()
        ]
    )


def ci(d, digits=4):
    lo, hi = d["interval"]
    return f"{d['delta']:+.{digits}f} ({lo:+.{digits}f} to {hi:+.{digits}f})"


def partitions(feed_dir, gol_dir, min_maps=30):
    """The fixed split every live-model refit shares (v2, v3): feed maps joined to
    Oracle's Elixir plus gol.gg maps through 2024, partitioned by date, cut to the
    minutes every partition covers with `min_maps` maps."""
    maps = [
        json.loads(p.read_text()) for p in sorted((feed_dir / "games").glob("*.json"))
    ]
    g = team_games()
    joined, why = join(maps, g)
    feed, clock_error = feed_rows(joined)
    gol = gol_rows(gol_dir, set(feed["game_id"]))
    data = add_features(pd.concat([feed, gol], ignore_index=True))
    # gol.gg dates carry an offset, Oracle's Elixir's are naive UTC.
    when_ = pd.to_datetime(data["date"], utc=True, format="mixed").dt.tz_convert(None)
    train = data[when_ < TRAIN_END].copy()
    calibration = data[
        (when_ >= TRAIN_END) & (when_ < CALIBRATION_END) & (data.source == "feed")
    ].copy()
    test = data[(when_ >= CALIBRATION_END) & (data.source == "feed")].copy()
    counts = [p.groupby("minute").game_id.nunique() for p in (train, calibration, test)]
    high = 0
    while all(c.get(high + 1, 0) >= min_maps for c in counts) and high < 40:
        high += 1
    if high < 20:
        raise ValueError(f"under {min_maps} maps a minute before minute 20")
    train, calibration, test = (
        p[p.seconds <= high * 60].copy() for p in (train, calibration, test)
    )
    return {
        "maps": maps,
        "g": g,
        "joined": joined,
        "why": why,
        "clock_error": clock_error,
        "data": data,
        "train": train,
        "calibration": calibration,
        "test": test,
        "high": high,
    }


def run(args):
    parts = partitions(args.feed, args.gol, args.min_maps)
    maps, g, joined, why = parts["maps"], parts["g"], parts["joined"], parts["why"]
    clock_error, data, high = parts["clock_error"], parts["data"], parts["high"]
    train, calibration, test = parts["train"], parts["calibration"], parts["test"]

    fitted = fit(train, calibration, FEATURES)
    model = model_json(fitted, high, sorted(train.year.unique().tolist()))
    p2 = score(fitted, test, FEATURES)
    if not np.allclose(p2, calls(model, test), atol=1e-9):
        raise ValueError("export mismatch")
    v1 = json.loads(V1.read_text())
    in_v1 = test.seconds <= v1["supported_seconds"][1]
    p1 = np.full(len(test), np.nan)
    p1[in_v1.to_numpy()] = calls(v1, test[in_v1])
    shared = test[in_v1.to_numpy()]
    paired = delta(shared, p2[in_v1.to_numpy()], p1[in_v1.to_numpy()])
    adopt = paired["interval"][1] < 0

    parts = []
    for label, lo, hi in (
        ("0–10", 0, 600),
        ("10–20", 600, 1200),
        ("20–30", 1200, 1800),
        ("30+", 1800, 1e9),
    ):
        mask = ((shared.seconds >= lo) & (shared.seconds < hi)).to_numpy()
        if mask.sum() and shared[mask].game_id.nunique() >= 30:
            parts.append(
                (
                    label,
                    shared[mask],
                    p2[in_v1.to_numpy()][mask],
                    p1[in_v1.to_numpy()][mask],
                )
            )
    tiers = []
    tier = shared.league.map(
        lambda lg: (
            "International"
            if lg in INTERNATIONAL
            else ("Major league" if lg in MAJORS else "Other")
        )
    )
    for name in ("Major league", "International", "Other"):
        mask = (tier == name).to_numpy()
        if shared[mask].game_id.nunique() >= 30:
            tiers.append(
                (
                    name,
                    shared[mask],
                    p2[in_v1.to_numpy()][mask],
                    p1[in_v1.to_numpy()][mask],
                )
            )

    # The series shift on the test's maps 2+ with the model the page will use.
    used = model if adopt else v1
    before = series_before(g)
    blue_rows = g[g.side == "Blue"].set_index("gameid")
    shift = {}
    for gid in shared.game_id.unique():
        r = blue_rows.loc[gid]
        won, lost = before[(gid, r.teamname)]
        if won + lost == 0 or not np.isfinite(r.series_p):
            continue
        rho = series_rho(r.home, r.opp_home)
        shift[gid] = map_shift(float(r.series_p), rho, won, lost)
    shift = pd.Series(shift, dtype=float)
    later = shared[shared.game_id.isin(shift.index)].copy()
    q = calls(used, later)
    shifted = 1 / (
        1 + np.exp(-(np.log(q / (1 - q)) + later.game_id.map(shift).to_numpy()))
    )
    shift_delta = delta(later, shifted, q) if len(later) else None

    lines = [
        "# Live map model v2: Riot feed timelines",
        "",
        f"Generated by `scripts/research/train_time_model_v2.py` on {date.today().isoformat()}.",
        "",
        f"Feed maps saved: {len(maps):,}; joined to Oracle's Elixir: {len(joined):,}"
        + (
            f" (not joined: {', '.join(f'{k} {v:,}' for k, v in sorted(why.items()))})"
            if why
            else ""
        )
        + ".",
        f"Estimated clock at a map's last sample minus Oracle's Elixir's game length: median {np.median(clock_error):+.0f} s, "
        f"middle 90% {np.percentile(clock_error, 5):+.0f} to {np.percentile(clock_error, 95):+.0f} s "
        "(the last sample is up to a minute before the end).",
        "",
        "| Partition | Maps | Rows | Sources |",
        "|---|---|---|---|",
    ]
    for name, part in (
        ("Train (to 2024)", train),
        ("Calibrate (2025 H1)", calibration),
        ("Test (2025 H2 on)", test),
    ):
        src = part.groupby("source").game_id.nunique().to_dict()
        lines.append(
            f"| {name} | {part.game_id.nunique():,} | {len(part):,} | {', '.join(f'{k} {v:,}' for k, v in src.items())} |"
        )
    lines += [
        "",
        f"Supported clock: 0–{high} minutes (at least {args.min_maps} maps a minute in every partition).",
        "",
        "## v2 against v1 on the test maps",
        "",
        "Log loss per map (each map's rows weighted equally), v2 minus v1; negative is better; 95% intervals resample whole series. "
        f"Rows within v1's range (0–{v1['supported_seconds'][1] // 60} minutes).",
        "",
        "| Slice | Maps | v1 LL | v2 LL | v2 − v1 |",
        "|---|---|---|---|---|",
        f"| All | {shared.game_id.nunique():,} | {metrics(shared, p1[in_v1.to_numpy()])['log_loss']:.4f} | "
        f"{metrics(shared, p2[in_v1.to_numpy()])['log_loss']:.4f} | {ci(paired)} |",
    ]
    for label, part, a, b in parts:
        lines.append(
            f"| Minutes {label} | {part.game_id.nunique():,} | {metrics(part, b)['log_loss']:.4f} | {metrics(part, a)['log_loss']:.4f} | {ci(delta(part, a, b))} |"
        )
    for label, part, a, b in tiers:
        lines.append(
            f"| {label} | {part.game_id.nunique():,} | {metrics(part, b)['log_loss']:.4f} | {metrics(part, a)['log_loss']:.4f} | {ci(delta(part, a, b))} |"
        )
    lines += [
        "",
        f"**Adopted: {'yes' if adopt else 'no'}** (rule: the all-maps interval is below zero).",
        "",
        "## Series shift on the test's maps 2+",
        "",
        f"With {'v2' if adopt else 'v1'}, each map 2+ call shifted by `live.series.map_shift` (the FORGE call before map 1 and "
        "`schedule.series_rho`), against the same calls unshifted.",
        "",
    ]
    if shift_delta:
        lines.append(
            f"{later.game_id.nunique():,} maps: log loss change {ci(shift_delta)}."
        )
        size = later.drop_duplicates("game_id").game_id.map(shift).abs()
        lines += [
            f"Median shift {size.median():.3f} log-odds (90th percentile {size.quantile(0.9):.3f}).",
            "",
            "| Slice | Maps | Shift minus none |",
            "|---|---|---|",
        ]
        tier_later = later.league.map(
            lambda lg: (
                "International"
                if lg in INTERNATIONAL
                else ("Major league" if lg in MAJORS else "Other")
            )
        )
        slices = [
            (
                f"Minutes {label}",
                ((later.seconds >= lo) & (later.seconds < hi)).to_numpy(),
            )
            for label, lo, hi in (
                ("0–10", 0, 600),
                ("10–20", 600, 1200),
                ("20+", 1200, 1e9),
            )
        ] + [
            (name, (tier_later == name).to_numpy())
            for name in ("Major league", "International", "Other")
        ]
        for label, mask in slices:
            if later[mask].game_id.nunique() >= 30:
                lines.append(
                    f"| {label} | {later[mask].game_id.nunique():,} | "
                    f"{ci(delta(later[mask], shifted[mask], q[mask]))} |"
                )
    else:
        lines.append("No maps 2+ in the test.")
    text = "\n".join(lines) + "\n"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model.json").write_text(json.dumps(model, indent=2) + "\n")
    data.to_csv(args.out / "rows.csv", index=False)
    if args.report:
        args.report.write_text(text)
    print(text)
    return adopt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, default=ROOT / "data" / "feed_timelines")
    parser.add_argument("--gol", type=Path, default=ROOT / "data" / "gol_training")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "data" / "research" / "time_model_v2"
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--min-maps", type=int, default=30, help="maps a minute in every partition"
    )
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
