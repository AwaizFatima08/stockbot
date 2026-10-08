"""Next-week view: not a prediction. Three things only (design 4.4):
1. what the current setups have historically been followed by (base rates, 5 sessions),
2. the typical size of a weekly move for this stock (historical distribution),
3. conditional levels: what would confirm or invalidate the current picture."""
from __future__ import annotations

import statistics

from stockbot.analysis.daily import SymbolSnapshot
from stockbot.storage.db import DB


def weekly_distribution(db: DB, symbol: str, as_of: str, years: int = 3) -> dict | None:
    rows = db.history(symbol, as_of, years * 250 + 5)
    closes = [float(r["close"]) for r in rows if r["close"] and r["close"] > 0]
    if len(closes) < 60:
        return None
    rets = [(closes[i + 5] / closes[i] - 1.0) * 100.0 for i in range(len(closes) - 5) if abs(closes[i + 5] / closes[i] - 1.0) < 0.6]
    if not rets:
        return None
    rets.sort()
    q = statistics.quantiles(rets, n=20)  # 5% steps
    return {
        "n_weeks": len(rets),
        "median_pct": statistics.median(rets),
        "p10_pct": q[1], "p25_pct": q[4], "p75_pct": q[14], "p90_pct": q[17],
        "up_weeks_pct": 100.0 * sum(1 for r in rets if r > 0) / len(rets),
    }


def levels(s: SymbolSnapshot, hist_rows) -> list[dict]:
    """Reference levels with what crossing them would mean, as plain conditions."""
    out = []
    if not s.close:
        return out
    highs = [float(r["high"]) for r in hist_rows[-20:] if r["high"]]
    lows = [float(r["low"]) for r in hist_rows[-20:] if r["low"] and r["low"] > 0]
    def pct(level): return (level / s.close - 1.0) * 100.0
    if s.sma_short:
        above = s.close > s.sma_short
        out.append({"label": f"20-day average", "level": s.sma_short, "distance_pct": pct(s.sma_short),
                    "meaning": ("A close below it would end the short-term uptrend reading." if above else "A close above it would end the short-term downtrend reading.")})
    if s.sma_long:
        above = s.close > s.sma_long
        out.append({"label": f"50-day average", "level": s.sma_long, "distance_pct": pct(s.sma_long),
                    "meaning": ("A close below it would weaken the medium-term picture." if above else "A close above it would improve the medium-term picture.")})
    if highs:
        h = max(highs)
        out.append({"label": "20-day high", "level": h, "distance_pct": pct(h), "meaning": "A close above it would be a new short-term high (breakout condition)."})
    if lows:
        l = min(lows)
        out.append({"label": "20-day low", "level": l, "distance_pct": pct(l), "meaning": "A close below it would be a new short-term low (breakdown condition)."})
    if s.high_52w:
        out.append({"label": "52-week high", "level": s.high_52w, "distance_pct": pct(s.high_52w), "meaning": "Closing above it would put the stock at a 1-year high."})
    if s.low_52w:
        out.append({"label": "52-week low", "level": s.low_52w, "distance_pct": pct(s.low_52w), "meaning": "Closing below it would put the stock at a 1-year low."})
    out.sort(key=lambda x: x["level"], reverse=True)
    return out


def build(db: DB, s: SymbolSnapshot, as_of: str) -> dict:
    hist = db.history(s.symbol, as_of, 60)
    dist = weekly_distribution(db, s.symbol, as_of)
    out = {
        "symbol": s.symbol,
        "trend": s.trend,
        "setups": [{"label": b["label"], "bias": b["bias"], "symbol_base_rate_5d": b["symbol"][0] if b["symbol"] else None,
                    "universe_base_rate_5d": b["universe"][0] if b["universe"] else None} for b in s.base_rates],
        "weekly_distribution": dist,
        "levels": levels(s, hist),
        "sentences": [],
    }
    sent = out["sentences"]
    if dist:
        sent.append(f"Over the last 3 years a typical week moved {dist['median_pct']:+.1f}% (middle half between {dist['p25_pct']:+.1f}% and {dist['p75_pct']:+.1f}%; 1 week in 10 worse than {dist['p10_pct']:+.1f}%, 1 in 10 better than {dist['p90_pct']:+.1f}%). {dist['up_weeks_pct']:.0f}% of weeks ended higher.")
    if s.trend == "uptrend":
        sent.append("The current reading is an uptrend (price above both averages).")
    elif s.trend == "downtrend":
        sent.append("The current reading is a downtrend (price below both averages).")
    else:
        sent.append("The current trend reading is mixed.")
    for st in out["setups"]:
        if st["symbol_base_rate_5d"]:
            sent.append(f"{st['label']} fired. {st['symbol_base_rate_5d']}.")
        if st["universe_base_rate_5d"]:
            sent.append(f"Across the market: {st['universe_base_rate_5d']}.")
    if not out["setups"]:
        sent.append("No defined setup fired today, so there is no setup-specific base rate to report.")
    near = [l for l in out["levels"] if abs(l["distance_pct"]) <= 5]
    for l in near[:3]:
        sent.append(f"{l['label']} at {l['level']:,.2f} ({l['distance_pct']:+.1f}% away): {l['meaning']}")
    sent.append("This is a description of history and of conditions, not a forecast.")
    return out
