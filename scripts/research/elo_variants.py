"""
elo_variants.py: a harness for testing "margin of victory" functions for player-built Elo.

Published Elo (`prometheus/elo.py`) gives the winner an "actual score" from game length
alone (`elo.winner_score`: 1.0 for very short wins down to 0.65 for very long ones). This
harness replays the same player-built Elo with any other margin function and scores it
exactly as `evaluate_metrics.py` scores "Elo (live)" and "FORGE (live)", so variants can
be compared with the published Elo on identical games. Nothing here writes the DB.

API (see each docstring):

    inputs = load_inputs()                                  # ~30 s, once
    base = replay(inputs, game_length_margin())             # pre-match Elo per (gameid, teamid)
    var = replay(inputs, with_fallback(my_margin))          # margin_fn(games) -> winner's score
    print(COMPARE_HEADER); print(compare(inputs, base, var, "my margin"))
    result = held_out(inputs, make_margin, {"scale": [1000, 2000]}, "gold, tuned")

A margin function takes `inputs.games` (one row per game, the order Elo replays them) and
returns the winner's actual score for every game, in (0.5, 1]; the loser gets 1 minus it.
`inputs.games` has gamelength (seconds) and, for each stat in `STATS`, `w_<stat>` (winner)
and `l_<stat>` (loser). Stats Oracle's Elixir didn't record are NaN (see `clean_stats`), so
a stat-based margin needs a fallback: `with_fallback(fn)` uses the published game-length
score wherever `fn` returns NaN. `per_row(fn)` adapts a function of one row.

Tuning: free parameters are tuned on seasons up to `TUNE_LAST_YEAR` (2021) and the variant
is reported on the later seasons only (`held_out`); the baseline is scored on the same
held-out games. Elo is replayed over every game either way (ratings carry across years),
but scoring, win curves and Form weights only use the years asked for.

Usage:
    uv run python scripts/research/elo_variants.py --baseline   # reproduction check, baseline row, timing
    uv run python scripts/research/elo_variants.py --coverage   # match_stats coverage per year
    uv run python scripts/research/elo_variants.py --example    # a tuned gold-margin variant, held out

On macOS set VECLIB_MAXIMUM_THREADS=1 (BLAS threads stall otherwise).
"""

import argparse
import contextlib
import functools
import io
import itertools
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from prometheus import elo, form
from prometheus.elo import (
    compute_elo_records,
    expected_score,
    load_elo_games,
    load_rosters,
    winner_score,
)
from prometheus.evaluation import (
    game_losses,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.types import INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_metrics as em  # noqa: E402  (scripts/ is not a package)

# End-of-game team stats from `match_stats` given to margin functions.
STATS = [
    "totalgold",
    "kills",
    "towers",
    "barons",
    "dragons",
    "atakhans",
    "heralds",
    "firstherald",
    "firstdragon",
    "firstbaron",
    "firsttower",
    "visionscore",
]
# The published game-length margin (`elo.winner_score` and its defaults).
GAME_LENGTH_DEFAULTS = {
    "upper_bound": 1.0,
    "lower_bound": 0.65,
    "center": 30 * 60,
    "steepness": 3,
}
K_DEFAULT = 20
# Tune on seasons up to this one; report on the later ones.
TUNE_LAST_YEAR = 2021
# Grid keys that go to `replay` (and on to `compute_elo_records`) instead of the margin.
REPLAY_PARAMS = ("K", "league_share", "active_days", "starting_elo")
METRICS = ("elo_live", "forge")
TEST_SETS = ("Domestic", "International")
ELO_COLUMNS = [
    "gameid",
    "teamid",
    "opponent_teamid",
    "gamelength",
    "result",
    "league",
    "date",
]


# --- inputs ------------------------------------------------------------------------


@dataclass
class Inputs:
    """Everything a replay and its scoring need, loaded once.

    games: `elo.load_elo_games()` rows in the same order (what `bootstrap_elo` replays),
        plus year, winner_id, loser_id and `w_<stat>` / `l_<stat>` for every `STATS`.
    rosters: `elo.load_rosters()`.
    frame: `evaluate_metrics.backtest` games (every season, the DB's Elo); the scored
        game set is fixed by it, so every variant is scored on the same games.
    form_games: `form.load_form_games()` rows (before opponent adjustment).
    db_pre_match: the DB's `game_length_elo.pre_match_elo`, indexed by (gameid, teamid).
    db_domestic: leagues in today's `INTERNATIONAL_LEAGUES` that the DB's Elo treated
        as home leagues (the DB was built before they were added); empty when current.
    """

    games: pd.DataFrame
    rosters: dict
    frame: pd.DataFrame
    form_games: pd.DataFrame
    db_pre_match: pd.Series
    db_domestic: tuple
    cache: dict = field(default_factory=dict, repr=False)

    def baseline(self) -> pd.Series:
        """The published Elo (game-length margin, current code), replayed once and cached."""
        if "baseline" not in self.cache:
            self.cache["baseline"] = replay(self, game_length_margin())
        return self.cache["baseline"]

    def baseline_scores(self, years=None, forge=True) -> "Scores":
        """`score` of the baseline on `years`, cached."""
        key = ("scores", None if years is None else tuple(sorted(years)), forge)
        if key not in self.cache:
            self.cache[key] = score(self, self.baseline(), years=years, forge=forge)
        return self.cache[key]


def clean_stats(stats: pd.DataFrame) -> pd.DataFrame:
    """Mark stats Oracle's Elixir didn't record as NaN.

    At ingest (`002_add_matches.py`) a missing stat was filled with that file's mean,
    or 0 when the whole file lacked it. Every stat is a whole number, so a fractional
    value is a filled one. Vision score 0 is a missing one (2014 to 2017). A 0 for a
    stat that didn't exist yet (atakhans before 2025, heralds before 2016) is kept.
    """
    out = stats.copy()
    for col in STATS:
        v = out[col].astype(float)
        out[col] = v.where(v == np.round(v))
    out["visionscore"] = out["visionscore"].where(out["visionscore"] != 0)
    return out


def _load_stat_games(games: pd.DataFrame) -> pd.DataFrame:
    engine = get_engine()
    years = pd.read_sql(
        "SELECT gameid, MIN(year) AS year FROM matches GROUP BY gameid", engine
    )
    stats = clean_stats(
        pd.read_sql(
            f"SELECT gameid, teamid, {', '.join(STATS)} FROM match_stats", engine
        )
    )
    stats = stats.set_index(["gameid", "teamid"])
    out = games.merge(years, on="gameid", how="left")
    won = out["result"].astype(bool).to_numpy()
    out["winner_id"] = np.where(won, out["teamid"], out["opponent_teamid"])
    out["loser_id"] = np.where(won, out["opponent_teamid"], out["teamid"])
    for prefix, col in (("w_", "winner_id"), ("l_", "loser_id")):
        side = stats.reindex(pd.MultiIndex.from_arrays([out["gameid"], out[col]]))
        for stat in STATS:
            out[prefix + stat] = side[stat].to_numpy()
    return out


def load_inputs(verbose=True) -> Inputs:
    """Read the games, rosters, stats, backtest games and Form inputs once (about 30 s)."""
    say = print if verbose else (lambda *a, **k: None)
    t = time.time()
    games = load_elo_games()
    stat_games = _load_stat_games(games)
    rosters = load_rosters()
    say(f"  Elo games, rosters and stats: {time.time() - t:.1f} s")

    t = time.time()
    years = em.get_available_years(em.ALL_MAJOR_LEAGUES)
    with contextlib.redirect_stdout(io.StringIO()):  # backtest prints every month
        frame = em.backtest(
            em.load_games(), em.load_results(), em.load_elo_timeline(), years
        )
    form_games = form.load_form_games()
    say(f"  Backtest games and Form inputs: {time.time() - t:.1f} s")

    db = pd.read_sql(
        "SELECT gameid, teamid, pre_match_elo, home_league FROM game_length_elo",
        get_engine(),
    )
    db_homes = set(db["home_league"].dropna())
    return Inputs(
        games=stat_games,
        rosters=rosters,
        frame=frame,
        form_games=form_games,
        db_pre_match=db.set_index(["gameid", "teamid"])["pre_match_elo"],
        db_domestic=tuple(l for l in INTERNATIONAL_LEAGUES if l in db_homes),
    )


# --- margins -------------------------------------------------------------------------


def game_length_margin(**params):
    """The published margin: `elo.winner_score` on game length (defaults unless overridden)."""
    kw = {**GAME_LENGTH_DEFAULTS, **params}
    return lambda games: winner_score(games["gamelength"].to_numpy(dtype=float), **kw)


def per_row(fn):
    """Adapt `fn(row) -> score` (one game, a Series) to a margin function. Slow (~seconds)."""
    return lambda games: games.apply(fn, axis=1).to_numpy(dtype=float)


def with_fallback(fn, fallback=None):
    """Use `fn`'s score, and `fallback`'s (the published game-length margin) where it is NaN."""
    fallback = fallback or game_length_margin()

    def margin(games):
        s = np.asarray(fn(games), dtype=float)
        return np.where(np.isnan(s), np.asarray(fallback(games), dtype=float), s)

    return margin


def bounded(x, scale, center=0.0, lower=0.65, upper=1.0):
    """Map a raw margin (larger = more decisive win) into (lower, upper) with a logistic.

    `center` is the margin that scores halfway; `scale` how fast it saturates. NaN stays NaN.
    """
    z = (np.asarray(x, dtype=float) - center) / scale
    return lower + (upper - lower) / (1 + np.exp(-z))


def winner_scores(inputs, margin_fn) -> np.ndarray:
    """`margin_fn(inputs.games)` as an array, checked to be one score in (0.5, 1] per game."""
    s = np.asarray(margin_fn(inputs.games), dtype=float).reshape(-1)
    if len(s) != len(inputs.games):
        raise ValueError(
            f"margin returned {len(s)} scores for {len(inputs.games)} games"
        )
    bad = ~((s > 0.5) & (s <= 1.0))  # NaN is bad too
    if bad.any():
        example = inputs.games.loc[bad, "gameid"].iloc[0]
        raise ValueError(
            f"{int(bad.sum())} winner scores outside (0.5, 1] or NaN (first: {example}, "
            f"{s[bad][0]}); use with_fallback for games without stats"
        )
    return s


def margin_elo_change(elo, opponent_elo, game_length, result, K=K_DEFAULT):
    """Elo change for `teamid` when the `game_length` slot carries the winner's score.

    `compute_elo_records` passes each row's gamelength to `elo_func`; `replay` puts the
    margin's winner score in that column, so this is `calculate_game_length_elo_change`
    with the score already computed: K x (actual - expected), actual = score for a win
    and 1 - score for a loss.
    """
    actual = game_length if result else 1 - game_length
    return K * (actual - expected_score(elo, opponent_elo))


@contextlib.contextmanager
def _international(leagues):
    """Temporarily replay with another set of international leagues (None: today's)."""
    if leagues is None:
        yield
    else:
        with mock.patch.object(elo, "INTERNATIONAL_LEAGUES", list(leagues)):
            yield


def replay(inputs, margin_fn, K=K_DEFAULT, international=None, records=False, **kw):
    """Replay player-built Elo over every game with `margin_fn` as the winner's score.

    Args:
        inputs: `load_inputs()` (or any object with `games` and `rosters`).
        margin_fn: `f(games) -> winner score per game` in (0.5, 1] (see module doc).
        K: Elo K factor (published: 20).
        international: replay with these international leagues instead of today's
            `INTERNATIONAL_LEAGUES` (for the DB reproduction check).
        records: return the full `compute_elo_records` frame instead.
        **kw: passed to `compute_elo_records` (league_share, active_days, starting_elo).
    Returns:
        Series of pre-match Elo indexed by (gameid, teamid), two rows per game.
    """
    games = inputs.games[ELO_COLUMNS].assign(
        gamelength=winner_scores(inputs, margin_fn)
    )
    with _international(international):
        out, _ = compute_elo_records(
            games,
            functools.partial(margin_elo_change, K=K),
            rosters=inputs.rosters,
            **kw,
        )
    return out if records else out.set_index(["gameid", "teamid"])["pre_match_elo"]


def pregame_elos(inputs, pre_match: pd.Series) -> pd.DataFrame:
    """`elo.get_pregame_elos` shape (gameid, teamid, elo, opp_elo) from a replay."""
    g = inputs.games
    rows = []
    for team, opp in (("teamid", "opponent_teamid"), ("opponent_teamid", "teamid")):
        rows.append(
            pd.DataFrame(
                {
                    "gameid": g["gameid"].to_numpy(),
                    "teamid": g[team].to_numpy(),
                    "elo": pre_match.reindex(
                        pd.MultiIndex.from_arrays([g["gameid"], g[team]])
                    ).to_numpy(),
                    "opp_elo": pre_match.reindex(
                        pd.MultiIndex.from_arrays([g["gameid"], g[opp]])
                    ).to_numpy(),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


# --- scoring -------------------------------------------------------------------------


@dataclass
class Scores:
    """Per-game losses on the backtest games, aligned with `games`.

    games: gameid, year, league, test_set ("Domestic" / "International"), won.
    losses: {"elo_live": ..., "forge": ...}, each with accuracy, brier, log_loss per game.
    """

    games: pd.DataFrame
    losses: dict

    def mask(self, test_set):
        return (self.games["test_set"] == test_set).to_numpy()

    def log_loss(self, metric, test_set) -> np.ndarray:
        return self.losses[metric]["log_loss"].to_numpy()[self.mask(test_set)]

    def summary(self) -> pd.DataFrame:
        """Games, accuracy, Brier and log loss per (metric, test set)."""
        rows = []
        for metric, losses in self.losses.items():
            for test_set in TEST_SETS:
                l = losses[self.mask(test_set)]
                rows.append(
                    {
                        "metric": metric,
                        "test_set": test_set,
                        "games": len(l),
                        **l.mean().to_dict(),
                    }
                )
        return pd.DataFrame(rows).set_index(["metric", "test_set"])


def _with_elo(frame, pre_match):
    """The backtest frame with its live Elo columns taken from `pre_match`."""
    frame = frame.copy()
    for side in ("blue", "red"):
        key = pd.MultiIndex.from_arrays([frame["gameid"], frame[f"{side}_id"]])
        frame[f"{side}_elo_live"] = pre_match.reindex(key).to_numpy()
    frame["elo_live"] = frame["blue_elo_live"] - frame["red_elo_live"]
    if frame["elo_live"].isna().any():
        raise ValueError("pre_match is missing backtest games")
    return frame


def variant_form_states(inputs, pre_match):
    """Form states with the opponent adjustment by `pre_match` Elo, as the site would."""
    return form.form_states(
        form.opponent_adjust(inputs.form_games, elos=pregame_elos(inputs, pre_match))
    )


def score(inputs, pre_match, years=None, forge=True, states=None) -> Scores:
    """Score a replay as `evaluate_metrics.py` scores Elo (live) and FORGE (live).

    Uses its functions: the backtest games, `out_of_year_probabilities` on the live Elo
    gap (the win curve for each season is fit on the other seasons), `add_form` (Form
    weights fit out of year) and `forge_probabilities` (Elo + Form within a league,
    Elo across). Form's opponent adjustment uses `pre_match` too, as it would if the
    variant were published, so FORGE's blend is refit on the variant.

    Args:
        years: score only these seasons; curves and Form weights then come only from
            them (so tuning years never see held-out results). None: every season.
        forge: also score FORGE (adds the Form pass, about 10 s).
        states: precomputed Form states (default: `variant_form_states`).
    """
    frame = inputs.frame
    if years is not None:
        frame = frame[frame["year"].isin(list(years))].reset_index(drop=True)
    frame = _with_elo(frame, pre_match)
    losses = {
        "elo_live": game_losses(
            out_of_year_probabilities(frame, "elo_live"), frame["won"]
        )
    }
    if forge:
        if states is None:
            states = variant_form_states(inputs, pre_match)
        frame = em.add_form(frame, states)
        losses["forge"] = game_losses(em.forge_probabilities(frame), frame["won"])
    games = frame[["gameid", "year", "league", "test_set", "won"]].reset_index(
        drop=True
    )
    return Scores(games, losses)


# --- comparison ----------------------------------------------------------------------

COMPARE_HEADER = (
    "| Variant | Elo dom. log loss (Δ, 95% CI) | Elo intl. log loss (Δ, 95% CI) "
    "| FORGE dom. log loss (Δ, 95% CI) | FORGE intl. log loss (Δ, 95% CI) |\n"
    "|---|---|---|---|---|"
)


def _as_scores(inputs, x, years):
    return x if isinstance(x, Scores) else score(inputs, x, years=years)


def deltas(baseline: Scores, variant: Scores) -> pd.DataFrame:
    """Log loss of each, and variant minus baseline with a paired 95% interval."""
    if not np.array_equal(
        baseline.games["gameid"].to_numpy(), variant.games["gameid"].to_numpy()
    ):
        raise ValueError("baseline and variant were scored on different games")
    rows = []
    for metric in METRICS:
        if metric not in baseline.losses or metric not in variant.losses:
            continue
        for test_set in TEST_SETS:
            b, v = (
                baseline.log_loss(metric, test_set),
                variant.log_loss(metric, test_set),
            )
            if len(v) == 0:
                continue
            mean, lo, hi = paired_bootstrap(v, b)
            rows.append(
                {
                    "metric": metric,
                    "test_set": test_set,
                    "games": len(v),
                    "baseline": b.mean(),
                    "variant": v.mean(),
                    "delta": mean,
                    "lo": lo,
                    "hi": hi,
                }
            )
    return pd.DataFrame(rows).set_index(["metric", "test_set"])


def compare(inputs, baseline_pre, variant_pre, label, years=None) -> str:
    """One markdown row (under `COMPARE_HEADER`): the variant's log loss and Δ vs baseline.

    `baseline_pre` / `variant_pre` are pre-match Series from `replay`, or `Scores`
    already computed on the same `years`. Δ < 0 means the variant is better; an
    interval that excludes 0 is a real difference (the significance rule in AGENTS.md).
    """
    d = deltas(
        _as_scores(inputs, baseline_pre, years), _as_scores(inputs, variant_pre, years)
    )
    cells = []
    for metric in METRICS:
        for test_set in TEST_SETS:
            if (metric, test_set) not in d.index:
                cells.append("–")
                continue
            r = d.loc[(metric, test_set)]
            cells.append(
                f"{r['variant']:.4f} ({r['delta']:+.4f}, {r['lo']:+.4f} to {r['hi']:+.4f})"
            )
    return f"| {label} | " + " | ".join(cells) + " |"


# --- tuning on early years, reporting on later ones ----------------------------------


def split_years(years, last_train_year=TUNE_LAST_YEAR):
    """(train, test): seasons up to `last_train_year`, and the later ones."""
    years = sorted(set(int(y) for y in years))
    train = [y for y in years if y <= last_train_year]
    test = [y for y in years if y > last_train_year]
    if not train or not test:
        raise ValueError(
            f"split at {last_train_year} leaves no train or no test seasons: {years}"
        )
    return train, test


def param_grid(grid):
    """A list of parameter dicts: a dict of lists (all combinations) or a list of dicts."""
    if isinstance(grid, dict):
        keys = list(grid)
        return [
            dict(zip(keys, values))
            for values in itertools.product(*(grid[k] for k in keys))
        ]
    return [dict(p) for p in grid]


def _split_params(params):
    replay_kw = {k: v for k, v in params.items() if k in REPLAY_PARAMS}
    margin_kw = {k: v for k, v in params.items() if k not in REPLAY_PARAMS}
    return margin_kw, replay_kw


def tune(
    inputs, make_margin, grid, years, objective=("elo_live", "Domestic"), verbose=True
) -> pd.DataFrame:
    """Score every parameter set on `years` only; best (lowest mean log loss) first.

    Returns one row per parameter set: each parameter, `params` (the dict) and
    `objective` (mean log loss of `objective` on `years`).

    `make_margin(**params)` returns a margin function. Grid keys in `REPLAY_PARAMS`
    (K, league_share, ...) go to `replay` instead. `objective` is (metric, test set);
    a "forge" objective adds the Form pass to each evaluation.
    """
    metric, test_set = objective
    rows = []
    for params in param_grid(grid):
        margin_kw, replay_kw = _split_params(params)
        pre = replay(inputs, make_margin(**margin_kw), **replay_kw)
        s = score(inputs, pre, years=years, forge=metric == "forge")
        rows.append(
            {
                **params,
                "params": params,
                "objective": s.log_loss(metric, test_set).mean(),
            }
        )
        if verbose:
            print(f"    {params}: {rows[-1]['objective']:.5f}")
    return (
        pd.DataFrame(rows)
        .sort_values("objective", kind="mergesort")
        .reset_index(drop=True)
    )


@dataclass
class HeldOut:
    params: dict  # chosen on the train years
    tuning: pd.DataFrame  # every parameter set's train objective
    train_years: list
    test_years: list
    pre_match: pd.Series  # the chosen variant's replay
    scores: Scores  # on the test years
    row: str  # `compare` row on the test years


def held_out(
    inputs,
    make_margin,
    grid,
    label,
    last_train_year=TUNE_LAST_YEAR,
    objective=("elo_live", "Domestic"),
    verbose=True,
) -> HeldOut:
    """Tune on seasons up to `last_train_year`, then compare with the baseline on later ones.

    The baseline (published Elo, current code) is scored on the same held-out games
    with the same procedure, so a gain can't come from in-sample tuning.
    """
    train, test = split_years(inputs.frame["year"].unique(), last_train_year)
    if verbose:
        print(f"  Tuning {label} on {train[0]}–{train[-1]}:")
    table = tune(inputs, make_margin, grid, train, objective, verbose)
    params = table["params"].iloc[0]
    margin_kw, replay_kw = _split_params(params)
    pre = replay(inputs, make_margin(**margin_kw), **replay_kw)
    scores = score(inputs, pre, years=test)
    row = compare(
        inputs, inputs.baseline_scores(test), scores, f"{label} {params}", years=test
    )
    return HeldOut(params, table, train, test, pre, scores, row)


# --- CLI ------------------------------------------------------------------------------


def coverage(inputs) -> pd.DataFrame:
    """Share of games per season with both teams' value of each stat recorded."""
    g = inputs.games
    out = {}
    for stat in STATS:
        out[stat] = (
            (g[f"w_{stat}"].notna() & g[f"l_{stat}"].notna()).groupby(g["year"]).mean()
        )
    table = pd.DataFrame(out)
    table.insert(0, "games", g.groupby("year").size())
    return table


def reproduction_check(inputs):
    """Replay the game-length margin and compare with the DB's pre_match_elo.

    The DB was built by `bootstrap_elo` with the international leagues of its day;
    `inputs.db_domestic` holds the ones it treated as home leagues. Replaying with that
    classification must reproduce the DB exactly; with today's it differs only where
    those leagues were played.
    """
    db = inputs.db_pre_match
    current = replay(inputs, game_length_margin())
    diff_now = (current - db.reindex(current.index)).abs()
    lines = [
        f"Current code vs DB: max |Δ| = {diff_now.max():.6g} over {len(diff_now):,} team-games; "
        f"{int((diff_now > 1e-6).sum()):,} differ"
    ]
    if inputs.db_domestic:
        era = [l for l in INTERNATIONAL_LEAGUES if l not in inputs.db_domestic]
        as_built = replay(inputs, game_length_margin(), international=era)
        diff = (as_built - db.reindex(as_built.index)).abs()
        lines.append(
            f"DB built with {', '.join(inputs.db_domestic)} as home leagues (since added to "
            f"INTERNATIONAL_LEAGUES). Replaying that way: max |Δ| = {diff.max():.3g}"
        )
        changed = diff_now[diff_now > 1e-6].index.get_level_values("gameid")
        if len(changed):
            first = inputs.games.loc[inputs.games["gameid"].isin(changed), "date"].min()
            lines.append(f"Current-code differences start at {first}")
    else:
        as_built, diff = current, diff_now
    assert diff.max() < 1e-6, "replay does not reproduce the DB's game_length_elo"
    lines.append("Reproduction: OK (max |Δ| < 1e-6)")
    return as_built, "\n".join(lines)


def evaluate_metrics_check(inputs, as_built):
    """`score` on the DB-reproducing replay equals `evaluate_metrics.score` on the DB."""
    frame = em.add_form(inputs.frame, em.form_states())
    theirs = {}
    for key, _, cols in em.METRICS:
        if key in METRICS:
            p = (
                em.forge_probabilities(frame)
                if cols == em.FORGE
                else out_of_year_probabilities(frame, cols)
            )
            theirs[key] = game_losses(p, frame["won"])["log_loss"].to_numpy()
    mine = score(inputs, as_built)
    worst = max(
        np.abs(mine.losses[k]["log_loss"].to_numpy() - theirs[k]).max() for k in METRICS
    )
    assert worst < 1e-9, f"score differs from evaluate_metrics by {worst}"
    return f"Same per-game log loss as evaluate_metrics.py on the DB (max |Δ| = {worst:.2g})"


def _summary_table(scores):
    s = scores.summary()
    lines = [
        "| Metric | Test set | Games | Accuracy | Brier | Log loss |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for (metric, test_set), r in s.iterrows():
        lines.append(
            f"| {metric} | {test_set} | {int(r['games']):,} | {r['accuracy']:.1%} "
            f"| {r['brier']:.4f} | {r['log_loss']:.4f} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Reproduction check, baseline row and timing",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="match_stats coverage per season"
    )
    parser.add_argument(
        "--example", action="store_true", help="A tuned gold-margin variant, held out"
    )
    args = parser.parse_args()
    if not (args.baseline or args.coverage or args.example):
        parser.error("pick --baseline, --coverage or --example")

    t = time.time()
    print("Loading inputs...")
    inputs = load_inputs()
    print(f"  load_inputs: {time.time() - t:.1f} s")

    if args.coverage:
        print("\nShare of games with both teams' stat recorded:\n")
        print(coverage(inputs).to_string(float_format=lambda v: f"{v:.2f}"))

    if args.baseline:
        print()
        as_built, text = reproduction_check(inputs)
        print(text)
        print(evaluate_metrics_check(inputs, as_built))

        t = time.time()
        base = inputs.baseline()
        t_replay = time.time() - t
        t = time.time()
        full = score(inputs, base)
        t_score = time.time() - t
        t = time.time()
        score(inputs, base, forge=False)
        t_elo = time.time() - t
        print(
            f"\nTiming: replay {t_replay:.1f} s, score with FORGE {t_score:.1f} s, Elo only {t_elo:.1f} s"
        )

        years = sorted(full.games["year"].unique())
        print(
            f"\n## Baseline (game-length margin, current code), every season {years[0]}–{years[-1]}\n"
        )
        print(_summary_table(full))
        train, test = split_years(years)
        held = inputs.baseline_scores(test)
        print(f"\n## Baseline on the held-out seasons {test[0]}–{test[-1]}\n")
        print(_summary_table(held))
        print("\n" + COMPARE_HEADER)
        print(compare(inputs, held, held, "baseline (vs itself)", years=test))

    if args.example:

        def gold_margin(scale):
            return with_fallback(
                lambda g: bounded(g["w_totalgold"] - g["l_totalgold"], scale)
            )

        t = time.time()
        result = held_out(
            inputs,
            gold_margin,
            {"scale": [2000, 5000, 10000]},
            "gold gap, logistic 0.65–1",
        )
        print(f"\n  held_out: {time.time() - t:.1f} s\n")
        print(COMPARE_HEADER)
        print(result.row)


if __name__ == "__main__":
    main()
