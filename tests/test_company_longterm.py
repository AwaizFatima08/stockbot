import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from stockbot import corporate
from stockbot.analysis import longterm, outlook
from stockbot.analysis.daily import SymbolSnapshot
from stockbot.sources import psx_agm, psx_company
from stockbot.sources.psx_daily import EodRow
from stockbot.storage.db import DB

PAGE = """<html><div id="quote"><div class="quote__name">Test Co Limited<div class="tag">XD</div></div>
<div class="quote__sector"><span>TECHNOLOGY &amp; COMMUNICATION</span></div>
<div class="stats_item"><div class="stats_label">P/E Ratio (TTM) **</div><div class="stats_value">7.50</div></div>
<div class="stats_item"><div class="stats_label">1-Year Change * ^</div><div class="stats_value change__text--neg"><i></i> (12.30%)</div></div>
<div class="stats_item"><div class="stats_label">YTD Change * ^</div><div class="stats_value">3.10%</div></div>
<div id="profile"><div>BUSINESS DESCRIPTION</div><p>Makes things.</p><div>Fiscal Year End</div><p>June</p></div>
<div class="section section--padded companyEquity" id="equity"><div class="stats_item"><div class="stats_label">Market Cap (000'<span>s</span>)</div><div class="stats_value">1,000,000</div></div>
<div class="stats_item"><div class="stats_label">Shares</div><div class="stats_value">10,000,000</div></div>
<div class="stats_item"><div class="stats_label">Free Float</div><div class="stats_value">2,500,000</div></div>
<div class="stats_item"><div class="stats_label">Free Float</div><div class="stats_value">25.00%</div></div></div>
<div class="section section--padded company" id="announcements"><div class="tabs__panels">
<div class="tabs__panel" data-name="Financial Results"><table><tbody><tr><td>Sep 4, 2026</td><td>FINANCIAL RESULTS FOR THE YEAR ENDED JUNE 30, 2026</td><td><a href="/download/document/1.pdf">PDF</a></td></tr></tbody></table></div>
<div class="tabs__panel" data-name="Board Meetings"><table><tbody><tr><td>Sep 24, 2026</td><td>Notice of Annual General Meeting</td><td><a href="/download/document/2.pdf">PDF</a></td></tr></tbody></table></div>
<div class="tabs__panel" data-name="Others"><table><tbody></tbody></table></div></div></div>
<div class="section section--padded company" id="financials"><div class="tabs__panels">
<div class="tabs__panel" data-name="Annual"><table><thead><tr><th></th><th>2026</th><th>2025</th></tr></thead><tbody>
<tr><td>Sales</td><td><span>1,000</span></td><td><span>900</span></td></tr><tr><td>EPS</td><td><span>5.00</span></td><td><span>(1.00)</span></td></tr></tbody></table></div>
<div class="tabs__panel" data-name="Quarterly"><table><thead><tr><th></th><th>Q1 2026</th></tr></thead><tbody><tr><td>EPS</td><td><span>1.2</span></td></tr></tbody></table></div></div></div>
<div class="section" id="ratios"><table><thead><tr><th></th><th>2026</th></tr></thead><tbody><tr><td>PEG</td><td>0.5</td></tr></tbody></table></div>
<div class="footer"></div></html>"""


class CompanyParseTests(unittest.TestCase):
    def test_parse(self):
        tmp = Path(tempfile.mkdtemp()) / "TEST.html"
        tmp.write_text(PAGE, encoding="utf-8")
        c = psx_company.parse(tmp, "TEST", date(2026, 10, 8))
        self.assertEqual(c.name, "Test Co Limited")
        self.assertEqual(c.sector, "Technology & Communication")
        self.assertEqual(c.pe_ttm, 7.5)
        self.assertEqual(c.change_1y_pct, -12.3)
        self.assertEqual(c.change_ytd_pct, 3.1)
        self.assertEqual(c.market_cap_000, 1_000_000)
        self.assertEqual(c.free_float_pct, 25.0)
        self.assertEqual(c.fiscal_year_end, "June")
        self.assertEqual(c.annual["years"], ["2026", "2025"])
        self.assertEqual(c.annual["EPS"], [5.0, -1.0])
        self.assertEqual(c.quarterly["EPS"], [1.2])
        self.assertEqual(c.ratios["PEG"], [0.5])
        self.assertEqual(len(c.announcements), 2)
        self.assertEqual(c.agm_notice.date, "2026-09-24")
        self.assertEqual(c.agm_notice.pdf, "/download/document/2.pdf")
        self.assertEqual(c.latest_result.date, "2026-09-04")
        d = c.to_dict()
        self.assertEqual(d["agm_notice"]["title"], "Notice of Annual General Meeting")


class AgmDateTests(unittest.TestCase):
    def test_phrasings(self):
        f = psx_agm.meeting_date_from_text
        self.assertEqual(f("will be held on Tuesday, October 28, 2026 at 10:00"), "2026-10-28")
        self.assertEqual(f("will be held on 28th October, 2026 at"), "2026-10-28")
        self.assertEqual(f("Meeting will be held on Monday the 3rd of November 2026"), "2026-11-03")
        # year-end dates before the notice are ignored
        self.assertEqual(f("for the year ended June 30, 2026 ... held on Monday, October 27, 2026", "2026-10-06"), "2026-10-27")
        self.assertIsNone(f("no date here"))


def rows(symbol, closes, names=None, start=date(2023, 1, 2)):
    out, d = [], start
    for i, c in enumerate(closes):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(EodRow(d.isoformat(), symbol, "0813", (names or {}).get(i, symbol), c, c * 1.02, c * 0.98, c, 1000, c))
        d += timedelta(days=1)
    return out


class CorporateAndLongTermTests(unittest.TestCase):
    def setUp(self):
        self.db = DB(Path(tempfile.mkdtemp()) / "db.sqlite")

    def tearDown(self):
        self.db.close()

    def test_ex_dates_from_name_markers(self):
        names = {10: "TestXD", 11: "TestXD", 12: "TestXD", 40: "TestXDXB", 41: "TestXDXB"}
        r = rows("AAA", [100.0] * 60, names)
        self.db.upsert_eod(r)
        ev = corporate.ex_events(self.db, "AAA")
        self.assertEqual([(e["date"], e["kinds"]) for e in ev], [(r[10].date, ["XD"]), (r[40].date, ["XB", "XD"])])
        s = corporate.summary(self.db, "AAA", r[-1].date)
        self.assertEqual(s["last_ex_dividend"], r[40].date)
        self.assertEqual(s["last_ex_bonus"], r[40].date)
        self.assertEqual(s["ex_dividends_last_12m"], 2)

    def test_price_stats_and_outlook(self):
        closes = [100.0 * (1.0 + 0.0005 * i) for i in range(800)]  # gentle rise, > 3 years
        r = rows("AAA", closes)
        self.db.upsert_eod(r)
        ps = longterm.price_stats(self.db, "AAA", r[-1].date)
        self.assertGreater(ps["return_1y_pct"], 0)
        self.assertIsNotNone(ps["cagr_3y_pct"])
        self.assertIsNone(ps["return_5y_pct"])
        self.assertAlmostEqual(ps["max_drawdown_3y_pct"], 0.0)
        self.assertEqual(ps["positive_year_windows_pct"], 100.0)
        fv = longterm.fundamentals_view({"annual": {"years": ["2026", "2025", "2024"], "EPS": [8.0, 6.0, 4.0]}, "pe_ttm": 9.0}, 100.0)
        self.assertEqual(fv["profitable_years"], 3)
        self.assertAlmostEqual(fv["eps_cagr_pct"], 41.42, places=1)
        self.assertAlmostEqual(fv["pe_on_latest_annual_eps"], 12.5)
        text = " ".join(longterm.sentences("AAA", ps, fv, {"last_ex_dividend": None}))
        self.assertIn("compounded", text)
        self.assertNotIn("will ", text)
        snap = SymbolSnapshot(symbol="AAA", name="A", sector="T", ok=True, close=closes[-1], sma_short=closes[-1] * 0.99, sma_long=closes[-1] * 0.97, trend="uptrend", high_52w=closes[-1] * 1.1, low_52w=closes[-1] * 0.8)
        o = outlook.build(self.db, snap, r[-1].date)
        self.assertIsNotNone(o["weekly_distribution"])
        self.assertTrue(any(l["label"] == "20-day average" for l in o["levels"]))
        self.assertIn("not a forecast", o["sentences"][-1])


if __name__ == "__main__":
    unittest.main()
