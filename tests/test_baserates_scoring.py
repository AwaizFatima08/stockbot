import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from stockbot import scoring
from stockbot.analysis import baserates, setups as su
from stockbot.sources.psx_daily import EodRow
from stockbot.storage.db import DB


def make_rows(symbol, closes, start=date(2026, 1, 5), sector="0813"):
    out, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(EodRow(d.isoformat(), symbol, sector, symbol, c, c * 1.01, c * 0.99, c, 1000, c))
        d += timedelta(days=1)
    return out


class BaseRateTests(unittest.TestCase):
    def test_forward_returns_and_glitch_filter(self):
        closes = [100.0] * 10 + [110.0, 111.0, 112.0, 113.0, 114.0, 115.0]
        rows = [dict(date=r.date, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume) for r in make_rows("AAA", closes)]
        s = su.build_series(rows)
        fr = baserates.forward_returns(s, 10)
        self.assertAlmostEqual(fr[5], (115 / 110 - 1) * 100)
        self.assertIsNone(fr[10])  # not enough future
        # a 50% jump inside the window invalidates it
        closes2 = [100.0] * 10 + [110.0, 170.0, 171.0, 172.0, 173.0, 174.0]
        rows2 = [dict(date=r.date, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume) for r in make_rows("AAA", closes2)]
        self.assertIsNone(baserates.forward_returns(su.build_series(rows2), 10)[5])

    def test_summarise(self):
        occ = [{5: 1.0, 10: -2.0, 20: None}, {5: -1.0, 10: 3.0, 20: None}, {5: 2.0, 10: None, 20: None}]
        br = {b.horizon: b for b in baserates.summarise("x", "AAA", occ)}
        self.assertEqual(br[5].n, 3)
        self.assertAlmostEqual(br[5].up_pct, 100 * 2 / 3)
        self.assertEqual(br[5].worst, -1.0)
        self.assertEqual(br[20].n, 0)
        self.assertIn("no past occurrences", br[20].text())

    def test_liquid_universe_excludes_debt_and_rights(self):
        tmp = Path(tempfile.mkdtemp())
        db = DB(tmp / "db.sqlite")
        db.upsert_eod(make_rows("AAA", [100.0] * 70))
        db.upsert_eod(make_rows("AAAR", [20.0] * 70))                  # right of AAA
        db.upsert_eod(make_rows("P01GIS141026", [100.0] * 70, sector="36"))  # govt security
        db.upsert_eod(make_rows("PENNY", [1.0] * 70))                  # below 5 PKR
        db.upsert_eod(make_rows("BBB", [50.0] * 70))
        u = baserates.liquid_universe(db, db.latest_date(), 10)
        self.assertEqual(sorted(u), ["AAA", "BBB"])
        db.close()


class ScoringTests(unittest.TestCase):
    def test_outcomes_and_hits(self):
        tmp = Path(tempfile.mkdtemp())
        db = DB(tmp / "db.sqlite")
        closes = [100.0 + i for i in range(30)]  # steadily rising
        rows = make_rows("AAA", closes)
        db.upsert_eod(rows)
        scoring.log_signals(db, rows[0].date, "AAA", 100.0, "uptrend", ["golden_cross", "death_cross"])
        outs = scoring.outcomes(db, rows[-1].date)
        self.assertEqual(len(outs), 3)
        by_key = {o.key: o for o in outs}
        self.assertTrue(by_key["uptrend"].hit(5))
        self.assertTrue(by_key["golden_cross"].hit(5))     # bullish, price rose
        self.assertFalse(by_key["death_cross"].hit(5))     # bearish, price rose
        self.assertAlmostEqual(by_key["uptrend"].returns[5], 5.0)
        md = scoring.scorecard_markdown(outs, rows[-1].date)
        self.assertIn("Trend: uptrend", md)
        self.assertIn("100% (1)", md)
        # too-recent signal has no returns yet
        scoring.log_signals(db, rows[-1].date, "AAA", closes[-1], "uptrend", [])
        outs = scoring.outcomes(db, rows[-1].date)
        self.assertTrue(all(v is None for v in outs[-1].returns.values()))
        db.close()


if __name__ == "__main__":
    unittest.main()
