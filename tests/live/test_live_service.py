import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from prometheus.live.service import (
    Game,
    feed_sides,
    live_events,
    mapping_for,
    patch_snapshot,
    pin_order,
    resolve_team,
    waiting_pages,
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


class WaitingTest(unittest.TestCase):
    now = "2026-10-16T18:00:00Z"

    def fixture(self, start="2026-10-16T19:00:00Z", state="unstarted"):
        e = event(state)
        e["startTime"] = start
        e["match"]["id"] = e.pop("id")
        # getSchedule has neither team IDs, slugs nor map assignments.
        for team in e["match"]["teams"]:
            team.pop("id")
            team.pop("slug")
        e["match"]["teams"][1]["name"] = "Cloud9"
        e["match"].pop("games")
        return e

    def test_waiting_fixture_is_indexed_without_invented_map_or_stats(self):
        (page,) = waiting_pages([self.fixture()], CATALOG, {}, self.now)
        self.assertEqual(page["status"], "waiting")
        self.assertIsNone(page["game"])
        self.assertIsNone(page["match"]["score"])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "m1.json").write_text(json.dumps(page))
            self.assertEqual(write_index(path, self.now), (1, True))
            (match,) = json.loads((path / "index.json").read_text())["matches"]
            self.assertEqual(match["id"], "m1")
            self.assertIsNone(match["game"])
            # The tracked page replaces the waiting file under the same URL.
            live = IndexTest().page(self.now)
            live["match"]["id"] = "m1"
            (path / "m1.json").write_text(json.dumps(live))
            write_index(path, self.now)
            (match,) = json.loads((path / "index.json").read_text())["matches"]
            self.assertEqual(match["status"], "live")

    def test_excludes_distant_expired_completed_unknown_and_tracked_fixtures(self):
        for e in [
            self.fixture("2026-10-16T19:16:00Z"),
            self.fixture("2026-10-16T13:59:00Z"),
            self.fixture(state="completed"),
        ]:
            self.assertEqual(waiting_pages([e], CATALOG, {}, self.now), [])
        e = self.fixture()
        e["match"]["teams"][0]["name"] = "TBD"
        self.assertEqual(waiting_pages([e], CATALOG, {}, self.now), [])
        self.assertEqual(
            waiting_pages([self.fixture()], CATALOG, {}, self.now, {"m1"}), []
        )

    def test_failed_active_map_is_not_relabelled_waiting_by_schedule(self):
        live = event()
        live["startTime"] = self.now
        live["match"]["games"][0]["state"] = "inProgress"
        live["match"]["games"][1]["state"] = "unstarted"
        self.assertEqual(
            waiting_pages([self.fixture(), live], CATALOG, {}, self.now, failed={"g4"}),
            [],
        )

    def test_late_match_stays_waiting_with_same_id(self):
        (page,) = waiting_pages(
            [self.fixture("2026-10-16T17:00:00Z")], CATALOG, {}, self.now
        )
        self.assertEqual(page["match"]["id"], "m1")


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
                g.page_out = root / "pages"
                from prometheus.live.requests import utc_now

                self.assertEqual(g.page(CATALOG, utc_now())["status"], "waiting")
                # getLive still says 1-2 after map 4: the settled map is added.
                self.assertEqual(g.score(), [2, 2])
                g.mapping["score"] = [2, 2]  # getLive caught up: not counted twice
                self.assertEqual(g.score(), [2, 2])
            finally:
                g.close()

    def test_score_before_this_map(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mapping = mapping_for(event(), CATALOG, {})
            sides = [{"id": "c9", "side": "blue"}, {"id": "kc", "side": "red"}]
            g = Game(
                root,
                mapping,
                {"id": "g4", "number": 4, "teams": sides},
                None,
                None,
                "2026-10-15T18:00:00Z",
            )
            try:
                self.assertEqual(g.score_before([2, 1]), [2, 1])  # map 4 live
                # Map 4 counted but its winner unknown yet: no score to use.
                self.assertIsNone(g.score_before([2, 2]))
                (root / "m1" / "results.json").write_text(
                    json.dumps({"4": {"winner": 1, "at": "t"}})
                )
                self.assertEqual(g.score_before([2, 2]), [2, 1])
                self.assertIsNone(g.score_before(None))
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


# getLive at the start of KC v MVK map 3 (2026-10-16): the last map's sides.
MAP3 = {
    "id": "g3",
    "number": 3,
    "teams": [{"id": "kc", "side": "blue"}, {"id": "mvk", "side": "red"}],
}


class FeedSidesTest(unittest.TestCase):
    def sides(self, payload):
        with mock.patch(
            "prometheus.live.service.fetch_json", return_value=({}, payload)
        ):
            return feed_sides(MAP3, Path("unused"))

    def window(self, blue, red):
        return {
            "gameMetadata": {
                "blueTeamMetadata": {"esportsTeamId": blue},
                "redTeamMetadata": {"esportsTeamId": red},
            }
        }

    def test_feed_sides_replace_getlive_sides(self):
        game = self.sides(self.window("mvk", "kc"))
        self.assertEqual(
            game["teams"], [{"id": "kc", "side": "red"}, {"id": "mvk", "side": "blue"}]
        )
        self.assertEqual(game["number"], 3)

    def test_no_feed_yet_waits(self):
        self.assertIsNone(self.sides(None))
        self.assertIsNone(self.sides({"frames": []}))

    def test_other_teams_in_the_feed_are_refused(self):
        with self.assertRaises(ValueError):
            self.sides(self.window("kc", "t1"))

    def test_resumed_game_keeps_its_selected_sides(self):
        with tempfile.TemporaryDirectory() as d:
            mapping = mapping_for(event(), CATALOG, {})
            sides = [{"id": "c9", "side": "blue"}, {"id": "kc", "side": "red"}]
            game = {"id": "g4", "number": 4, "teams": sides}
            Game(Path(d), mapping, game, None, None).close()
            # getLive has since swapped them; the saved session still resumes.
            swapped = [{"id": "c9", "side": "red"}, {"id": "kc", "side": "blue"}]
            again = Game(Path(d), mapping, dict(game, teams=swapped), None, None)
            try:
                selection = again.collector.state["selection"]
                self.assertEqual(
                    (selection["blue_id"], selection["red_id"]), ("c9", "kc")
                )
            finally:
                again.close()


class PinOrderTest(unittest.TestCase):
    def test_match_keeps_its_first_team_order(self):
        with tempfile.TemporaryDirectory() as d:
            first = event()
            self.assertIs(pin_order(first, Path(d)), first)
            swapped = event()
            swapped["match"]["teams"].reverse()
            swapped["match"]["teams"][0]["result"]["gameWins"] = 3
            again = pin_order(swapped, Path(d))
            mapping = mapping_for(again, CATALOG, {})
            self.assertEqual(
                [t["name"] for t in mapping["teams"]], ["Karmine Corp", "Cloud9"]
            )
            self.assertEqual(mapping["score"], [1, 3])  # the score follows the teams
            self.assertEqual(swapped["match"]["teams"][0]["id"], "c9")  # not mutated

    def test_other_teams_are_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            pin_order(event(), Path(d))
            other = event()
            other["match"]["teams"][0]["id"] = "t1"
            self.assertIs(pin_order(other, Path(d)), other)


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


class FastQuotesTest(unittest.TestCase):
    def test_prices_refresh_without_rebuilding_feed_or_calls(self):
        from prometheus.live.service import Game

        with tempfile.TemporaryDirectory() as tmp:
            game = object.__new__(Game)
            game.dir = Path(tmp) / "map1"
            game.dir.mkdir()
            game.ticker = "map"
            game.series_ticker = "series"
            game.start = {"source_at": "2026-10-17T00:00:00+00:00"}
            q = {"at": "2026-10-17T00:00:12+00:00", "bid": 0.6, "ask": 0.62}
            (game.dir / "quotes.jsonl").write_text(json.dumps(q) + "\n")
            game.series_quotes_path.write_text(json.dumps(q) + "\n")
            page = {
                "match": {"series": {"ours": 0.7}},
                "game": {"frames": [], "calls": ["unchanged"]},
            }
            updated = game.add_quotes(page)
            self.assertEqual(updated["game"]["market"], [q])
            self.assertEqual(updated["match"]["series"]["kalshi"], q)
            self.assertEqual(updated["game"]["calls"], ["unchanged"])
            self.assertEqual(updated["match"]["series"]["ours"], 0.7)

    def test_fast_cycle_preserves_ten_second_feed_cadence(self):
        from types import SimpleNamespace

        from prometheus.live import service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "teams.json").write_text("[]")
            e = event()
            e["match"]["games"] = [{"id": "g4", "number": 4, "state": "inProgress"}]
            g = mock.Mock()
            g.mapping = {"match_id": "m1", "teams": [{"name": "A"}, {"name": "B"}]}
            g.id, g.number, g.state = "g4", 4, "live"
            g.forge, g.ticker, g.series_ticker = {}, "map", "series"
            g.dir = root
            page = {"match": {"id": "m1"}, "game": {}}
            g.page.return_value = page
            g.add_quotes.return_value = page
            args = SimpleNamespace(
                team_catalog=root / "teams.json",
                aliases=root / "none",
                model=None,
                skip_game=[],
                adopt=[],
                root=root,
                page_out=root,
                discover_interval=60,
                interval=10,
                ratings=None,
                forge=False,
                s3=None,
                idle_exit=None,
            )
            clock = [100.0]

            def sleep(seconds):
                clock[0] += seconds
                if clock[0] >= 112:
                    raise service.Stop("test complete")

            payload = {"data": {"schedule": {"events": [e]}}}
            with (
                mock.patch.multiple(
                    service,
                    fetch_json=mock.Mock(return_value=({}, payload)),
                    pin_order=mock.Mock(side_effect=lambda e, r: e),
                    mapping_for=mock.Mock(return_value=g.mapping),
                    feed_sides=mock.Mock(side_effect=lambda game, out: game),
                    Game=mock.Mock(return_value=g),
                    waiting_pages=mock.Mock(return_value=[]),
                    write_index=mock.Mock(return_value=(1, True)),
                    log=mock.Mock(),
                ),
                mock.patch.object(
                    service.time, "monotonic", side_effect=lambda: clock[0]
                ),
                mock.patch.object(service.time, "sleep", side_effect=sleep),
            ):
                self.assertEqual(service.run(args), service.REFUSED)
            self.assertEqual(g.poll.call_count, 2)
            self.assertEqual(g.page.call_count, 2)
            self.assertEqual(g.settle.call_count, 2)
            self.assertEqual(g.poll_quote.call_count, 12)  # two books in six cycles
            self.assertEqual(g.add_quotes.call_count, 4)


PRE_EVENT = {"id": "m1", "startTime": "2026-10-17T09:00:00Z"}
PRE_GAME = {"id": "g2", "number": 2}
PRE_BOOK = {
    "orderbook_fp": {
        "yes_dollars": [["0.55", "100"], ["0.56", "40"], ["0.50", "0"]],
        "no_dollars": [["0.42", "70"]],
    }
}


class PreMapsTest(unittest.TestCase):
    def test_polls_the_book_until_the_map_is_tracked(self):
        import tempfile

        from prometheus.live.service import PreMaps

        with tempfile.TemporaryDirectory() as tmp:
            pre = PreMaps(Path(tmp))
            mapping = {"match_id": "m1", "teams": []}
            pre.seen(PRE_EVENT, PRE_GAME, mapping)
            pre.seen(PRE_EVENT, PRE_GAME, mapping)  # once per map
            self.assertTrue(pre.want_tickers())
            with mock.patch(
                "prometheus.live.service.contract", return_value="KXLOLMAP-X-2-A"
            ):
                pre.match([])
            self.assertFalse(pre.want_tickers())
            with mock.patch(
                "prometheus.live.service.fetch_json", return_value=({}, PRE_BOOK)
            ):
                pre.poll()
                pre.poll()
            rows = [
                json.loads(line)
                for line in (Path(tmp) / "m1" / "g2" / "pre_quotes.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[0]["bid"], rows[0]["ask"]), (0.56, 0.58))
            self.assertEqual(rows[0]["yes"], [[0.56, 40.0], [0.55, 100.0]])
            self.assertEqual(rows[0]["no"], [[0.42, 70.0]])
            pre.keep({"m1"})
            self.assertIn("g2", pre.maps)
            pre.drop("g2")  # tracked now: the in-game poll takes over
            self.assertEqual(pre.maps, {})
            pre.seen(PRE_EVENT, PRE_GAME, mapping)
            pre.keep(set())  # match no longer live
            self.assertEqual(pre.maps, {})
