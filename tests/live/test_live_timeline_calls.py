import math
import unittest
from datetime import UTC, datetime, timedelta

from prometheus.live.timeline import elapsed_seconds, timeline_calls

T0 = datetime(2026, 10, 15, 21, 0, tzinfo=UTC)
MODEL = {
    "schema": "time_gold_elo_v1",
    "features": [
        "gold_k",
        "gold_fraction",
        "elo_hundred",
        "time",
        "gold_time",
        "elo_time",
    ],
    "supported_seconds": [0, 2400],
    "mean": [0, 0, 0, 0, 0, 0],
    "scale": [1, 1, 1, 1, 1, 1],
    "coef": [0.5, 0, 0.3, 0, 0, 0],
    "intercept": 0,
    "calibration_slope": 1,
    "calibration_intercept": 0,
}


def frame(seconds, blue, red):
    at = (T0 + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
    return {"at": at, "source_at": at, "teams": [{"gold": blue}, {"gold": red}]}


class ElapsedTest(unittest.TestCase):
    def test_starts_at_starting_gold_and_ignores_loading_frames(self):
        frames = [frame(0, 0, 0), frame(4, 2500, 2500), frame(64, 3000, 3100)]
        self.assertEqual(elapsed_seconds(frames), [None, 0.0, 60.0])

    def test_no_seen_start_gives_no_clock(self):
        self.assertEqual(elapsed_seconds([frame(0, 9000, 9100)]), [None])

    def test_early_flat_gold_is_not_a_pause(self):
        frames = [frame(0, 2500, 2500), frame(50, 2500, 2500), frame(70, 2600, 2600)]
        self.assertEqual(elapsed_seconds(frames)[-1], 70.0)

    def test_flat_gold_after_two_minutes_is_removed_as_a_pause(self):
        frames = [frame(0, 2500, 2500), frame(300, 8000, 8000)]
        frames += [frame(300 + s, 8000, 8000) for s in (10, 20, 30, 40)]
        frames.append(frame(350, 8100, 8050))
        el = elapsed_seconds(frames)
        self.assertEqual(el[4], 300.0)  # held while paused
        self.assertEqual(el[-1], 310.0)  # 40 paused seconds removed


class CallsTest(unittest.TestCase):
    ratings = ({"elo": 1800}, {"elo": 1700})

    def test_first_team_orientation_follows_blue_side(self):
        frames = [frame(0, 2500, 2500), frame(120, 6000, 4000)]
        blue_first = {"game": {"blue": 0, "frames": frames, "calls": []}}
        red_first = {"game": {"blue": 1, "frames": frames, "calls": []}}
        pre0, calls0 = timeline_calls(blue_first, MODEL, self.ratings)
        pre1, calls1 = timeline_calls(red_first, MODEL, self.ratings)
        self.assertGreater(pre0, 0.5)
        self.assertGreater(pre1, 0.5)  # teams[0] still has the higher Elo
        # Frames are in match-team order, so teams[0] leads gold on either side.
        self.assertGreater(calls0[-1]["p"], pre0)
        self.assertGreater(calls1[-1]["p"], pre1)

    def test_series_shift_moves_every_call(self):
        frames = [frame(0, 2500, 2500), frame(120, 6000, 4000)]
        page = lambda: {"game": {"blue": 1, "frames": frames, "calls": []}}
        pre, calls = timeline_calls(page(), MODEL, self.ratings)
        up_pre, up_calls = timeline_calls(page(), MODEL, self.ratings, shift=0.3)
        logit = lambda p: math.log(p / (1 - p))
        self.assertAlmostEqual(logit(up_pre) - logit(pre), 0.3)
        self.assertAlmostEqual(logit(up_calls[-1]["p"]) - logit(calls[-1]["p"]), 0.3)

    def test_one_call_per_minute_newest_wins_and_stops_past_range(self):
        frames = [frame(0, 2500, 2500)]
        frames += [frame(s, 2500 + s, 2500 + s) for s in (70, 80, 130, 2500)]
        _, calls = timeline_calls(
            {"game": {"blue": 0, "frames": frames, "calls": []}}, MODEL, self.ratings
        )
        self.assertEqual([c["minute"] for c in calls], [0.0, 1.3, 2.2])


if __name__ == "__main__":
    unittest.main()
