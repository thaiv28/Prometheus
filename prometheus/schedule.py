"""Upcoming and recent pro matches from Leaguepedia, matched to our teams and predicted.

Leaguepedia's Cargo API (lol.fandom.com) lists every scheduled pro match with its
teams, start time, best-of and, once played, the result. It needs no key but
rate-limits anonymous clients after a few quick calls, so a build makes one or two
paged requests and backs off when refused.

Predictions use the published forecasts: FORGE between two teams of the same
league (with its own weights outside the major leagues), and Elo alone between
leagues (as the FORGE head to head does).
A series chance follows from the one-game chance, treating games as independent.

Each build updates a prediction log (JSON): a match's prediction is refreshed
until it starts and then frozen, and its result is filled in once Leaguepedia has
it. Matches that were already over before they entered the log get a
reconstructed prediction from the ratings as they stood the day before, and are
marked as such.
"""

import datetime
import http.cookiejar
import json
import math
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from prometheus import markets
from prometheus.elo import LatestElos, get_latest_elos
from prometheus.forge import (
    CROSS_REGION_ELO_WEIGHT,
    ELO_WEIGHT,
    FORM_POINTS,
    other_league_forge_probability,
    other_league_weight,
    team_forms,
)
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

API_URL = "https://lol.fandom.com/api.php"
USER_AGENT = "Prometheus/1.0 (https://prometheus.thaiv.dev; https://github.com/thaiv28/Prometheus)"
PAGE_SIZE = 500
# Seconds to wait after each rate-limit refusal; the API usually lets a client
# back in within a few minutes.
BACKOFF = (20, 40, 60, 90, 120)
MAJORS = [l.value for l in ALL_MAJOR_LEAGUES]

# Leaguepedia's league names mapped to Oracle's Elixir league codes, so a match is
# shown under the league it is played in. Unmapped events take their league from
# the teams' home leagues (see `event_league`).
EVENT_LEAGUES = {
    "LoL Champions Korea": "LCK",
    "Tencent LoL Pro League": "LPL",
    "LoL EMEA Championship": "LEC",
    "League of Legends Championship Series": "LCS",
    "League of Legends Championship of The Americas North": "LCS",
    "World Championship": "Worlds",
    "Mid-Season Invitational": "MSI",
    "Esports World Cup": "EWC",
    "First Stand": "FST",
    "Demacia Cup Global Invitational": "DCGI",
    "EMEA Masters": "EM",
    "World Star Challengers Invitational": "WSCI",
    "LCK Challengers League": "LCKC",
    "LCK Academy Series": "LAS",
    "North American Challengers League": "NACL",
    "Circuit Brazilian League of Legends": "CBLOL",
    "Circuito Desafiante": "CD",
    "League of Legends Championship Pacific": "LCP",
    "Pacific Championship Series": "PCS",
    "Vietnam Championship Series": "VCS",
    "LoL Japan League": "LJL",
    "La Ligue Française": "LFL",
    "Prime League Pro Division": "PRM",
    "Liga Española de League of Legends": "LES",
    "Northern League of Legends Championship": "NLC",
    "Turkish Championship League": "TCL",
    "Hitpoint Masters": "HM",
    "Hitpoint Challengers": "HC",
    "Esports Balkan League": "EBL",
    "Hellenic Legends League": "HLL",
    "Rift Legends": "RL",
    "Arabian League": "AL",
    "Liga Portuguesa": "LPLOL",
    "LIT": "LIT",
}

# Leaguepedia names that don't fold to an Oracle's Elixir name. Keys are folded
# (see `fold`); values are team names as they appear in `matches`.
ALIASES_PATH = Path(__file__).with_name("team_aliases.json")


# Letters that Unicode doesn't split into a base letter and an accent.
_PLAIN_LETTERS = str.maketrans(
    {"ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "đ": "d", "ł": "l", "þ": "th"}
)


def fold(name):
    """Lower-case, accent-free, punctuation-free form of a team name."""
    name = str(name).lower().translate(_PLAIN_LETTERS)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def strip_disambiguation(name):
    """'LYON (2024 American Team)' -> 'LYON'. Leaguepedia adds these to tell apart teams with one name."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(name)).strip()


# ---------------------------------------------------------------- fetching


_opener = None

# Local builds can keep the bot password in a gitignored `.env` at the repo root.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
CREDENTIALS = ("LEAGUEPEDIA_USER", "LEAGUEPEDIA_PASSWORD")


def credentials(env_path=ENV_PATH, environ=os.environ):
    """(user, password) from the environment, else from `env_path` (KEY=VALUE lines)."""
    values = {key: environ.get(key) for key in CREDENTIALS}
    if not all(values.values()) and Path(env_path).exists():
        for line in Path(env_path).read_text().splitlines():
            key, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and key.strip() in CREDENTIALS and not values[key.strip()]:
                values[key.strip()] = value.strip().strip("'\"")
    return values["LEAGUEPEDIA_USER"], values["LEAGUEPEDIA_PASSWORD"]


def _client():
    """A URL opener, logged in when LEAGUEPEDIA_USER and LEAGUEPEDIA_PASSWORD are set
    (in the environment, or in `.env` for local builds).

    Logged-in clients (a bot password from Special:BotPasswords) get a much higher
    rate limit than anonymous ones, which matters on shared CI addresses.
    """
    global _opener
    if _opener is not None:
        return _opener
    _opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    _opener.addheaders = [("User-Agent", USER_AGENT)]
    user, password = credentials()
    if user and password:
        token_url = (
            API_URL
            + "?"
            + urllib.parse.urlencode(
                {"action": "query", "meta": "tokens", "type": "login", "format": "json"}
            )
        )
        with _opener.open(token_url, timeout=30) as response:
            token = json.load(response)["query"]["tokens"]["logintoken"]
        body = urllib.parse.urlencode(
            {
                "action": "login",
                "lgname": user,
                "lgpassword": password,
                "lgtoken": token,
                "format": "json",
            }
        ).encode()
        with _opener.open(API_URL, data=body, timeout=30) as response:
            result = json.load(response).get("login", {}).get("result")
        if result != "Success":
            print(f"Leaguepedia login failed ({result}); continuing anonymously.")
    return _opener


def _get(params, sleep=time.sleep):
    url = API_URL + "?" + urllib.parse.urlencode(params)
    for wait in (*BACKOFF, None):
        with _client().open(url, timeout=30) as response:
            data = json.load(response)
        if "cargoquery" in data:
            return [row["title"] for row in data["cargoquery"]]
        code = data.get("error", {}).get("code")
        if code != "ratelimited" or wait is None:
            raise RuntimeError(
                f"Leaguepedia refused the schedule query: {data.get('error')}"
            )
        sleep(wait)


def fetch_schedule(start, end, sleep=time.sleep):
    """Every pro match scheduled from `start` up to `end` (UTC dates), from Leaguepedia.

    Returns a DataFrame: match_id, start (UTC timestamp), team1, team2, best_of,
    winner (1, 2 or None), score1, score2, event (tournament name), event_league
    (Leaguepedia league name), overview_page.
    """
    fields = (
        "MS.MatchId=match_id, MS.DateTime_UTC=start, MS.Team1=team1, MS.Team2=team2, "
        "MS.BestOf=best_of, MS.Winner=winner, MS.Team1Score=score1, MS.Team2Score=score2, "
        "MS.OverviewPage=overview_page, T.Name=event, T.League=event_league"
    )
    rows, offset = [], 0
    while True:
        page = _get(
            {
                "action": "cargoquery",
                "format": "json",
                "tables": "MatchSchedule=MS, Tournaments=T",
                "join_on": "MS.OverviewPage=T.OverviewPage",
                "fields": fields,
                "where": f"MS.DateTime_UTC >= '{start}' AND MS.DateTime_UTC < '{end}'",
                "order_by": "MS.DateTime_UTC, MS.MatchId",
                "limit": PAGE_SIZE,
                "offset": offset,
            },
            sleep=sleep,
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        sleep(5)
    return parse_schedule(rows)


def parse_schedule(rows):
    """Cargo rows -> tidy schedule frame (see `fetch_schedule`)."""
    cols = [
        "match_id",
        "start",
        "team1",
        "team2",
        "best_of",
        "winner",
        "score1",
        "score2",
        "event",
        "event_league",
        "overview_page",
    ]
    df = pd.DataFrame(rows).reindex(columns=cols)
    if df.empty:
        return df
    df["start"] = pd.to_datetime(df["start"], utc=True, errors="coerce")
    for col in ("best_of", "winner", "score1", "score2"):
        df[col] = pd.to_numeric(df[col].replace("", None), errors="coerce")
    df["best_of"] = df["best_of"].fillna(1).astype(int)
    df["event"] = df["event"].replace("", None).fillna(df["overview_page"])
    df = df.dropna(subset=["match_id", "start"]).drop_duplicates("match_id")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- team matching


class TeamMatcher:
    """Resolves Leaguepedia team names to team names in our data.

    Tries, in order: an alias, the exact name, the folded name, and the folded name
    without Leaguepedia's "(... Team)" disambiguation. Among teams sharing a folded
    name the one that played most recently wins.
    """

    def __init__(self, teams, aliases=None):
        """`teams`: rows with teamname and latest_date (e.g. `get_latest_elos`)."""
        order = teams.sort_values("latest_date", ascending=False)["teamname"]
        self.names = set(order)
        self.folded = {}
        for name in order:
            self.folded.setdefault(fold(name), name)
        if aliases is None:
            aliases = (
                json.loads(ALIASES_PATH.read_text()) if ALIASES_PATH.exists() else {}
            )
        self.aliases = {fold(k): v for k, v in aliases.items()}

    def __call__(self, name):
        if not isinstance(name, str) or not name or name == "TBD":
            return None
        for key in (fold(name), fold(strip_disambiguation(name))):
            if key in self.aliases and self.aliases[key] in self.names:
                return self.aliases[key]
        if name in self.names:
            return name
        return self.folded.get(fold(name)) or self.folded.get(
            fold(strip_disambiguation(name))
        )


# ---------------------------------------------------------------- probabilities


def series_probability(p, best_of):
    """Chance to win a best-of-`best_of` series when each game is won with chance `p`."""
    need = best_of // 2 + 1
    q = 1 - p
    # Win the deciding game after k losses, for k = 0 .. need - 1.
    return sum(math.comb(need - 1 + k, k) * p**need * q**k for k in range(need))


def team_ratings(forms_now, elos):
    """One row per team name: home league, Elo, Form (Elo points) and FORGE.

    `forms_now` is `team_forms(...)[0]`; `elos` is `get_latest_elos` output (as of
    the same moment). Teams without Form get FORGE = Elo.
    """
    elos = elos.sort_values("latest_date", ascending=False).drop_duplicates("teamname")
    forms = forms_now.sort_values("latest_date", ascending=False).drop_duplicates(
        "teamname"
    )
    df = elos[["teamname", "league", "elo", "latest_date"]].merge(
        forms[["teamname", "form"]], on="teamname", how="left"
    )
    df["has_form"] = df["form"].notna()
    df["form"] = FORM_POINTS * df["form"].fillna(0.0)
    df["forge"] = df["elo"] + df["form"]
    return df.set_index("teamname")


def game_probability(a, b):
    """(chance team `a` wins one game, method) for two `team_ratings` rows."""
    if a["league"] != b["league"]:
        return 1 / (
            1 + math.exp(-CROSS_REGION_ELO_WEIGHT * (a["elo"] - b["elo"]))
        ), "elo-cross"
    if a["league"] in MAJORS:
        return 1 / (1 + math.exp(-ELO_WEIGHT * (a["forge"] - b["forge"]))), "forge"
    if a["has_form"] and b["has_form"]:
        return float(
            other_league_forge_probability(a["elo"] - b["elo"], a["form"] - b["form"])
        ), "forge"
    weight = other_league_weight(a["league"])
    return 1 / (1 + math.exp(-weight * (a["elo"] - b["elo"]))), "elo"


def event_league(row, home1, home2):
    """The league a match is shown under.

    - Two teams from one league at that league's own event show under it
      (Leaguepedia files the LPL regional finals under the World Championship).
    - Otherwise the event's own league code (an LCS promotion series is "LCS";
      `is_major` decides whether it counts as a major-league match).
    - Otherwise the teams' shared home league, "Intl" for teams from two leagues,
      or whichever league we know.
    """
    page = str(row.get("overview_page") or "").split("/")[0]
    shared = home1 if home1 and home1 == home2 else None
    if shared and page == shared:
        return shared
    code = EVENT_LEAGUES.get(row.get("event_league"))
    if code:
        return code
    if shared:
        return shared
    if home1 and home2:
        return "Intl"
    return home1 or home2 or "Other"


def predict(schedule, ratings, match_team):
    """Predictions for every scheduled match whose two teams we can rate.

    Returns one dict per match with the schedule fields plus our team names, leagues,
    p_game and p_series (for team 1), method, and `matched` (False when a team is
    unknown; those rows carry no probability).
    """
    out = []
    for row in schedule.to_dict(orient="records"):
        ours = [match_team(row["team1"]), match_team(row["team2"])]
        rated = [ratings.loc[t] if t in ratings.index else None for t in ours]
        homes = [None if r is None else r["league"] for r in rated]
        rec = {
            "match_id": row["match_id"],
            "start": row["start"].strftime("%Y-%m-%dT%H:%MZ"),
            "team1": row["team1"],
            "team2": row["team2"],
            "ours1": ours[0],
            "ours2": ours[1],
            "home1": homes[0],
            "home2": homes[1],
            "best_of": int(row["best_of"]),
            "event": row["event"],
            "league": event_league(row, *homes),
            "matched": all(r is not None for r in rated) and ours[0] != ours[1],
        }
        if rec["matched"]:
            p, method = game_probability(*rated)
            rec.update(
                p_game=round(p, 4),
                p_series=round(series_probability(p, rec["best_of"]), 4),
                method=method,
            )
        out.append(rec)
    return out


# ---------------------------------------------------------------- the log


def load_log(path):
    path = Path(path)
    if not path.exists():
        return {}
    return {m["match_id"]: m for m in json.loads(path.read_text())["matches"]}


def save_log(log, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    matches = sorted(log.values(), key=lambda m: (m["start"], m["match_id"]))
    path.write_text(json.dumps({"matches": matches}, ensure_ascii=False, indent=1))


def _result(row):
    if pd.isna(row["winner"]):
        return {}
    return {
        "winner": int(row["winner"]),
        "score1": None if pd.isna(row["score1"]) else int(row["score1"]),
        "score2": None if pd.isna(row["score2"]) else int(row["score2"]),
    }


def update_log(log, schedule, predictions, now, data_through, reconstruct=None):
    """Fold today's schedule and predictions into the log, in place.

    - A match that hasn't started gets today's prediction (replacing any earlier one),
      stamped with `data_through` (the newest game behind the ratings).
    - A match that has started keeps the prediction it had; if it never had one, it
      gets `reconstruct(match_row)` (a prediction from the ratings the day before),
      marked reconstructed.
    - Results come from the schedule whenever it has them.
    Schedule changes (a team named, a time moved) are taken until the match starts.
    """
    by_id = {p["match_id"]: p for p in predictions}
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    for row in schedule.to_dict(orient="records"):
        mid = row["match_id"]
        pred = by_id.get(mid)
        old = log.get(mid)
        started = pred["start"] <= now_s
        if not started:
            entry = {
                **pred,
                "predicted": now_s,
                "data_through": data_through,
                "reconstructed": False,
            }
            if old is not None and pred.get("matched"):
                # Until a newer price replaces them.
                for key in ("market", "market_12h"):
                    if key in old:
                        entry[key] = old[key]
        elif old is not None and old.get("matched"):
            entry = old
        else:
            entry = reconstruct(row) if reconstruct else {**pred, "matched": False}
            entry = {**entry, "reconstructed": True}
        entry = {
            k: v for k, v in entry.items() if k not in ("winner", "score1", "score2")
        }
        entry.update(_result(row))
        log[mid] = entry
    return log


# ---------------------------------------------------------------- building


def current_ratings(states):
    """`team_ratings` for today from the Form states of every game so far."""
    forms_now, _ = team_forms(states)
    return team_ratings(forms_now, get_latest_elos("game_length"))


def ratings_before(states, day):
    """`team_ratings` from games before `day` (a date): what we knew the day before."""
    forms_now, _ = team_forms(states[pd.to_datetime(states["date"]).dt.date < day])
    return team_ratings(
        forms_now, get_latest_elos("game_length", day - datetime.timedelta(days=1))
    )


class RatingsBefore:
    """`ratings_before(states, day)` for many days, cached by day.

    Same ratings, but the game days and the Elo history are read once (on the
    first call) instead of for every day: about 0.15 s a day instead of 1.2 s,
    which is most of the market benchmark's run time.
    """

    def __init__(self, states):
        self.states = states
        self.cache = {}
        self._days = None
        self._elos = None

    def __call__(self, day):
        if day not in self.cache:
            if self._elos is None:
                self._days = pd.to_datetime(self.states["date"]).dt.date
                self._elos = LatestElos("game_length")
            forms_now, _ = team_forms(self.states[self._days < day])
            self.cache[day] = team_ratings(
                forms_now, self._elos(day - datetime.timedelta(days=1))
            )
        return self.cache[day]

    def __len__(self):
        return len(self.cache)


def build_predictions(
    states,
    log_path,
    days_back=3,
    days_ahead=7,
    backfill_days=30,
    now=None,
    schedule=None,
):
    """Fetch the schedule around today, predict it, update and save the log.

    `states` is `form.form_states(...)` for every game. A new log is backfilled
    `backfill_days` back. Returns (log, matcher_stats) where matcher_stats counts
    matched and unmatched teams in this fetch, for reporting.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    log = load_log(log_path)
    back = days_back if log else backfill_days
    if schedule is None:
        schedule = fetch_schedule(
            (now - datetime.timedelta(days=back)).date(),
            (now + datetime.timedelta(days=days_ahead + 1)).date(),
        )

    ratings = current_ratings(states)
    match_team = TeamMatcher(ratings.reset_index())
    data_through = str(pd.to_datetime(states["date"]).max())[:10]
    predictions = predict(schedule, ratings, match_team)

    before = RatingsBefore(states)

    def reconstruct(row):
        day = row["start"].date()
        rec = predict(pd.DataFrame([row]), before(day), match_team)[0]
        return {
            **rec,
            "predicted": None,
            "data_through": str(day - datetime.timedelta(days=1)),
        }

    update_log(log, schedule, predictions, now, data_through, reconstruct)
    priced = attach_market_prices(log, ratings, now)
    save_log(log, log_path)
    unmatched = sorted(
        {
            p[f"team{i}"]
            for p in predictions
            for i in (1, 2)
            if p[f"ours{i}"] is None and p[f"team{i}"] not in ("TBD", None)
        }
    )
    return log, {
        "matches": len(predictions),
        "matched": sum(p["matched"] for p in predictions),
        "unmatched": unmatched,
        "priced": priced,
        "at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "data_through": data_through,
    }


def attach_market_prices(log, ratings, now, fetch=None):
    """Kalshi's current chance on every logged match that hasn't started (see
    `markets.attach_prices`). Never fails the build: on any error, or with
    KALSHI_PRICES=0, matches keep the prices they had. Returns the number priced,
    or None when skipped or failed."""
    if os.environ.get("KALSHI_PRICES", "1") == "0":
        return None
    try:
        open_markets = (fetch or markets.fetch_open_markets)()
        aliases = json.loads(ALIASES_PATH.read_text()) if ALIASES_PATH.exists() else {}
        match_team = TeamMatcher(
            ratings.reset_index(), {**aliases, **markets.MARKET_ALIASES}
        )
        return markets.attach_prices(log, open_markets, match_team, now)
    except Exception as e:  # network, rate limit, schema change
        print(f"Predictions: Kalshi prices not updated ({e}).")
        return None


def is_major(entry):
    """A major-league or international match (the home page's set). A major
    league's event counts only when a team from that league plays (not an LCS
    promotion series between two challengers)."""
    if entry["league"] in INTERNATIONAL_LEAGUES:
        return True
    return entry["league"] in MAJORS and entry["league"] in (
        entry.get("home1"),
        entry.get("home2"),
    )


def display_name(entry, side):
    """Our team name when matched, else Leaguepedia's without its disambiguation."""
    return entry.get(f"ours{side}") or strip_disambiguation(entry[f"team{side}"])


def scorecard(entries):
    """How the predictions did, for matched entries with a result.

    Returns rows for "Saved before the match", "Reconstructed" and "All": series
    called and picked right, games and games picked right, and the mean log loss
    per game (each game in a series scored on the one-game chance). A 50-50 call
    counts as half right.
    """
    rows = []
    groups = [
        ("Saved before the match", lambda e: not e.get("reconstructed")),
        ("Reconstructed", lambda e: e.get("reconstructed")),
        ("All", lambda e: True),
    ]
    done = [e for e in entries if e.get("matched") and e.get("winner") in (1, 2)]
    for label, keep in groups:
        sel = [e for e in done if keep(e)]
        series = right = games = games_right = 0
        loss = 0.0
        for e in sel:
            p = e["p_series"]
            series += 1
            right += 0.5 if p == 0.5 else float((p > 0.5) == (e["winner"] == 1))
            w1, w2 = e.get("score1"), e.get("score2")
            if w1 is None or w2 is None or w1 + w2 == 0:
                w1, w2 = (1, 0) if e["winner"] == 1 else (0, 1)
            g = min(max(e["p_game"], 1e-6), 1 - 1e-6)
            games += w1 + w2
            games_right += (w1 if g > 0.5 else w2) if g != 0.5 else (w1 + w2) / 2
            loss -= w1 * math.log(g) + w2 * math.log(1 - g)
        rows.append(
            {
                "label": label,
                "series": series,
                "right": right,
                "series_pct": None if not series else 100 * right / series,
                "games": games,
                "games_right": games_right,
                "games_pct": None if not games else 100 * games_right / games,
                "log_loss": None if not games else loss / games,
            }
        )
    return rows


# Tables III and IV: FORGE calls within a major league, and every other call (Elo
# across leagues, and FORGE or Elo within other leagues), each saved before the
# match or rebuilt afterwards (the backtest).
BET_GROUPS = [
    ("FORGE", "saved"),
    ("FORGE", "backtest"),
    ("Other", "saved"),
    ("Other", "backtest"),
]


def _group(entry):
    """(method label, source) of a logged call, as `BET_GROUPS` names them."""
    major_forge = entry.get("method") == "forge" and entry.get("home1") in MAJORS
    label = "FORGE" if major_forge else "Other"
    return label, "backtest" if entry.get("reconstructed") else "saved"


# Fewest settled series before the market comparison gives an interval.
MARKET_MIN_SERIES = 30


def market_scorecard(entries, min_n=MARKET_MIN_SERIES):
    """Our series calls against Kalshi's, on settled matches priced before the start
    and 12 hours out (`market_12h`), the matches Table IV's every-match row bets on.

    `market.p` is the last price read before the start (prices stop updating
    once a match begins; for matches before the hourly reads, the last hourly
    quote from Kalshi's price history). Returns rows for FORGE (within a major
    league) and Other (every other call), each split by `source`: "saved" (calls saved before
    the match) and "backtest" (calls rebuilt afterwards from the ratings the day
    before): series, how often each favourite won (a 50-50 call counts as half),
    each side's mean log loss per series, and `diff` (ours minus Kalshi's, with a
    95% paired-bootstrap interval; below 0 means we beat the market) once a row
    has `min_n` series, else None.
    """
    from prometheus.evaluation import paired_bootstrap

    def clip(p):
        return min(max(p, 1e-6), 1 - 1e-6)

    def right(p, won1):
        return 0.5 if p == 0.5 else float((p > 0.5) == won1)

    done = [
        e
        for e in entries
        if e.get("matched")
        and e.get("winner") in (1, 2)
        and (e.get("market") or {}).get("p") is not None
        and e["market"]["at"] <= e["start"]
        and e.get("market_12h")
    ]
    rows = []
    for label, source in BET_GROUPS:
        ours, theirs, ours_right, theirs_right = [], [], 0.0, 0.0
        for e in (e for e in done if _group(e) == (label, source)):
            won1 = e["winner"] == 1
            p, q = clip(e["p_series"]), clip(e["market"]["p"])
            ours.append(-math.log(p if won1 else 1 - p))
            theirs.append(-math.log(q if won1 else 1 - q))
            ours_right += right(e["p_series"], won1)
            theirs_right += right(e["market"]["p"], won1)
        n = len(ours)
        rows.append(
            {
                "label": label,
                "source": source,
                "series": n,
                "ours_pct": 100 * ours_right / n if n else None,
                "market_pct": 100 * theirs_right / n if n else None,
                "ours_loss": sum(ours) / n if n else None,
                "market_loss": sum(theirs) / n if n else None,
                "diff": (
                    tuple(float(x) for x in paired_bootstrap(ours, theirs))
                    if n >= min_n
                    else None
                ),
            }
        )
    return rows


# The edges, in chance points, the page scores paper bets above.
# None is every match, backing our pick.
BET_EDGES = (None, 0.0, 0.03, 0.05, 0.10)


def edge_record(entries, edges=BET_EDGES, rate=0.07, min_n=MARKET_MIN_SERIES):
    """Paper bets on settled matches, `markets.BET_LEAD` before the start: $1 on
    our pick in every match (edge None, the row Table III's matches line up
    with), or on our side where our chance beats what a contract cost then
    (`market_12h`'s ask) by more than each edge.

    The side is the one with the larger edge. Each bet scores its profit after
    Kalshi's fee at `rate` and its CLV: the last price before the start for that
    team (`market.p`) minus the price paid. Returns rows for "FORGE" and "Other",
    each edge in turn: bets, won, mean return per dollar and mean CLV, each with a
    95% bootstrap interval once there are `min_n` bets (else None), and the share
    of bets beating the close. Rows come in `BET_GROUPS` order, split by source
    (calls saved before the match, and the backtest of calls rebuilt after it).
    """
    from prometheus.evaluation import paired_bootstrap

    bets = []
    for e in entries:
        early, close = e.get("market_12h"), e.get("market") or {}
        if not e.get("matched") or e.get("winner") not in (1, 2) or not early:
            continue
        if early.get("ours") is None:
            continue
        options = {}
        for side in (1, 2):
            cost = early.get(f"ask{side}")
            if cost is None or not 0 < cost < 1:
                continue
            ours = early["ours"] if side == 1 else 1 - early["ours"]
            options[side] = (ours - cost, cost)
        if not options:
            continue

        def bet(side):
            edge, cost = options[side]
            won = e["winner"] == side
            shut = close.get("p")
            if shut is not None and side == 2:
                shut = 1 - shut
            return {
                "edge": edge,
                "won": won,
                "profit": (1 / cost - 1 if won else -1) - markets.fee(cost, 1, rate),
                "clv": None if shut is None else shut - cost,
            }

        pick = 1 if early["ours"] >= 0.5 else 2
        bets.append(
            {
                "group": _group(e),
                "value": bet(max(options, key=lambda side: options[side][0])),
                "pick": bet(pick) if pick in options else None,
            }
        )

    def interval(values):
        if len(values) < min_n:
            return None
        _, lo, hi = paired_bootstrap(values, [0.0] * len(values))
        return float(lo), float(hi)

    rows = []
    for label, source in BET_GROUPS:
        group = [b for b in bets if b["group"] == (label, source)]
        for edge in edges:
            if edge is None:  # every match: back our pick
                sel = [b["pick"] for b in group if b["pick"]]
            else:
                sel = [b["value"] for b in group if b["value"]["edge"] > edge]
            profits = [b["profit"] for b in sel]
            clvs = [b["clv"] for b in sel if b["clv"] is not None]
            rows.append(
                {
                    "label": label,
                    "source": source,
                    "edge": edge,
                    "bets": len(sel),
                    "won": sum(b["won"] for b in sel),
                    "roi": sum(profits) / len(profits) if profits else None,
                    "roi_ci": interval(profits),
                    "clv": sum(clvs) / len(clvs) if clvs else None,
                    "clv_ci": interval(clvs),
                    "beat": sum(c > 0 for c in clvs) / len(clvs) if clvs else None,
                }
            )
    return rows
