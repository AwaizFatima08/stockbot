import unittest

from stockbot import indicators as ind


class IndicatorTests(unittest.TestCase):
    def test_sma(self):
        self.assertIsNone(ind.sma([1, 2], 3))
        self.assertAlmostEqual(ind.sma([1, 2, 3, 4], 3), 3.0)
        self.assertEqual(ind.sma_series([1, 2, 3, 4], 2), [None, 1.5, 2.5, 3.5])

    def test_rsi_known_values(self):
        # Classic textbook example (Wilder): 14-period RSI of this series is ~70.46
        closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                  45.89, 46.03, 45.61, 46.28, 46.28]
        self.assertAlmostEqual(ind.rsi(closes, 14), 70.46, places=1)
        self.assertIsNone(ind.rsi(closes[:10], 14))

    def test_rsi_extremes(self):
        self.assertEqual(ind.rsi(list(range(1, 20)), 14), 100.0)
        self.assertEqual(ind.rsi(list(range(20, 1, -1)), 14), 0.0)

    def test_pct_change(self):
        self.assertAlmostEqual(ind.pct_change([100, 110], 1), 10.0)
        self.assertIsNone(ind.pct_change([100], 1))
        self.assertIsNone(ind.pct_change([0, 5], 1))

    def test_high_low_average(self):
        v = [3.0, 9.0, 1.0, 4.0]
        self.assertEqual(ind.highest(v, 3), 9.0)
        self.assertEqual(ind.lowest(v, 2), 1.0)
        self.assertEqual(ind.average(v, 2), 2.5)
        self.assertIsNone(ind.average(v, 5))


if __name__ == "__main__":
    unittest.main()
