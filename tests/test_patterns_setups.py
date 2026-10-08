import unittest

from stockbot.analysis import patterns as pat, setups as su


def C(o, h, l, c):
    return pat.Candle(o, h, l, c)


class PatternTests(unittest.TestCase):
    def test_doji(self):
        hits = pat.detect([C(10, 11, 9, 10.02)])
        self.assertIn("doji", [h.name for h in hits])

    def test_hammer_needs_prior_decline(self):
        decline = [C(12, 12.2, 11.8, 11.9), C(11.9, 12, 11.5, 11.6), C(11.6, 11.7, 11.2, 11.3), C(11.3, 11.4, 11.0, 11.1), C(11.1, 11.2, 10.8, 10.9), C(10.9, 11, 10.5, 10.6)]
        hammer = C(10.5, 10.6, 9.5, 10.55)  # tiny body at top, long lower shadow
        names = [h.name for h in pat.detect(decline + [hammer], 0.4)]
        self.assertIn("hammer", names)
        advance = [C(o, o + 0.2, o - 0.2, o + 0.15) for o in (10, 10.3, 10.6, 10.9, 11.2, 11.5)]
        self.assertNotIn("hammer", [h.name for h in pat.detect(advance + [hammer], 0.4)])

    def test_engulfing(self):
        prev = C(10.0, 10.1, 9.4, 9.5)   # red
        cur = C(9.4, 10.4, 9.3, 10.3)    # green, engulfs
        self.assertIn("bullish_engulfing", [h.name for h in pat.detect([prev, cur])])
        self.assertIn("bearish_engulfing", [h.name for h in pat.detect([C(9.5, 10.1, 9.4, 10.0), C(10.1, 10.2, 9.2, 9.3)])])

    def test_gaps(self):
        self.assertIn("gap_up", [h.name for h in pat.detect([C(10, 10.5, 9.8, 10.2), C(10.8, 11, 10.7, 10.9)])])
        self.assertIn("gap_down", [h.name for h in pat.detect([C(10, 10.5, 9.8, 10.2), C(9.5, 9.6, 9.2, 9.3)])])

    def test_invalid_candle_gives_nothing(self):
        self.assertEqual(pat.detect([C(0, 0, 0, 0)]), [])


def rows(closes, vols=None):
    vols = vols or [1000] * len(closes)
    return [{"date": f"2026-01-{i+1:02d}", "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": v}
            for i, (c, v) in enumerate(zip(closes, vols))]


class SetupTests(unittest.TestCase):
    def test_cross_above_sma20(self):
        closes = [100.0] * 25 + [95.0, 105.0]  # dips below then jumps above the 20-day average
        s = su.build_series(rows(closes))
        self.assertIn("cross_below_sma20", su.setups_at(s, 25))
        self.assertIn("cross_above_sma20", su.setups_at(s, 26))

    def test_volume_spike(self):
        closes = [100.0 + i * 0.1 for i in range(30)]
        vols = [1000] * 29 + [5000]
        s = su.build_series(rows(closes, vols))
        self.assertIn("volume_spike_up", su.setups_at(s, 29))

    def test_rsi_oversold_entry_fires_once(self):
        closes = [100.0] * 15 + [100 - i * 1.5 for i in range(1, 15)]
        s = su.build_series(rows(closes))
        fires = [i for i in range(len(closes)) if "rsi_oversold_entry" in su.setups_at(s, i)]
        self.assertEqual(len(fires), 1)

    def test_all_setups_known(self):
        closes = [100 + (i % 7) for i in range(60)]
        s = su.build_series(rows(closes))
        for i in range(len(closes)):
            for k in su.setups_at(s, i):
                self.assertIn(k, su.SETUPS)


if __name__ == "__main__":
    unittest.main()
