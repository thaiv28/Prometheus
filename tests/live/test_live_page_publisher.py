import json
import tempfile
import unittest
from pathlib import Path

from test_live_collector import response, select
from test_live_page_state import mapping

from prometheus.live.collector import Collector
from prometheus.live.page import publish


class PublisherTests(unittest.TestCase):
    def test_index_matches_current_contract_and_source_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collector = root / "collector"
            c = Collector(collector, "simulated_replay")
            c.process(select())
            c.process(response())
            c.close()
            m = mapping()
            catalog = [{"n": t["name"]} for t in m["teams"]]
            idx = publish(
                collector, m, catalog, root / "live", at="2026-10-04T20:33:31Z"
            )
            self.assertEqual(len(idx["matches"]), 1)
            match = idx["matches"][0]
            self.assertEqual(match["game"]["blue"], 1)
            self.assertIsNone(match["game"]["clock"])
            self.assertIsNone(match["game"]["call"])
            self.assertEqual(match["url"], "live/m.json")
            page = json.loads((root / "live/m.json").read_text())
            self.assertFalse(page["live_state_verified"])
            self.assertEqual(page["note"], "Research preview.")
            stale = publish(
                collector, m, catalog, root / "live", at="2026-10-04T20:34:31Z"
            )
            self.assertEqual(stale["matches"], [])
            bad = publish(collector, m, [], root / "live", at="2026-10-04T20:34:31Z")
            self.assertEqual(bad["matches"], [])

    def test_output_inside_collector_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                publish(tmp, mapping(), [], Path(tmp) / "live")
