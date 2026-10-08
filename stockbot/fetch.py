"""Fetch orchestration: one day, or a range (backfill)."""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from stockbot.config import Settings
from stockbot.sources import ksestocks, psx_agm, psx_company, psx_daily
from stockbot.storage.db import DB

log = logging.getLogger(__name__)


def fetch_day(db: DB, cfg: Settings, d: date, force: bool = False) -> str:
    """Returns 'ok' | 'holiday' | 'cached' | 'error'. Logs every outcome."""
    iso = d.isoformat()
    if d.weekday() >= 5:
        return "weekend"
    prior = db.fetch_status(iso)
    if prior in ("ok", "holiday") and not force:
        return "cached"
    try:
        path = psx_daily.download(d, cfg.raw_dir, cfg.user_agent)
        if path is None:
            db.log_fetch(iso, "holiday", 0, "portal returned 404 (no file for this date)")
            return "holiday"
        rows = psx_daily.parse(path, expected_date=d)
        warns = psx_daily.sanity_warnings(rows)
        n = db.upsert_eod(rows)
        msg = f"{n} rows" + (f"; {len(warns)} warnings: " + " | ".join(warns[:5]) if warns else "")
        db.log_fetch(iso, "ok", n, msg)
        if warns:
            log.warning("%s: %s", iso, msg)
        return "ok"
    except (psx_daily.FetchError, psx_daily.ParseError) as e:
        db.log_fetch(iso, "error", 0, str(e))
        log.error("%s: %s", iso, e)
        # a bad download must not be re-used
        p = psx_daily.raw_path(cfg.raw_dir, d)
        if p.exists() and isinstance(e, psx_daily.ParseError):
            p.rename(p.with_suffix(".bad"))
        return "error"


def backfill(db: DB, cfg: Settings, start: date, end: date) -> dict[str, int]:
    counts: dict[str, int] = {}
    d = start
    while d <= end:
        status = fetch_day(db, cfg, d)
        counts[status] = counts.get(status, 0) + 1
        if status in ("ok", "holiday", "error"):
            time.sleep(cfg.backfill_delay_seconds)
        d += timedelta(days=1)
    return counts


def latest_trading_day(today: date) -> date:
    """Most recent weekday on or before today (holidays resolved by fetch)."""
    d = today
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def update_companies(db: DB, cfg: Settings, as_of: date, symbols: list[str] | None = None) -> dict[str, str]:
    """Fetch and store the PSX company page for each watchlist symbol (one GET each, cached per day)."""
    results = {}
    for sym in symbols or [s.symbol for s in cfg.watchlist]:
        try:
            path = psx_company.fetch(sym, cfg.data_dir / "raw" / "company", cfg.user_agent, as_of)
            comp = psx_company.parse(path, sym, as_of)
            payload = comp.to_dict()
            notice = payload.get("agm_notice")
            payload["agm_date"] = psx_agm.meeting_date(notice["pdf"], cfg.data_dir / "raw" / "agm", cfg.user_agent, notice["date"]) if notice and notice.get("pdf") else None
            db.save_company(sym, as_of.isoformat(), payload)
            results[sym] = "ok"
        except Exception as e:  # noqa: BLE001 - one bad page must not stop the others
            log.warning("company page %s: %s", sym, e)
            results[sym] = f"error: {e}"
        time.sleep(cfg.backfill_delay_seconds)
    return results


def update_payouts(db: DB, cfg: Settings, as_of: date) -> str:
    """Fetch the ksestocks Book Closures page once per day and merge into the payouts table."""
    try:
        path = ksestocks.fetch(cfg.data_dir / "raw" / "ksestocks", cfg.user_agent, as_of)
        rows = ksestocks.parse(path)
        n = db.upsert_payouts(rows, as_of.isoformat(), ksestocks.SOURCE)
        return f"ok ({n} rows)"
    except Exception as e:  # noqa: BLE001
        log.warning("payouts: %s", e)
        return f"error: {e}"
