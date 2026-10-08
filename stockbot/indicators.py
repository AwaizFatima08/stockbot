"""Transparent, textbook indicator maths on plain Python lists.
No black boxes (design doc section 2). All functions return None when there
is not enough history, so callers must say so instead of guessing."""
from __future__ import annotations


def sma(values: list[float], n: int) -> float | None:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n


def sma_series(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= n:
            running -= values[i - n]
        out.append(running / n if i >= n - 1 else None)
    return out


def rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder's RSI. Needs at least period+1 closes."""
    if period <= 0 or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes[:-1], closes[1:]):
        ch = cur - prev
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def pct_change(values: list[float], n: int) -> float | None:
    """Percent change from the value n observations ago to the last value."""
    if n <= 0 or len(values) < n + 1 or values[-n - 1] == 0:
        return None
    return (values[-1] / values[-n - 1] - 1.0) * 100.0


def highest(values: list[float], n: int) -> float | None:
    if not values:
        return None
    return max(values[-n:])


def lowest(values: list[float], n: int) -> float | None:
    if not values:
        return None
    return min(values[-n:])


def average(values: list[float], n: int) -> float | None:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n
