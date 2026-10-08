import io
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from stockbot.sources import psx_daily

SAMPLE = "\n".join(
    [f"07OCT2026|SYM{i:03d}|0813|Company {i}|10.0|11.0|9.5|10.5|{1000+i}|10.2|||" for i in range(120)]
    + [
        "07OCT2026|OGDC|0820|Oil & Gas Dev|318.0|318.45|315|315.91|2260742|317.05|||",
        "07OCT2026|OGDC-CDEC|40|Oil & Gas Dev|0.0|0|0|326.66|0|327.98|||",
        "07OCT2026|ZUMA|0828|Zuma Resources Ltd.|28.1|28.2|26.91|27.3|2668540|28.15|||",
    ]
) + "\n"


def make_zip(text: str, member="closing11.lis") -> Path:
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "2026-10-07.Z"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, text)
    return p


class ParseTests(unittest.TestCase):
    def test_parses_equities_and_skips_futures(self):
        rows = psx_daily.parse(make_zip(SAMPLE), expected_date=date(2026, 10, 7))
        syms = {r.symbol for r in rows}
        self.assertIn("OGDC", syms)
        self.assertIn("ZUMA", syms)
        self.assertNotIn("OGDC-CDEC", syms)
        ogdc = next(r for r in rows if r.symbol == "OGDC")
        self.assertEqual(ogdc.date, "2026-10-07")
        self.assertEqual((ogdc.open, ogdc.high, ogdc.low, ogdc.close), (318.0, 318.45, 315.0, 315.91))
        self.assertEqual(ogdc.volume, 2260742)
        self.assertEqual(ogdc.ldcp, 317.05)
        self.assertEqual(ogdc.sector_code, "0820")

    def test_wrong_date_fails_loud(self):
        with self.assertRaises(psx_daily.ParseError):
            psx_daily.parse(make_zip(SAMPLE), expected_date=date(2026, 10, 8))

    def test_too_few_rows_fails_loud(self):
        short = "\n".join(SAMPLE.splitlines()[:10]) + "\n"
        with self.assertRaises(psx_daily.ParseError):
            psx_daily.parse(make_zip(short))

    def test_bad_number_fails_loud(self):
        bad = SAMPLE.replace("|318.0|", "|abc|")
        with self.assertRaises(psx_daily.ParseError):
            psx_daily.parse(make_zip(bad))

    def test_sanity_warnings(self):
        rows = psx_daily.parse(make_zip(SAMPLE))
        self.assertEqual(psx_daily.sanity_warnings(rows), [])
        odd = SAMPLE.replace("|315.91|2260742|", "|400.0|2260742|")
        warns = psx_daily.sanity_warnings(psx_daily.parse(make_zip(odd)))
        self.assertEqual(len(warns), 1)
        self.assertIn("OGDC", warns[0])


if __name__ == "__main__":
    unittest.main()


class ArchiveLayoutTests(unittest.TestCase):
    def test_zip_with_folder_entry(self):
        tmp = Path(tempfile.mkdtemp())
        p = tmp / "2026-10-07.Z"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("20261007_new.lis/", "")
            zf.writestr("20261007_new.lis/closing11.lis", SAMPLE)
        self.assertEqual(len(psx_daily.parse(p, expected_date=date(2026, 10, 7))), 122)

    def test_plain_gzip(self):
        import gzip
        tmp = Path(tempfile.mkdtemp())
        p = tmp / "2026-10-07.Z"
        with gzip.open(p, "wb") as fh:
            fh.write(SAMPLE.encode())
        self.assertEqual(len(psx_daily.parse(p, expected_date=date(2026, 10, 7))), 122)
