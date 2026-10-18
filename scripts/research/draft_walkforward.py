"""
draft_walkforward.py: walk-forward backtest of the four-feature draft model (v2).

For each test year Y in TEST_YEARS, the draft model is fit only on games from
FIT_FROM to Y - 1 and scores year Y, so every scored game is out of sample for
the model that scored it. The draft is a shift on top of the production map
call: FORGE within a league, regionally calibrated Elo across leagues
(`schedule.game_probability` with ratings from games before the match day, as
the Predictions page and the market benchmark build it).

Features (blue minus red, summed over the five roles), from games on earlier
UTC days only (never the match day, as a live call would know them), read from
the full roster (`match_players`, so games without lane snapshots, most of the
LPL among them, count):

- `exp`: log(1 + the player's earlier pro games on the champion);
- `meta`: the champion in that role, every player, the META_DAYS before the
  day: sum(result - p) / (n + SHRINK_META), p the Elo chance;
- `matchup`: the champion against the opposing champion in the same role, every
  earlier day: sum(result - p) / (n + SHRINK_PAIR);
- `synergy`: the team's ten champion-role pairs, every earlier day, each
  sum(team result - p) / (n + SHRINK_PAIR), summed.

The four were chosen after the first draft study and a second one
(`docs/research/forecast-followup-2026-10-17/`) had viewed 2025-2026; test years
before 2025 played no part in that choice.

Compared, on the same games: the production call; FORGE recalibrated (a
logistic fit of the result on its log-odds, same training years); and FORGE +
draft. The draft's gain is FORGE + draft against recalibrated FORGE. Each
feature's part is the full model against the model without it. Intervals
resample series (league, UTC day, team pair).

    uv run python scripts/research/draft_walkforward.py --out docs/research/draft_walkforward.md

The production calls are cached in `data/research/draft_v2/forge.pkl`
(about 7 minutes to build).

**Against Kalshi, split in time.** Every settled Kalshi map market matched to its
OE game (`evaluate_live.match_oe_game`), with the walk-forward draft shift (each
map's from the model fit before its year). At each entry (60 s before the start,
after the draft; 45 s after it, when Riot's feed has the picks) our chance is
Kalshi's last trade moved by the shift in log-odds (weight 1, nothing fitted on
these maps). Bets: $1 on a side when that beats the last traded cost of backing
it (within 10 minutes) by the edge, after the taker fee. The edge is chosen on
maps before SPLIT (highest flat return) and scored unchanged on maps from SPLIT;
the result on Kalshi's log-odds and the shift is fit on each half.
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from prometheus import DB_PATH, schedule
from prometheus.evaluation import game_losses, resamples
from prometheus.types import INTERNATIONAL_LEAGUES

CACHE = ROOT / "data" / "research" / "draft_v2"
FIT_FROM = 2019
TEST_YEARS = range(2021, 2027)
FEATURES = ["exp", "meta", "matchup", "synergy"]
SHRINK_META = 50
META_DAYS = 60
SHRINK_PAIR = 20
MAJORS = {"LCK", "LPL", "LEC", "LCS"}
SPLIT = "2026-05-01"
ENTRIES = {"60 s before the start": -60, "45 s after the start": 45}
BET_EDGES = (0.02, 0.03, 0.05, 0.10)
N_RESAMPLES = 2000


def _log(message):
    print(message, flush=True)


# ---------------------------------------------------------------- rows


def load_rows(db=DB_PATH):
    """One row per player-game from the full roster: day, game, side, result,
    role, champion, and the Elo chance of the player's team."""
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        teams = pd.read_sql(
            "SELECT m.gameid, m.teamid, m.teamname, m.date, m.league, m.side,"
            " m.result, e.pre_match_elo AS elo FROM matches m JOIN game_length_elo e"
            " ON e.gameid=m.gameid AND e.teamid=m.teamid",
            conn,
        )
        players = pd.read_sql(
            "SELECT gameid, teamid, position, playerid, champion FROM match_players"
            " WHERE champion IS NOT NULL AND champion != ''",
            conn,
        )
    opp = teams[["gameid", "teamid", "elo"]].rename(
        columns={"teamid": "opp_teamid", "elo": "opp_elo"}
    )
    teams = teams.merge(opp, on="gameid")
    teams = teams[teams["teamid"] != teams["opp_teamid"]]
    teams["p"] = 1 / (1 + 10 ** (-(teams["elo"] - teams["opp_elo"]) / 400))
    teams["date"] = pd.to_datetime(teams["date"])
    rows = players.merge(teams, on=["gameid", "teamid"])
    rows["day"] = rows["date"].dt.normalize()
    rows["wae"] = rows["result"] - rows["p"]
    rows["one"] = 1.0
    return rows.sort_values(["date", "gameid", "teamid", "position"]).reset_index(
        drop=True
    )


def prior_days(frame, keys, values):
    """For each row, the sums of `values` over the same keys' rows on earlier
    days (the row's own day excluded)."""
    daily = (
        frame.groupby([*keys, "day"], sort=False)[values]
        .sum()
        .reset_index()
        .sort_values([*keys, "day"])
    )
    cum = daily.groupby(keys, sort=False)[values].cumsum() - daily[values]
    daily[[f"{v}_before" for v in values]] = cum.to_numpy()
    out = frame[[*keys, "day"]].merge(
        daily[[*keys, "day", *(f"{v}_before" for v in values)]],
        on=[*keys, "day"],
        how="left",
    )
    return out[[f"{v}_before" for v in values]].to_numpy()


def player_features(rows):
    """Adds exp, meta and matchup to each player-game; synergy per team-game."""
    rows = rows.copy()
    n = prior_days(rows, ["playerid", "champion"], ["one"])[:, 0]
    rows["exp"] = np.log1p(n)

    # Meta: the champion-role over the META_DAYS before the day.
    daily = (
        rows.groupby(["champion", "position", "day"])[["wae", "one"]]
        .sum()
        .reset_index()
    )
    parts = []
    for _, g in daily.groupby(["champion", "position"], sort=False):
        g = g.sort_values("day").set_index("day")
        rolled = g[["wae", "one"]].rolling(f"{META_DAYS}D", closed="left").sum()
        parts.append(
            g[["champion", "position"]].assign(
                meta=(rolled["wae"].fillna(0) / (rolled["one"].fillna(0) + SHRINK_META))
            )
        )
    meta = pd.concat(parts).reset_index()
    rows = rows.merge(meta, on=["champion", "position", "day"], how="left")

    # Matchup: against the champion in the same role on the other team.
    opp = rows[["gameid", "teamid", "position", "champion"]].rename(
        columns={"teamid": "lane_teamid", "champion": "opp_champion"}
    )
    lanes = rows.merge(opp, on=["gameid", "position"])
    lanes = lanes[lanes["teamid"] != lanes["lane_teamid"]]
    sums = prior_days(lanes, ["position", "champion", "opp_champion"], ["wae", "one"])
    lanes["matchup"] = sums[:, 0] / (sums[:, 1] + SHRINK_PAIR)
    rows = rows.merge(
        lanes[["gameid", "teamid", "position", "matchup"]],
        on=["gameid", "teamid", "position"],
        how="left",
    )
    rows["matchup"] = rows["matchup"].fillna(0.0)
    return rows


def synergy(rows):
    """Each team-game's sum over its ten champion-role pairs."""
    token = rows["position"] + ":" + rows["champion"]
    teams = (
        rows.assign(token=token)
        .groupby(["gameid", "teamid"], sort=False)
        .agg(day=("day", "first"), wae=("wae", "first"), tokens=("token", list))
        .reset_index()
    )
    teams = teams[teams["tokens"].map(len) == 5]
    pairs = teams.assign(
        pair=teams["tokens"].map(
            lambda t: [
                f"{a}|{b}" for i, a in enumerate(sorted(t)) for b in sorted(t)[i + 1 :]
            ]
        ),
        one=1.0,
    ).explode("pair")
    sums = prior_days(pairs, ["pair"], ["wae", "one"])
    pairs["value"] = sums[:, 0] / (sums[:, 1] + SHRINK_PAIR)
    return pairs.groupby(["gameid", "teamid"])["value"].sum().rename("synergy")


def game_table(rows, team_synergy):
    """One row per game, blue v red: result and the four draft differences."""
    side = (
        rows.groupby(["gameid", "teamid"], sort=False)
        .agg(
            date=("date", "first"),
            league=("league", "first"),
            side=("side", "first"),
            teamname=("teamname", "first"),
            result=("result", "first"),
            players=("champion", "size"),
            exp=("exp", "sum"),
            meta=("meta", "sum"),
            matchup=("matchup", "sum"),
        )
        .join(team_synergy)
        .reset_index()
    )
    blue = side[side["side"] == "Blue"].set_index("gameid")
    red = side[side["side"] == "Red"].set_index("gameid")
    both = blue.join(red, rsuffix="_red", how="inner")
    both = both[(both["players"] == 5) & (both["players_red"] == 5)]
    both = both.dropna(subset=["synergy", "synergy_red"])
    out = pd.DataFrame(
        {
            "date": both["date"],
            "year": both["date"].dt.year,
            "league": both["league"],
            "blue": both["teamname"],
            "red": both["teamname_red"],
            "won": both["result"].astype(int),
        },
        index=both.index,
    )
    for f in FEATURES:
        out[f] = both[f] - both[f"{f}_red"]
    pair = [tuple(sorted(x)) for x in zip(out["blue"], out["red"])]
    out["series"] = [
        f"{lg}|{d}|{a}|{b}"
        for lg, d, (a, b) in zip(out["league"], out["date"].dt.date, pair)
    ]
    return out.reset_index()


# ---------------------------------------------------------------- production call


def forge_calls(games, refresh=False):
    """The production map call for blue in every game (cached): ratings from
    games before the match day, `schedule.game_probability`."""
    path = CACHE / "forge.pkl"
    if path.exists() and not refresh:
        cached = pd.read_pickle(path)
        if set(games["gameid"]) <= set(cached["gameid"]):
            return cached
    from prometheus.form import load_states

    before = schedule.RatingsBefore(load_states())
    rows, started = [], time.monotonic()
    for i, (day, group) in enumerate(games.groupby(games["date"].dt.date), 1):
        ratings = before(day)
        for g in group.itertuples(index=False):
            if g.blue not in ratings.index or g.red not in ratings.index:
                continue
            p, method = schedule.game_probability(
                ratings.loc[g.blue],
                ratings.loc[g.red],
                event=g.league,
                title=g.league,
                at=day,
                event_day=g.date,
            )
            rows.append({"gameid": g.gameid, "p_forge": p, "method": method})
        if i % 250 == 0:
            _log(f"  {i} days ({time.monotonic() - started:.0f} s)")
    out = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_pickle(path)
    return out


# ---------------------------------------------------------------- walk-forward


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _fit(frame, cols):
    model = LogisticRegression(C=1e6, max_iter=1000)
    return model.fit(frame[cols].to_numpy(), frame["won"].to_numpy())


def walk_forward(games):
    """Each test year scored by models fit on earlier years only."""
    variants = {
        "forge_refit": ["forge_logit"],
        "draft": ["forge_logit", *FEATURES],
        **{
            f"without_{f}": ["forge_logit", *(x for x in FEATURES if x != f)]
            for f in FEATURES
        },
    }
    parts, coefs = [], {}
    for year in TEST_YEARS:
        train = games[games["year"].between(FIT_FROM, year - 1)]
        test = games[games["year"] == year].copy()
        if test.empty:
            continue
        for name, cols in variants.items():
            model = _fit(train, cols)
            test[name] = model.predict_proba(test[cols].to_numpy())[:, 1]
            if name == "draft":
                coefs[year] = dict(
                    zip(["intercept", *cols], [model.intercept_[0], *model.coef_[0]])
                )
                test["shift"] = model.decision_function(test[cols].to_numpy()) - _fit(
                    train, ["forge_logit"]
                ).decision_function(test[["forge_logit"]].to_numpy())
        parts.append(test)
    return pd.concat(parts, ignore_index=True), coefs


def paired(frame, a, b):
    """Mean log loss of a and b, a - b, and its 95% series-bootstrap interval."""
    la = game_losses(frame[a], frame["won"])["log_loss"].to_numpy()
    lb = game_losses(frame[b], frame["won"])["log_loss"].to_numpy()
    diff = la - lb
    codes = pd.factorize(frame["series"])[0]
    # Exact same series draws as resamples(groups, N_RESAMPLES), aggregated
    # before drawing: repeated row concatenation is avoidable. Keep the ratio
    # of row sums/counts so unequal-size series retain the original weighting.
    valid = codes >= 0
    totals = np.bincount(codes[valid], weights=diff[valid])
    sizes = np.bincount(codes[valid])
    rng = np.random.default_rng(0)  # resamples' unchanged default seed
    draws = []
    for _ in range(N_RESAMPLES):
        pick = rng.integers(0, len(sizes), len(sizes))
        draws.append(totals[pick].sum() / sizes[pick].sum())
    return la.mean(), lb.mean(), diff.mean(), *np.percentile(draws, [2.5, 97.5])


def slices(frame):
    yield "all", frame
    yield "major leagues", frame[frame["league"].isin(MAJORS)]
    yield "LPL", frame[frame["league"] == "LPL"]
    yield "international", frame[frame["league"].isin(INTERNATIONAL_LEAGUES)]
    yield (
        "other leagues",
        frame[
            ~frame["league"].isin(MAJORS) & ~frame["league"].isin(INTERNATIONAL_LEAGUES)
        ],
    )


def _ci(d, lo, hi):
    return f"{d:+.4f} ({lo:+.4f} to {hi:+.4f})"


def report(games, scored, coefs, counts):
    lines = [
        "# Draft model v2: walk-forward backtest",
        "",
        "Generated by `scripts/research/draft_walkforward.py` (protocol in its",
        "docstring). Each test year is scored by models fit on"
        f" {FIT_FROM} to the year before. Negative favours the first call.",
        "",
        f"Games with all ten champions, the four features and a production call: "
        f"{len(games):,} ({FIT_FROM}–{games['year'].max()}); scored "
        f"{len(scored):,} ({min(TEST_YEARS)}–{scored['year'].max()}). "
        + ", ".join(f"{k} {v:,}" for k, v in counts.items())
        + ".",
        "",
        "## FORGE + draft against FORGE",
        "",
        "| Slice | Games | Production LL | FORGE refit LL | + draft LL "
        "| Draft − FORGE refit (95%) | Draft − production (95%) |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for name, frame in slices(scored):
        if len(frame) < 100:
            continue
        a, b, d, lo, hi = paired(frame, "draft", "forge_refit")
        _, p, d2, lo2, hi2 = paired(frame, "draft", "p_forge")
        lines.append(
            f"| {name} | {len(frame):,} | {p:.4f} | {b:.4f} | {a:.4f} "
            f"| {_ci(d, lo, hi)} | {_ci(d2, lo2, hi2)} |"
        )
    lines += [
        "",
        "## By test year (all leagues)",
        "",
        "| Year | Games | FORGE refit LL | + draft LL | Draft − FORGE refit (95%) |",
        "|---:|---:|---:|---:|---|",
    ]
    for year in TEST_YEARS:
        frame = scored[scored["year"] == year]
        if frame.empty:
            continue
        a, b, d, lo, hi = paired(frame, "draft", "forge_refit")
        lines.append(
            f"| {year} | {len(frame):,} | {b:.4f} | {a:.4f} | {_ci(d, lo, hi)} |"
        )
    early = scored[scored["year"] < 2025]
    a, b, d, lo, hi = paired(early, "draft", "forge_refit")
    lines += [
        "",
        f"Test years before 2025 only (no part in choosing the features): "
        f"{len(early):,} games, draft − FORGE refit {_ci(d, lo, hi)}.",
        "",
        "## Each feature's part (all test years)",
        "",
        "Full draft model against the same model without the feature, each fit on",
        "the earlier years. Negative: the feature helps.",
        "",
        "| Feature | All (95%) | Major leagues (95%) | Before 2025 (95%) |",
        "|---|---|---|---|",
    ]
    majors = scored[scored["league"].isin(MAJORS)]
    for f in FEATURES:
        cells = [
            _ci(*paired(frame, "draft", f"without_{f}")[2:])
            for frame in (scored, majors, early)
        ]
        lines.append(f"| {f} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Weights by fit (draft model)",
        "",
        "| Test year | " + " | ".join(["intercept", "forge_logit", *FEATURES]) + " |",
        "|---:|" + "---:|" * (2 + len(FEATURES)),
    ]
    for year, c in coefs.items():
        lines.append(
            f"| {year} | "
            + " | ".join(
                f"{c[k]:+.3f}" for k in ["intercept", "forge_logit", *FEATURES]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- Kalshi


def kalshi_maps(scored, fetch=True):
    """Priced maps with the walk-forward shift and Kalshi at each entry (blue)."""
    import json

    sys.path.insert(0, str(ROOT / "scripts"))
    import evaluate_live as el

    from prometheus import markets
    from prometheus.elo import get_latest_elos

    matcher = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **markets.MARKET_ALIASES},
    )
    by_pair = dict(list(el.oe_games().groupby(["blue", "red"])))
    cutoff = markets.get("/historical/cutoff")["trades_created_ts"] if fetch else ""
    keyed = scored.set_index("gameid")
    rows = []
    for event in markets.events(json.loads(el.MARKET_LIST.read_text())):
        hit = el.match_oe_game(event, matcher, by_pair)
        if hit is None or hit[0]["gameid"] not in keyed.index:
            continue
        game, blue_is_team1 = hit
        at = game["date"]
        tp = el.tape(event, el.premap_trades(event, at, cutoff, fetch), blue_is_team1)
        g = keyed.loc[game["gameid"]]
        row = {
            "gameid": game["gameid"],
            "day": at.date().isoformat(),
            "series": g["series"],
            "league": g["league"],
            "won": int(g["won"]),
            "shift": g["shift"],
            "p_close": el.price_at(
                tp, at + pd.Timedelta(minutes=3), stale=el.PRE_STALE
            ),
        }
        for label, offset in ENTRIES.items():
            t = at + pd.Timedelta(seconds=offset)
            row[f"{label}|p"] = el.price_at(tp, t, stale=el.PRE_STALE)
            row[f"{label}|cost0"] = el.cost_to_back(tp, t, 0, stale=el.PRE_STALE)
            row[f"{label}|cost1"] = el.cost_to_back(tp, t, 1, stale=el.PRE_STALE)
        rows.append(row)
    return pd.DataFrame(rows)


def _bets_frame(frame, label):
    p = 1 / (1 + np.exp(-(_logit(frame[f"{label}|p"]) + frame["shift"])))
    return pd.DataFrame(
        {
            "series": frame["series"],
            "game": frame["gameid"],
            "won": frame["won"],
            "p": p,
            "cost0": frame[f"{label}|cost0"],
            "cost1": frame[f"{label}|cost1"],
            "p_start": frame["p_close"],
        }
    )


def _weights(frame, label):
    x = np.column_stack([_logit(frame[f"{label}|p"]), frame["shift"]])
    y = frame["won"].to_numpy()
    model = LogisticRegression(C=1e6, fit_intercept=False)
    point = model.fit(x, y).coef_[0]
    codes = pd.factorize(frame["series"])[0]
    groups = [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]
    draws = np.array(
        [
            model.fit(x[i], y[i]).coef_[0]
            for i in resamples(groups, 1000)
            if len(set(y[i])) == 2
        ]
    )
    lo, hi = np.percentile(draws[:, 1], [2.5, 97.5])
    return point[1], lo, hi


def kalshi_section(maps):
    import evaluate_live as el

    lines = [
        "",
        "## Against Kalshi, split in time",
        "",
        f"{len(maps):,} priced maps matched to OE games; first half before {SPLIT}, "
        "second half from it. Our chance: Kalshi's price plus the walk-forward draft"
        " shift. The edge is chosen on the first half and scored unchanged on the"
        " second. Shift weight: the result on Kalshi's log-odds and the shift (no"
        " intercept); above 0 means Kalshi's price misses part of the draft.",
    ]
    for label in ENTRIES:
        f = maps[maps[f"{label}|p"].between(0.001, 0.999)]
        first, second = f[f["day"] < SPLIT], f[f["day"] >= SPLIT]
        if len(first) < 100 or len(second) < 100:
            lines += ["", f"{label}: too few maps ({len(first)} / {len(second)})."]
            continue
        rows = []
        for edge in BET_EDGES:
            s1 = el.bet_summary(el.premap_bets(_bets_frame(first, label), edge))
            s2 = el.bet_summary(el.premap_bets(_bets_frame(second, label), edge))
            rows.append((edge, s1, s2))
        chosen = max(rows, key=lambda r: r[1]["roi"][0] if r[1] else -9)[0]
        lines += [
            "",
            f"### {label}",
            "",
            "| Half | Maps | Shift weight (95%) |",
            "|---|---:|---|",
        ]
        for name, part in (("first", first), ("second", second)):
            w, lo, hi = _weights(part, label)
            lines.append(
                f"| {name} | {len(part):,} | {w:+.2f} ({lo:+.2f} to {hi:+.2f}) |"
            )
        lines += [
            "",
            "| Edge | Half | Bets | Won | Flat ROI (95%) | Kelly growth/bet (95%) | Kelly multiple | CLV (3 min) |",
            "|---:|---|---:|---:|---|---|---:|---:|",
        ]
        for edge, s1, s2 in rows:
            for name, s in (("first", s1), ("second", s2)):
                if s is None:
                    continue
                mark = " **(chosen)**" if edge == chosen and name == "second" else ""
                clv = "" if s["clv"] is None else f"{s['clv'] * 100:+.1f}"
                lines.append(
                    f"| {edge:.2f}{mark} | {name} | {s['n']} | {s['won']:.1%} "
                    f"| {_ci(*s['roi'])} | {_ci(*s['growth'])} | {s['multiple']:.2f} | {clv} |"
                )
    return lines


def build(refresh=False):
    """(games with the four features and the production call, counts)."""
    started = time.monotonic()
    rows = player_features(load_rows())
    games = game_table(rows, synergy(rows))
    _log(f"features: {len(games):,} games ({time.monotonic() - started:.0f} s)")
    games = games[games["year"] >= FIT_FROM]
    forge = forge_calls(games, refresh)
    counts = {"with ten champions": len(games)}
    games = games.merge(forge, on="gameid")
    counts["with a production call"] = len(games)
    games["forge_logit"] = _logit(games["p_forge"])
    return games, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--refresh", action="store_true", help="rebuild FORGE calls")
    parser.add_argument("--no-kalshi", action="store_true")
    parser.add_argument("--offline", action="store_true", help="cached trades only")
    args = parser.parse_args()
    games, counts = build(args.refresh)
    scored, coefs = walk_forward(games)
    text = report(games, scored, coefs, counts)
    if not args.no_kalshi:
        maps = kalshi_maps(scored, fetch=not args.offline)
        maps.to_pickle(CACHE / "kalshi_maps.pkl")
        text += "\n".join(kalshi_section(maps)) + "\n"
    if args.out:
        args.out.write_text(text)
        _log(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
