import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prometheus.live.archive import axis, backfill, compact, series_record
from prometheus.live.data import map_files
from prometheus.site import config as site_config
from prometheus.site import live_results


def at(seconds):
    t = datetime.datetime(2026, 10, 16, 19, tzinfo=datetime.UTC)
    return (t + datetime.timedelta(seconds=seconds)).isoformat()


def page(number=2, winner=0, teams=("Karmine Corp", "MVK Esports")):
    """A finished map file: 10 minutes of frames from clock 120 s, a call a
    minute, Kalshi every 10 s (one quote too thin to use)."""
    frames = [
        {
            "at": at(s),
            "clock": None,
            "clock_estimate": 120 + s,
            "teams": [{"gold": 2500 + 10 * s}, {"gold": 2500 + 8 * s}],
        }
        for s in range(0, 601, 10)
    ]
    calls = [{"minute": 3 + m, "p": 0.6 + m / 100, "at": at(60 * m)} for m in range(10)]
    market = [{"at": at(s), "bid": 0.6, "ask": 0.62} for s in range(0, 600, 10)]
    market[5] = {"at": at(50), "bid": 0.3, "ask": 0.9}
    return {
        "match": {
            "id": "m1",
            "league": "WLDs",
            "event": "Worlds Play-Ins",
            "best_of": 5,
            "teams": [{"name": n, "code": n[:3]} for n in teams],
        },
        "game": {
            "number": number,
            "blue": 0,
            "winner": winner,
            "ended_at": at(600),
            "pregame": {"p": 0.7, "by": "FORGE", "market": {"bid": 0.7, "ask": 0.72}},
            "frames": frames,
            "calls": calls,
            "market": market,
        },
    }


class CompactTest(unittest.TestCase):
    def test_axis_follows_the_estimated_clock(self):
        x = axis(page()["game"]["frames"])
        t = datetime.datetime.fromisoformat(at(95)).timestamp()
        self.assertAlmostEqual(x(t), 215)

    def test_compact_keeps_what_the_figure_draws(self):
        c = compact(page())
        self.assertEqual(c["length"], 720)
        self.assertEqual(c["calls"][0], [120, 0.6])
        self.assertEqual(len(c["calls"]), 10)
        # Only changes of the middle price; the thin quote is a gap, not a price.
        self.assertEqual(c["market"][0], [120, 0.61])
        self.assertIn([170, None], c["market"])
        self.assertEqual(c["gold"][:2], [[120, 0], [150, 60]])
        self.assertEqual(
            c["pregame"], {"p": 0.7, "by": "FORGE", "market": 0.71, "backfilled": False}
        )
        self.assertEqual(c["match"]["teams"], ["Karmine Corp", "MVK Esports"])
        self.assertLess(len(json.dumps(c)), 2500)

    def test_compact_copies_are_not_map_files(self):
        with tempfile.TemporaryDirectory() as d:
            pages = Path(d) / "m1" / "pages"
            pages.mkdir(parents=True)
            (pages / "map2.json").write_text("{}")
            (pages / "map2.min.json").write_text("{}")
            self.assertEqual([p.name for p in map_files(d)], ["map2.json"])


class BackfillTest(unittest.TestCase):
    RULE = (
        "If {side} wins game 2 in the Worlds 2026: Karmine Corp vs. MVK Esports "
        "League of Legends match originally scheduled for Oct 16, 2026 at 2:00 PM EDT"
    )

    def get(self, path, **query):
        self.calls.append((path, query))
        if path == "/markets":
            if query["series_ticker"] != "KXLOLMAP":
                return {"markets": []}
            return {
                "markets": [
                    {
                        "ticker": f"T-{code}",
                        "event_ticker": "T",
                        "rules_primary": self.RULE.format(side=side),
                    }
                    for code, side in (("KC", "Karmine Corp"), ("MVK", "MVK Esports"))
                ]
            }
        start = datetime.datetime.fromisoformat(at(0)).timestamp()
        # One candle before the map (the pre-map price), two during it.
        return {
            "candlesticks": [
                {
                    "end_period_ts": int(start + dt),
                    "yes_bid": {"close_dollars": b},
                    "yes_ask": {"close_dollars": a},
                }
                for dt, b, a in (
                    (-60, "0.70", "0.72"),
                    (60, "0.60", "0.62"),
                    (120, "0.50", "0.52"),
                )
            ]
        }

    def test_a_map_without_kalshi_gets_its_minute_prices(self):
        self.calls = []
        bare = page()
        bare["game"]["market"] = []
        bare["game"]["pregame"]["market"] = None
        filled = backfill(bare, get=self.get)
        self.assertEqual(
            self.calls[-1][0], "/series/KXLOLMAP/markets/T-KC/candlesticks"
        )
        c = compact(filled)
        self.assertTrue(c["market_backfilled"])
        self.assertEqual(c["pregame"]["market"], 0.71)
        self.assertTrue(c["pregame"]["backfilled"])
        self.assertEqual([m for _, m in c["market"]], [0.61, 0.51])
        self.assertNotIn("market_backfilled", bare["game"])  # input untouched

    def test_a_map_with_kalshi_is_left_alone(self):
        self.calls = []
        full = page()
        self.assertIs(backfill(full, get=self.get), full)
        self.assertEqual(self.calls, [])


class SeriesRecordTest(unittest.TestCase):
    RULE = (
        "If {side} wins {game}the Worlds 2026: Karmine Corp vs. MVK Esports "
        "League of Legends match originally scheduled for Oct 16, 2026 at 2:00 PM EDT"
    )

    def riot(self, url, key=None):
        if "getEventDetails" in url:
            games = [
                {"number": 1, "id": "g1", "state": "completed"},
                {"number": 2, "id": "g2", "state": self.second},
                {"number": 3, "id": "g3", "state": "unneeded"},
            ]
            return {"data": {"event": {"match": {"games": games}}}}
        return {"frames": [{"rfc460Timestamp": at(0 if url.endswith("g1") else 3600)}]}

    def get(self, path, **query):
        if path == "/markets":
            series = query["series_ticker"]
            games = (
                [("1", "game 1 in "), ("2", "game 2 in ")]
                if series == "KXLOLMAP"
                else [("S", "")]
            )
            return {
                "markets": [
                    {
                        "ticker": f"{n}-{code}",
                        "event_ticker": n,
                        "result": "yes" if (code == "KC") == (n != "2") else "no",
                        "rules_primary": self.RULE.format(side=side, game=game),
                    }
                    for n, game in games
                    for code, side in (("KC", "Karmine Corp"), ("MVK", "MVK Esports"))
                ]
            }
        start = datetime.datetime.fromisoformat(at(0)).timestamp()
        price = {"1-KC": "0.70", "2-KC": "0.60", "S-KC": "0.80"}[path.split("/")[4]]
        return {
            "candlesticks": [
                {
                    "end_period_ts": int(start + dt),
                    "yes_bid": {"close_dollars": price},
                    "yes_ask": {"close_dollars": price},
                }
                for dt in (-60, 3540)
            ]
        }

    def test_every_played_map_with_kalshi_before_it(self):
        self.second = "completed"
        r = series_record(
            "m1",
            ["Karmine Corp", "MVK Esports"],
            ["KC", "MVK"],
            get=self.get,
            riot=self.riot,
        )
        self.assertEqual([m["number"] for m in r["maps"]], [1, 2])
        self.assertEqual([m["winner"] for m in r["maps"]], [0, 1])
        self.assertEqual([m["kalshi_map"] for m in r["maps"]], [0.7, 0.6])
        self.assertEqual([m["kalshi_series"] for m in r["maps"]], [0.8, 0.8])

    def test_an_unfinished_match_has_no_record(self):
        self.second = "inProgress"
        self.assertIsNone(
            series_record(
                "m1",
                ["Karmine Corp", "MVK Esports"],
                ["KC", "MVK"],
                get=self.get,
                riot=self.riot,
            )
        )


def entry(**kw):
    e = {
        "match_id": "Worlds/1",
        "start": "2026-10-16T18:00Z",
        "team1": "MVK Esports",
        "team2": "Karmine Corp",
        "ours1": "MVK Esports",
        "ours2": "Karmine Corp",
        "best_of": 5,
        "league": "Worlds",
        "event": "Worlds Play-In",
        "matched": True,
        "p_game": 0.2,
        "p_series": 0.1,
        "method": "elo-cross",
        "market": {"p": 0.16, "at": "2026-10-16T17:29Z", "ticker": "KXLOLGAME-X"},
        "winner": 2,
        "score1": 0,
        "score2": 3,
    }
    return dict(e, **kw)


class SeriesTest(unittest.TestCase):
    def archive(self, maps=(2,), results=None, record=None, forge=None):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m1").mkdir()
            if record:
                (Path(d) / "m1" / "series.min.json").write_text(json.dumps(record))
            if forge:
                (Path(d) / "m1" / "forge.json").write_text(json.dumps(forge))
            for n in maps:
                path = Path(d) / "m1" / "pages" / f"map{n}.min.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(compact(page(n))))
            if results:
                (Path(d) / "m1" / "results.json").write_text(json.dumps(results))
            return live_results.load_archive(d)

    def test_series_takes_the_logged_call_in_the_log_order(self):
        archive = self.archive(results={"1": {"winner": 0}, "2": {"winner": 0}})
        log = {"a": entry()}
        (s,) = live_results.series_view(log, archive, {"karmine-corp"})
        self.assertEqual(s["names"], ["MVK Esports", "Karmine Corp"])
        self.assertEqual((s["row"]["pct1"], s["row"]["mkt1"]), (10, 16))
        self.assertEqual(s["row"]["score"], "0–3")
        self.assertEqual(s["row"]["href"], "m1.html")
        self.assertEqual([m["number"] for m in s["maps"]], [1, 2, 3])
        self.assertEqual(s["missing"], [1, 3])
        # Live's first team is KC: the chances turn to MVK's.
        recorded = s["maps"][1]
        self.assertEqual(recorded["before"]["map_ours"], 20)
        self.assertEqual(recorded["winner"], "Karmine Corp")
        # The last map goes to the series winner even without a settled result.
        self.assertEqual(s["maps"][2]["winner"], "Karmine Corp")
        self.assertTrue(recorded["figure"]["ours"] and recorded["figure"]["market"])
        # The hover reading's series are in the page's team order too.
        trace = recorded["figure"]["trace"]
        self.assertAlmostEqual(trace["calls"][0][1], 0.2)  # the logged call
        self.assertEqual(trace["market"][0], (120, 0.39))

    def test_before_each_map_in_the_log_order(self):
        record = {
            "maps": [
                {"number": 1, "winner": 0, "kalshi_map": 0.75, "kalshi_series": 0.85},
                {"number": 2, "winner": 0, "kalshi_map": 0.8, "kalshi_series": 0.95},
                {"number": 3, "winner": 0, "kalshi_map": None, "kalshi_series": 0.97},
            ]
        }
        # forge.json for the other team (an order swap): the log's call wins.
        archive = self.archive(record=record, forge={"p_game": 0.2, "rho": 0.127})
        (s,) = live_results.series_view({"a": entry()}, archive, set())
        before = [m["before"] for m in s["maps"]]
        self.assertEqual([b["score"] for b in before], ["0–0", "0–1", "0–2"])
        self.assertEqual({b["map_ours"] for b in before}, {20})
        self.assertEqual(before[0]["series_ours"], 11)  # the logged 0.107
        self.assertEqual([b["map_kalshi"] for b in before], [25, 20, None])
        self.assertEqual([b["series_kalshi"] for b in before], [15, 5, 3])
        self.assertEqual(s["missing"], [1, 3])
        # The figure starts from the logged call too.
        self.assertAlmostEqual(s["maps"][1]["figure"]["trace"]["calls"][0][1], 0.2)

    def test_a_match_the_log_lacks_still_shows(self):
        archive = self.archive()
        far = {"a": entry(start="2026-10-20T18:00Z")}
        (s,) = live_results.series_view(far, archive, set())
        self.assertEqual(s["names"], ["Karmine Corp", "MVK Esports"])
        self.assertNotIn("score", s["row"])
        # Without a logged call the figure starts from the map file's.
        self.assertAlmostEqual(s["maps"][1]["figure"]["trace"]["calls"][0][1], 0.7)

    def test_pages_render(self):
        archive = self.archive()
        series = live_results.series_view({"a": entry()}, archive, set())
        months = live_results.month_views(series)
        now = datetime.datetime(2026, 10, 17, tzinfo=datetime.UTC)
        recent = live_results.recent(series, now)
        self.assertEqual(recent[0]["rows"][0]["href"], "live-results/m1.html")
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(site_config, "OUTPUT_DIR", d):
                live_results.render_live_results(months)
            month = (Path(d) / "live-results" / "2026-10.html").read_text()
            page = (Path(d) / "live-results" / "m1.html").read_text()
        # The month lists the series, each row opening its own page.
        self.assertIn('data-href="m1.html"', month)
        self.assertNotIn('class="ours"', month)
        self.assertIn('class="ours"', page)
        self.assertIn("Not recorded: maps 1, 3.", page)
        self.assertIn('href="2026-10.html"', page)
        self.assertIn("data-trace=", page)
        self.assertIn("live_results.js", page)

    def test_no_archive_renders_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(live_results.load_archive(Path(d) / "none"), {})
            with mock.patch.object(site_config, "OUTPUT_DIR", d):
                live_results.render_live_results([])
            self.assertFalse((Path(d) / "live-results").exists())


if __name__ == "__main__":
    unittest.main()
