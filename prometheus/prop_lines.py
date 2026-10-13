"""Player prop lines for League of Legends from the pick'em apps, read directly.

- Underdog: the public `v1/over_under_lines` JSON (every sport; LoL rows kept),
  with each side's payout multiplier and implied probability.
- DraftKings Pick6: the LoL page is server-rendered with its data as a React
  Router "turbo stream" (one flat JSON array whose objects point at other
  entries by index); decoded, it holds the pick cards (line, each side's
  multiplier), players, teams and matches. The page shows its first pick group
  (a day's slate); every other group comes from an event page
  (`/events/LOL/<group>/<competition>`). Only each group's default stat is
  served this way (kills so far).
- PrizePicks: the partner API's projections for league 121 (LoL). It rate-limits
  hard (429 after a few calls), so it is read once per run. Combination props
  ("A + B + C") are dropped.

A side an app doesn't offer has no multiplier (None): Underdog's and Pick6's
one-sided lines, PrizePicks' demon and goblin lines.

Every source returns rows in one shape (`ROW_FIELDS`); `collect` appends them,
stamped with the time read, to a JSON-lines log. Nothing here is on the site.
"""

import datetime
import json
import re
import time
import urllib.request

UNDERDOG_URL = "https://api.underdogfantasy.com/v1/over_under_lines"
PICK6_URL = "https://pick6.draftkings.com/?sport=LOL"
PICK6_EVENT_URL = "https://pick6.draftkings.com/events/LOL"
PRIZEPICKS_URL = (
    "https://partner-api.prizepicks.com/projections?league_id=121&per_page=1000"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html",
}
ROW_FIELDS = (
    "source", "line_id", "player", "team", "opponent", "position", "stat", "maps",
    "line", "over_mult", "under_mult", "over_prob", "start", "match", "league",
)  # fmt: skip
STAT_NAMES = {
    "kills": "kills",
    "assists": "assists",
    "creep score": "cs",
    "cs": "cs",
    "deaths": "deaths",
    "fantasy points": "fantasy",
    "fantasy score": "fantasy",
}


def _stat_and_maps(text):
    """("kills", "1-3") from labels like "Kills on Maps 1+2+3" or "MAPS 1-2 Kills"."""
    low = text.lower()
    maps = re.search(r"maps?\s*([\d+\-]+)", low)
    span = None
    if maps:
        nums = [int(n) for n in re.findall(r"\d", maps.group(1))]
        span = f"{min(nums)}-{max(nums)}" if len(nums) > 1 else str(nums[0])
    stat = next((v for k, v in STAT_NAMES.items() if k in low), low)
    return stat, span


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_underdog(data):
    apps = {a["id"]: a for a in data.get("appearances", [])}
    players = {p["id"]: p for p in data.get("players", [])}
    games = {g["id"]: g for g in data.get("games", [])}
    rows = []
    for line in data.get("over_under_lines", []):
        stat = line.get("over_under", {}).get("appearance_stat", {})
        app = apps.get(stat.get("appearance_id"), {})
        player = players.get(app.get("player_id"), {})
        if player.get("sport_id") != "LOL":
            continue
        game = games.get(app.get("match_id"), {})
        home = app.get("team_id") == game.get("home_team_id")
        names = (game.get("abbreviated_title") or "").split(" vs ")
        team = opp = None
        if len(names) == 2:
            # abbreviated_title is "AWAY vs HOME".
            team, opp = (names[1], names[0]) if home else (names[0], names[1])
        options = {o.get("choice"): o for o in line.get("options", [])}
        over, under = options.get("higher", {}), options.get("lower", {})
        prob = ((over.get("odds") or {}).get("fantasy") or {}).get("probability")
        name, span = _stat_and_maps(stat.get("display_stat", ""))
        rows.append(
            {
                "source": "underdog",
                "line_id": line.get("id"),
                "player": (
                    player.get("last_name") or player.get("first_name") or ""
                ).strip(),
                "team": team,
                "opponent": opp,
                "position": player.get("position_name"),
                "stat": name,
                "maps": span,
                "line": _float(line.get("stat_value")),
                "over_mult": _float(over.get("payout_multiplier")),
                "under_mult": _float(under.get("payout_multiplier")),
                "over_prob": _float(prob) / 100 if _float(prob) is not None else None,
                "start": game.get("scheduled_at"),
                "match": game.get("full_team_names_title"),
                "league": None,
            }
        )
    return rows


def decode_turbo_stream(html):
    """The first React Router turbo-stream payload in a page, resolved into plain
    objects. Object keys are "_<index of the key string>" and values are indexes;
    negative indexes are special values (undefined, null, NaN, ...)."""
    found = re.search(r"streamController\.enqueue\((\".*?\")\);?</script>", html, re.S)
    if not found:
        return None
    data = json.loads(json.loads(found.group(1)))
    memo = {}

    def resolve(i):
        if not isinstance(i, int):
            return i
        if i < 0:
            return None
        if i in memo:
            return memo[i]
        v = data[i]
        if isinstance(v, dict):
            out = memo[i] = {}
            for k, vi in v.items():
                out[data[int(k[1:])]] = resolve(vi)
            return out
        if isinstance(v, list):
            # Typed values (dates, promises, ...) start with a one-letter tag.
            if v and isinstance(v[0], str) and len(v[0]) == 1:
                return v
            out = memo[i] = []
            out.extend(resolve(x) for x in v)
            return out
        return v

    return resolve(0)


def parse_pick6(html):
    """The home page's cards (its default pick group and stat)."""
    root = decode_turbo_stream(html)
    if not root:
        return []
    home = (root.get("loaderData") or {}).get("routes/_homeShared") or {}
    return _pick6_rows(home.get("pickCardsResponse") or {})


def _pick6_rows(cards):
    entities = cards.get("entityInfoByDkId") or {}
    teams = cards.get("displayTeamById") or {}
    comps = cards.get("competitionById") or {}
    markets = cards.get("pickSixMarketById") or {}
    rows = []
    for card in (cards.get("pickCardByPickableId") or {}).values():
        for ent in card.get("entities") or []:
            dk = str(ent.get("dkId"))
            for comp_id in ent.get("compIds") or []:
                comp = comps.get(str(comp_id)) or {}
                where = (comp.get("entityCompByDkId") or {}).get(dk) or {}
                team_id = where.get("teamId")
                opp_id = (
                    comp.get("awayTeamId")
                    if team_id == comp.get("homeTeamId")
                    else comp.get("homeTeamId")
                )
                for market in card.get("activePickableMarkets") or []:
                    mult = {
                        s.get("statLinePropositionId"): s.get("standingsMultiplier")
                        for s in market.get("activeSelections") or []
                    }
                    info = markets.get(str(market.get("pickSixMarketId"))) or {}
                    stat, _ = _stat_and_maps(info.get("name", ""))
                    _, span = _stat_and_maps(comp.get("totalCompTime") or "")
                    rows.append(
                        {
                            "source": "pick6",
                            "line_id": str(market.get("pickableMarketId")),
                            "player": (entities.get(dk) or {}).get("name"),
                            "team": (teams.get(str(team_id)) or {}).get("name"),
                            "opponent": (teams.get(str(opp_id)) or {}).get("name"),
                            "position": where.get("position"),
                            "stat": stat,
                            "maps": span,
                            "line": _float(market.get("targetValue")),
                            "over_mult": _float(mult.get(1)),
                            "under_mult": _float(mult.get(2)),
                            "over_prob": None,
                            "start": comp.get("startTime"),
                            "match": comp.get("name"),
                            "league": comp.get("leagueAbbr"),
                        }
                    )
    return rows


def parse_prizepicks(data):
    included = {
        (x["type"], x["id"]): x.get("attributes", {}) for x in data.get("included", [])
    }
    rows = []
    for proj in data.get("data", []):
        a = proj.get("attributes", {})
        rel = proj.get("relationships", {})
        pid = ((rel.get("new_player") or {}).get("data") or {}).get("id")
        player = included.get(("new_player", pid), {})
        if "+" in (player.get("name") or ""):
            continue
        stat, span = _stat_and_maps(a.get("stat_type", ""))
        rows.append(
            {
                "source": "prizepicks",
                "line_id": proj.get("id"),
                "player": player.get("name"),
                "team": player.get("team"),
                "opponent": a.get("description"),
                "position": player.get("position"),
                "stat": stat,
                "maps": span,
                "line": _float(a.get("line_score")),
                # Standard lines take either side at the standard payout; demon and
                # goblin lines only the over, at a payout PrizePicks doesn't publish.
                "over_mult": 1.0 if a.get("odds_type") == "standard" else None,
                "under_mult": 1.0 if a.get("odds_type") == "standard" else None,
                "over_prob": None,
                "start": a.get("start_time"),
                "match": a.get("description"),
                "league": player.get("league"),
                "odds_type": a.get("odds_type"),
            }
        )
    return rows


SOURCES = {
    "underdog": (
        UNDERDOG_URL,
        {"client-type": "web", "client-version": "2026.10.01"},
        "json",
        parse_underdog,
    ),
    "pick6": (PICK6_URL, {}, "text", parse_pick6),
    "prizepicks": (PRIZEPICKS_URL, {}, "json", parse_prizepicks),
}


def _get(url, extra=None, timeout=30):
    request = urllib.request.Request(url, headers={**HEADERS, **(extra or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def pick6_groups(html):
    """The LoL pick groups listed on Pick6's page (one per day or slate), and a
    competition id to address their event pages with."""
    root = decode_turbo_stream(html) or {}
    home = (root.get("loaderData") or {}).get("routes/_homeShared") or {}
    groups = [
        g.get("pickGroupId")
        for g in home.get("pickGroups") or []
        if g.get("pickGroupId")
    ]
    comps = [
        c.get("competitionId")
        for c in home.get("allCompetitions") or []
        if c.get("competitionId")
    ]
    selected = (home.get("selectedPickGroup") or {}).get("pickGroupId")
    return groups, selected, comps[0] if comps else None


def fetch_pick6(timeout=30, sleep=time.sleep):
    """The home page's group, then each other listed group through an event page
    (any competition id serves a group's page)."""
    html = _get(PICK6_URL, timeout=timeout)
    rows = parse_pick6(html)
    groups, selected, comp = pick6_groups(html)
    for group in groups:
        if group == selected or comp is None:
            continue
        sleep(1)
        # An event page carries its whole group's cards, like the home page.
        rows += parse_pick6(_get(f"{PICK6_EVENT_URL}/{group}/{comp}", timeout=timeout))
    unique = {r["line_id"]: r for r in rows}
    return list(unique.values())


def fetch(source, timeout=30):
    """Read one source's current LoL lines; raises on an HTTP error."""
    if source == "pick6":
        return fetch_pick6(timeout)
    url, extra, kind, parse = SOURCES[source]
    body = _get(url, extra, timeout)
    return parse(json.loads(body) if kind == "json" else body)


# A read is logged only when one of these differs from the line's last logged read.
CHANGE_FIELDS = ("line", "over_mult", "under_mult", "over_prob", "start")


def last_logged(path):
    """Each line's last logged read in the log at `path`: (source, line_id) -> row."""
    last = {}
    try:
        with open(path) as f:
            for text in f:
                if text.strip():
                    row = json.loads(text)
                    last[(row.get("source"), row.get("line_id"))] = row
    except FileNotFoundError:
        pass
    return last


def collect(path, sources=tuple(SOURCES), now=None):
    """Append every source's lines that are new or changed since their last logged
    read to the JSON-lines log at `path`, stamped with the time read. Returns
    {source: "read N, logged M", or the error}."""
    now = now or datetime.datetime.now(datetime.UTC)
    stamp = now.isoformat(timespec="seconds")
    last = last_logged(path)
    result = {}
    with open(path, "a") as f:
        for source in sources:
            try:
                rows = fetch(source)
            except Exception as err:
                result[source] = f"error: {err}"
                continue
            logged = 0
            for row in rows:
                before = last.get((row.get("source"), row.get("line_id")))
                if before and all(before.get(k) == row.get(k) for k in CHANGE_FIELDS):
                    continue
                f.write(json.dumps({"read_at": stamp, **row}) + "\n")
                last[(row.get("source"), row.get("line_id"))] = row
                logged += 1
            result[source] = f"read {len(rows)}, logged {logged}"
    return result
