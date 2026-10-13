"""Player props: projections of a player's kills, assists, deaths, CS and fantasy
points in one game and over a series' first maps.

A projection is a mixture over the game's result. For each count stat a Poisson
model (log link) gives the expected count in a win and in a loss from the
player's, their team's and the opponent's recent rates, the league's pace and the
role; a negative binomial spread (one dispersion per stat, role and result) turns
each mean into a distribution, and the pre-game Elo chance `p` weights the two:

    P(x) = p · NB(x; mu_win, a_win) + (1 − p) · NB(x; mu_loss, a_loss)

Fantasy points (DraftKings Pick6: kill 3, assist 2, death −1, CS 0.02) are a
normal per result with the same mixture: the mean is the scored component means,
the spread is fit on the residuals, so it carries the stats' correlation.

Rates are exponentially weighted means over earlier games only, with a half-life
in games. A player's is shrunk toward their league and role's pace by
`prior_games` pseudo-games; a team's toward its league's. Each stat has its own
(half-life, prior games), its `settings` (`add_stat_states`); the fitted model is
saved as plain numbers in `props_weights.json` (`PropModel.to_dict`), which the
site reads instead of refitting.

Over a series every map uses the states before its first map (as a line set
before the series would). Maps are independent given each map's result, so the
total over the first `maps` maps is a sum over the possible result sequences
(`series_pmf`, `series_normal`).

Research: nothing on the site uses it yet. See `scripts/evaluate_props.py`.
"""

import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from prometheus.gamelog import SERIES_GAP
from prometheus.utils import get_engine

STATS = ("kills", "assists", "deaths", "cs")
WEIGHTS_PATH = Path(__file__).with_name("props_weights.json")
ROLES = ("top", "jng", "mid", "bot", "sup")
FANTASY = {"kills": 3.0, "assists": 2.0, "deaths": -1.0, "cs": 0.02}
# Team-level rate behind each stat, for the player's team and for the opponent:
# kills and assists follow the kills a team makes and the opponent concedes;
# deaths the kills a team concedes and the opponent makes; CS the game's length.
TEAM_RATE = {
    "kills": ("team_kills", "team_deaths"),
    "assists": ("team_kills", "team_deaths"),
    "deaths": ("team_deaths", "team_kills"),
    "cs": ("minutes", "minutes"),
}
# Pace states move slowly: a league-role pace is about 2 rows a game.
PACE_HALFLIFE = 400
TEAM_PRIOR_GAMES = 5
# Count supports, wide enough that the mass beyond is negligible for one map.
SUPPORT = {"kills": 40, "assists": 60, "deaths": 30, "cs": 900}
MIN_ALPHA = 1e-6


def load_prop_games(since=None):
    """One row per starter per game with the full-game totals, the opponent and
    both teams' pre-game Elo, in time order; games on or after `since` (a date)
    only when given."""
    stmt = """
    SELECT mp.gameid, mp.teamid, mp.position, mp.playerid, mp.playername,
           mp.kills, mp.assists, mp.deaths, mp.cs,
           m.date, m.year, m.league, m.teamname, m.gamelength, m.result,
           o.teamid AS opp_teamid, o.teamname AS opp_teamname,
           e.pre_match_elo AS elo, oe.pre_match_elo AS opp_elo
    FROM match_players mp
    JOIN matches m ON m.gameid = mp.gameid AND m.teamid = mp.teamid
    JOIN matches o ON o.gameid = m.gameid AND o.teamid != m.teamid
    LEFT JOIN game_length_elo e ON e.gameid = m.gameid AND e.teamid = m.teamid
    LEFT JOIN game_length_elo oe ON oe.gameid = o.gameid AND oe.teamid = o.teamid
    WHERE mp.kills IS NOT NULL AND mp.cs IS NOT NULL{}
    """.format(" AND m.date >= ?" if since is not None else "")
    params = [str(since)] if since is not None else []
    # The engine's raw sqlite3 connection: pandas reads it without SQLAlchemy's
    # row objects, several seconds faster on a million rows.
    raw = get_engine().raw_connection()
    try:
        games = pd.read_sql(stmt, raw.driver_connection, params=params)
    finally:
        raw.close()
    return prepare(games)


def games_from_tables(tables):
    """`load_prop_games` from tables the site build has already read (a
    `PlayerTables`), with no Elo: the live projections take current Elo from the
    ratings and never read the past games' Elo."""
    m = tables.matches[
        [
            "gameid",
            "teamid",
            "date",
            "year",
            "league",
            "teamname",
            "gamelength",
            "result",
        ]
    ]
    opp = m[["gameid", "teamid", "teamname"]].rename(
        columns={"teamid": "opp_teamid", "teamname": "opp_teamname"}
    )
    games = (
        tables.totals.merge(tables.roster, on=["gameid", "teamid", "position"])
        .merge(m, on=["gameid", "teamid"])
        .merge(opp, on="gameid")
    )
    games = games[games["teamid"] != games["opp_teamid"]]
    return prepare(games.assign(elo=np.nan, opp_elo=np.nan))


def prepare(games):
    """Add team totals, game minutes, the series and the map number, sorted by time."""
    g = games.copy()
    g["date"] = pd.to_datetime(g["date"])
    g["result"] = g["result"].astype(int)
    g["minutes"] = g["gamelength"] / 60.0
    team = g.groupby(["gameid", "teamid"])[["kills", "deaths"]].transform("sum")
    g["team_kills"], g["team_deaths"] = team["kills"], team["deaths"]
    g = g.sort_values(["date", "gameid", "teamid", "position"], kind="mergesort")
    g = g.reset_index(drop=True)
    return add_series(g)


def add_series(g, gap=SERIES_GAP):
    """`series` (an id per team per series: consecutive games against one opponent,
    each within `gap` of the last), `map` (1, 2, ...) and the series' final score
    from this team's side (`series_wins`, `series_losses`)."""
    tg = g.drop_duplicates(["gameid", "teamid"])[
        ["gameid", "teamid", "opp_teamid", "date", "result"]
    ]
    tg = tg.sort_values(["teamid", "date", "gameid"], kind="mergesort")
    new = (
        (tg["teamid"] != tg["teamid"].shift())
        | (tg["opp_teamid"] != tg["opp_teamid"].shift())
        | (tg["date"] - tg["date"].shift() > gap)
    )
    tg = tg.assign(series=new.cumsum())
    tg["map"] = tg.groupby("series").cumcount() + 1
    tg["series_wins"] = tg.groupby("series")["result"].transform("sum")
    tg["series_losses"] = (
        tg.groupby("series")["result"].transform("size") - tg["series_wins"]
    )
    cols = ["gameid", "teamid", "series", "map", "series_wins", "series_losses"]
    return g.merge(tg[cols], on=["gameid", "teamid"], how="left")


def _ew_mean(values, keys, halflife):
    """Pre-game exponentially weighted mean of `values` within each key (earlier
    rows only; NaN for a key's first row) and the weight behind it."""
    d = 0.5 ** (1.0 / halflife)
    frame = pd.DataFrame({"v": values, "k": keys})
    grouped = frame.groupby("k", sort=False)["v"]
    running = grouped.ewm(halflife=halflife).mean().droplevel(0).sort_index()
    mean = running.groupby(frame["k"], sort=False).shift()
    n = grouped.cumcount()
    weight = (1 - d**n) / (1 - d)
    return mean.to_numpy(), weight.to_numpy()


def _shrunk(mean, weight, prior, prior_games):
    mean = np.where(np.isnan(mean), 0.0, mean)
    return (mean * weight + prior * prior_games) / (weight + prior_games)


def add_states(g, halflife, prior_games):
    """`add_stat_states` with one (half-life, prior games) for every stat."""
    return add_stat_states(g, uniform(halflife, prior_games))


def uniform(halflife, prior_games):
    """The same (half-life, prior games) for every stat."""
    return dict.fromkeys(STATS, (halflife, prior_games))


def stat_columns(stat):
    return [f"p_{stat}", f"pace_{stat}", f"t_{stat}", f"o_{stat}"]


def _pace(values, codes):
    """A slow league pace (`PACE_HALFLIFE` rows) before each row; a key's first
    rows take the running mean of everything before them."""
    pace, _ = _ew_mean(values, codes, PACE_HALFLIFE)
    series = pd.Series(values)
    fallback = series.expanding().mean().shift().fillna(series.iloc[0]).to_numpy()
    return np.where(np.isnan(pace), fallback, pace)


def add_stat_states(g, settings):
    """Add each row's pre-game states for every stat, with that stat's own
    (half-life, prior games) from `settings`: `pace_<stat>` (league and role),
    `p_<stat>` (the player, shrunk toward the pace) and `t_<stat>` / `o_<stat>`,
    the team's and the opponent's rate behind the stat (`TEAM_RATE`). League
    paces don't depend on the settings and each weighted mean is taken once, at
    the half-life that needs it, so mixed settings cost little more than one."""
    out = g.copy()
    lr = pd.factorize(out["league"] + "|" + out["position"])[0]
    players = pd.factorize(out["playerid"])[0]
    for stat in STATS:
        halflife, prior_games = settings[stat]
        values = out[stat].to_numpy(float)
        pace = _pace(values, lr)
        out[f"pace_{stat}"] = pace
        mean, weight = _ew_mean(values, players, halflife)
        out[f"p_{stat}"] = _shrunk(mean, weight, pace, prior_games)

    rates = ("team_kills", "team_deaths", "minutes")
    teams = out.drop_duplicates(["gameid", "teamid"])[
        ["gameid", "teamid", "league", *rates]
    ]
    team_codes = pd.factorize(teams["teamid"])[0]
    league_codes = pd.factorize(teams["league"])[0]
    paces = {r: _pace(teams[r].to_numpy(float), league_codes) for r in rates}
    needed = {}
    for stat, (team_rate, opp_rate) in TEAM_RATE.items():
        halflife = settings[stat][0]
        needed[(team_rate, halflife)] = f"{team_rate}@{halflife}"
        needed[(opp_rate, halflife)] = f"{opp_rate}@{halflife}"
    for (rate, halflife), col in needed.items():
        mean, weight = _ew_mean(teams[rate].to_numpy(float), team_codes, halflife)
        teams[col] = _shrunk(mean, weight, paces[rate], TEAM_PRIOR_GAMES)
    cols = list(needed.values())
    own = out[["gameid", "teamid"]].merge(
        teams[["gameid", "teamid", *cols]], how="left"
    )
    opp = out[["gameid", "opp_teamid"]].merge(
        teams[["gameid", "teamid", *cols]].rename(columns={"teamid": "opp_teamid"}),
        how="left",
    )
    for stat, (team_rate, opp_rate) in TEAM_RATE.items():
        halflife = settings[stat][0]
        out[f"t_{stat}"] = own[f"{team_rate}@{halflife}"].to_numpy()
        out[f"o_{stat}"] = opp[f"{opp_rate}@{halflife}"].to_numpy()
    return out


def series_start_states(g):
    """Every map's states replaced by those before the series' first map (a line is
    set before the series). A player who first appears later in the series keeps
    the states before their first map."""
    cols = [c for c in g.columns if c.startswith(("pace_", "p_", "t_", "o_"))]
    cols += ["elo", "opp_elo"]
    first = g.groupby(["series", "playerid"], sort=False)[cols].transform("first")
    out = g.copy()
    out[cols] = first
    return out


def features(g, stat, result):
    """Model inputs for `stat` with the game's result set to `result` (0 or 1, or an
    array): logs of the player, team, opponent and pace rates, role dummies, and
    the result with a term per role."""
    x = pd.DataFrame(
        {
            "player": np.log(g[f"p_{stat}"].clip(lower=0.05)),
            "team": np.log(g[f"t_{stat}"].clip(lower=0.05)),
            "opp": np.log(g[f"o_{stat}"].clip(lower=0.05)),
            "pace": np.log(g[f"pace_{stat}"].clip(lower=0.05)),
        },
        index=g.index,
    )
    win = np.broadcast_to(np.asarray(result, dtype=float), len(g))
    x["win"] = win
    for role in ROLES[1:]:
        is_role = (g["position"] == role).to_numpy(float)
        x[f"is_{role}"] = is_role
        x[f"win_{role}"] = win * is_role
    return x.to_numpy()


def _alpha(y, mu):
    """Negative binomial dispersion by moments: Var = mu + alpha·mu²."""
    return max(MIN_ALPHA, float(((y - mu) ** 2 - mu).sum() / (mu**2).sum()))


class LogLinear:
    """A fitted Poisson regression as plain numbers: exp(b + ((x - mean) / scale) · w)."""

    def __init__(self, mean, scale, coef, intercept):
        self.mean, self.scale = np.asarray(mean), np.asarray(scale)
        self.coef, self.intercept = np.asarray(coef), float(intercept)

    @classmethod
    def from_pipeline(cls, pipe):
        scaler, reg = pipe[0], pipe[-1]
        return cls(scaler.mean_, scaler.scale_, reg.coef_, reg.intercept_)

    def predict(self, x):
        return np.exp(self.intercept + ((x - self.mean) / self.scale) @ self.coef)

    def to_dict(self):
        return {
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "coef": self.coef.tolist(),
            "intercept": self.intercept,
        }


class _Curve:
    """A logistic win curve as plain numbers: sigmoid(a + b · diff)."""

    def __init__(self, a, b):
        self.a, self.b = float(a), float(b)

    def __call__(self, diff):
        return 1 / (1 + np.exp(-(self.a + self.b * np.asarray(diff, dtype=float))))


@dataclass
class PropModel:
    settings: dict  # stat -> (half-life, prior games)
    models: dict = field(default_factory=dict)  # stat -> LogLinear
    alpha: dict = field(default_factory=dict)  # (stat, role, result) -> dispersion
    fantasy_sd: dict = field(default_factory=dict)  # (role, result) -> sd
    win_curve: object = None

    def means(self, g, stat):
        """Expected `stat` in a win and in a loss, one value per row each."""
        m = self.models[stat]
        return m.predict(features(g, stat, 1)), m.predict(features(g, stat, 0))

    def alphas(self, g, stat, result):
        return g["position"].map(lambda r: self.alpha[(stat, r, result)]).to_numpy()

    def win_chance(self, g):
        """Each row's chance of winning a map: `p_map` where given (a live call),
        else the Elo curve on the pre-game ratings."""
        diff = (g["elo"] - g["opp_elo"]).fillna(0.0).to_numpy()
        p = self.win_curve(diff)
        if "p_map" in g:
            given = g["p_map"].to_numpy(dtype=float)
            p = np.where(np.isnan(given), p, given)
        return p

    def to_dict(self):
        """Everything the live projections need, as JSON (`props_weights.json`)."""
        return {
            "settings": {s: list(v) for s, v in self.settings.items()},
            "models": {s: m.to_dict() for s, m in self.models.items()},
            "alpha": {f"{s}|{r}|{w}": a for (s, r, w), a in self.alpha.items()},
            "fantasy_sd": {f"{r}|{w}": v for (r, w), v in self.fantasy_sd.items()},
            "win_curve": [self.win_curve.a, self.win_curve.b],
        }

    @classmethod
    def from_dict(cls, d):
        model = cls({s: tuple(v) for s, v in d["settings"].items()})
        model.models = {s: LogLinear(**m) for s, m in d["models"].items()}
        for key, a in d["alpha"].items():
            stat, role, result = key.split("|")
            model.alpha[(stat, role, int(result))] = a
        for key, v in d["fantasy_sd"].items():
            role, result = key.split("|")
            model.fantasy_sd[(role, int(result))] = v
        model.win_curve = _Curve(*d["win_curve"])
        return model

    def fantasy(self, g):
        """Fantasy points' mean and sd in a win and in a loss."""
        mean = {1: 0.0, 0: 0.0}
        for stat, points in FANTASY.items():
            mw, ml = self.means(g, stat)
            mean[1] = mean[1] + points * mw
            mean[0] = mean[0] + points * ml
        sd = {
            r: g["position"].map(lambda p, r=r: self.fantasy_sd[(p, r)]).to_numpy()
            for r in (0, 1)
        }
        return mean[1], sd[1], mean[0], sd[0]


def load_model(path=WEIGHTS_PATH):
    """The published model (`scripts/evaluate_props.py --write-weights`)."""
    return PropModel.from_dict(json.loads(Path(path).read_text()))


def fantasy_points(g):
    return sum(points * g[stat] for stat, points in FANTASY.items())


def _fit_curve(diff, won):
    """P(win) = sigmoid(a + b · Elo gap), fit by logistic regression."""
    x = np.asarray(diff, dtype=float).reshape(-1, 1)
    reg = LogisticRegression(C=1e6).fit(x / 100, np.asarray(won, dtype=int))
    return _Curve(reg.intercept_[0], reg.coef_[0, 0] / 100)


def fit(g, settings, result_term=True):
    """Fit the per-stat models, dispersions and fantasy spreads on `g` (rows with
    states), and the Elo win curve on its team-games. With `result_term=False`
    the result is left out (an ablation: one distribution regardless of result)."""
    model = PropModel(dict(settings))
    teams = g.drop_duplicates(["gameid", "teamid"])
    diff = (teams["elo"] - teams["opp_elo"]).fillna(0.0).to_numpy()
    model.win_curve = _fit_curve(diff, teams["result"].to_numpy())
    result = g["result"].to_numpy() if result_term else np.zeros(len(g))
    fitted = {}
    for stat in STATS:
        y = g[stat].to_numpy(float)
        reg = make_pipeline(
            StandardScaler(), PoissonRegressor(alpha=1e-6, max_iter=1000)
        )
        reg.fit(features(g, stat, result), y)
        model.models[stat] = LogLinear.from_pipeline(reg)
        mu = model.models[stat].predict(features(g, stat, result))
        fitted[stat] = mu
        for role in ROLES:
            for r in (0, 1):
                mask = (g["position"] == role).to_numpy()
                if result_term:
                    mask &= g["result"].to_numpy() == r
                model.alpha[(stat, role, r)] = _alpha(y[mask], mu[mask])
    points = fantasy_points(g).to_numpy()
    mean = sum(FANTASY[s] * fitted[s] for s in STATS)
    for role in ROLES:
        for r in (0, 1):
            mask = (g["position"] == role).to_numpy()
            if result_term:
                mask &= g["result"].to_numpy() == r
            model.fantasy_sd[(role, r)] = float(np.std(points[mask] - mean[mask]))
    return model


def nb_pmf(mu, alpha, support):
    """Negative binomial pmf over 0..support-1, one row per mean."""
    k = np.arange(support)
    mu = np.asarray(mu, dtype=float)[:, None]
    n = 1.0 / np.asarray(alpha, dtype=float)[:, None]
    return stats.nbinom.pmf(k[None, :], n, n / (n + mu))


def game_pmf(model, g, stat):
    """Each row's projected pmf for one map, and the win and loss pmfs behind it."""
    mw, ml = model.means(g, stat)
    win = nb_pmf(mw, model.alphas(g, stat, 1), SUPPORT[stat])
    loss = nb_pmf(ml, model.alphas(g, stat, 0), SUPPORT[stat])
    p = model.win_chance(g)[:, None]
    return p * win + (1 - p) * loss, win, loss


def result_sequences(best_of, maps):
    """Every way a best-of-`best_of` can go, as (probability exponents, counted
    results): for each sequence, how many wins and losses it has in total (for its
    probability) and among the first `maps` maps (for the stat's total)."""
    need = best_of // 2 + 1
    seqs = []
    for length in range(need, best_of + 1):
        for seq in itertools.product((1, 0), repeat=length):
            w = sum(seq)
            l_ = length - w
            # It must end on the deciding game, with no earlier winner.
            if max(w, l_) != need or (seq[-1] == 1) != (w == need):
                continue
            counted = seq[:maps]
            seqs.append((w, l_, sum(counted), len(counted) - sum(counted)))
    return seqs


def series_pmf(win, loss, p, best_of, maps):
    """Pmf of the total over the first `maps` maps actually played (maps not played
    add nothing), with each map won with chance `p` independently."""
    support = win.shape[1] * maps
    fw, fl = np.fft.rfft(win, n=support), np.fft.rfft(loss, n=support)
    p = np.asarray(p, dtype=float)[:, None]
    total = np.zeros((win.shape[0], support))
    for w, l_, cw, cl in result_sequences(best_of, maps):
        prob = p**w * (1 - p) ** l_
        total += prob * np.fft.irfft(fw**cw * fl**cl, n=support)
    return np.clip(total, 0.0, None)


def series_normal(mean_w, sd_w, mean_l, sd_l, p, best_of, maps):
    """The same sum for a stat that is normal per result: a list of (weight, mean,
    sd) arrays, one per result sequence."""
    parts = []
    for w, l_, cw, cl in result_sequences(best_of, maps):
        prob = p**w * (1 - p) ** l_
        parts.append(
            (prob, cw * mean_w + cl * mean_l, np.sqrt(cw * sd_w**2 + cl * sd_l**2))
        )
    return parts


def game_log_score(model, g, stat):
    """Minus the log of each row's one-map probability of its actual count, from
    the two negative binomials directly (no full pmf: what the CI benchmark needs)."""
    y = g[stat].to_numpy(dtype=float)
    mw, ml = model.means(g, stat)
    p = model.win_chance(g)
    prob = 0.0
    for mu, r, weight in ((mw, 1, p), (ml, 0, 1 - p)):
        n = 1.0 / model.alphas(g, stat, r)
        prob = prob + weight * stats.nbinom.pmf(y, n, n / (n + mu))
    return -np.log(np.clip(prob, 1e-12, None))


def log_score(pmf, y):
    """Negative log of each row's probability of the observed count."""
    y = np.asarray(y, dtype=int)
    inside = y < pmf.shape[1]
    prob = np.where(
        inside, pmf[np.arange(len(y)), np.minimum(y, pmf.shape[1] - 1)], 0.0
    )
    return -np.log(np.clip(prob, 1e-12, None))


def rps(pmf, y):
    """Ranked probability score (the discrete CRPS) of each row's pmf."""
    cdf = np.cumsum(pmf, axis=1)
    k = np.arange(pmf.shape[1])
    return ((cdf - (k[None, :] >= np.asarray(y)[:, None])) ** 2).sum(axis=1)


def prob_over(pmf, line):
    """P(total > line) for a half-point line (one per row)."""
    k = np.arange(pmf.shape[1])
    return (pmf * (k[None, :] > np.asarray(line, dtype=float)[:, None])).sum(axis=1)


def normal_mixture_crps(parts, y, step=0.5):
    """CRPS of a mixture of normals, integrated on a grid."""
    y = np.asarray(y, dtype=float)
    lo = min((m - 5 * s).min() for _, m, s in parts)
    hi = max((m + 5 * s).max() for _, m, s in parts)
    lo, hi = min(lo, y.min()), max(hi, y.max())
    grid = np.arange(lo, hi + step, step)
    cdf = sum(
        np.asarray(w)[:, None]
        * stats.norm.cdf((grid[None, :] - m[:, None]) / s[:, None])
        for w, m, s in parts
    )
    return (((cdf - (grid[None, :] >= y[:, None])) ** 2).sum(axis=1)) * step
