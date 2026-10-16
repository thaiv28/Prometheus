"""Offline behavioral collector checks using explicitly synthetic snapshots."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_live_riot_feed import fixture

from prometheus.live.collector import Collector, read_probe, replay


def select(at="2026-10-04T20:33:29Z", session="s", game="g", blue="b", red="r"):
    return {
        "action": "select",
        "at": at,
        "session": session,
        "competition": "synthetic-league",
        "match_id": "m",
        "game_id": game,
        "blue_id": blue,
        "red_id": red,
        "max_age_seconds": 5,
    }


def response(at="2026-10-04T20:33:31Z", payload=None):
    return {
        "action": "response",
        "at": at,
        "fixture": True,
        "payload": payload or fixture(),
    }


class CollectorTests(unittest.TestCase):
    def test_malformed_simulated_source_time_records_rejection_without_crashing(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            try:
                c.process(select())
                data = fixture()
                data["frames"][0]["rfc460Timestamp"] = "invalid"
                event = response(payload=data)
                event["actual_received_at_utc"] = event["at"]
                result = c.process(event)
                self.assertEqual(result["status"], "unavailable")
                self.assertIn("invalid_source_timestamp", result["unavailable_reason"])
                self.assertEqual(
                    c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], 2
                )
            finally:
                c.close()

    def test_duplicate_does_not_refresh_age_and_tick_expires_current(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            try:
                c.process(select())
                got = c.process(response())
                self.assertEqual(got["status"], "simulated_current")
                self.assertFalse(got["live_state_verified"])
                self.assertIsNone(got["observation"]["received_at_utc"])
                self.assertEqual(got["observation"]["simulated_source_age_seconds"], 1)
                c.process(response("2026-10-04T20:33:34Z"))
                old_source = c.snapshot()["observation"]["source_timestamp"]
                got = c.process({"action": "tick", "at": "2026-10-04T20:33:36Z"})
                self.assertEqual(got["status"], "stale")
                self.assertEqual(got["effective_age_seconds"], 6)
                self.assertEqual(old_source, got["observation"]["source_timestamp"])
                self.assertEqual(
                    json.loads((Path(root) / "latest.json").read_text()), got
                )
            finally:
                c.close()

    def test_outage_keeps_evidence_but_new_observation_recovers(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            try:
                c.process(select())
                c.process(response())
                got = c.process(
                    {
                        "action": "error",
                        "at": "2026-10-04T20:33:32Z",
                        "reason": "simulated_network_failure",
                    }
                )
                self.assertEqual(got["status"], "unavailable")
                self.assertIsNotNone(got["observation"])
                data = fixture()
                data["frames"][0]["rfc460Timestamp"] = "2026-10-04T20:33:33Z"
                got = c.process(response("2026-10-04T20:33:34Z", data))
                self.assertEqual(got["status"], "simulated_current")
                self.assertIsNone(got["unavailable_reason"])
            finally:
                c.close()

    def test_restart_persists_duplicate_history_and_identical_event_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            c.process(select())
            c.process(response())
            c.close()
            c = Collector(root, "simulated_replay")
            try:
                self.assertEqual(c.snapshot()["status"], "simulated_current")
                count = c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
                c.process(response())
                self.assertEqual(
                    c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], count
                )
                got = c.process(response("2026-10-04T20:33:32Z"))
                self.assertEqual(got["last_result"]["candidate_count"], 0)
                self.assertEqual(
                    got["observation"]["simulated_received_at_utc"],
                    "2026-10-04T20:33:31Z",
                )
            finally:
                c.close()

    def test_same_side_and_swapped_side_maps_clear_prior_state(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            try:
                c.process(select())
                c.process(response())
                got = c.process(select("2026-10-04T20:33:32Z", "s2", "g2"))
                self.assertEqual(got["status"], "awaiting_data")
                self.assertIsNone(got["observation"])
                old = c.process(response("2026-10-04T20:33:33Z"))
                self.assertEqual(old["status"], "unavailable")
                data = fixture()
                data["esportsGameId"] = "g2"
                data["gameMetadata"]["blueTeamMetadata"]["participantMetadata"][0][
                    "championId"
                ] = "DifferentDraft"
                self.assertEqual(
                    c.process(response("2026-10-04T20:33:34Z", data))["observation"][
                        "teams"
                    ]["blue"]["participant_metadata"][0]["championId"],
                    "DifferentDraft",
                )
                got = c.process(select("2026-10-04T20:33:35Z", "s3", "g3", "r", "b"))
                self.assertIsNone(got["observation"])
                c.process({"action": "deselect", "at": "2026-10-04T20:33:36Z"})
                self.assertEqual(c.snapshot()["status"], "no_selected_game")
                with self.assertRaises(ValueError):
                    c.process(select("2026-10-04T20:33:37Z", "s2", "g2"))
            finally:
                c.close()

    def test_pause_terminal_collision_and_later_gameplay_do_not_stay_current(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            try:
                c.process(select())
                c.process(response())
                data = fixture()
                data["frames"][0]["rfc460Timestamp"] = "2026-10-04T20:33:32Z"
                data["frames"][0]["gameState"] = "paused"
                self.assertEqual(
                    c.process(response("2026-10-04T20:33:33Z", data))["status"],
                    "unavailable",
                )
                data["frames"][0]["gameState"] = "finished"
                self.assertEqual(
                    c.process(response("2026-10-04T20:33:34Z", data))["status"],
                    "finished",
                )
                data["frames"][0]["rfc460Timestamp"] = "2026-10-04T20:33:34Z"
                data["frames"][0]["gameState"] = "in_game"
                got = c.process(response("2026-10-04T20:33:35Z", data))
                self.assertEqual(got["status"], "finished")
                self.assertEqual(got["last_result"]["candidate_count"], 0)
            finally:
                c.close()

    def test_snapshot_recovers_after_commit_before_atomic_replace(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            c.process(select())
            with patch.object(
                c, "_publish_local", side_effect=OSError("simulated disk interruption")
            ):
                with self.assertRaises(OSError):
                    c.process(response())
            self.assertEqual(
                c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], 2
            )
            c.close()
            c = Collector(root, "simulated_replay")
            try:
                self.assertEqual(
                    json.loads((Path(root) / "latest.json").read_text())["status"],
                    "simulated_current",
                )
                c.process(response())
                self.assertEqual(
                    c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], 2
                )
            finally:
                c.close()

    def test_receipt_order_event_id_collision_and_writer_lock_are_enforced(self):
        with tempfile.TemporaryDirectory() as root:
            c = Collector(root, "simulated_replay")
            try:
                event = select()
                event["event_id"] = "explicit-id"
                c.process(event)
                with self.assertRaises(ValueError):
                    Collector(root, "simulated_replay")
                altered = copy.deepcopy(event)
                altered["game_id"] = "other"
                with self.assertRaises(ValueError):
                    c.process(altered)
                with self.assertRaises(ValueError):
                    c.process({"action": "tick", "at": "2026-10-04T20:33:28Z"})
                self.assertEqual(
                    c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], 1
                )
            finally:
                c.close()
            with self.assertRaises(ValueError):
                Collector(root, "recorded_replay")

    def test_recorded_replay_keeps_real_receipts_and_rejects_old_in_game(self):
        with tempfile.TemporaryDirectory() as root:
            events = Path(root) / "events.jsonl"
            at = "2026-10-08T01:00:00Z"
            event = response(at)
            event["actual_received_at_utc"] = at
            events.write_text(
                "\n".join(
                    json.dumps(e) for e in [select("2026-10-08T00:59:59Z"), event]
                )
            )
            result = replay(events, Path(root) / "collector")
            self.assertEqual(result["status"], "stale")
            self.assertIsNone(result["observation"])
            self.assertEqual(result["age_basis"], "recorded_receipt")
            c = Collector(Path(root) / "collector", "recorded_replay")
            try:
                row = json.loads(
                    c.db.execute(
                        "SELECT result FROM journal WHERE sequence=2"
                    ).fetchone()[0]
                )["rows"][0]
                self.assertIn("stale_source_timestamp", row["rejection_reasons"])
                self.assertEqual(row["received_at_utc"], at)
                self.assertNotIn("simulated_received_at_utc", row)
            finally:
                c.close()

    def test_tampered_probe_is_logged_unavailable_without_replacing_observation(self):
        with tempfile.TemporaryDirectory() as root:
            probe = Path(root) / "probe"
            probe.mkdir()
            (probe / "raw.bin").write_bytes(b"{}")
            (probe / "manifest.json").write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "http_status": 200,
                                "raw_file": "raw.bin",
                                "sha256": "bad",
                                "received_at_utc": "2026-10-04T20:33:32Z",
                            }
                        ]
                    }
                )
            )
            with self.assertRaises(ValueError):
                read_probe(probe)
            c = Collector(Path(root) / "collector", "simulated_replay")
            try:
                c.process(select())
                c.process(response())
                result = c.process(
                    {
                        "action": "response",
                        "at": "2026-10-04T20:33:33Z",
                        "probe_dir": str(probe),
                    }
                )
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(
                    result["unavailable_reason"], "raw_response_hash_mismatch"
                )
                self.assertEqual(
                    c.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0], 3
                )
            finally:
                c.close()


if __name__ == "__main__":
    unittest.main()
