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
    }
