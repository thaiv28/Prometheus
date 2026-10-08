"""
series_independence.py: are the games of a series independent, and what does fearless draft change?

The Predictions page and the game logs turn our one-game chance p into a series
chance as if every game were an independent coin flip (`schedule.series_probability`).
This script checks that against every past Bo3 and Bo5 (series grouped as the game
logs group them, `gamelog.add_series`; the call is game 1's, `gamelog.add_calls`) and
fits the alternative, a beta-binomial: each series draws its own chance from a Beta
with mean p and within-series correlation rho, and its games are independent given
that chance. rho = 0 is today's formula; a game-1 win moves game 2's chance from p to
p + rho * (1 - p).

Fearless draft (no champion picked in an earlier game of the series, by either team)
is read off the data: a league-split is fearless when under 5% of its multi-game
series repeat a champion, not fearless when over 60% do (else unlabelled).

Leagues where 1% or more of multi-game series end tied (missing games, Bo2s, or two
Bo1s against one opponent on one day) are left out: a missing game turns a 2-1 into
a 2-0 and fakes dependence.

Usage:
    uv run python scripts/research/series_independence.py --out docs/research/series_independence.md

Needs db/prometheus.db; the Kalshi section uses data/markets/frames.pkl when present.
"""

import argparse
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import betaln, expit, gammaln, logit

from prometheus import gamelog
from prometheus.form import form_states, load_form_games, opponent_adjust
from prometheus.types import ALL_MAJOR_LEAGUES

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "db" / "prometheus.db"
FRAMES = ROOT / "data" / "markets" / "frames.pkl"
MAJORS = {l.value for l in ALL_MAJOR_LEAGUES}
FEARLESS_MAX, CLASSIC_MIN = 0.05, 0.6  # share of series repeating a champion
TIE_MAX = 0.01  # share of tied multi-game series for a league to count as clean
POOL_DAYS = 180  # champion pool window before a series
ROSTER_DAYS = 365  # window for games a roster has played together
LEAGUE_PRIOR = (
    200  # series: a league's own rho is shrunk toward its tier's by n / (n + this)
)
RHO_MAX = 0.7
SEED = 42
BOOT = 2000


# ---------------------------------------------------------------- the model


def _lcomb(n, k):
    return gammaln(n + 1) - gammaln(k + 1) - gammaln(n - k + 1)


def _log_moment(p, rho, wins, losses):
    """log E[pi^wins (1 - pi)^losses] for pi ~ Beta with mean p and correlation rho
    (a number or one per series)."""
    p = np.asarray(p, dtype=float)
    rho = np.asarray(rho, dtype=float)
    independent = wins * np.log(p) + losses * np.log1p(-p)
    if np.all(rho <= 0):
        return independent
    kappa = 1 / np.maximum(rho, 1e-12) - 1
    a, b = p * kappa, (1 - p) * kappa
    return np.where(rho <= 0, independent, betaln(a + wins, b + losses) - betaln(a, b))


def beta_series(p, best_of, rho):
    """Chance to win a best-of series when the series' one-game chance is drawn from a
    Beta with mean `p` and within-series correlation `rho` (0: independent games)."""
    p = np.asarray(p, dtype=float)
    need = np.asarray(best_of) // 2 + 1
    out = np.zeros(np.broadcast(p, need).shape)
    for k in range(int(np.max(need))):
        # win the deciding game after k losses
        term = np.exp(_lcomb(need - 1 + k, k) + _log_moment(p, rho, need, k))
        out += np.where(k < need, term, 0.0)
    return out


def length_probs(p, best_of, rho):
    """{games played: mean chance} over the series in `p` (all the same best-of)."""
    p = np.asarray(p, dtype=float)
    need = best_of // 2 + 1
    out = {}
    for n in range(need, best_of + 1):
        k = n - need
        c = _lcomb(n - 1, k)
        out[n] = float(
            (
                np.exp(c + _log_moment(p, rho, need, k))
                + np.exp(c + _log_moment(1 - p, rho, need, k))
            ).mean()
        )
    return out


def sequence_nll(p, wins, losses, rho):
    """Negative log likelihood of each series' games (order and stopping rule drop out)."""
    return -_log_moment(p, rho, wins, losses).sum()


def log_loss(p, y):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def fit_rho(d, how="sequence"):
    """(rho, low, high): maximum likelihood with a profile-likelihood 95% interval.

    `sequence` uses every game's result; `series` only who took the series.
    """
    if how == "sequence":
        p, w, l = d["p"].to_numpy(), d["w"].to_numpy(), d["l"].to_numpy()
        f = lambda r: sequence_nll(p, w, l, r)
    else:
        p, bo, y = d["p"].to_numpy(), d["bo"].to_numpy(), d["won"].to_numpy()
        f = lambda r: log_loss(beta_series(p, bo, r), y).sum()
    rho = minimize_scalar(f, bounds=(0, RHO_MAX), method="bounded").x
    best = f(rho)
    ok = [r for r in np.linspace(0, RHO_MAX, 281) if f(r) - best <= 1.92]
    return rho, min(ok), max(ok)


def fit_rho_model(d, cols):
    """Coefficients of logit(rho) = c0 + c . cols, by maximum sequence likelihood."""
    X = _design(d, cols)
    p, w, l = d["p"].to_numpy(), d["w"].to_numpy(), d["l"].to_numpy()
    r = minimize(
        lambda c: sequence_nll(p, w, l, np.clip(expit(X @ c), 1e-6, 0.95)),
        np.r_[-2.0, np.zeros(len(cols))],
        method="Nelder-Mead",
        options={"maxiter": 4000, "xatol": 1e-5, "fatol": 1e-6},
    )
    return r.x


def rho_model(d, cols, coef):
    return np.clip(expit(_design(d, cols) @ coef), 1e-6, 0.95)


def _design(d, cols):
    return np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])


def logistic(d, cols):
    """Logistic fit of `y` on `cols` (Newton): {name: (coef, se)}, intercept `a`."""
    X = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])
    y = d["y"].to_numpy(float)
    b = np.zeros(X.shape[1])
    for _ in range(30):
        p = expit(X @ b)
        H = X.T @ (X * (p * (1 - p))[:, None])
        b = b + np.linalg.solve(H, X.T @ (y - p))
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return dict(zip(["a", *cols], zip(b, se)))


def paired(x, rng):
    """Mean of x and its bootstrap 95% interval."""
    idx = rng.integers(0, len(x), (BOOT, len(x)))
    m = x[idx].mean(axis=1)
    return x.mean(), *np.percentile(m, [2.5, 97.5])


# ---------------------------------------------------------------- data


def fearless_labels(series):
    """{(league, year, split): True / False / NaN} from how often series repeat a champion."""
    multi = series[(series["n"] >= 2) & series["any_rep"].notna()]
    share = (
        multi.assign(r=multi["any_rep"].astype(float))
        .groupby(["league", "year", "split"], dropna=False)["r"]
        .mean()
    )
    return pd.Series(
        np.where(share < FEARLESS_MAX, 1.0, np.where(share > CLASSIC_MIN, 0.0, np.nan)),
        index=share.index,
        name="fearless",
    )


def load(con):
    """(games, series): one side of every series (the alphabetically first team)."""
    states = form_states(opponent_adjust(load_form_games()))
    g = gamelog.add_series(gamelog.add_calls(gamelog.load_team_games(), states))
    home = states[["gameid", "teamid", "home"]].drop_duplicates(["gameid", "teamid"])
    g = g.merge(home, on=["gameid", "teamid"], how="left").merge(
        home.rename(columns={"teamid": "opp_id", "home": "opp_home"}),
        on=["gameid", "opp_id"],
        how="left",
    )
    split = pd.read_sql(
        "SELECT DISTINCT gameid, split FROM matches", con
    ).drop_duplicates("gameid")
    g = g.merge(split, on="gameid", how="left")
    g = g[g["teamname"] < g["opp"]].sort_values(["when", "gameid"], kind="mergesort")
    g["k"] = g.groupby("series").cumcount() + 1

    champs = pd.read_sql(
        "SELECT gameid, teamid, champion FROM player_stats "
        "WHERE champion IS NOT NULL AND champion != ''",
        con,
    )
    picks = pd.concat(
        [
            champs.merge(g[["gameid", "teamid", "series"]], on=["gameid", "teamid"]),
            champs.merge(
                g[["gameid", "opp_id", "series"]].rename(columns={"opp_id": "teamid"}),
                on=["gameid", "teamid"],
            ),
        ]
    )
    repeat = (
        picks.groupby(["series", "champion"])["gameid"]
        .nunique()
        .gt(1)
        .groupby("series")
        .any()
    )

    s = g.groupby("series").agg(
        when=("when", "first"),
        year=("year", "first"),
        league=("league", "first"),
        home1=("home", "first"),
        home2=("opp_home", "first"),
        split=("split", "first"),
        p=("p", "first"),
        w=("result", "sum"),
        n=("result", "size"),
        res=("result", list),
    )
    s["any_rep"] = repeat.reindex(s.index)
    s["l"] = s["n"] - s["w"]
    s = s.join(fearless_labels(s), on=["league", "year", "split"])
    # Tier: both teams from major leagues (home league as Form keeps it), whatever
    # the event, so an international between two major-league teams is "major".
    s["major"] = s["home1"].isin(MAJORS) & s["home2"].isin(MAJORS)
    tie = (
        s[s["n"] >= 2]
        .assign(t=lambda d: d["w"] * 2 == d["n"])
        .groupby("league")["t"]
        .mean()
    )
    s["clean"] = s["league"].map(tie) < TIE_MAX
    s = s[s["w"] != s["l"]].dropna(subset=["p"])
    s["bo"] = 2 * s[["w", "l"]].max(axis=1) - 1
    s = s[s["bo"].isin([3, 5])].copy()
    s["won"] = (s["w"] > s["l"]).astype(int)
    s["p_ind"] = beta_series(s["p"], s["bo"], 0)
    return g, s


def later_games(s):
    """One row per game: result, logit of the game-1 call, lead before it, game number."""
    rows = []
    for r in s.itertuples():
        x = logit(np.clip(r.p, 1e-4, 1 - 1e-4))
        for k, y in enumerate(r.res):
            won = sum(r.res[:k])
            rows.append(
                {
                    "series": r.Index,
                    "k": k + 1,
                    "y": y,
                    "x": x,
                    "lead": won - (k - won),
                    "fearless": r.fearless,
                    "bo": r.bo,
                }
            )
    return pd.DataFrame(rows)


def roster_games(con, g, s):
    """Per series and side: games in the year before it that at least four of game 1's
    starters played together (on any team), as `together_1` / `together_2`."""
    mp = pd.read_sql(
        "SELECT gameid, teamid, playerid FROM match_players WHERE playerid IS NOT NULL",
        con,
    )
    dates = pd.read_sql("SELECT DISTINCT gameid, date FROM matches", con)
    mp = mp.merge(dates.drop_duplicates("gameid"), on="gameid")
    mp["when"] = pd.to_datetime(mp["date"]).to_numpy(dtype="datetime64[ns]")
    mp = mp.sort_values("when")
    by_player = {
        pid: (d["when"].to_numpy(), d["gameid"].to_numpy())
        for pid, d in mp.groupby("playerid")
    }
    roster = mp.groupby(["gameid", "teamid"])["playerid"].apply(list).to_dict()
    year = np.timedelta64(ROSTER_DAYS, "D")

    def together(gameid, teamid, start):
        seen = Counter()
        for pid in roster.get((gameid, teamid), []):
            if pid in by_player:
                t, gid = by_player[pid]
                seen.update(
                    gid[np.searchsorted(t, start - year) : np.searchsorted(t, start)]
                )
        return sum(1 for v in seen.values() if v >= 4)

    first = g.sort_values(["series", "k"]).drop_duplicates("series").set_index("series")
    first = first.loc[s.index]
    rows = []
    for sid, r in first.iterrows():
        start = np.datetime64(r["when"], "ns")
        rows.append(
            {
                "series": sid,
                "together_1": together(r["gameid"], r["teamid"], start),
                "together_2": together(r["gameid"], r["opp_id"], start),
            }
        )
    return pd.DataFrame(rows).set_index("series")


def pool_features(con, g, series_ids):
    """Per series game and side: champion-pool depth and share of the pool already used.

    A player's pool is their champions over the `POOL_DAYS` before the series. Depth is
    its effective size (exp of entropy); burn is the share of those games on champions
    picked earlier in the series by either team; experience is the number of those
    games. Team values average the starters with a pool (at least four).
    """
    ps = pd.read_sql(
        """SELECT p.gameid, p.playerid, p.teamid, p.champion, m.date FROM player_stats p
        JOIN (SELECT DISTINCT gameid, date FROM matches) m ON m.gameid = p.gameid
        WHERE p.champion IS NOT NULL AND p.champion != '' AND p.playerid IS NOT NULL""",
        con,
    )
    ps["when"] = pd.to_datetime(ps["date"])
    ps = ps.sort_values("when")
    hist = {
        pid: (d["when"].to_numpy(), d["champion"].to_numpy())
        for pid, d in ps.groupby("playerid")
    }
    roster = ps.groupby(["gameid", "teamid"])["playerid"].apply(list).to_dict()
    picked = ps.groupby("gameid")["champion"].apply(set).to_dict()
    window = np.timedelta64(POOL_DAYS, "D")

    def team(players, start, used):
        burns, depths, games = [], [], []
        for pid in players:
            if pid not in hist:
                continue
            t, c = hist[pid]
            i0, i1 = np.searchsorted(t, start - window), np.searchsorted(t, start)
            if i1 <= i0:
                continue
            cnt = Counter(c[i0:i1])
            n = sum(cnt.values())
            games.append(n)
            burns.append(sum(v for ch, v in cnt.items() if ch in used) / n)
            q = np.array(list(cnt.values())) / n
            depths.append(np.exp(-(q * np.log(q)).sum()))
        if len(burns) < 4:
            return np.nan, np.nan, np.nan
        return np.mean(burns), np.mean(depths), np.mean(games)

    rows = []
    sub = g[g["series"].isin(series_ids)].sort_values(["series", "k"])
    for sid, d in sub.groupby("series", sort=False):
        start = np.datetime64(d["when"].iloc[0])
        used = set()
        for r in d.itertuples():
            bo, do, eo = team(roster.get((r.gameid, r.teamid), []), start, used)
            bt, dt, et = team(roster.get((r.gameid, r.opp_id), []), start, used)
            rows.append(
                {
                    "series": sid,
                    "k": r.k,
                    "burn": bo - bt,
                    "depth": do - dt,
                    "experience": eo - et,
                }
            )
            used |= picked.get(r.gameid, set())
    f = pd.DataFrame(rows)
    for col in ("depth", "experience"):
        f[col] = f[col] / f[col].std()
    return f


# ---------------------------------------------------------------- report


def _ci(r):
    return f"{r[0]:.3f} [{r[1]:.3f}, {r[2]:.3f}]"


def _coef(c):
    return f"{c[0]:+.3f} ± {c[1]:.3f}"


def report(con):
    rng = np.random.default_rng(SEED)
    g, s = load(con)
    out = []
    add = out.append
    clean = s[s["clean"]]
    recent = clean[clean["year"].between(2024, 2026)]

    add("# Series independence and fearless draft\n")
    add(
        f"Generated by `scripts/research/series_independence.py` on {date.today()}. "
        f"{len(s):,} Bo3 and Bo5 series from {s['year'].min()} to {s['year'].max()} "
        f"({len(clean):,} in the {clean['league'].nunique()} leagues with under "
        f"{TIE_MAX:.0%} tied multi-game series, used below unless said). One side per "
        "series; the call is game 1's pre-game chance as the game logs make it.\n"
    )
    add(
        "**Model.** Today's series odds treat games as independent coin flips with "
        "chance p. The beta-binomial draws each series' chance from a Beta with mean p "
        "and within-series correlation ρ; ρ = 0 is today's formula, and a game-1 win "
        "moves game 2's chance from p to p + ρ(1 − p). ρ is fitted by maximum "
        "likelihood on every game's result in a series (the *sequence* fit) or on the "
        "series result alone; intervals are profile-likelihood 95%. *Major* means "
        "both teams' home leagues are LCK, LPL, LEC or LCS (whatever the event); "
        "*other* is every other series, internationals included.\n"
    )

    # Fearless adoption
    add("## Fearless draft in the data\n")
    add(
        "Share of multi-game series in which some champion is picked in two games (by "
        "either team), and series by label (a league-split is fearless when under "
        f"{FEARLESS_MAX:.0%} repeat, not fearless when over {CLASSIC_MIN:.0%}).\n"
    )
    add("| Year | Series | Repeat a champion | Fearless | Not | Unlabelled |")
    add("|---|---|---|---|---|---|")
    for y, d in s.groupby("year"):
        if y < 2018:
            continue
        rep = d.loc[d["any_rep"].notna(), "any_rep"].astype(float).mean()
        add(
            f"| {y} | {len(d):,} | {rep:.1%} | {(d['fearless'] == 1).sum():,} | "
            f"{(d['fearless'] == 0).sum():,} | {d['fearless'].isna().sum():,} |"
        )
    add(
        "\nFrom 2025 nearly every league plays hard fearless; 2024 has a few fearless "
        "splits. The format change and the calendar coincide, so fearless vs not is "
        "also 2025–26 vs earlier.\n"
    )

    # Independence check
    add("## Does independence hold?\n")
    add(
        "Calibration slope: logistic fit of the result on the logit of our chance "
        "(1 is calibrated, under 1 overconfident). Game 1 against the one-game chance; "
        "the series against today's series chance. All years.\n"
    )
    add("| Best of | Series | Game-1 slope | Series slope |")
    add("|---|---|---|---|")
    for bo in (3, 5):
        d = clean[clean["bo"] == bo]
        g1 = logistic(
            pd.DataFrame(
                {"y": [r[0] for r in d["res"]], "x": logit(d["p"].clip(1e-4, 1 - 1e-4))}
            ),
            ["x"],
        )["x"]
        ser = logistic(
            pd.DataFrame({"y": d["won"], "x": logit(d["p_ind"].clip(1e-6, 1 - 1e-6))}),
            ["x"],
        )["x"]
        add(f"| {bo} | {len(d):,} | {_coef(g1)} | {_coef(ser)} |")
    rho_recent = fit_rho(recent)[0]
    add(
        "\nHow often a series goes the distance, 2024–2026: actual, today's model, and "
        f"the beta-binomial at the pooled 2024–2026 ρ ({rho_recent:.3f}).\n"
    )
    add("| Leagues | Best of | Series | Actual | Independent | Beta-binomial |")
    add("|---|---|---|---|---|---|")
    for seg, m in (("Major", recent["major"]), ("Other", ~recent["major"])):
        for bo in (3, 5):
            d = recent[m & (recent["bo"] == bo)]
            p = d["p"].to_numpy()
            add(
                f"| {seg} | {bo} | {len(d):,} | {(d['n'] == bo).mean():.1%} | "
                f"{length_probs(p, bo, 0)[bo]:.1%} | "
                f"{length_probs(p, bo, rho_recent)[bo]:.1%} |"
            )
    dirty = s[~s["clean"] & s["year"].between(2024, 2026) & (s["bo"] == 3)]
    add(
        f"\nLeft out: in the other leagues' Bo3s 2024–2026 ({len(dirty):,}), "
        f"{(dirty['n'] == 3).mean():.1%} go to game 3 against "
        f"{length_probs(dirty['p'].to_numpy(), 3, 0)[3]:.1%} predicted, mostly "
        "missing games.\n"
    )

    # rho by year and slice
    add("## ρ, 2024–2026\n")
    add("| Slice | Series | ρ (sequence) | ρ (series result) |")
    add("|---|---|---|---|")
    slices = [
        ("2024–2026, all", recent),
        ("2024–2026, major", recent[recent["major"]]),
        ("2024–2026, other", recent[~recent["major"]]),
        ("2024–2026, Bo3", recent[recent["bo"] == 3]),
        ("2024–2026, Bo5", recent[recent["bo"] == 5]),
        ("2024–2026, fearless", recent[recent["fearless"] == 1]),
        ("2024–2026, not fearless", recent[recent["fearless"] == 0]),
        (
            "2022–2026 fearless",
            clean[clean["year"].between(2022, 2026) & (clean["fearless"] == 1)],
        ),
        (
            "2022–2026 not fearless",
            clean[clean["year"].between(2022, 2026) & (clean["fearless"] == 0)],
        ),
    ] + [(str(y), clean[clean["year"] == y]) for y in range(2018, 2027)]
    for name, d in slices:
        add(
            f"| {name} | {len(d):,} | {_ci(fit_rho(d))} | {_ci(fit_rho(d, 'series'))} |"
        )
    add("")

    # Out of sample
    add("## Out of sample: which ρ\n")
    clean = clean.join(roster_games(con, g, clean))
    clean["tog_min"] = clean[["together_1", "together_2"]].min(axis=1)
    clean["tog_mean"] = np.log1p(clean[["together_1", "together_2"]]).mean(axis=1)
    clean["maj"] = clean["major"].astype(float)
    train = clean[clean["year"].between(2018, 2024)].copy()
    test = clean[clean["year"].between(2025, 2026)].copy()
    cut = train["tog_min"].quantile(0.25)
    for d in (train, test):
        d["new"] = (d["tog_min"] < cut).astype(float)
    rho_tr = fit_rho(train)[0]
    tier = {m: fit_rho(train[train["major"] == m])[0] for m in (True, False)}
    leagues = {
        name: (fit_rho(d)[0], len(d))
        for name, d in train.groupby("league")
        if len(d) >= 30
    }

    def league_rho(r):
        base = tier[r["major"]]
        if r["league"] not in leagues:
            return base
        v, n = leagues[r["league"]]
        w = n / (n + LEAGUE_PRIOR)
        return w * v + (1 - w) * base

    team_cols, new_cols = ["tog_mean", "maj"], ["maj", "new"]
    team_coef = fit_rho_model(train, team_cols)
    new_coef = fit_rho_model(train, new_cols)
    rhos = {
        "Independent": np.zeros(len(test)),
        f"One ρ ({rho_tr:.3f})": np.full(len(test), rho_tr),
        f"By tier (major {tier[True]:.3f}, other {tier[False]:.3f})": test["major"].map(
            tier
        ),
        f"By league ({len(leagues)} leagues, shrunk to tier)": test.apply(
            league_rho, axis=1
        ),
        "By team: tier + mean log roster games": rho_model(test, team_cols, team_coef),
        (
            f"By team: tier + new roster (either side under {cut:.0f} games "
            f"together; {test['new'].mean():.0%} of test series)"
        ): rho_model(test, new_cols, new_coef),
    }
    add(
        "Every ρ fitted on 2018–2024 (sequence fit) and scored on 2025–2026 "
        "(fearless): mean series log loss, and each model minus the tier model "
        "(negative is better) on the series result and on every game's result (the "
        f"sequence log likelihood), paired bootstrap over series ({BOOT} draws). "
        "*Roster games*: games in the year before the series that four of game 1's "
        "starters played together.\n"
    )
    add("| ρ | Series log loss | − tier | Sequence − tier |")
    add("|---|---|---|---|")
    y, p, bo = test["won"], test["p"].to_numpy(), test["bo"].to_numpy()
    w, l = test["w"].to_numpy(), test["l"].to_numpy()
    tier_name = next(k for k in rhos if k.startswith("By tier"))
    ls = {k: log_loss(beta_series(p, bo, np.asarray(r)), y) for k, r in rhos.items()}
    sq = {k: -_log_moment(p, np.asarray(r), w, l) for k, r in rhos.items()}
    for k in rhos:
        cells = [
            "{:+.4f} [{:+.4f}, {:+.4f}]".format(*paired(x[k] - x[tier_name], rng))
            for x in (ls, sq)
        ]
        add(f"| {k} | {ls[k].mean():.4f} | " + " | ".join(cells) + " |")
    test["p_beta"] = beta_series(p, bo, test["major"].map(tier).to_numpy())
    add(
        "\nThe tier model against independent games, by slice (series log loss, "
        "negative is better):\n"
    )
    add("| Slice | Series | Independent | Difference | 95% interval |")
    add("|---|---|---|---|---|")
    for name, d in (
        ("All", test),
        ("Major", test[test["major"]]),
        ("Other", test[~test["major"]]),
        ("Bo3", test[test["bo"] == 3]),
        ("Bo5", test[test["bo"] == 5]),
    ):
        li = log_loss(d["p_ind"], d["won"])
        m, lo, hi = paired(log_loss(d["p_beta"], d["won"]) - li, rng)
        add(
            f"| {name} | {len(d):,} | {li.mean():.4f} | {m:+.4f} | "
            f"[{lo:+.4f}, {hi:+.4f}] |"
        )
    if FRAMES.exists():
        f = pd.read_pickle(FRAMES)[0].dropna(subset=["p_game", "market_close"])
        f = f[f["best_of"].isin([3, 5])].copy()
        f["p_beta"] = beta_series(
            f["p_game"], f["best_of"], f["major"].map(tier).to_numpy()
        )
        add(
            f"\nKalshi's priced series ({f['start'].min():%b %Y}–"
            f"{f['start'].max():%b %Y}, every league, no tie filter), ρ by tier: "
            "our log loss, beta-binomial minus independent, and each against "
            "Kalshi's close.\n"
        )
        add(
            "| Slice | Series | Independent | Beta − independent | "
            "Independent − Kalshi | Beta − Kalshi |"
        )
        add("|---|---|---|---|---|---|")
        for name, d in (
            ("All", f),
            ("Major", f[f["major"]]),
            ("Other", f[~f["major"]]),
            ("Bo5", f[f["best_of"] == 5]),
        ):
            y = d["won1"].astype(int)
            li = log_loss(d["p_series"], y)
            lb = log_loss(d["p_beta"], y)
            lk = log_loss(d["market_close"], y)
            cells = [
                "{:+.4f} [{:+.4f}, {:+.4f}]".format(*paired(x, rng))
                for x in (lb - li, li - lk, lb - lk)
            ]
            add(
                f"| {name} | {len(d):,} | {li.mean():.4f} | " + " | ".join(cells) + " |"
            )
        add(
            "\nCalibration slope on these series (logistic fit of the result on the "
            "logit of the chance; over 1 is underconfident):\n"
        )
        add("| Slice | Ours (independent) | Kalshi |")
        add("|---|---|---|")
        for name, d in (("Major", f[f["major"]]), ("Other", f[~f["major"]])):
            y = d["won1"].astype(int)
            cells = [
                _coef(
                    logistic(
                        pd.DataFrame({"y": y, "x": logit(d[c].clip(1e-6, 1 - 1e-6))}),
                        ["x"],
                    )["x"]
                )
                for c in ("p_series", "market_close")
            ]
            add(f"| {name} | " + " | ".join(cells) + " |")
    add("")

    # Fearless: later games
    add("## Fearless: later games\n")
    G = later_games(
        clean[clean["year"].between(2022, 2026) & clean["fearless"].notna()]
    )
    add(
        "2022–2026, labelled splits. Per game number: logistic fit of the result on "
        "the logit of the game-1 call (how much of the pre-series edge carries; later "
        "games are reached more often by close series, so the slope falls under any "
        "model).\n"
    )
    add("| Game | Not fearless: games | Slope | Fearless: games | Slope |")
    add("|---|---|---|---|---|")
    for k in range(1, 6):
        cells = []
        for fl in (0, 1):
            d = G[(G["fearless"] == fl) & (G["k"] == k)]
            cells += [f"{len(d):,}", _coef(logistic(d, ["x"])["x"])]
        add(f"| {k} | " + " | ".join(cells) + " |")
    add(
        "\nGames 2 on: result on the game-1 call and the lead before the game (log-odds "
        "per game of lead). Under the beta-binomial, one game of lead at p = 0.5 is "
        f"worth logit(0.5 + ρ/2) = {logit(0.5 + rho_recent / 2):.3f} at ρ = "
        f"{rho_recent:.3f}.\n"
    )
    add("| Format | Best of | Games | Call slope | Lead |")
    add("|---|---|---|---|---|")
    for fl, name in ((0, "Not fearless"), (1, "Fearless")):
        for bo in (3, 5):
            d = G[(G["fearless"] == fl) & (G["k"] >= 2) & (G["bo"] == bo)]
            c = logistic(d, ["x", "lead"])
            add(
                f"| {name} | {bo} | {len(d):,} | {_coef(c['x'])} | {_coef(c['lead'])} |"
            )
    d = G[G["k"] >= 2].assign(
        f_lead=lambda d: d["fearless"] * d["lead"], f_x=lambda d: d["fearless"] * d["x"]
    )
    c = logistic(d, ["x", "lead", "f_lead", "f_x"])
    add(
        f"\nPooled, fearless × lead {_coef(c['f_lead'])}, fearless × call slope "
        f"{_coef(c['f_x'])}.\n"
    )

    # Fearless: champion pools
    add("## Fearless: champion pools\n")
    pools = pool_features(con, g, set(G["series"]))
    P = G.merge(pools, on=["series", "k"]).dropna(subset=["burn", "depth"])
    corr = P.loc[P["k"] == 1, ["depth", "experience"]].corr().iloc[0, 1]
    add(
        f"A player's pool is their champions in the {POOL_DAYS} days before the "
        "series. **Burn**: the share of those games on champions already picked in "
        "the series (by either team), ours minus the opponent's; under fearless "
        "those champions are gone, otherwise still allowed (a placebo). **Depth**: "
        "effective pool size (exp of entropy), ours minus the opponent's, in standard "
        "deviations. **Experience**: games in the window, ours minus the opponent's, "
        f"in standard deviations (correlation with depth {corr:.2f}). Team values "
        "average the starters. Logistic fits on the game-1 call, the lead (games 2 "
        "on) and the feature.\n"
    )
    add("| Feature | Not fearless | Fearless |")
    add("|---|---|---|")
    for feat, k_sel, name in (
        ("burn", P["k"] >= 2, "Burn, games 2 on"),
        ("burn", P["k"] >= 3, "Burn, games 3 on"),
        ("depth", P["k"] == 1, "Depth, game 1"),
        ("depth", P["k"] >= 2, "Depth, games 2 on"),
        ("depth", P["k"] >= 3, "Depth, games 3 on"),
        ("depth", P["k"] == 1, "Depth, game 1, with experience"),
        ("depth", P["k"] >= 2, "Depth, games 2 on, with experience"),
    ):
        cells = []
        for fl in (0, 1):
            d = P[k_sel & (P["fearless"] == fl)]
            cols = ["x", feat] if "game 1" in name else ["x", "lead", feat]
            if "experience" in name:
                cols.append("experience")
            cells.append(f"{_coef(logistic(d, cols)[feat])} (n {len(d):,})")
        add(f"| {name} | " + " | ".join(cells) + " |")
    add("\nDepth on game 1 by year:\n")
    add("| Year | Games | Depth |")
    add("|---|---|---|")
    for y in range(2022, 2027):
        d = P[(P["k"] == 1) & P["series"].isin(clean.index[clean["year"] == y])]
        add(f"| {y} | {len(d):,} | {_coef(logistic(d, ['x', 'depth'])['depth'])} |")
    add("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, help="write the report here (else print)")
    args = ap.parse_args()
    with sqlite3.connect(DB) as con:
        text = report(con)
    if args.out:
        args.out.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
