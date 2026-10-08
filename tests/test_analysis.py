import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from stockbot.analysis import daily
from stockbot.config import Settings, Stock
from stockbot.reports import daily_note
from stockbot.sources.psx_daily import EodRow
from stockbot.storage.db import DB

ADVICE = re.compile(r"\b(buy|sell|hold|target)\b", re.I)


def settings(tmp: Path) -> Settings:
    return Settings(
        root=tmp, timezone="Asia/Karachi", data_dir=tmp / "data", reports_dir=tmp / "reports",
        raw_dir=tmp / "raw", snapshots_dir=tmp / "snap", db_path=tmp / "db.sqlite",
        backfill_delay_seconds=0, user_agent="test", sma_short=5, sma_long=10, rsi_period=5,
        volume_avg_period=5, history_days=400, ai_enabled=False, ai_model="none",
        watchlist=(Stock("AAA", "Alpha", "Test"), Stock("MISSING", "Nobody", "Test")),
    )


def seed(db: DB, n_days: int, start_price=100.0):
    d = date(2026, 1, 5)
    rows = []
    price = start_price
    for i in range(n_days):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        prev = price
        price = price * (1.01 if i % 3 else 0.995)
        rows.append(EodRow(d.isoformat(), "AAA", "0813", "Alpha", prev, max(prev, price) * 1.01, min(prev, price) * 0.99, price, 1000 + i * 10, prev))
        d += timedelta(days=1)
    db.upsert_eod(rows)
    return rows[-1].date


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = settings(self.tmp)
        self.db = DB(self.cfg.db_path)

    def tearDown(self):
        self.db.close()

    def test_snapshot_and_note(self):
        last = seed(self.db, 30)
        a = daily.build(self.db, self.cfg, date.fromisoformat(last))
        aaa = a.snapshots[0]
        self.assertTrue(aaa.ok)
        self.assertIsNotNone(aaa.sma_short)
        self.assertIsNotNone(aaa.sma_long)
        self.assertIsNotNone(aaa.rsi)
        self.assertIsNotNone(aaa.ret_1w)
        self.assertIsNone(aaa.high_52w)  # not enough history for 52-week figures
        self.assertTrue(aaa.sentences)
        # a missing symbol is reported, not silently dropped
        self.assertFalse(a.data_ok)
        self.assertTrue(any("MISSING" in p for p in a.data_problems))
        md, snap = daily_note.write(a, self.cfg, None, "AI off")
        text = md.read_text()
        self.assertIn("PROBLEMS", text)
        self.assertIn("AAA", text)
        self.assertTrue(snap.exists())

    def test_sentences_contain_no_advice(self):
        last = seed(self.db, 40)
        a = daily.build(self.db, self.cfg, date.fromisoformat(last))
        text = daily_note.render(a, self.cfg, None, "AI off")
        body = text.split("---")[0]  # exclude the disclaimer, which names the words to say we don't use them
        self.assertIsNone(ADVICE.search(body), ADVICE.search(body))

    def test_stale_date_is_flagged(self):
        last = seed(self.db, 20)
        later = date.fromisoformat(last) + timedelta(days=3)
        a = daily.build(self.db, self.cfg, later)
        self.assertFalse(a.data_ok)
        self.assertTrue(any("no market data" in p for p in a.data_problems))


if __name__ == "__main__":
    unittest.main()
