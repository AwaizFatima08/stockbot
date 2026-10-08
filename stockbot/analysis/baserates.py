"""Historical base rates - the forecast substitute (design 4.3, Decided).

"When this setup occurred historically, price rose over the next N sessions
X% of the time; worst -Y%, best +Z%." Computed per stock from its own
history and across a liquid universe (top-N stocks by traded value) so
rare setups still have a sample. Sample sizes are always shown."""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path

from stockbot.analysis import setups as su
from stockbot.config import Settings
from stockbot.storage.db import DB

HORIZONS = (5, 10, 20)
# PSX enforces daily price limits (about 10%). A session-to-session move beyond this
# is a corporate action (split, rights adjustment) or a data error, and any forward
# window containing one is discarded rather than counted as a return.
MAX_DAILY_MOVE = 0.30
MAX_CALENDAR_GAP = 3.5  # calendar days per trading session allowed inside a window (catches holes in history)


@dataclass
class BaseRate:
    setup: str
    scope: str            # "SYM" or "universe"
    n: int
    horizon: int
    up_pct: float | None  # share of occurrences with a positive forward return
    median: float | None
    worst: float | None
    best: float | None

    def text(self) -> str:
        if self.n == 0 or self.up_pct is None:
            return f"{self.scope}: no past occurrences"
        return (f"{self.scope}: {self.n} past occurrences; price was higher {self.horizon} sessions later "
                f"{self.up_pct:.0f}% of the time (median {self.median:+.1f}%, worst {self.worst:+.1f}%, best {self.best:+.1f}%)")


def _window_ok(series: su.Series, i: int, j: int) -> bool:
    from datetime import date
    if series.closes[i] <= 0:
        return False
    d0, d1 = date.fromisoformat(series.dates[i]), date.fromisoformat(series.dates[j])
    if (d1 - d0).days > MAX_CALENDAR_GAP * (j - i) + 10:
        return False
    for k in range(i + 1, j + 1):
        a, b = series.closes[k - 1], series.closes[k]
        if a <= 0 or b <= 0 or abs(b / a - 1.0) > MAX_DAILY_MOVE:
            return False
    return True


def forward_returns(series: su.Series, i: int) -> dict[int, float | None]:
    out = {}
    for h in HORIZONS:
        j = i + h
        out[h] = (series.closes[j] / series.closes[i] - 1.0) * 100.0 if j < len(series.closes) and _window_ok(series, i, j) else None
    return out


def occurrences(series: su.Series) -> dict[str, list[dict[int, float | None]]]:
    """setup -> list of forward-return dicts, one per historical occurrence."""
    occ: dict[str, list] = {k: [] for k in su.SETUPS}
    for i in range(1, len(series.closes)):
        keys = su.setups_at(series, i)
        if keys:
            fr = forward_returns(series, i)
            for k in keys:
                occ[k].append(fr)
    return occ


def summarise(setup: str, scope: str, occ: list[dict[int, float | None]]) -> list[BaseRate]:
    out = []
    for h in HORIZONS:
        vals = [o[h] for o in occ if o[h] is not None]
        if not vals:
            out.append(BaseRate(setup, scope, 0, h, None, None, None, None))
            continue
        out.append(BaseRate(setup, scope, len(vals), h,
                            100.0 * sum(1 for v in vals if v > 0) / len(vals),
                            statistics.median(vals), min(vals), max(vals)))
    return out


def liquid_universe(db: DB, as_of: str, n: int = 100, lookback: int = 60) -> list[str]:
    """Top-n symbols by average traded value (close*volume) over the last `lookback` sessions."""
    dates = [d for d in db.trading_dates() if d <= as_of][-lookback:]
    if not dates:
        return []
    rows = db.conn.execute(
        "SELECT symbol, AVG(close*volume) AS tv, AVG(close) AS px FROM eod WHERE date>=? AND date<=? AND volume>0 "
        "AND sector_code GLOB '08[0-9][0-9]' GROUP BY symbol HAVING px >= 5 ORDER BY tv DESC LIMIT ?", (dates[0], dates[-1], n * 2)).fetchall()
    all_syms = {r["symbol"] for r in db.conn.execute("SELECT DISTINCT symbol FROM eod")}
    out = []
    for r in rows:
        sym = r["symbol"]
        # rights / preference instruments: e.g. XYZR, XYZR1, XYZPPR when the parent XYZ is listed
        m = re.match(r"^([A-Z]+?)(PP)?R\d?$", sym)
        if m and m.group(1) in all_syms:
            continue
        if re.match(r"^P\d{2}[A-Z]{3}\d{6}$", sym):  # government securities (GIS, PIB, T-bill style symbols)
            continue
        out.append(sym)
        if len(out) >= n:
            break
    return out


def universe_stats(db: DB, cfg: Settings, as_of: str, cache_dir: Path, n: int = 100) -> dict[str, list[dict]]:
    """Base rates per setup across the liquid universe; cached per as_of date."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"universe-{as_of}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    pooled: dict[str, list] = {k: [] for k in su.SETUPS}
    syms = liquid_universe(db, as_of, n)
    for sym in syms:
        rows = db.history(sym, as_of, 10_000)
        if len(rows) < 60:
            continue
        s = su.build_series(rows, cfg.sma_short, cfg.sma_long, cfg.rsi_period, cfg.volume_avg_period)
        for k, lst in occurrences(s).items():
            pooled[k].extend(lst)
    result = {k: [asdict(b) for b in summarise(k, f"{len(syms)} liquid stocks", lst)] for k, lst in pooled.items()}
    cache.write_text(json.dumps(result))
    return result


def symbol_stats(series: su.Series, symbol: str) -> dict[str, list[BaseRate]]:
    return {k: summarise(k, symbol, lst) for k, lst in occurrences(series).items()}
