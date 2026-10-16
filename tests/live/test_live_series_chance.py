import math
import unittest

from prometheus.live.series import series_chance


def prometheus_series(p, best_of, rho):
    """Prometheus schedule.series_probability, copied for a fixed comparison."""
    need = best_of // 2 + 1
    kappa = 1 / rho - 1
    a, b = p * kappa, (1 - p) * kappa
    lb = lambda x, y: math.lgamma(x) + math.lgamma(y) - math.lgamma(x + y)
    return sum(
        math.comb(need - 1 + k, k) * math.exp(lb(a + need, b + k) - lb(a, b))
        for k in range(need)
    )


class SeriesChanceTest(unittest.TestCase):
    def test_matches_prometheus_before_the_series(self):
        for p, bo, rho in ((0.6248, 5, 0.054), (0.3, 3, 0.127)):
            self.assertAlmostEqual(
                series_chance(p, bo, rho, [0, 0]), prometheus_series(p, bo, rho)
            )

    def test_decided_series(self):
        self.assertEqual(series_chance(0.4, 5, 0.054, [3, 1]), 1.0)
        self.assertEqual(series_chance(0.9, 5, 0.054, [0, 3]), 0.0)

    def test_live_map_moves_the_series(self):
        low = series_chance(0.62, 5, 0.054, [1, 2], 0.2)
        high = series_chance(0.62, 5, 0.054, [1, 2], 0.9)
        self.assertLess(low, series_chance(0.62, 5, 0.054, [1, 2]))
        self.assertGreater(high, series_chance(0.62, 5, 0.054, [1, 2]))
        # Losing map 4 at 1-2 ends a best of five.
        self.assertAlmostEqual(series_chance(0.62, 5, 0.054, [1, 2], 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
