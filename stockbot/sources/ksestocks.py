"""ksestocks.com Book Closures page - declared payouts with book-closure dates.

The page embeds a JSON object (`var bcs = {"cur": [...], "old": [...]}`) where
each entry has symbol, company name, face value, book-closure from/to, the
payout text ("Dividend=60%", "Bonus=20%", "Right=50%", combinations, or
"Nil") and last close. Dividend per share = pct x face value / 100.

Reviewed 8 Oct 2026 (docs/data-sources.md): robots.txt allows all, the site's
disclaimer sets no restriction on automated use; data mirrors PSX notices.
PSX announcements remain the authority. One GET per day, cached on disk."""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)
URL = "https://www.ksestocks.com/BookClosures"
SOURCE = "ksestocks.com"


class PayoutFetchError(Exception):
    pass


@dataclass(frozen=True)
class Payout:
    symbol: str
    company: str
    face_value: float
    bc_from: str | None      # ISO or None when not yet announced
    bc_to: str | None
    payout_text: str         # as published, e.g. "Dividend=60%Bonus=20%"
    dividend_pct: float | None
    dividend_per_share: float | None
    bonus_pct: float | None
    right_pct: float | None
    last_close: float | None
    bucket: str              # "cur" | "old"


def fetch(raw_dir: Path, user_agent: str, as_of: date, timeout: int = 60) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{as_of.isoformat()}.html"
    if path.exists() and path.stat().st_size > 5_000:
        return path
    req = urllib.request.Request(URL, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PayoutFetchError(str(e)) from e
    if b"var bcs" not in body:
        raise PayoutFetchError(f"page has no bcs data ({len(body)} bytes)")
    path.write_bytes(body)
    return path


_PCT = re.compile(r"(Dividend|Bonus|Right)=([0-9.]+)%", re.I)


def _date(s: str | None) -> str | None:
    s = (s or "").strip()
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def _num(s) -> float | None:
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse(path: Path) -> list[Payout]:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"var\s+bcs\s*=\s*(\{.*?\})\s*;", text, re.S)
    if not m:
        raise PayoutFetchError("bcs JSON not found")
    data = json.loads(m.group(1))
    out: list[Payout] = []
    for bucket in ("cur", "old"):
        for e in data.get(bucket, []):
            sym = str(e.get("symbol", "")).strip().upper()
            if not sym:
                continue
            fv = _num(e.get("faceval")) or 10.0
            txt = str(e.get("payout", "")).strip()
            parts = {k.lower(): float(v) for k, v in _PCT.findall(txt)}
            div = parts.get("dividend")
            out.append(Payout(
                symbol=sym, company=str(e.get("cname", "")).strip(), face_value=fv,
                bc_from=_date(e.get("bcfrom")), bc_to=_date(e.get("bcto")), payout_text=txt,
                dividend_pct=div, dividend_per_share=(div * fv / 100.0) if div is not None else None,
                bonus_pct=parts.get("bonus"), right_pct=parts.get("right"),
                last_close=_num(e.get("lc")), bucket=bucket,
            ))
    if len(out) < 10:
        raise PayoutFetchError(f"only {len(out)} payout rows parsed")
    return out
