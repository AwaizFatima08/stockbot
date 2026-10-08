"""Corporate-action facts derivable from data we already hold.

The daily closing file appends XD (ex-dividend), XB (ex-bonus) and XR
(ex-right) to the company name on the ex-date and for a few sessions after.
That gives ex-dates and how often a company has paid, but not the amount."""
from __future__ import annotations

import re

from stockbot.storage.db import DB

_MARK = re.compile(r"(XD|XB|XR)+$")


def ex_events(db: DB, symbol: str) -> list[dict]:
    """[{date, kinds:['XD',...]}] - first session of each marked run (the ex-date)."""
    rows = db.conn.execute("SELECT date, name FROM eod WHERE symbol=? ORDER BY date", (symbol.upper(),)).fetchall()
    events, prev_kinds = [], set()
    for r in rows:
        m = _MARK.search(r["name"] or "")
        kinds = set(re.findall(r"XD|XB|XR", m.group(0))) if m else set()
        new = kinds - prev_kinds
        if new:
            events.append({"date": r["date"], "kinds": sorted(new)})
        prev_kinds = kinds
    return events


def payout_facts(db: DB, symbol: str, as_of: str) -> dict:
    """Declared payouts from the payouts table (ksestocks mirror of PSX notices)."""
    rows = [dict(r) for r in db.payouts(symbol)]
    dated = [r for r in rows if r["bc_from"]]
    past = [r for r in dated if r["bc_from"] <= as_of]
    upcoming = [r for r in dated if r["bc_from"] > as_of]
    undated = [r for r in rows if not r["bc_from"]]
    last_div = next((r for r in past if r["dividend_per_share"]), None)
    year_ago = f"{int(as_of[:4]) - 1}{as_of[4:]}"
    divs_12m = [r["dividend_per_share"] for r in past if r["dividend_per_share"] and r["bc_from"] > year_ago]
    def slim(r):
        return {k: r[k] for k in ("bc_from", "bc_to", "payout_text", "dividend_pct", "dividend_per_share", "bonus_pct", "right_pct", "face_value")}
    return {
        "last_dividend": slim(last_div) if last_div else None,
        "upcoming": [slim(r) for r in sorted(upcoming, key=lambda r: r["bc_from"])][:3],
        "announced_undated": [slim(r) for r in undated][:3],
        "dividends_per_share_12m": sum(divs_12m) if divs_12m else None,
        "n_dividends_12m_tracked": len(divs_12m),
        "payout_history": [slim(r) for r in past][:12],
        "payout_source": "ksestocks.com (mirror of PSX notices); tracked since 2026-10-08",
    }


def summary(db: DB, symbol: str, as_of: str) -> dict:
    ev = [e for e in ex_events(db, symbol) if e["date"] <= as_of]
    divs = [e for e in ev if "XD" in e["kinds"]]
    bonus = [e for e in ev if "XB" in e["kinds"]]
    rights = [e for e in ev if "XR" in e["kinds"]]
    year_ago = f"{int(as_of[:4]) - 1}{as_of[4:]}"
    three_ago = f"{int(as_of[:4]) - 3}{as_of[4:]}"
    return {
        "last_ex_dividend": divs[-1]["date"] if divs else None,
        "ex_dividends_last_12m": sum(1 for e in divs if e["date"] > year_ago),
        "ex_dividends_last_3y": sum(1 for e in divs if e["date"] > three_ago),
        "last_ex_bonus": bonus[-1]["date"] if bonus else None,
        "last_ex_right": rights[-1]["date"] if rights else None,
        "ex_dates": [e for e in ev][-12:],
        **payout_facts(db, symbol, as_of),
    }
