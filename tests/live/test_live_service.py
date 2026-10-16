import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from prometheus.live.service import (
    Game,
    live_events,
    mapping_for,
    patch_snapshot,
    resolve_team,
    write_index,
)
from prometheus.live.start import find_start

CATALOG = [
    {"n": "Cloud9", "s": "cloud9"},
    {"n": "Karmine Corp", "s": "karmine-corp"},
]


def event(state="inProgress"):
    team = lambda i, n, s, c, w: {
        "id": i,
        "name": n,
        "slug": s,
        "code": c,
        "result": {"gameWins": w},
    }
    return {
        "id": "m1",
        "state": state,
        "blockName": "Play-Ins",
        "league": {"slug": "worlds", "name": "Worlds"},
        "match": {
            "strategy": {"count": 5},
            "teams": [
                team("kc", "Karmine Corp", "karmine-corp", "KC", 1),
                team("c9", "Cloud9 Kia", "cloud9", "C9", 2),
            ],
            "games": [{"id": "g4", "number": 4}, {"id": "g5", "number": 5}],
        },
    }


class MappingTest(unittest.TestCase):
    def test_resolves_by_name_then_slug_then_alias(self):
        self.assertEqual(
            resolve_team({"id": "x", "name": "Karmine Corp"}, CATALOG, {}),
            "Karmine Corp",
        )
        self.assertEqual(
            resolve_team(
                {"id": "x", "name": "Cloud9 Kia", "slug": "cloud9"}, CATALOG, {}
            ),
            "Cloud9",
        )
        self.assertEqual(
            resolve_team({"id": "x", "name": "?"}, CATALOG, {"x": "Cloud9"}), "Cloud9"
        )
        self.assertIsNone(
            resolve_team({"id": "x", "name": "?", "slug": "?"}, CATALOG, {})
        )

    def test_mapping_from_live_event(self):
        m = mapping_for(event(), CATALOG, {})
        self.assertEqual([t["name"] for t in m["teams"]], ["Karmine Corp", "Cloud9"])
        self.assertEqual((m["league"], m["best_of"], m["score"]), ("WLDs", 5, [1, 2]))
        self.assertEqual(m["games"], {"g4": 4, "g5": 5})

    def test_unknown_team_is_refused(self):
        with self.assertRaises(ValueError):
            mapping_for(event(), CATALOG[:1], {})

    def test_only_in_progress_matches(self):
        payload = {"data": {"schedule": {"events": [event(), event("unstarted")]}}}
        self.assertEqual(len(list(live_events(payload))), 1)


class IndexTest(unittest.TestCase):
    def page(self, published, status="live"):
        return {
            "schema": 1,
            "published_at": published,
            "status": status,
            "match": {
                "id": "m",
                "league": "WLDs",
                "event": "e",
                "best_of": 5,
                "teams": [],
                "score": None,
            },
            "game": {
                "number": 1,
                "blue": 0,
                "pregame": None,
                "calls": [],
                "frames": [],
            },
        }

    def test_index_keeps_only_fresh_shown_matches(self):
        now = datetime(2026, 10, 15, 22, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "a.json").write_text(json.dumps(self.page(now.isoformat())))
            old = (now - timedelta(seconds=120)).isoformat()
            (d / "b.json").write_text(json.dumps(self.page(old)))
            (d / "c.json").write_text(
                json.dumps(self.page(now.isoformat(), "unavailable"))
            )
            self.assertEqual(write_index(d, now.isoformat()), (1, True))

    def test_idle_index_is_not_rewritten(self):
        now = datetime(2026, 10, 15, 22, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertEqual(write_index(d, now.isoformat()), (0, True))
            first = (d / "index.json").read_text()
            later = (now + timedelta(minutes=5)).isoformat()
            self.assertEqual(write_index(d, later), (0, False))
            self.assertEqual((d / "index.json").read_text(), first)


class GameStateTest(unittest.TestCase):
    def test_new_game_reloads_saved_tickers_and_counts_settled_maps(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mapping = mapping_for(event(), CATALOG, {})
            gdir = root / "m1" / "g5"
            gdir.mkdir(parents=True)
            (gdir / "kalshi.json").write_text(json.dumps({"map": "T5", "series": "S"}))
            (root / "m1" / "results.json").write_text(
                json.dumps({"4": {"winner": 0, "at": "t"}})
            )
            game = {
                "id": "g5",
                "number": 5,
                "teams": [{"id": "c9", "side": "blue"}, {"id": "kc", "side": "red"}],
            }
            g = Game(root, mapping, game, None, None, "2026-10-15T18:00:00Z")
            try:
                self.assertEqual((g.ticker, g.series_ticker), ("T5", "S"))
                self.assertEqual(g.state, "waiting")
                # getLive still says 1-2 after map 4: the settled map is added.
                self.assertEqual(g.score(), [2, 2])
                g.mapping["score"] = [2, 2]  # getLive caught up: not counted twice
                self.assertEqual(g.score(), [2, 2])
            finally:
                g.close()

    def test_deciding_map_is_the_series(self):
        with tempfile.TemporaryDirectory() as d:
            mapping = mapping_for(event(), CATALOG, {})
            sides = [{"id": "c9", "side": "blue"}, {"id": "kc", "side": "red"}]
            start = "2026-10-15T18:00:00Z"
            five = Game(
                Path(d),
                mapping,
                {"id": "g5", "number": 5, "teams": sides},
                None,
                None,
                start,
            )
            four = Game(
                Path(d),
                mapping,
                {"id": "g4", "number": 4, "teams": sides},
                None,
                None,
                start,
            )
            try:
                self.assertTrue(five.deciding([2, 2]))
                # Map 5 of 5 stays the deciding map after the score counts it.
                self.assertTrue(five.deciding([3, 2]))
                self.assertFalse(four.deciding([2, 1]))
                self.assertFalse(four.deciding([1, 1]))
            finally:
                five.close()
                four.close()

    def test_snapshot_gets_the_settled_winner(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            snap, results = d / "map4.json", d / "results.json"
            page = {
                "note": "",
                "game": {"number": 4, "frames": [{"at": "end"}], "winner": None},
            }
            snap.write_text(json.dumps(page))
            results.write_text(json.dumps({"4": {"winner": 1, "at": "t"}}))
            patch_snapshot(snap, results, ["Karmine Corp", "Cloud9"])
            game = json.loads(snap.read_text())["game"]
            self.assertEqual((game["winner"], game["ended_at"]), (1, "end"))


class StartSearchTest(unittest.TestCase):
    def test_finds_first_starting_gold_frame(self):
        start = datetime(2026, 10, 15, 21, 14, 11, 178000, tzinfo=UTC)

        def fetch(t):
            frames = []
            for i in range(20):
                s = t + timedelta(seconds=i * 0.5)
                gold = (
                    0
                    if s < start
                    else 2500
                    if s < start + timedelta(seconds=60)
                    else 3000
                )
                frames.append(
                    {
                        "rfc460Timestamp": s.isoformat().replace("+00:00", "Z"),
                        "blueTeam": {"totalGold": gold},
                        "redTeam": {"totalGold": gold},
                    }
                )
            return frames

        found = find_start(fetch, start + timedelta(minutes=30))
        self.assertLess(
            abs(
                (
                    datetime.fromisoformat(found.replace("Z", "+00:00")) - start
                ).total_seconds()
            ),
            0.6,
        )

    def test_start_older_than_lookback_is_unknown(self):
        frames = [
            {
                "rfc460Timestamp": "2026-10-15T21:00:00Z",
                "blueTeam": {"totalGold": 9000},
                "redTeam": {"totalGold": 9000},
            }
        ]
        self.assertIsNone(
            find_start(lambda t: frames, datetime(2026, 10, 15, 23, tzinfo=UTC))
        )


if __name__ == "__main__":
    unittest.main()
