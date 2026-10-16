"""Synthetic fixtures; no saved footage, network, OCR or credentials required."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from prometheus.live.feed import WindowSession, timestamp
from prometheus.live.requests import discover_events, probe


def fixture():
    frame = {"rfc460Timestamp": "2026-10-04T20:33:30Z", "gameState": "in_game"}
    metadata = {}
    for side, team_id in [("blue", "b"), ("red", "r")]:
        frame[f"{side}Team"] = {
            "totalGold": 27000,
            "totalKills": 0,
            "towers": 0,
            "inhibitors": 0,
            "barons": 0,
            "dragons": [],
            "participants": [{"participantId": 1, "maxHealth": 1000}],
        }
        metadata[f"{side}TeamMetadata"] = {
            "esportsTeamId": team_id,
            "participantMetadata": [{"championId": "SyntheticChampion"}],
        }
    return {
        "esportsGameId": "g",
        "esportsMatchId": "m",
        "gameMetadata": metadata,
        "frames": [frame],
    }


def session(max_age=30, game_id="g"):
    return WindowSession("selected-map", "m", game_id, "b", "r", max_age)


class RiotFeedTests(unittest.TestCase):
    def test_reported_team_kills_disagreeing_with_player_sum_are_preserved_but_rejected(
        self,
    ):
        data = fixture()
        data["frames"][0]["blueTeam"]["participants"] = [
            {"participantId": i, "kills": 0, "maxHealth": 1000} for i in range(1, 6)
        ]
        data["frames"][0]["blueTeam"]["totalKills"] = 1
        row = session().review(data, "2026-10-04T20:33:31Z", {})[0]
        self.assertEqual(row["teams"]["blue"]["totalKills"], 1)
        self.assertIn(
            "blue.totalKills:participant_sum_disagreement", row["field_reasons"]
        )
        self.assertEqual(row["status"], "rejected")

    def test_stale_in_game_never_becomes_live_and_elapsed_stays_null(self):
        row = session().review(fixture(), "2026-10-08T00:00:00Z", {})[0]
        self.assertIn("stale_source_timestamp", row["rejection_reasons"])
        self.assertIsNone(row["elapsed_game_seconds"])
        self.assertFalse(row["live_state_verified"])
        row = session(None).review(fixture(), "2026-10-04T20:33:31Z", {})[0]
        self.assertIn("freshness_policy_unassessed", row["rejection_reasons"])

    def test_missing_malformed_fields_are_null_but_observed_zero_is_preserved(self):
        data = fixture()
        del data["frames"][0]["blueTeam"]["towers"]
        data["frames"][0]["redTeam"]["totalGold"] = True
        rows = session().review(data, "2026-10-04T20:33:31Z", {})
        self.assertIsNone(rows[0]["teams"]["blue"]["towers"])
        self.assertIsNone(rows[0]["teams"]["red"]["totalGold"])
        self.assertEqual(rows[0]["teams"]["blue"]["totalKills"], 0)
        self.assertIn("incomplete_or_invalid_fields", rows[0]["rejection_reasons"])

    def test_overlap_collision_and_ordering_are_explicit(self):
        state = session()
        data = fixture()
        state.review(data, "2026-10-04T20:33:31Z", {})
        duplicate = state.review(data, "2026-10-04T20:33:32Z", {})[0]
        self.assertIn("duplicate", duplicate["rejection_reasons"])
        data["frames"][0]["blueTeam"]["totalKills"] = 1
        collision = state.review(data, "2026-10-04T20:33:32Z", {})[0]
        self.assertIn("timestamp_collision", collision["rejection_reasons"])
        data["frames"][0]["rfc460Timestamp"] = "2026-10-04T20:33:29Z"
        backwards = state.review(data, "2026-10-04T20:33:32Z", {})[0]
        self.assertIn("out_of_order", backwards["rejection_reasons"])

    def test_identity_and_future_frames_cannot_poison_session(self):
        state = session()
        data = fixture()
        data["esportsGameId"] = "another-map"
        row = state.review(data, "2026-10-04T20:33:31Z", {})[0]
        self.assertIn("selected_game_or_match_mismatch", row["rejection_reasons"])
        self.assertIsNone(state.anchor)
        data["esportsGameId"] = "g"
        state.review(data, "2026-10-04T20:33:29Z", {})
        self.assertIsNone(state.anchor)
        self.assertEqual(
            state.review(data, "2026-10-04T20:33:31Z", {})[0]["status"],
            "research_candidate",
        )
        data["gameMetadata"]["blueTeamMetadata"]["esportsTeamId"] = "r"
        self.assertIn(
            "blue_team_identity_mismatch",
            state.review(data, "2026-10-04T20:33:32Z", {})[0]["rejection_reasons"],
        )

    def test_same_side_map_transition_requires_new_session_and_draft(self):
        first = fixture()
        state = session()
        state.review(first, "2026-10-04T20:33:31Z", {})
        next_map = copy.deepcopy(first)
        next_map["esportsGameId"] = "g2"
        next_map["gameMetadata"]["blueTeamMetadata"]["participantMetadata"][0][
            "championId"
        ] = "OtherChampion"
        self.assertIn(
            "selected_game_or_match_mismatch",
            state.review(next_map, "2026-10-04T20:33:32Z", {})[0]["rejection_reasons"],
        )
        row = session(game_id="g2").review(next_map, "2026-10-04T20:33:32Z", {})[0]
        self.assertEqual(
            row["teams"]["blue"]["participant_metadata"][0]["championId"],
            "OtherChampion",
        )
        self.assertNotIn("duplicate", row["rejection_reasons"])

    def test_finished_map_and_startup_placeholder_rejected(self):
        state = session()
        data = fixture()
        state.review(data, "2026-10-04T20:33:31Z", {})
        data["frames"][0]["gameState"] = "finished"
        terminal = state.review(data, "2026-10-04T20:33:31Z", {})[0]
        self.assertIn("timestamp_collision", terminal["rejection_reasons"])
        self.assertTrue(state.finished)
        data["frames"][0]["rfc460Timestamp"] = "2026-10-04T20:33:31Z"
        data["frames"][0]["gameState"] = "in_game"
        self.assertIn(
            "selected_map_already_finished",
            state.review(data, "2026-10-04T20:33:32Z", {})[0]["rejection_reasons"],
        )
        data["frames"][0]["blueTeam"]["totalGold"] = 0
        data["frames"][0]["blueTeam"]["participants"][0]["maxHealth"] = 0
        self.assertIn(
            "blue_startup_placeholder_pattern",
            session().review(data, "2026-10-04T20:33:32Z", {})[0]["rejection_reasons"],
        )

    def test_source_order_is_past_only_and_invalid_timing_rejected(self):
        data = fixture()
        next_frame = copy.deepcopy(data["frames"][0])
        next_frame["rfc460Timestamp"] = "2026-10-04T20:33:32Z"
        data["frames"].append(next_frame)
        all_rows = session().review(data, "2026-10-04T20:33:33Z", {})
        data["frames"] = data["frames"][:1]
        prefix = session().review(data, "2026-10-04T20:33:33Z", {})
        for rows in [all_rows, prefix]:
            for row in rows:
                row.pop("processed_at_utc")
        self.assertEqual(all_rows[:1], prefix)
        data["frames"][0]["rfc460Timestamp"] = "bad"
        self.assertIn(
            "invalid_source_timestamp",
            session().review(data, "2026-10-04T20:33:33Z", {})[0]["rejection_reasons"],
        )
        with self.assertRaises(ValueError):
            timestamp("2026-10-04T20:33:30")
        for age in [0, float("nan"), float("inf"), -1]:
            with self.assertRaises(ValueError):
                session(age)

    def test_probe_stops_on_rate_limit_saves_error_and_never_retries(self):
        class FailingOpener:
            calls = 0

            def open(self, request, timeout):
                self.calls += 1
                raise HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {},
                    io.BytesIO(b'{"error":"limit"}'),
                )

        opener = FailingOpener()
        with (
            tempfile.TemporaryDirectory() as root,
            patch("prometheus.live.requests.time.sleep") as sleep,
        ):
            out = Path(root) / "probe"
            records = probe(
                "https://feed.lolesports.com/livestats/v1/window/1",
                out,
                3,
                opener=opener,
            )
            self.assertEqual(opener.calls, 1)
            sleep.assert_not_called()
            self.assertEqual(records[0]["http_status"], 429)
            self.assertEqual(
                (out / "response_000.bin").read_bytes(), b'{"error":"limit"}'
            )
            self.assertTrue((out / "manifest.json").is_file())
            with self.assertRaises(FileExistsError):
                probe(
                    "https://feed.lolesports.com/livestats/v1/window/1",
                    out,
                    opener=opener,
                )

    def test_public_discovery_and_probe_bounds(self):
        event = {
            "__typename": "EventMatch",
            "id": "match",
            "match": {"games": [{"id": "game"}]},
            "state": "completed",
        }
        html = "prefix" + json.dumps(event, separators=(",", ":")) + "suffix"
        self.assertEqual(discover_events(html + html), [event])
        with tempfile.TemporaryDirectory() as root:
            for url, count in [
                ("https://example.com/", 1),
                ("https://lolesports.com/", 13),
            ]:
                with self.assertRaises(ValueError):
                    probe(url, Path(root) / "out", count)
                self.assertFalse((Path(root) / "out").exists())


if __name__ == "__main__":
    unittest.main()
