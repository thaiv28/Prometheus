import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prometheus.live.archive import axis, compact
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
        self.assertEqual(c["pregame"], {"p": 0.7, "by": "FORGE", "market": 0.71})
        self.assertEqual(c["match"]["teams"], ["Karmine Corp", "MVK Esports"])
        self.assertLess(len(json.dumps(c)), 2500)

    def test_compact_copies_are_not_map_files(self):
        with tempfile.TemporaryDirectory() as d:
            pages = Path(d) / "m1" / "pages"
            pages.mkdir(parents=True)
            (pages / "map2.json").write_text("{}")
            (pages / "map2.min.json").write_text("{}")
            self.assertEqual([p.name for p in map_files(d)], ["map2.json"])


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
    def archive(self, maps=(2,), results=None):
        with tempfile.TemporaryDirectory() as d:
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
        self.assertEqual(s["row"]["href"], "#s-m1")
        self.assertEqual([m["number"] for m in s["maps"]], [1, 2, 3])
        self.assertEqual(s["missing"], [1, 3])
        # Live's first team is KC: the chances turn to MVK's.
        recorded = s["maps"][1]
        self.assertEqual((recorded["pre"], recorded["pre_market"]), (30, 29))
        self.assertEqual(recorded["winner"], "Karmine Corp")
        # The last map goes to the series winner even without a settled result.
        self.assertEqual(s["maps"][2]["winner"], "Karmine Corp")
        self.assertTrue(recorded["figure"]["ours"] and recorded["figure"]["market"])

    def test_a_match_the_log_lacks_still_shows(self):
        archive = self.archive()
        far = {"a": entry(start="2026-10-20T18:00Z")}
        (s,) = live_results.series_view(far, archive, set())
        self.assertEqual(s["names"], ["Karmine Corp", "MVK Esports"])
        self.assertNotIn("score", s["row"])
        self.assertEqual(s["maps"][1]["pre"], 70)

    def test_pages_render(self):
        archive = self.archive()
        series = live_results.series_view({"a": entry()}, archive, set())
        months = live_results.month_views(series)
        now = datetime.datetime(2026, 10, 17, tzinfo=datetime.UTC)
        recent = live_results.recent(series, now)
        self.assertEqual(recent[0]["rows"][0]["href"], "live-results/2026-10.html#s-m1")
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(site_config, "OUTPUT_DIR", d):
                live_results.render_live_results(months)
            html = (Path(d) / "live-results" / "2026-10.html").read_text()
        self.assertIn('id="s-m1"', html)
        self.assertIn('class="ours"', html)
        self.assertIn("Not recorded: maps 1, 3.", html)

    def test_no_archive_renders_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(live_results.load_archive(Path(d) / "none"), {})
            with mock.patch.object(site_config, "OUTPUT_DIR", d):
                live_results.render_live_results([])
            self.assertFalse((Path(d) / "live-results").exists())


if __name__ == "__main__":
    unittest.main()
