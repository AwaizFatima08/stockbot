"""Setup definitions shared by the base-rate engine and the self-scoring log.

A setup is a condition that is true on a given session for a given stock.
They are deliberately simple and transparent. Adding one is a design
change, not a silent addition."""
from __future__ import annotations

from dataclasses import dataclass

from stockbot import indicators as ind
from stockbot.analysis import patterns as pat

YEAR = 250


@dataclass(frozen=True)
class Setup:
    key: str
    label: str
    bias: str  # the conventional reading, used only for wording and scoring direction


SETUPS: dict[str, Setup] = {s.key: s for s in [
    Setup("rsi_oversold_entry", "RSI14 drops below 30", "bullish"),
    Setup("rsi_overbought_entry", "RSI14 rises above 70", "bearish"),
    Setup("cross_above_sma20", "Close crosses above 20-day average", "bullish"),
    Setup("cross_below_sma20", "Close crosses below 20-day average", "bearish"),
    Setup("golden_cross", "20-day average crosses above 50-day average", "bullish"),
    Setup("death_cross", "20-day average crosses below 50-day average", "bearish"),
    Setup("volume_spike_up", "Up day on 2x+ average volume", "bullish"),
    Setup("volume_spike_down", "Down day on 2x+ average volume", "bearish"),
    Setup("new_52w_high", "Close at a 52-week high", "bullish"),
    Setup("new_52w_low", "Close at a 52-week low", "bearish"),
    Setup("hammer", "Hammer candle after a decline", "bullish"),
    Setup("shooting_star", "Shooting star after an advance", "bearish"),
    Setup("bullish_engulfing", "Bullish engulfing candle", "bullish"),
    Setup("bearish_engulfing", "Bearish engulfing candle", "bearish"),
]}

PATTERN_SETUPS = {"hammer", "shooting_star", "bullish_engulfing", "bearish_engulfing"}


@dataclass
class Series:
    """Per-stock history in column form plus derived series."""
    dates: list[str]
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]
    sma_s: list[float | None]
    sma_l: list[float | None]
    rsi: list[float | None]
    avg_vol: list[float | None]
    hi_52: list[float | None]
    lo_52: list[float | None]


def build_series(rows, sma_short=20, sma_long=50, rsi_period=14, vol_period=20) -> Series:
    dates = [r["date"] for r in rows]
    opens = [float(r["open"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    vols = [float(r["volume"]) for r in rows]
    # average volume of the PREVIOUS vol_period sessions (exclude today)
    av = ind.sma_series(vols, vol_period)
    avg_vol: list[float | None] = [None] + av[:-1]
    return Series(
        dates, opens, highs, lows, closes, vols,
        ind.sma_series(closes, sma_short), ind.sma_series(closes, sma_long),
        ind.rsi_series(closes, rsi_period), avg_vol,
        ind.rolling_max(closes, YEAR), ind.rolling_min(closes, YEAR),
    )


def setups_at(s: Series, i: int) -> list[str]:
    """Setup keys that fire on session index i."""
    if i < 1 or s.closes[i] <= 0 or s.closes[i - 1] <= 0:
        return []
    out: list[str] = []
    c, pc = s.closes[i], s.closes[i - 1]
    r, pr = s.rsi[i], s.rsi[i - 1]
    if r is not None and pr is not None:
        if r < 30 <= pr:
            out.append("rsi_oversold_entry")
        if r > 70 >= pr:
            out.append("rsi_overbought_entry")
    ss, pss = s.sma_s[i], s.sma_s[i - 1]
    if ss is not None and pss is not None:
        if c > ss and pc <= pss:
            out.append("cross_above_sma20")
        if c < ss and pc >= pss:
            out.append("cross_below_sma20")
    sl, psl = s.sma_l[i], s.sma_l[i - 1]
    if ss is not None and sl is not None and pss is not None and psl is not None:
        if ss > sl and pss <= psl:
            out.append("golden_cross")
        if ss < sl and pss >= psl:
            out.append("death_cross")
    av = s.avg_vol[i]
    if av and s.volumes[i] >= 2.0 * av:
        out.append("volume_spike_up" if c > pc else "volume_spike_down" if c < pc else "")
    if s.hi_52[i] is not None and c >= s.hi_52[i] and i >= YEAR:
        out.append("new_52w_high")
    if s.lo_52[i] is not None and c <= s.lo_52[i] and i >= YEAR:
        out.append("new_52w_low")
    # candlestick patterns (need a few candles of context)
    lo = max(0, i - 25)
    candles = [pat.Candle(s.opens[k], s.highs[k], s.lows[k], s.closes[k]) for k in range(lo, i + 1)]
    for h in pat.detect(candles, pat.average_range(candles)):
        if h.name in PATTERN_SETUPS:
            out.append(h.name)
    return [k for k in out if k]
