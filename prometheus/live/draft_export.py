"""Offline prior-day draft histories; the worker imports only live.draft."""

import sqlite3
from collections import defaultdict, deque
from datetime import date, timedelta
from itertools import combinations, groupby

from .draft import key, normalized, pair_key


class History:
    """Single chronological SQL pass; snapshots exclude the entire requested day."""

    def __init__(self, db):
        self.db = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        rows = self.db.execute(
            "SELECT m.gameid,m.teamid,m.teamname,m.date,m.result,e.pre_match_elo AS elo,"
            " o.pre_match_elo AS opp_elo,p.playerid,p.playername,p.position,p.champion"
            " FROM matches m JOIN game_length_elo e USING(gameid,teamid)"
            " JOIN game_length_elo o ON o.gameid=m.gameid AND o.teamid!=m.teamid"
            " JOIN match_players p USING(gameid,teamid)"
            " WHERE p.champion IS NOT NULL AND p.champion!=''"
            " ORDER BY m.date,m.gameid,m.teamid,p.position"
        )
        self.games = iter(groupby(rows, lambda r: (r["date"], r["gameid"])))
        self.pending = next(self.games, None)
        self.as_of, self.through = None, None
        self.experience = defaultdict(int)
        self.meta, self.matchup, self.synergy = (
            defaultdict(lambda: [0.0, 0]) for _ in range(3)
        )
        self.teams = defaultdict(lambda: defaultdict(set))
        self.champions, self.meta_rows = {}, deque()
        self.players = defaultdict(set)

    def close(self):
        self.db.close()

    def _consume(self, rows):
        sides = defaultdict(dict)
        for r in rows:
            self.through = r["date"]
            sides[r["teamid"]][r["position"]] = r
            p = 1 / (1 + 10 ** (-(r["elo"] - r["opp_elo"]) / 400))
            wae = r["result"] - p
            self.experience[key(r["playerid"], r["champion"])] += 1
            self.teams[r["teamname"]][normalized(r["playername"])].add(r["playerid"])
            self.champions[normalized(r["champion"])] = r["champion"]
            self.players[normalized(r["playername"])].add(r["playerid"])
            mk = key(r["position"], r["champion"])
            self.meta[mk][0] += wae
            self.meta[mk][1] += 1
            self.meta_rows.append((r["date"][:10], mk, wae))
        if len(sides) != 2:
            return
        for side, opp in (
            tuple(sides.values()),
            tuple(reversed(tuple(sides.values()))),
        ):
            for role, r in side.items():
                if role not in opp:
                    continue
                p = 1 / (1 + 10 ** (-(r["elo"] - r["opp_elo"]) / 400))
                k = key(role, r["champion"], opp[role]["champion"])
                self.matchup[k][0] += r["result"] - p
                self.matchup[k][1] += 1
        for side in sides.values():
            if len(side) != 5:
                continue
            r = next(iter(side.values()))
            p = 1 / (1 + 10 ** (-(r["elo"] - r["opp_elo"]) / 400))
            tokens = [f"{role}:{v['champion']}" for role, v in side.items()]
            for a, b in combinations(tokens, 2):
                k = pair_key(a, b)
                self.synergy[k][0] += r["result"] - p
                self.synergy[k][1] += 1

    def before(self, day):
        if self.as_of and day < self.as_of:
            raise ValueError("history must advance chronologically")
        while self.pending and self.pending[0][0][:10] < day:
            self._consume(list(self.pending[1]))
            self.pending = next(self.games, None)
        low = (date.fromisoformat(day) - timedelta(days=60)).isoformat()
        while self.meta_rows and self.meta_rows[0][0] < low:
            _, k, wae = self.meta_rows.popleft()
            self.meta[k][0] -= wae
            self.meta[k][1] -= 1
        self.as_of = day
        return self

    def snapshot(self):
        if self.as_of is None:
            raise ValueError("history day required")
        return {
            "schema": "draft_history_v2",
            "as_of": self.as_of,
            "data_through": self.through,
            "champions": dict(self.champions),
            "players": {n: sorted(ids) for n, ids in self.players.items()},
            "teams": {
                name: {n: sorted(ids) for n, ids in aliases.items()}
                for name, aliases in self.teams.items()
            },
            "experience": dict(self.experience),
            **{
                name: {
                    k: [float(total), int(n)]
                    for k, (total, n) in getattr(self, name).items()
                    if n > 0
                }
                for name in ("meta", "matchup", "synergy")
            },
        }


def build(db, day):
    state = History(db)
    try:
        return state.before(day).snapshot()
    finally:
        state.close()
