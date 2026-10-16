"""Offline adapter checks; no Prometheus checkout or ignored database required."""

import tempfile
import unittest
from pathlib import Path

from test_live_collector import response, select
from test_live_riot_feed import fixture

from prometheus.live.collector import Collector
from prometheus.live.page import (
    build_state,
    first_team_probability,
    read_collector,
    validate_mapping,
)


def mapping():
    return {
        "schema": 1,
        "match_id": "m",
        "competition": "synthetic-league",
        "league": "LCS",
        "event": "Test",
        "best_of": 3,
        "teams": [
            {"riot_team_id": "r", "name": "First Team"},
            {"riot_team_id": "b", "name": "Second Team"},
        ],
        "games": {"g": 1, "g2": 2},
        "score": None,
    }


class LivePageTests(unittest.TestCase):
    def make_collector(self, root):
        c = Collector(Path(root) / "collector", "simulated_replay")
        c.process(select())
        data = fixture()
        data["frames"][0]["blueTeam"]["totalGold"] = 32000
        data["frames"][0]["redTeam"]["dragons"] = ["infernal", "elder"]
        c.process(response(payload=data))
        c.close()
        return Path(root) / "collector"

    def test_side_orientation_and_null_clock_no_inferred_predictions(self):
        with tempfile.TemporaryDirectory() as root:
            state, rows = read_collector(self.make_collector(root))
            page = build_state(state, rows, mapping(), "2026-10-04T20:33:31Z", True)
            self.assertEqual(page["status"], "live")
            self.assertIn("RESEARCH PREVIEW", page["note"])
            self.assertEqual(page["game"]["blue"], 1)
            frame = page["game"]["frames"][0]
            self.assertEqual(frame["teams"][1]["gold"], 32000)
            self.assertEqual(frame["teams"][0]["dragons"], 2)
            self.assertEqual(frame["dragon_types"][0], ["infernal", "elder"])
            self.assertEqual(frame["at"], "2026-10-04T20:33:31Z")
            self.assertIsNone(frame["actual_received_at"])
            self.assertIsNone(frame["clock"])
            self.assertEqual(page["game"]["calls"], [])
            self.assertEqual(page["game"]["market"], [])
            self.assertFalse(page["live_state_verified"])
            self.assertAlmostEqual(first_team_probability(0.7, 1), 0.3)
            self.assertEqual(first_team_probability(0.7, 0), 0.7)
            self.assertIsNone(first_team_probability(None, 1))
            with self.assertRaises(ValueError):
                first_team_probability(float("nan"), 1)

    def test_default_is_unavailable_and_reexport_never_refreshes_source_age(self):
        with tempfile.TemporaryDirectory() as root:
            state, rows = read_collector(self.make_collector(root))
            self.assertEqual(
                build_state(state, rows, mapping(), "2026-10-04T20:33:31Z")["status"],
                "unavailable",
            )
            page = build_state(state, rows, mapping(), "2026-10-04T20:34:00Z", True)
            self.assertEqual(page["status"], "unavailable")
            self.assertEqual(page["quality"]["source_age_seconds"], 30)
            self.assertIn("stale", page["note"])

    def test_new_swapped_map_has_no_old_frames_and_failure_retains_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.make_collector(root)
            c = Collector(path, "simulated_replay")
            c.process(select("2026-10-04T20:33:32Z", "s2", "g2", "r", "b"))
            c.close()
            state, rows = read_collector(path)
            page = build_state(state, rows, mapping(), "2026-10-04T20:33:32Z", True)
            self.assertEqual(page["game"]["frames"], [])
            self.assertEqual(page["game"]["blue"], 0)
            self.assertEqual(page["game"]["number"], 2)
            self.assertEqual(page["status"], "unavailable")

    def test_terminal_outage_and_deselection_statuses(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.make_collector(root)
            c = Collector(path, "simulated_replay")
            c.process(
                {"action": "error", "at": "2026-10-04T20:33:32Z", "reason": "outage"}
            )
            c.close()
            state, rows = read_collector(path)
            page = build_state(state, rows, mapping(), "2026-10-04T20:33:32Z", True)
            self.assertEqual(page["status"], "unavailable")
            self.assertTrue(page["game"]["frames"])
            state["unavailable_reason"] = None
            state["window"]["finished"] = True
            self.assertEqual(
                build_state(state, rows, mapping(), "2026-10-04T20:33:32Z", True)[
                    "status"
                ],
                "between_games",
            )
            state["selection"] = None
            self.assertEqual(
                build_state(state, rows, mapping(), "2026-10-04T20:33:32Z")["status"],
                "idle",
            )

    def test_identity_errors_future_receipts_and_ambiguous_mappings(self):
        catalog = [{"n": "First Team"}, {"n": "Second Team"}]
        config = mapping()
        config["teams"][1]["riot_team_id"] = "r"
        with self.assertRaises(ValueError):
            validate_mapping(config, catalog)
        with tempfile.TemporaryDirectory() as root:
            state, rows = read_collector(self.make_collector(root))
            config = mapping()
            config["match_id"] = "wrong"
            with self.assertRaises(ValueError):
                build_state(state, rows, config, "2026-10-04T20:33:31Z", True)
            rows[0]["teams"]["red"]["team_id"] = "wrong"
            with self.assertRaises(ValueError):
                build_state(state, rows, mapping(), "2026-10-04T20:33:31Z", True)
            page = build_state(state, rows, mapping(), "2026-10-04T20:33:29Z", True)
            self.assertEqual(page["game"]["frames"], [])
            self.assertEqual(page["status"], "unavailable")
