import math
import unittest

from prometheus.live.timeline import FEATURES, features, predict


class TimeModelTests(unittest.TestCase):
    def test_continuous_time_and_strict_domain(self):
        model = {
            "schema": "time_gold_elo_v1",
            "features": FEATURES,
            "supported_seconds": [0, 2400],
            "mean": [0] * 6,
            "scale": [1] * 6,
            "coef": [0, 0, 0, 1, 0, 0],
            "intercept": 0,
            "calibration_slope": 1,
            "calibration_intercept": 0,
        }
        self.assertAlmostEqual(
            predict(model, 750, 20000, 20000, 1500, 1500),
            1 / (1 + math.exp(-750 / 1200)),
        )
        for t in [-1, 2401, float("nan"), True]:
            with self.assertRaises(ValueError):
                predict(model, t, 20000, 20000, 1500, 1500)
        with self.assertRaises(ValueError):
            features(750, 0, 20000, 1500, 1500)
