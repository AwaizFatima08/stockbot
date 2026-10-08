"""Candlestick patterns from pure OHLC arithmetic (design doc 4.3: no image
recognition). Each hit carries a plain-language line that says what the
pattern conventionally describes; none of them is a signal on its own."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def green(self) -> bool:
        return self.close > self.open

    @property
    def red(self) -> bool:
        return self.close < self.open


@dataclass(frozen=True)
class PatternHit:
    name: str          # machine key, e.g. "bullish_engulfing"
    label: str         # human label
    bias: str          # "bullish" | "bearish" | "neutral"
    text: str          # one plain-language line


DESCRIPTIONS = {
    "doji": ("Doji", "neutral", "Open and close were almost equal (a doji), which conventionally describes indecision between buyers and sellers."),
    "hammer": ("Hammer", "bullish", "A hammer after a decline: sellers pushed the price well down during the session but it closed near the top of its range. Conventionally read as a possible pause in the decline, needing confirmation from the next session."),
    "shooting_star": ("Shooting star", "bearish", "A shooting star after an advance: buyers pushed the price well up during the session but it closed near the bottom of its range. Conventionally read as a possible pause in the advance, needing confirmation."),
    "bullish_engulfing": ("Bullish engulfing", "bullish", "A bullish engulfing candle: today's up-body completely covered yesterday's down-body. Conventionally read as buyers overpowering the previous session's sellers."),
    "bearish_engulfing": ("Bearish engulfing", "bearish", "A bearish engulfing candle: today's down-body completely covered yesterday's up-body. Conventionally read as sellers overpowering the previous session's buyers."),
    "gap_up": ("Gap up", "bullish", "The session opened above the previous session's high (a gap up)."),
    "gap_down": ("Gap down", "bearish", "The session opened below the previous session's low (a gap down)."),
    "marubozu_up": ("Strong up candle", "bullish", "A long up candle with almost no shadows: buyers were in control from open to close."),
    "marubozu_down": ("Strong down candle", "bearish", "A long down candle with almost no shadows: sellers were in control from open to close."),
}


def _hit(name: str) -> PatternHit:
    label, bias, text = DESCRIPTIONS[name]
    return PatternHit(name, label, bias, text)


def _valid(c: Candle) -> bool:
    return c.range > 0 and c.open > 0 and c.close > 0 and c.high >= c.low


def _trend_before(closes: list[float], lookback: int = 5) -> str:
    """'down' | 'up' | 'flat' over the candles before the last one."""
    if len(closes) < lookback + 1:
        return "flat"
    prior = closes[-lookback - 1 : -1]
    first, last = prior[0], prior[-1]
    if first <= 0:
        return "flat"
    ch = last / first - 1.0
    return "down" if ch < -0.02 else "up" if ch > 0.02 else "flat"


def detect(candles: list[Candle], avg_range: float | None = None) -> list[PatternHit]:
    """Patterns completed by the LAST candle in the list."""
    if not candles:
        return []
    c = candles[-1]
    if not _valid(c):
        return []
    hits: list[PatternHit] = []
    closes = [x.close for x in candles]
    trend = _trend_before(closes)
    rng = c.range
    body = c.body
    avg_range = avg_range or rng

    if body <= 0.1 * rng:
        hits.append(_hit("doji"))
    # Hammer / shooting star need a meaningful range (not a tiny candle)
    # Hammer: long lower shadow (>= 60% of the range), little or no upper shadow, after a decline.
    # Shooting star: the mirror image after an advance. Body colour is not required.
    if rng >= 0.5 * avg_range and body > 0:
        if c.lower_shadow >= 0.6 * rng and c.upper_shadow <= 0.15 * rng and trend == "down":
            hits.append(_hit("hammer"))
        if c.upper_shadow >= 0.6 * rng and c.lower_shadow <= 0.15 * rng and trend == "up":
            hits.append(_hit("shooting_star"))
    if body >= 0.9 * rng and rng >= 1.2 * avg_range:
        hits.append(_hit("marubozu_up" if c.green else "marubozu_down"))

    if len(candles) >= 2:
        p = candles[-2]
        if _valid(p):
            if p.red and c.green and c.open <= p.close and c.close >= p.open and c.body > p.body:
                hits.append(_hit("bullish_engulfing"))
            if p.green and c.red and c.open >= p.close and c.close <= p.open and c.body > p.body:
                hits.append(_hit("bearish_engulfing"))
            if c.open > p.high:
                hits.append(_hit("gap_up"))
            elif c.open < p.low:
                hits.append(_hit("gap_down"))
    return hits


def average_range(candles: list[Candle], n: int = 20) -> float | None:
    recent = [x.range for x in candles[-n - 1 : -1] if _valid(x)]
    return sum(recent) / len(recent) if recent else None
