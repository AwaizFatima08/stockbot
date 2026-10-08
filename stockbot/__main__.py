"""Command line: python -m stockbot <command>"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from stockbot import config
from stockbot.ai import gemini
from stockbot.analysis import daily as daily_analysis
from stockbot.fetch import backfill, fetch_day, latest_trading_day
from stockbot.reports import daily_note
from stockbot.storage.db import DB


def _date(s: str) -> date:
    return date.fromisoformat(s)


def cmd_fetch(args, cfg, db):
    d = args.date or latest_trading_day(datetime.now(ZoneInfo(cfg.timezone)).date())
    status = fetch_day(db, cfg, d, force=args.force)
    print(f"{d}: {status}")
    return 0 if status in ("ok", "cached", "holiday", "weekend") else 1


def cmd_backfill(args, cfg, db):
    end = args.end or latest_trading_day(datetime.now(ZoneInfo(cfg.timezone)).date())
    counts = backfill(db, cfg, args.start, end)
    print(f"backfill {args.start}..{end}: {counts}")
    print(db.counts())
    return 0 if counts.get("error", 0) == 0 else 1


def cmd_note(args, cfg, db):
    d = args.date or (date.fromisoformat(db.latest_date()) if db.latest_date() else None)
    if d is None:
        print("database empty; run fetch/backfill first", file=sys.stderr)
        return 1
    analysis = daily_analysis.build(db, cfg, d)
    narrative, ai_status = (None, "AI narrative skipped (--no-ai)") if args.no_ai else gemini.narrate(analysis.to_dict(), cfg)
    md, snap = daily_note.write(analysis, cfg, narrative, ai_status)
    print(f"note: {md}\nsnapshot: {snap}\nstatus: {'OK' if analysis.data_ok else 'PROBLEMS'}; {ai_status}")
    if not analysis.data_ok:
        for p in analysis.data_problems:
            print(f"  - {p}")
    return 0 if analysis.data_ok else 2


def cmd_run(args, cfg, db):
    """Daily job: fetch the latest trading day, then write its note."""
    d = latest_trading_day(datetime.now(ZoneInfo(cfg.timezone)).date())
    status = fetch_day(db, cfg, d)
    print(f"fetch {d}: {status}")
    if status == "holiday":
        print("no trading file for today (holiday or not yet published); no note written")
        return 0
    if status == "error":
        print("fetch failed; no note written", file=sys.stderr)
        return 1
    args.date, args.no_ai = d, args.no_ai
    return cmd_note(args, cfg, db)


def cmd_status(args, cfg, db):
    c = db.counts()
    print(f"rows={c['rows']} days={c['days']} first={c['first']} last={c['last']}")
    print("watchlist:", ", ".join(s.symbol for s in cfg.watchlist))
    print("AI:", "key set" if cfg.gemini_api_key else "no GEMINI_API_KEY", "/", "enabled" if cfg.ai_enabled else "disabled", "/", cfg.ai_model)
    for r in db.conn.execute("SELECT * FROM fetch_log ORDER BY date DESC LIMIT 5"):
        print(f"  {r['date']} {r['status']:8} {r['rows']:5} {r['message'][:70]}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="stockbot", description="Stock Guru - PSX decision-support agent (analysis only)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="download one trading day (default: latest weekday)")
    s.add_argument("--date", type=_date)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("backfill", help="download a date range")
    s.add_argument("--start", type=_date, required=True)
    s.add_argument("--end", type=_date)
    s.set_defaults(fn=cmd_backfill)

    s = sub.add_parser("note", help="write the daily note for a date already in the database")
    s.add_argument("--date", type=_date)
    s.add_argument("--no-ai", action="store_true")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("run", help="daily job: fetch latest day + write note")
    s.add_argument("--no-ai", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("status", help="database and config summary")
    s.set_defaults(fn=cmd_status)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config.load()
    db = DB(cfg.db_path)
    try:
        return args.fn(args, cfg, db)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
