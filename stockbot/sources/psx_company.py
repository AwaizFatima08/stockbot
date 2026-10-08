"""PSX Data Portal company page (https://dps.psx.com.pk/company/SYMBOL).

Server-rendered, one plain GET per stock. Gives: quote stats (P/E TTM, 1-year
and YTD change, market cap, shares, free float), fiscal year end, annual and
quarterly financials (sales, profit after tax, EPS), ratios, and the
announcements lists (financial results, board meetings, others) which carry
AGM notices and result dates. Payout (dividend) history is loaded by the
page through an AJAX call the portal blocks, so dividend amounts are NOT
available here; ex-dividend dates come from the XD marker in the daily
closing files instead (see corporate.py).
"""
from __future__ import annotations

import html as htmlmod
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)
URL = "https://dps.psx.com.pk/company/{sym}"


class CompanyFetchError(Exception):
    pass


@dataclass
class Announcement:
    date: str       # ISO
    title: str
    category: str   # Financial Results | Board Meetings | Others
    pdf: str | None = None


@dataclass
class Company:
    symbol: str
    as_of: str
    name: str = ""
    sector: str = ""
    fiscal_year_end: str = ""
    pe_ttm: float | None = None
    change_1y_pct: float | None = None
    change_ytd_pct: float | None = None
    market_cap_000: float | None = None
    shares: float | None = None
    free_float_shares: float | None = None
    free_float_pct: float | None = None
    annual: dict = field(default_factory=dict)     # {"years": [...], "Sales": [...], "Profit after Taxation": [...], "EPS": [...]}
    quarterly: dict = field(default_factory=dict)
    ratios: dict = field(default_factory=dict)     # {"years": [...], "<ratio>": [...]}
    announcements: list[Announcement] = field(default_factory=list)
    website: str = ""
    business: str = ""

    # derived conveniences
    @property
    def agm_notice(self) -> Announcement | None:
        for a in self.announcements:  # newest first
            if re.search(r"annual general meeting|\bAGM\b", a.title, re.I) and re.search(r"notice", a.title, re.I):
                return a
        return None

    @property
    def latest_result(self) -> Announcement | None:
        for a in self.announcements:
            if a.category == "Financial Results" and re.search(r"financial result", a.title, re.I):
                return a
        return None

    @property
    def next_board_meeting(self) -> Announcement | None:
        for a in self.announcements:
            if a.category == "Board Meetings":
                return a
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["agm_notice"] = asdict(self.agm_notice) if self.agm_notice else None
        d["latest_result"] = asdict(self.latest_result) if self.latest_result else None
        d["latest_board_meeting"] = asdict(self.next_board_meeting) if self.next_board_meeting else None
        return d


def fetch(symbol: str, raw_dir: Path, user_agent: str, as_of: date, timeout: int = 60) -> Path:
    """Download the page once per day per symbol; cached on disk."""
    d = raw_dir / as_of.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{symbol}.html"
    if path.exists() and path.stat().st_size > 10_000:
        return path
    req = urllib.request.Request(URL.format(sym=symbol), headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CompanyFetchError(f"{symbol}: {e}") from e
    if b'id="quote"' not in body:
        raise CompanyFetchError(f"{symbol}: page has no quote section ({len(body)} bytes)")
    path.write_bytes(body)
    return path


# ---------------------------------------------------------------- parsing
_TAG = re.compile(r"<[^>]+>")


def _text(s: str) -> str:
    return htmlmod.unescape(_TAG.sub(" ", s)).replace("\xa0", " ").strip()


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _text(s)).strip()


def _num(s: str) -> float | None:
    s = _clean(s).replace(",", "").replace("%", "").replace("Rs.", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _stat(page: str, label_regex: str) -> str | None:
    m = re.search(r'stats_label">\s*' + label_regex + r'.*?stats_value[^"]*">(.*?)</div>', page, re.S)
    return m.group(1) if m else None


def _table(block: str) -> dict:
    """Parse a tbl with a header row of years and rows of label + values."""
    out: dict = {}
    head = re.search(r"<thead.*?</thead>", block, re.S)
    if head:
        out["years"] = [_clean(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", head.group(0), re.S)][1:]
    body = re.search(r"<tbody.*?</tbody>", block, re.S)
    if body:
        for row in re.findall(r"<tr>(.*?)</tr>", body.group(0), re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) >= 2:
                out[_clean(cells[0])] = [_num(c) for c in cells[1:]]
    return out


def _panel(page: str, section_id: str, panel_name: str) -> str | None:
    sec = re.search(r'id="%s".*?(?=<div class="section section--padded|<div class="footer)' % section_id, page, re.S)
    if not sec:
        return None
    m = re.search(r'tabs__panel" data-name="%s">(.*?)(?=<div class="tabs__panel"|</div></div></div>)' % re.escape(panel_name), sec.group(0), re.S)
    return m.group(1) if m else None


def _date(s: str) -> str:
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(_clean(s), fmt).date().isoformat()
        except ValueError:
            continue
    return _clean(s)


def parse(path: Path, symbol: str, as_of: date) -> Company:
    page = path.read_text(encoding="utf-8", errors="replace")
    c = Company(symbol=symbol, as_of=as_of.isoformat())
    m = re.search(r'class="quote__name">(.*?)<div', page, re.S)
    c.name = _clean(m.group(1)) if m else symbol
    m = re.search(r'class="quote__sector"><span>(.*?)</span>', page, re.S)
    c.sector = _clean(m.group(1)).title() if m else ""
    m = re.search(r"Fiscal Year End</div>\s*<p>(.*?)</p>", page, re.S)
    c.fiscal_year_end = _clean(m.group(1)) if m else ""
    m = re.search(r"WEBSITE.*?<a[^>]*>(.*?)</a>", page, re.S)
    c.website = _clean(m.group(1)) if m else ""
    m = re.search(r"BUSINESS DESCRIPTION</div>\s*<p>(.*?)</p>", page, re.S)
    c.business = _clean(m.group(1))[:600] if m else ""

    v = _stat(page, r"P/E Ratio \(TTM\)")
    c.pe_ttm = _num(v) if v else None
    v = _stat(page, r"1-Year Change")
    c.change_1y_pct = _num(v) if v else None
    v = _stat(page, r"YTD Change")
    c.change_ytd_pct = _num(v) if v else None
    v = _stat(page, r"Market Cap")
    c.market_cap_000 = _num(v) if v else None
    v = _stat(page, r"Shares</div>")
    c.shares = _num(v) if v else None
    ff = re.findall(r'stats_label">Free Float</div><div class="stats_value">(.*?)</div>', page, re.S)
    for x in ff:
        if "%" in x:
            c.free_float_pct = _num(x)
        else:
            c.free_float_shares = _num(x)

    fin = _panel(page, "financials", "Annual")
    if fin:
        c.annual = _table(fin)
    finq = _panel(page, "financials", "Quarterly")
    if finq:
        c.quarterly = _table(finq)
    rat = re.search(r'id="ratios".*?<table.*?</table>', page, re.S)
    if rat:
        c.ratios = _table(rat.group(0))

    for cat in ("Financial Results", "Board Meetings", "Others"):
        pan = _panel(page, "announcements", cat)
        if not pan:
            continue
        for row in re.findall(r"<tr>(.*?)</tr>", pan, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) >= 2:
                pdf = re.search(r'href="(/download/document/[^"]+)"', cells[2] if len(cells) > 2 else "")
                c.announcements.append(Announcement(_date(cells[0]), _clean(cells[1]), cat, pdf.group(1) if pdf else None))
    c.announcements.sort(key=lambda a: a.date, reverse=True)
    return c
