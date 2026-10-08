"""PSX Data Portal daily Market Summary (closing) file.

Source: https://dps.psx.com.pk/download/mkt_summary/YYYY-MM-DD.Z
One small ZIP per trading day containing a pipe-delimited file
(closing11.lis). Columns, as observed on 2026-10-07:

    DATE(DDMONYYYY) | SYMBOL | SECTOR_CODE | NAME | OPEN | HIGH | LOW | CLOSE | VOLUME | LDCP | | |

LDCP = last day closing price (previous close). Rows whose symbol contains
"-" are futures/derivative contracts (sector code 40) and are skipped.
Non-trading days return HTTP 404.

Terms of use: the portal's terms restrict automated/systematic retrieval.
This module downloads one official file per trading day, once, and keeps a
local copy so a day is never fetched twice. Whether that is acceptable for
personal research use is Homi's decision (design doc section 7).
"""
from __future__ import annotations

import io
import logging
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

URL_TEMPLATE = "https://dps.psx.com.pk/download/mkt_summary/{d}.Z"
MIN_EXPECTED_ROWS = 100


class FetchError(Exception):
    """Network or server problem (not a holiday)."""


class ParseError(Exception):
    """File downloaded but its content is not what we expect."""


@dataclass(frozen=True)
class EodRow:
    date: str  # ISO yyyy-mm-dd
    symbol: str
    sector_code: str
    name: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    ldcp: float


def raw_path(raw_dir: Path, d: date) -> Path:
    return raw_dir / f"{d.isoformat()}.Z"


def download(d: date, raw_dir: Path, user_agent: str, timeout: int = 60) -> Path | None:
    """Download the day's file into raw_dir. Returns the path, or None if the
    portal has no file for that date (HTTP 404 = holiday / weekend / not yet
    published). Re-uses an existing local copy. Raises FetchError otherwise."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_path(raw_dir, d)
    if path.exists() and path.stat().st_size > 0:
        log.debug("using cached %s", path.name)
        return path

    req = urllib.request.Request(URL_TEMPLATE.format(d=d.isoformat()), headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise FetchError(f"HTTP {e.code} for {d}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(f"network error for {d}: {e}") from e

    if not body.startswith(b"PK"):
        raise ParseError(f"{d}: response is not a ZIP file ({len(body)} bytes)")
    path.write_bytes(body)
    return path


def _num(v: str, field: str, line_no: int) -> float:
    v = v.strip()
    if v == "":
        return 0.0
    try:
        return float(v)
    except ValueError as e:
        raise ParseError(f"line {line_no}: bad {field} value {v!r}") from e


def parse(path: Path, expected_date: date | None = None) -> list[EodRow]:
    """Parse the ZIP at `path` into equity rows. Validates structure and date."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if len(names) != 1:
                raise ParseError(f"{path.name}: expected 1 file in ZIP, got {names}")
            text = zf.read(names[0]).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as e:
        raise ParseError(f"{path.name}: bad ZIP") from e

    rows: list[EodRow] = []
    dates_seen: set[str] = set()
    for line_no, line in enumerate(io.StringIO(text), start=1):
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 10:
            raise ParseError(f"{path.name} line {line_no}: only {len(parts)} fields: {line[:80]!r}")
        symbol = parts[1].strip().upper()
        if not symbol:
            raise ParseError(f"{path.name} line {line_no}: empty symbol")
        if "-" in symbol:
            continue  # futures / derivative contract
        try:
            d_iso = datetime.strptime(parts[0].strip(), "%d%b%Y").date().isoformat()
        except ValueError as e:
            raise ParseError(f"{path.name} line {line_no}: bad date {parts[0]!r}") from e
        dates_seen.add(d_iso)
        row = EodRow(
            date=d_iso,
            symbol=symbol,
            sector_code=parts[2].strip(),
            name=parts[3].strip(),
            open=_num(parts[4], "open", line_no),
            high=_num(parts[5], "high", line_no),
            low=_num(parts[6], "low", line_no),
            close=_num(parts[7], "close", line_no),
            volume=int(_num(parts[8], "volume", line_no)),
            ldcp=_num(parts[9], "ldcp", line_no),
        )
        rows.append(row)

    if len(rows) < MIN_EXPECTED_ROWS:
        raise ParseError(f"{path.name}: only {len(rows)} equity rows (expected >= {MIN_EXPECTED_ROWS})")
    if len(dates_seen) != 1:
        raise ParseError(f"{path.name}: mixed dates in file: {sorted(dates_seen)}")
    file_date = next(iter(dates_seen))
    if expected_date and file_date != expected_date.isoformat():
        raise ParseError(f"{path.name}: file is for {file_date}, expected {expected_date}")
    return rows


def sanity_warnings(rows: list[EodRow]) -> list[str]:
    """Soft checks that should be reported, not fatal."""
    warns = []
    for r in rows:
        if r.volume > 0:
            if r.high < r.low:
                warns.append(f"{r.symbol}: high {r.high} < low {r.low}")
            if not (r.low <= r.close <= r.high):
                warns.append(f"{r.symbol}: close {r.close} outside [{r.low}, {r.high}]")
            if r.close <= 0:
                warns.append(f"{r.symbol}: non-positive close with volume {r.volume}")
    return warns
