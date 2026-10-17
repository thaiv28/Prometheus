"""
draft_score.py: does the draft add to the pre-match call, and to Kalshi's price?

A map's draft, scored from each player's history on the champion they picked
and the champion's recent results, added to a pre-match Elo call. Protocol,
fixed before scoring:

- **Games.** Every Oracle's Elixir game with both teams' pre-match game-length
  Elo and all ten champions. Rows are blue v red (the intercept is the side).
- **Base.** Logistic fit of the result on the Elo log-odds (400-point curve) with
  an intercept (blue side), on 2019-2023.
- **Draft features**, blue minus red, summed over the five roles, each from
  strictly earlier games only (any league):
  - `exp`: log(1 + the player's earlier games on the champion);
  - `champ_wae`: the player's wins above Elo's expectation on the champion,
    shrunk: sum(result - p) / (n + 10);
  - `champ_gd15`: the player's lane gold difference at 15 minutes on the
    champion minus their own running average gold difference at 15 (thousands),
    shrunk: sum / (n + 10);
  - `meta`: the champion in that role, every player, the 60 days before:
    sum(result - p) / (n + 50).
- **Fit** base + draft on 2019-2023 (same rows as the base). **Development**
  2024; **test** 2025-2026 (held out; no constant changes after viewing it).
  Log loss head-to-head, paired, resampling series (a team pair in one league
  on one UTC day). Each feature alone on top of the base is reported, not
  selected.
- **Kalshi.** On the live benchmark's priced maps (`data/live_bench/`), our
  draft shift (draft model log-odds minus base log-odds) beside Kalshi's last
  trade at game start, and its relation to Kalshi's move from 12 minutes before
  the start (roughly before the draft) to the start.

Pre-match Elo here is the live rating (after any earlier game the same day),
not the published day-old call; OE's game time stands for the start.

    uv run python scripts/research/draft_score.py --out docs/research/draft_score.md

**Frozen model (prospective test).** `--freeze` fits base and draft + matchup +
synergy on every game from 2019 to the DB's last day and writes the weights,
constants, last day seen and this script's hash to `FROZEN` (refuses to
overwrite). `--prospective --out FILE` scores only games after that day with
those weights: log loss against Elo alone, and against Kalshi a minute before
the start (after the draft) and 45 s after it (when Riot's feed delivers the
picks), with paper bets on Kalshi's price plus the frozen shift.

    uv run python scripts/research/draft_score.py --freeze
    uv run python scripts/research/draft_score.py --prospective --out docs/research/draft_prospective.md
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from prometheus import DB_PATH, markets
from prometheus.evaluation import game_losses, resamples

FIT = (2019, 2023)
DEV = (2024, 2024)
TEST = (2025, 2026)
SHRINK_PLAYER = 10
SHRINK_META = 50
META_DAYS = 60
FEATURES = ["exp", "champ_wae", "champ_gd15", "meta"]
# Second round (exploratory: the test years were already viewed in round one).
SHRINK_PAIR = 20
INTERACTIONS = ["matchup", "synergy"]
N_RESAMPLES = 2000


def load_rows(db=DB_PATH):
    """One row per player-game: date, game, side, result, role, champion, lane
    gold difference at 15, and the Elo chance of the player's team."""
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        teams = pd.read_sql(
            "SELECT m.gameid, m.teamid, m.teamname, m.date, m.league, m.side, m.result,"
            " e.pre_match_elo AS elo FROM matches m JOIN game_length_elo e"
            " ON e.gameid=m.gameid AND e.teamid=m.teamid",
            conn,
        )
        players = pd.read_sql(
            "SELECT gameid, teamid, playerid, position, champion,"
            " goldat15 - opp_goldat15 AS gd15 FROM player_stats",
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
    rows = rows[rows["champion"].notna() & (rows["champion"] != "")]
    return rows.sort_values(["date", "gameid", "teamid", "position"]).reset_index(
        drop=True
    )


def _prior_sum(frame, keys, value):
    """Sum of `value` over the same keys' earlier rows (the row itself excluded)."""
    return frame.groupby(keys, sort=False)[value].cumsum() - frame[value]


def player_features(rows):
    """Adds exp, champ_wae, champ_gd15 and meta to each player-game, from
    earlier rows only."""
    rows = rows.copy()
    rows["one"] = 1.0
    rows["wae"] = rows["result"] - rows["p"]
    pc = ["playerid", "champion"]
    n = _prior_sum(rows, pc, "one")
    rows["exp"] = np.log1p(n)
    rows["champ_wae"] = _prior_sum(rows, pc, "wae") / (n + SHRINK_PLAYER)

    # Lane gold: against the player's own running average before this game.
    has = rows["gd15"].notna()
    gd = rows["gd15"].fillna(0) / 1000
    rows["gd_k"], rows["has_gd"] = gd, has.astype(float)
    seen = _prior_sum(rows, ["playerid"], "has_gd")
    mean_before = _prior_sum(rows, ["playerid"], "gd_k") / seen.replace(0, np.nan)
    rows["gd_resid"] = np.where(has & seen.gt(0), gd - mean_before, 0.0)
    rows["has_resid"] = (has & seen.gt(0)).astype(float)
    m = _prior_sum(rows, pc, "has_resid")
    rows["champ_gd15"] = _prior_sum(rows, pc, "gd_resid") / (m + SHRINK_PLAYER)

    # Meta: the champion in this role over the days before (all players).
    rows["meta"] = _meta(rows)
    return rows


def _meta(rows):
    """sum(result - p) / (n + SHRINK_META) for the champion and role over the
    META_DAYS before each game (games at the same moment excluded)."""
    out = np.zeros(len(rows))
    window = f"{META_DAYS}D"
    frame = rows[["date", "champion", "position", "wae", "one"]].assign(
        pos=np.arange(len(rows))
    )
    for _, g in frame.groupby(["champion", "position"], sort=False):
        g = g.set_index("date")
        s = g["wae"].rolling(window, closed="left").sum().fillna(0).to_numpy()
        c = g["one"].rolling(window, closed="left").sum().fillna(0).to_numpy()
        out[g["pos"].to_numpy()] = s / (c + SHRINK_META)
    return out


def interaction_features(rows):
    """Adds `matchup` (the champion against the opposing champion in the same
    role) and `synergy` (the team's ten champion-role pairs), each from every
    earlier game: sum(result - p) / (n + SHRINK_PAIR). `synergy` is the team's
    total, on every one of its rows."""
    rows = rows.copy()
    opp = rows[["gameid", "teamid", "position", "champion"]].rename(
        columns={"teamid": "lane_teamid", "champion": "opp_champion"}
    )
    lanes = rows.reset_index().merge(opp, on=["gameid", "position"])
    lanes = lanes[lanes["teamid"] != lanes["lane_teamid"]].set_index("index")
    lanes = lanes.loc[lanes.index.intersection(rows.index)].sort_index()
    key = ["position", "champion", "opp_champion"]
    n = _prior_sum(lanes, key, "one")
    rows["matchup"] = 0.0
    rows.loc[lanes.index, "matchup"] = (
        _prior_sum(lanes, key, "wae") / (n + SHRINK_PAIR)
    ).to_numpy()

    token = rows["position"] + ":" + rows["champion"]
    team = rows.assign(token=token).groupby(["gameid", "teamid"], sort=False)
    teams = team.agg(
        date=("date", "first"), wae=("wae", "first"), tokens=("token", list)
    )
    teams = teams[teams["tokens"].map(len) == 5].reset_index()
    pairs = teams.assign(
        pair=teams["tokens"].map(
            lambda t: [
                f"{a}|{b}" for i, a in enumerate(sorted(t)) for b in sorted(t)[i + 1 :]
            ]
        )
    ).explode("pair")
    pairs = pairs.sort_values(["date", "gameid"], kind="stable").assign(one=1.0)
    m = _prior_sum(pairs, ["pair"], "one")
    pairs["value"] = _prior_sum(pairs, ["pair"], "wae") / (m + SHRINK_PAIR)
    synergy = pairs.groupby(["gameid", "teamid"])["value"].sum().rename("synergy")
    rows = rows.merge(synergy, on=["gameid", "teamid"], how="left")
    rows["synergy"] = rows["synergy"].fillna(0.0)
    return rows


def game_table(rows):
    """One row per game, blue v red: result, Elo log-odds and draft differences."""
    side = rows.groupby(["gameid", "teamid"], sort=False).agg(
        date=("date", "first"),
        league=("league", "first"),
        side=("side", "first"),
        teamname=("teamname", "first"),
        result=("result", "first"),
        p=("p", "first"),
        players=("champion", "size"),
        **{f: (f, "sum") for f in FEATURES + ["matchup"]},
        synergy=("synergy", "first"),
    )
    side = side.reset_index()
    blue = side[side["side"] == "Blue"].set_index("gameid")
    red = side[side["side"] == "Red"].set_index("gameid")
    both = blue.join(red, rsuffix="_red", how="inner")
    both = both[(both["players"] == 5) & (both["players_red"] == 5)]
    out = pd.DataFrame(
        {
            "date": both["date"],
            "year": both["date"].dt.year,
            "league": both["league"],
            "blue": both["teamname"],
            "red": both["teamname_red"],
            "won": both["result"].astype(int),
            "elo_logit": _logit(both["p"]),
        },
        index=both.index,
    )
    for f in FEATURES + INTERACTIONS:
        out[f] = both[f] - both[f"{f}_red"]
    pair = [tuple(sorted(x)) for x in zip(out["blue"], out["red"])]
    out["series"] = [
        f"{lg}|{d}|{a}|{b}"
        for lg, d, (a, b) in zip(out["league"], out["date"].dt.date, pair)
    ]
    return out.reset_index()


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def fit(frame, cols):
    """Logistic fit (with intercept: blue side) on the given columns."""
    model = LogisticRegression(C=1e6, max_iter=1000)
    model.fit(frame[cols].to_numpy(), frame["won"].to_numpy())
    return model


def predict(model, frame, cols):
    return model.predict_proba(frame[cols].to_numpy())[:, 1]


def log_odds(model, frame, cols):
    return model.decision_function(frame[cols].to_numpy())


def paired(frame, a, b):
    """Mean log loss of a and b, and a - b with a 95% series-bootstrap interval."""
    la = game_losses(frame[a], frame["won"])["log_loss"].to_numpy()
    lb = game_losses(frame[b], frame["won"])["log_loss"].to_numpy()
    diff = la - lb
    codes = pd.factorize(frame["series"])[0]
    groups = [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]
    draws = [diff[i].mean() for i in resamples(groups, N_RESAMPLES)]
    return la.mean(), lb.mean(), diff.mean(), *np.percentile(draws, [2.5, 97.5])


def span(frame, years):
    return frame[frame["year"].between(*years)]


def evaluate(games):
    """Fit base, base + draft and base + each feature on FIT; score DEV and TEST."""
    base_cols = ["elo_logit"]
    variants = {"draft": base_cols + FEATURES}
    variants.update({f"+{f}": base_cols + [f] for f in FEATURES})
    draft_cols = base_cols + FEATURES
    variants.update(
        {
            "draft+matchup": draft_cols + ["matchup"],
            "draft+synergy": draft_cols + ["synergy"],
            "draft+both": draft_cols + INTERACTIONS,
        }
    )
    train = span(games, FIT)
    base = fit(train, base_cols)
    models = {name: fit(train, cols) for name, cols in variants.items()}
    scored = games.copy()
    scored["base"] = predict(base, scored, base_cols)
    scored["base_logit"] = log_odds(base, scored, base_cols)
    for name, cols in variants.items():
        scored[name] = predict(models[name], scored, cols)
    scored["draft_logit"] = log_odds(models["draft"], scored, variants["draft"])
    scored["shift"] = scored["draft_logit"] - scored["base_logit"]
    both_logit = log_odds(models["draft+both"], scored, variants["draft+both"])
    scored["shift_both"] = both_logit - scored["base_logit"]
    coefs = {
        name: dict(zip(["intercept", *cols], [m.intercept_[0], *m.coef_[0]]))
        for name, (m, cols) in {
            "base": (base, base_cols),
            **{n: (models[n], c) for n, c in variants.items()},
        }.items()
    }
    return scored, list(variants), coefs


MAJORS = {"LCK", "LPL", "LEC", "LCS", "WLDs", "MSI", "Worlds", "EWC", "FST"}


def reference(name):
    """What a variant is compared with: round-two variants with the draft score,
    the rest with the Elo-only base."""
    return "draft" if name.startswith("draft+") else "base"


def score_table(scored, names):
    lines = [
        "| Period | Slice | Games | Variant | Against | Reference LL | Variant LL "
        "| Variant − reference (95%) |",
        "|---|---|---:|---|---|---:|---:|---|",
    ]
    for label, years in (("development 2024", DEV), ("test 2025–26", TEST)):
        period = span(scored, years)
        for slice_name, pick in (
            ("all", period),
            ("major leagues", period[period["league"].isin(MAJORS)]),
        ):
            for name in names:
                ref = reference(name)
                v, r, d, lo, hi = paired(pick, name, ref)
                lines.append(
                    f"| {label} | {slice_name} | {len(pick):,} | {name} | {ref} "
                    f"| {r:.4f} | {v:.4f} | {d:+.4f} ({lo:+.4f} to {hi:+.4f}) |"
                )
    return lines


# ---------------------------------------------------------------- Kalshi


def priced_games(scored, fetch=True):
    """Every settled Kalshi map market matched to its OE game
    (`evaluate_live.build_premaps`), joined to our scored calls: Kalshi's last
    trade a minute before the start (after the draft) and 12 minutes before
    (about before it), for blue."""
    import evaluate_live as el

    from prometheus import schedule
    from prometheus.elo import get_latest_elos

    matcher = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **markets.MARKET_ALIASES},
    )
    events = markets.events(json.loads(el.MARKET_LIST.read_text()))
    cutoff = markets.get("/historical/cutoff")["trades_created_ts"] if fetch else ""
    premaps, counts = el.build_premaps(matcher, events, cutoff, fetch=fetch)
    print(counts, flush=True)
    pre = pd.DataFrame(
        [
            {"gameid": m["game"], **dict(zip(el.PREMAP_FIELDS, m["market"]))}
            for m in premaps
        ]
    )
    joined = pre.merge(scored, on="gameid")
    joined = joined[(joined["p_bet"] > 0) & (joined["p_bet"] < 1)]
    return joined.rename(columns={"p_bet": "kalshi", "p_before": "kalshi_before"})


EDGES = (0.0, 0.02, 0.03, 0.05, 0.10)


def market_bets(frame):
    """Paper bets a minute before the start: Kalshi's price moved by our draft
    shift (weight 1, nothing fitted on these maps), $1 on a side when that beats
    the last traded cost of backing it by the edge, after the taker fee; and
    quarter Kelly. CLV: Kalshi's price at the start minus the cost."""
    import evaluate_live as el

    lines = [
        "",
        "Paper bets a minute before the start: our chance is Kalshi's price plus"
        " the draft shift in log-odds (weight 1, not fitted here); $1 when it beats"
        " the last traded cost of a side by the edge, after Kalshi's taker fee."
        " Intervals resample series. CLV: the price at the start minus the cost, in"
        " points.",
        "",
        "| Shift | Edge | Bets | Won | Avg cost | Avg ours | Flat ROI (95%) "
        "| Kelly growth/bet (95%) | Kelly multiple | Max drawdown | CLV |",
        "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for label, col in (("draft", "shift"), ("draft + matchup + synergy", "shift_both")):
        p = 1 / (1 + np.exp(-(_logit(frame["kalshi"]) + frame[col])))
        pre = frame.assign(p=p, game=frame["gameid"], p_start=frame["p_start"])
        pre = pre.sort_values("date")
        for edge in EDGES:
            s = el.bet_summary(el.premap_bets(pre, edge))
            if s is None:
                continue
            clv = "" if s["clv"] is None else f"{s['clv'] * 100:+.1f}"
            lines.append(
                f"| {label} | {edge:.2f} | {s['n']} | {s['won']:.1%} | {s['cost']:.3f} "
                f"| {s['p']:.3f} | {_ci3(s['roi'])} | {_ci3(s['growth'], 4)} "
                f"| {s['multiple']:.2f} | {s['drawdown']:.0%} | {clv} |"
            )
    return lines


def _ci3(v, digits=3):
    point, lo, hi = v
    return f"{point:+.{digits}f} ({lo:+.{digits}f} to {hi:+.{digits}f})"


def kalshi_section(frame):
    if len(frame) < 30:
        return ["", f"Only {len(frame)} priced maps joined; not scored."]
    lines = [
        "",
        f"{len(frame)} priced maps ({frame['series'].nunique()} series), blue's chance.",
        "",
        "| Call | Log loss | − Kalshi a minute before the start (95%) |",
        "|---|---:|---|",
    ]
    for name in ("base", "draft", "draft+both"):
        a, _, d, lo, hi = paired(frame, name, "kalshi")
        lines.append(f"| {name} | {a:.4f} | {d:+.4f} ({lo:+.4f} to {hi:+.4f}) |")
    lines.append(
        f"| Kalshi a minute before | {game_losses(frame['kalshi'], frame['won'])['log_loss'].mean():.4f} | |"
    )
    y = frame["won"].to_numpy()
    codes = pd.factorize(frame["series"])[0]
    groups = [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]
    lines += [
        "",
        "Result on Kalshi's log-odds a minute before the start and a draft shift"
        " (ours minus Elo-only, log-odds; no intercept). A shift weight above 0"
        " means Kalshi's price misses part of what the draft score sees.",
        "",
        "| Shift | Kalshi weight (95%) | Shift weight (95%) |",
        "|---|---|---|",
    ]
    for label, col in (("draft", "shift"), ("draft + matchup + synergy", "shift_both")):
        x = np.column_stack([_logit(frame["kalshi"]), frame[col]])
        model = LogisticRegression(C=1e6, fit_intercept=False)
        point = model.fit(x, y).coef_[0]
        draws = np.array(
            [
                model.fit(x[i], y[i]).coef_[0]
                for i in resamples(groups, 1000)
                if len(set(y[i])) == 2
            ]
        )
        lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
        lines.append(
            f"| {label} | {point[0]:+.2f} ({lo[0]:+.2f} to {hi[0]:+.2f}) "
            f"| {point[1]:+.2f} ({lo[1]:+.2f} to {hi[1]:+.2f}) |"
        )
    lines += market_bets(frame)
    moved = frame.dropna(subset=["kalshi_before"])
    if len(moved) >= 30:
        move = _logit(moved["kalshi"]) - _logit(moved["kalshi_before"])
        r = np.corrcoef(move, moved["shift"])[0, 1]
        lines.append(
            f"\nOn {len(moved)} maps with a price 12 minutes before the start, the "
            "correlation of Kalshi's log-odds move from then to a minute before the"
            f" start with our draft shift is {r:+.2f}."
        )
    return lines


def report(games, scored, names, coefs, kalshi):
    lines = [
        "# Draft score",
        "",
        "Generated by `scripts/research/draft_score.py`. Protocol in the script's",
        "docstring (fixed before scoring). Blue v red; log loss of the blue result.",
        "",
        f"Games: {len(games):,} ({games['year'].min()}–{games['year'].max()}); fit "
        f"{FIT[0]}–{FIT[1]}: {len(span(games, FIT)):,}, development 2024: "
        f"{len(span(games, DEV)):,}, test 2025–26: {len(span(games, TEST)):,}.",
        "",
        "## Pre-match Elo + draft against pre-match Elo",
        "",
        *score_table(scored, names),
        "",
        "## Fitted weights",
        "",
        "| Variant | "
        + " | ".join(["intercept", "elo_logit", *FEATURES, *INTERACTIONS])
        + " |",
        "|---|" + "---:|" * (2 + len(FEATURES) + len(INTERACTIONS)),
    ]
    for name, c in coefs.items():
        cells = [c.get(k) for k in ["intercept", "elo_logit", *FEATURES, *INTERACTIONS]]
        lines.append(
            f"| {name} | "
            + " | ".join("" if v is None else f"{v:+.3f}" for v in cells)
            + " |"
        )
    sd = span(games, TEST)[FEATURES + INTERACTIONS].std()
    lines += [
        "",
        "Test-period standard deviation of each difference: "
        + ", ".join(f"{f} {sd[f]:.3f}" for f in FEATURES + INTERACTIONS)
        + ".",
        "",
        "## Against Kalshi (every priced map matched to its OE game)",
        *kalshi_section(kalshi),
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- frozen model

FROZEN = Path(__file__).with_name("draft_model_v1.json")
FROZEN_COLS = ["elo_logit", *FEATURES, *INTERACTIONS]
ENTRIES = {"60 s before the start": -60, "45 s after the start": 45}
PROSPECTIVE_EDGES = (0.02, 0.03, 0.05)


def all_games():
    rows = interaction_features(player_features(load_rows()))
    games = game_table(rows)
    return games[games["year"] >= FIT[0]]


def freeze(games, path=FROZEN):
    """Fit base and the full draft model on every game and write them."""
    import datetime as dt
    import hashlib

    if path.exists():
        raise SystemExit(f"{path.name} exists: a frozen model is never refit")
    base, draft = fit(games, ["elo_logit"]), fit(games, FROZEN_COLS)
    model = {
        "name": "draft_v1",
        "frozen_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fit_from": f"{FIT[0]}-01-01",
        "fit_through": str(games["date"].max().date()),
        "games": len(games),
        "base": {
            "columns": ["elo_logit"],
            "intercept": base.intercept_[0],
            "coef": list(base.coef_[0]),
        },
        "draft": {
            "columns": FROZEN_COLS,
            "intercept": draft.intercept_[0],
            "coef": list(draft.coef_[0]),
        },
        "constants": {
            "SHRINK_PLAYER": SHRINK_PLAYER,
            "SHRINK_META": SHRINK_META,
            "META_DAYS": META_DAYS,
            "SHRINK_PAIR": SHRINK_PAIR,
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    path.write_text(json.dumps(model, indent=2) + "\n")
    print(f"froze {path.name}: {len(games):,} games through {model['fit_through']}")


def frozen_logit(part, frame):
    cols = part["columns"]
    return part["intercept"] + frame[cols].to_numpy() @ np.asarray(part["coef"])


def prospective(games, out, fetch=True, path=FROZEN):
    """Score the frozen model on games after its last fit day."""
    import evaluate_live as el

    from prometheus import schedule
    from prometheus.elo import get_latest_elos

    model = json.loads(path.read_text())
    new = games[games["date"].dt.date.astype(str) > model["fit_through"]].copy()
    new["base_logit"] = frozen_logit(model["base"], new)
    new["shift"] = frozen_logit(model["draft"], new) - new["base_logit"]
    new["base"] = 1 / (1 + np.exp(-new["base_logit"]))
    new["draft"] = 1 / (1 + np.exp(-(new["base_logit"] + new["shift"])))
    lines = [
        "# Draft model v1, prospective",
        "",
        f"Frozen {model['frozen_at'][:10]} on {model['games']:,} games through "
        f"{model['fit_through']} (`scripts/research/{path.name}`). Every game below was "
        "played after that day. Generated by `draft_score.py --prospective`.",
        "",
    ]
    if len(new) < 30:
        lines.append(f"{len(new)} games so far; scored from 30.")
        out.write_text("\n".join(lines) + "\n")
        print(lines[-1])
        return
    a, b, d, lo, hi = paired(new, "draft", "base")
    lines += [
        f"{len(new):,} games ({new['date'].min().date()} to {new['date'].max().date()}).",
        "",
        "| Call | Log loss | Draft − Elo (95%) |",
        "|---|---:|---|",
        f"| Elo | {b:.4f} | |",
        f"| Elo + draft | {a:.4f} | {d:+.4f} ({lo:+.4f} to {hi:+.4f}) |",
    ]
    matcher = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **markets.MARKET_ALIASES},
    )
    by_pair = dict(list(el.oe_games().groupby(["blue", "red"])))
    cutoff = markets.get("/historical/cutoff")["trades_created_ts"] if fetch else ""
    keyed = new.set_index("gameid")
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
            "series": g["series"],
            "won": int(g["won"]),
            "shift": g["shift"],
            "base": g["base"],
            "draft": g["draft"],
        }
        for label, offset in ENTRIES.items():
            t = at + pd.Timedelta(seconds=offset)
            row[(label, "p")] = el.price_at(tp, t, stale=el.PRE_STALE)
            row[(label, "cost0")] = el.cost_to_back(tp, t, 0, stale=el.PRE_STALE)
            row[(label, "cost1")] = el.cost_to_back(tp, t, 1, stale=el.PRE_STALE)
        row["p_close"] = el.price_at(
            tp, at + pd.Timedelta(minutes=3), stale=el.PRE_STALE
        )
        rows.append(row)
    priced = pd.DataFrame(rows)
    lines += ["", f"## Against Kalshi ({len(priced)} priced maps)"]
    for label in ENTRIES:
        if priced.empty:
            break
        f = priced[priced[(label, "p")].notna()]
        f = f[(f[(label, "p")] > 0) & (f[(label, "p")] < 1)]
        f = f.assign(kalshi=f[(label, "p")])
        if len(f) < 30:
            lines += ["", f"{label}: {len(f)} maps so far; scored from 30."]
            continue
        a, _, d, lo, hi = paired(f, "draft", "kalshi")
        b, _, d0, lo0, hi0 = paired(f, "base", "kalshi")
        lines += [
            "",
            f"### {label}: {len(f)} maps",
            "",
            f"Elo − Kalshi {d0:+.4f} ({lo0:+.4f} to {hi0:+.4f}); "
            f"Elo + draft − Kalshi {d:+.4f} ({lo:+.4f} to {hi:+.4f}).",
            "",
            "| Edge | Bets | Won | Flat ROI (95%) | Kelly growth/bet (95%) | Kelly multiple | CLV (3 min) |",
            "|---:|---:|---:|---|---|---:|---:|",
        ]
        p = 1 / (1 + np.exp(-(_logit(f["kalshi"]) + f["shift"])))
        pre = pd.DataFrame(
            {
                "series": f["series"],
                "game": range(len(f)),
                "won": f["won"],
                "p": p,
                "cost0": f[(label, "cost0")],
                "cost1": f[(label, "cost1")],
                "p_start": f["p_close"],
            }
        )
        for edge in PROSPECTIVE_EDGES:
            s = el.bet_summary(el.premap_bets(pre, edge))
            if s is None:
                continue
            clv = "" if s["clv"] is None else f"{s['clv'] * 100:+.1f}"
            lines.append(
                f"| {edge:.2f} | {s['n']} | {s['won']:.1%} | {_ci3(s['roi'])} "
                f"| {_ci3(s['growth'], 4)} | {s['multiple']:.2f} | {clv} |"
            )
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--offline", action="store_true", help="cached trades only")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--prospective", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(all_games())
        return
    if args.prospective:
        prospective(
            all_games(),
            args.out or Path("docs/research/draft_prospective.md"),
            not args.offline,
        )
        return
    rows = interaction_features(player_features(load_rows()))
    games = game_table(rows)
    games = games[games["year"] >= FIT[0]]
    scored, names, coefs = evaluate(games)
    kalshi = priced_games(scored, fetch=not args.offline)
    text = report(games, scored, names, coefs, kalshi)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
