import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from stockbot import corporate
from stockbot.sources import ksestocks
from stockbot.sources.psx_daily import EodRow
from stockbot.storage.db import DB

PAGE = """<html><script>
var bcs={"cur":[{"symbol":"HUBC","cname":"Hub Power Company Limited","faceval":"10","bcfrom":"2026-10-13","bcto":"2026-10-20","payout":"Dividend=50%","lc":"200.49"},
{"symbol":"BPL","cname":"Burshane","faceval":"10","bcfrom":"2026-10-09","bcto":"2026-10-15","payout":"Dividend=10%Bonus=20%","lc":"48.95"},
{"symbol":"THALL","cname":"Thal","faceval":"5","bcfrom":"2026-10-16","bcto":"2026-10-22","payout":"Dividend=300%","lc":"518.24"},
{"symbol":"LOADS","cname":"Loads","faceval":"10","bcfrom":"2026-10-13","bcto":"2026-10-20","payout":"Nil"},
{"symbol":"BAPL","cname":"Bawany","faceval":"10","bcfrom":"-","bcto":"-","payout":"Right=98.965%","lc":"40.86"},
{"symbol":"A1","cname":"a","faceval":"10","bcfrom":"2026-10-20","bcto":"2026-10-21","payout":"Dividend=5%","lc":"1"},
{"symbol":"A2","cname":"a","faceval":"10","bcfrom":"2026-10-20","bcto":"2026-10-21","payout":"Dividend=5%","lc":"1"},
{"symbol":"A3","cname":"a","faceval":"10","bcfrom":"2026-10-20","bcto":"2026-10-21","payout":"Dividend=5%","lc":"1"}],
"old":[{"symbol":"HUBC","cname":"Hub Power Company Limited","faceval":"10","bcfrom":"2026-06-10","bcto":"2026-06-17","payout":"Dividend=30%"},
{"symbol":"LUCK","cname":"Lucky","faceval":"10","bcfrom":"2026-09-18","bcto":"2026-09-25","payout":"Dividend=250%"}]};
$(function(){});
</script></html>"""


class KsestocksParseTests(unittest.TestCase):
    def test_parse(self):
        p = Path(tempfile.mkdtemp()) / "2026-10-08.html"
        p.write_text(PAGE, encoding="utf-8")
        rows = ksestocks.parse(p)
        by = {(r.symbol, r.bc_from): r for r in rows}
        h = by[("HUBC", "2026-10-13")]
        self.assertEqual((h.dividend_pct, h.dividend_per_share, h.bonus_pct, h.bucket), (50.0, 5.0, None, "cur"))
        b = by[("BPL", "2026-10-09")]
        self.assertEqual((b.dividend_per_share, b.bonus_pct), (1.0, 20.0))
        self.assertEqual(by[("THALL", "2026-10-16")].dividend_per_share, 15.0)  # 300% of Rs 5 face value
        self.assertIsNone(by[("LOADS", "2026-10-13")].dividend_pct)
        r = by[("BAPL", None)]
        self.assertEqual(r.right_pct, 98.965)
        self.assertEqual(by[("HUBC", "2026-06-10")].bucket, "old")

    def test_too_few_rows_fails(self):
        p = Path(tempfile.mkdtemp()) / "x.html"
        p.write_text('<script>var bcs={"cur":[{"symbol":"X","payout":"Nil"}],"old":[]};</script>', encoding="utf-8")
        with self.assertRaises(ksestocks.PayoutFetchError):
            ksestocks.parse(p)


class PayoutFactsTests(unittest.TestCase):
    def test_facts_and_idempotent_upsert(self):
        db = DB(Path(tempfile.mkdtemp()) / "db.sqlite")
        p = Path(tempfile.mkdtemp()) / "2026-10-08.html"
        p.write_text(PAGE, encoding="utf-8")
        rows = ksestocks.parse(p)
        db.upsert_payouts(rows, "2026-10-08", "test")
        db.upsert_payouts(rows, "2026-10-09", "test")  # same rows again: no duplicates
        self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM payouts WHERE symbol='HUBC'").fetchone()[0], 2)
        f = corporate.payout_facts(db, "HUBC", "2026-10-08")
        self.assertEqual(f["upcoming"][0]["dividend_per_share"], 5.0)
        self.assertEqual(f["last_dividend"]["dividend_per_share"], 3.0)
        self.assertEqual(f["dividends_per_share_12m"], 3.0)
        # once the closure date has passed it becomes the last dividend
        f2 = corporate.payout_facts(db, "2026-10-14".replace("2026-10-14", "2026-10-14") and "HUBC", "2026-10-14")
        self.assertEqual(f2["last_dividend"]["dividend_per_share"], 5.0)
        self.assertEqual(f2["upcoming"], [])
        self.assertEqual(f2["dividends_per_share_12m"], 8.0)
        # summary() merges payout facts with XD markers
        d = date(2026, 10, 1)
        db.upsert_eod([EodRow(d.isoformat(), "HUBC", "0824", "Hub Power", 200, 201, 199, 200, 1000, 200)])
        s = corporate.summary(db, "HUBC", "2026-10-08")
        self.assertIn("upcoming", s)
        self.assertIn("last_ex_dividend", s)
        db.close()


if __name__ == "__main__":
    unittest.main()
