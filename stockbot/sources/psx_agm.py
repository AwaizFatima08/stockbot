"""Pull the actual meeting date out of an AGM/EOGM notice PDF on the PSX portal.
One small PDF per notice, cached. Text extraction with pypdf; the date is found
by a regex on phrases like 'will be held on Tuesday, October 28, 2026'."""
from __future__ import annotations

import logging
import re
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)
BASE = "https://dps.psx.com.pk"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
_DATE_PATTERNS = [
    re.compile(r"held\s+on\s+(?:\w+day,?\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + MONTHS + r")[,.]?\s+(\d{4})", re.I),
    re.compile(r"held\s+on\s+(?:\w+day,?\s+)?(" + MONTHS + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I),
    re.compile(r"(?:\w+day),?\s+(" + MONTHS + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I),
    re.compile(r"(?:\w+day),?\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + MONTHS + r")[,.]?\s+(\d{4})", re.I),
]


def _parse(day: str, month: str, year: str) -> str | None:
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(f"{int(day)} {month[:3] if fmt == '%d %b %Y' else month} {year}", fmt).date().isoformat()
        except ValueError:
            continue
    return None


def meeting_date_from_text(text: str, notice_date: str | None = None) -> str | None:
    """First date that reads as the meeting date and is on/after the notice date
    (a notice always announces a future meeting; earlier dates are year-ends etc.)."""
    text = re.sub(r"\s+", " ", text)
    candidates: list[tuple[int, str]] = []
    for prio, pat in enumerate(_DATE_PATTERNS):
        for m in pat.finditer(text):
            g = m.groups()
            d = _parse(g[0], g[1], g[2]) if g[0].isdigit() else _parse(g[1], g[0], g[2])
            if d and (notice_date is None or d >= notice_date):
                candidates.append((prio, d))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def meeting_date(pdf_path: str, cache_dir: Path, user_agent: str, notice_date: str | None = None) -> str | None:
    """pdf_path like '/download/document/283329.pdf'. Returns ISO date or None."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    local = cache_dir / Path(pdf_path).name
    if not local.exists():
        req = urllib.request.Request(BASE + pdf_path, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                local.write_bytes(r.read())
        except Exception as e:  # noqa: BLE001
            log.warning("AGM pdf %s: %s", pdf_path, e)
            return None
    try:
        reader = PdfReader(str(local))
        text = " ".join((p.extract_text() or "") for p in reader.pages[:3])
    except Exception as e:  # noqa: BLE001
        log.warning("AGM pdf parse %s: %s", pdf_path, e)
        return None
    if len(text.strip()) < 40:
        return None  # scanned image, no text layer
    return meeting_date_from_text(text, notice_date)
