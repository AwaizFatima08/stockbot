"""Command line: python -m stockbot <command>"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from stockbot import config, export, scoring, server
from stockbot.cloud import firebase as cloud
from stockbot.ai import gemini
from stockbot.analysis import daily as daily_analysis, setups as su
from stockbot.fetch import backfill, fetch_day, latest_trading_day, update_companies, update_payouts
from stockbot.reports import charts, daily_note, email as email_report, pdf as pdf_report
from stockbot.storage.db import DB


def _charts(db, cfg, analysis) -> dict:
    out = {}
    if not cfg.charts_enabled:
        return out
    for s in analysis.snapshots:
        if not s.ok:
            continue
        hist = db.history(s.symbol, analysis.as_of, cfg.history_days)
        series = su.build_series(hist, cfg.sma_short, cfg.sma_long, cfg.rsi_period, cfg.volume_avg_period)
        hits = [__import__("stockbot.analysis.patterns", fromlist=["PatternHit"]).PatternHit(**p) for p in s.patterns]
        levels = {k: v for k, v in {"20d high": max(series.highs[-20:]), "20d low": min(x for x in series.lows[-20:] if x > 0),
                                    "52w high": s.high_52w, "52w low": s.low_52w}.items() if v}
        caption = s.sentences[2] if len(s.sentences) > 2 else (s.sentences[0] if s.sentences else "")
        path = cfg.reports_dir / "charts" / analysis.as_of / f"{s.symbol}.png"
        try:
            out[s.symbol] = charts.draw(series, s.symbol, s.name, path, cfg.chart_sessions, hits, levels, caption,
                                        (f"SMA{cfg.sma_short}", f"SMA{cfg.sma_long}"))
        except Exception as e:  # noqa: BLE001
            logging.getLogger(__name__).warning("chart %s failed: %s", s.symbol, e)
    return out


def _date(s: str) -> date:
    return date.fromisoformat(s)


def cmd_fetch(args, cfg, db):
    d = args.date or latest_trading_day(datetime.now(ZoneInfo(cfg.timezone)).date())
    status = fetch_day(db, cfg, d, force=args.force)
    print(f"{d}: {status}")
    if status in ("ok", "cached") and not args.no_company:
        res = update_companies(db, cfg, d)
        print("company pages:", ", ".join(f"{k}={v}" for k, v in res.items()))
        print("payouts (ksestocks):", update_payouts(db, cfg, d))
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
    narrative, ai_status = (None, "AI narrative skipped (--no-ai)") if args.no_ai else gemini.narrate(analysis.ai_payload(), cfg)
    chart_paths = _charts(db, cfg, analysis)
    md, snap = daily_note.write(analysis, cfg, narrative, ai_status, chart_paths)
    for s in analysis.snapshots:
        if s.ok and s.close:
            scoring.log_signals(db, analysis.as_of, s.symbol, s.close, s.trend, s.setups)
    pdf_path = pdf_report.write(md.read_text(encoding="utf-8"), cfg.reports_dir / "daily" / f"{analysis.as_of}.pdf", chart_paths)
    export.build(db, cfg, d, analysis, chart_paths)
    try:
        print("cloud:", cloud.publish(cfg.root, cfg.data_dir / "app"))
    except cloud.CloudDisabled as e:
        print(f"cloud: {e}")
    except Exception as e:  # noqa: BLE001 - cloud is an extra, never block the note
        print(f"cloud publish failed: {type(e).__name__}: {e}")
    print(f"note: {md}\npdf: {pdf_path}\nsnapshot: {snap}\ncharts: {len(chart_paths)}\nstatus: {'OK' if analysis.data_ok else 'PROBLEMS'}; {ai_status}")
    if not analysis.data_ok:
        for p in analysis.data_problems:
            print(f"  - {p}")
    if getattr(args, "email", False):
        print(email_report.send(cfg.email, f"Stock Guru daily note {analysis.as_of}", md.read_text(encoding="utf-8"), [pdf_path]))
    return 0 if analysis.data_ok else 2


def cmd_export(args, cfg, db):
    d = args.date or (date.fromisoformat(db.latest_date()) if db.latest_date() else None)
    if d is None:
        print("database empty", file=sys.stderr)
        return 1
    charts_dir = cfg.reports_dir / "charts" / d.isoformat()
    charts = {p.stem: p for p in charts_dir.glob("*.png")} if charts_dir.exists() else {}
    out = export.build(db, cfg, d, None, charts)
    print(f"app bundle: {out}")
    return 0


def cmd_serve(args, cfg, db):
    db.close()
    server.serve(cfg.root, args.port)
    return 0


def cmd_publish(args, cfg, db):
    print(cloud.publish(cfg.root, cfg.data_dir / "app"))
    return 0


def cmd_allow_user(args, cfg, db):
    cloud.allow_user(cfg.root, args.email, args.role)
    print("allowed:", [u["email"] for u in cloud.list_users(cfg.root)])
    return 0


def cmd_cloud_poll(args, cfg, db):
    """Apply a pending watchlist request from the app (runs from a 5-minute timer)."""
    req = cloud.pending_request(cfg.root)
    if not req:
        print("no pending request")
        return 0
    syms = [str(s).strip().upper() for s in req.get("symbols", [])]
    symfile = cfg.data_dir / "app" / "symbols.json"
    known = {s["symbol"]: s for s in __import__("json").loads(symfile.read_text())["symbols"]} if symfile.exists() else {}
    bad = [s for s in syms if s not in known]
    if len(syms) != 10 or len(set(syms)) != 10 or bad:
        cloud.set_request_status(cfg.root, "rejected", f"need 10 distinct listed symbols; unknown: {bad}")
        print("rejected:", bad)
        return 0
    cloud.set_request_status(cfg.root, "working", "regenerating on the NAS")
    server._write_watchlist(cfg.root, syms, {s: known[s]["name"] for s in syms}, {s: known[s].get("sector_code", "") for s in syms})
    cfg2 = config.load(cfg.root)
    d = date.fromisoformat(db.latest_date())
    args.date, args.no_ai, args.email = d, True, False
    rc = cmd_note(args, cfg2, db)   # regenerates note, bundle and publishes to the cloud
    cloud.set_request_status(cfg.root, "done" if rc in (0, 2) else "failed", f"watchlist applied by {req.get('requested_by')}")
    print("applied:", syms)
    return 0


def cmd_scorecard(args, cfg, db):
    d = args.date or (date.fromisoformat(db.latest_date()) if db.latest_date() else None)
    if d is None:
        print("database empty", file=sys.stderr)
        return 1
    p = scoring.write_scorecard(db, cfg.reports_dir, d.isoformat())
    print(f"scorecard: {p}")
    return 0


def cmd_run(args, cfg, db):
    """Daily job: fetch the latest trading day, then write its note."""
    d = latest_trading_day(datetime.now(ZoneInfo(cfg.timezone)).date())
    status = fetch_day(db, cfg, d)
    print(f"fetch {d}: {status}")
    if status in ("ok", "cached"):
        update_companies(db, cfg, d)
        print("payouts (ksestocks):", update_payouts(db, cfg, d))
    if status == "holiday":
        print("no trading file for today (holiday or not yet published); no note written")
        return 0
    if status == "error":
        print("fetch failed; no note written", file=sys.stderr)
        return 1
    args.date, args.email = d, True
    rc = cmd_note(args, cfg, db)
    if d.weekday() == 4:  # Friday: weekly scorecard
        args.date = d
        cmd_scorecard(args, cfg, db)
    return rc


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
    s.add_argument("--no-company", action="store_true", help="skip the company pages")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("backfill", help="download a date range")
    s.add_argument("--start", type=_date, required=True)
    s.add_argument("--end", type=_date)
    s.set_defaults(fn=cmd_backfill)

    s = sub.add_parser("note", help="write the daily note (md + pdf + charts) for a date already in the database")
    s.add_argument("--date", type=_date)
    s.add_argument("--no-ai", action="store_true")
    s.add_argument("--email", action="store_true", help="also email the PDF if [email] is enabled")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("export", help="write the app bundle (data/app) for the latest date")
    s.add_argument("--date", type=_date)
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("serve", help="run the phone-app API server")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("publish", help="upload the app bundle to Firestore (cloud carrier)")
    s.set_defaults(fn=cmd_publish)

    s = sub.add_parser("allow-user", help="allow a Google account (email) to use the app via the cloud")
    s.add_argument("email")
    s.add_argument("--role", default="user")
    s.set_defaults(fn=cmd_allow_user)

    s = sub.add_parser("cloud-poll", help="apply a pending watchlist request from the cloud")
    s.set_defaults(fn=cmd_cloud_poll)

    s = sub.add_parser("scorecard", help="how past readings fared (self-scoring log)")
    s.add_argument("--date", type=_date)
    s.set_defaults(fn=cmd_scorecard)

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
