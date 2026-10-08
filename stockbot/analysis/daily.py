"""Per-symbol end-of-day facts and plain-language sentences.

Deterministic rules only. Every sentence describes evidence; none of them
tells anyone to buy, sell or hold (design doc section 2). The optional AI
narrative (stockbot.ai) only rewords what is produced here."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date

from stockbot import indicators as ind
from stockbot.config import Settings, Stock
from stockbot.storage.db import DB

# Approximate trading-day counts used for return windows.
WEEK, MONTH, QUARTER, YEAR = 5, 21, 63, 250


@dataclass
class SymbolSnapshot:
    symbol: str
    name: str
    sector: str
    date: str | None = None
    ok: bool = False
    problems: list[str] = field(default_factory=list)
    close: float | None = None
    prev_close: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    avg_volume: float | None = None
    volume_ratio: float | None = None
    sma_short: float | None = None
    sma_long: float | None = None
    rsi: float | None = None
    ret_1w: float | None = None
    ret_1m: float | None = None
    ret_3m: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    off_high_pct: float | None = None
    above_low_pct: float | None = None
    history_days: int = 0
    sentences: list[str] = field(default_factory=list)


@dataclass
class DailyAnalysis:
    as_of: str
    generated_for: str
    data_ok: bool
    data_problems: list[str]
    snapshots: list[SymbolSnapshot]

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of,
            "generated_for": self.generated_for,
            "data_ok": self.data_ok,
            "data_problems": self.data_problems,
            "snapshots": [asdict(s) for s in self.snapshots],
        }


def _fmt(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:,.{nd}f}"


def _sentences(s: SymbolSnapshot, cfg: Settings) -> list[str]:
    out: list[str] = []
    if s.close is None:
        return out

    # 1. Day move and volume
    if s.change_pct is not None:
        direction = "rose" if s.change_pct > 0 else "fell" if s.change_pct < 0 else "was unchanged"
        if s.change_pct == 0:
            out.append(f"{s.symbol} closed unchanged at {_fmt(s.close)}.")
        else:
            out.append(f"{s.symbol} {direction} {abs(s.change_pct):.2f}% to close at {_fmt(s.close)} (previous close {_fmt(s.prev_close)}).")
    if s.volume_ratio is not None:
        if s.volume_ratio >= 2.0:
            out.append(f"Volume was {s.volume_ratio:.1f}x its {cfg.volume_avg_period}-day average, which is unusually heavy.")
        elif s.volume_ratio >= 1.3:
            out.append(f"Volume was above average ({s.volume_ratio:.1f}x the {cfg.volume_avg_period}-day average).")
        elif s.volume_ratio <= 0.5:
            out.append(f"Volume was light, about {s.volume_ratio:.1f}x the {cfg.volume_avg_period}-day average.")
        else:
            out.append(f"Volume was close to its {cfg.volume_avg_period}-day average ({s.volume_ratio:.1f}x).")
    elif s.volume == 0:
        out.append("No shares traded on this date.")

    # 2. Trend vs moving averages
    if s.sma_short is not None and s.sma_long is not None:
        above_s = s.close > s.sma_short
        above_l = s.close > s.sma_long
        rel = "above" if s.sma_short > s.sma_long else "below"
        if above_s and above_l and rel == "above":
            trend = "The price is above both moving averages and the shorter average is above the longer one, the configuration usually described as an uptrend."
        elif not above_s and not above_l and rel == "below":
            trend = "The price is below both moving averages and the shorter average is below the longer one, the configuration usually described as a downtrend."
        else:
            trend = "The price sits between or around its moving averages, so the trend picture is mixed."
        out.append(
            f"{trend} ({cfg.sma_short}-day average {_fmt(s.sma_short)}, {cfg.sma_long}-day average {_fmt(s.sma_long)}.)"
        )
    elif s.sma_short is not None:
        pos = "above" if s.close > s.sma_short else "below"
        out.append(f"The price is {pos} its {cfg.sma_short}-day average ({_fmt(s.sma_short)}); not enough history yet for the {cfg.sma_long}-day average.")

    # 3. RSI
    if s.rsi is not None:
        if s.rsi >= 70:
            out.append(f"RSI({cfg.rsi_period}) is {s.rsi:.0f}, in the zone conventionally labelled overbought. Historically this describes a stretched move, not a turning point by itself.")
        elif s.rsi <= 30:
            out.append(f"RSI({cfg.rsi_period}) is {s.rsi:.0f}, in the zone conventionally labelled oversold. Historically this describes a stretched decline, not a turning point by itself.")
        else:
            out.append(f"RSI({cfg.rsi_period}) is {s.rsi:.0f}, in the neutral range.")

    # 4. Returns and 52-week position
    rets = [(n, v) for n, v in (("1 week", s.ret_1w), ("1 month", s.ret_1m), ("3 months", s.ret_3m)) if v is not None]
    if rets:
        out.append("Returns: " + ", ".join(f"{n} {v:+.1f}%" for n, v in rets) + ".")
    if s.off_high_pct is not None and s.above_low_pct is not None:
        out.append(f"It is {s.off_high_pct:.1f}% below its 52-week high ({_fmt(s.high_52w)}) and {s.above_low_pct:.1f}% above its 52-week low ({_fmt(s.low_52w)}).")
    return out


def analyse_symbol(db: DB, stock: Stock, as_of: str, cfg: Settings) -> SymbolSnapshot:
    s = SymbolSnapshot(symbol=stock.symbol, name=stock.name, sector=stock.sector)
    hist = db.history(stock.symbol, as_of, cfg.history_days)
    s.history_days = len(hist)
    if not hist:
        s.problems.append("no price history in database")
        return s
    last = hist[-1]
    s.date = last["date"]
    if last["date"] != as_of:
        s.problems.append(f"no row for {as_of}; latest available is {last['date']}")
        return s

    closes = [float(r["close"]) for r in hist]
    vols = [float(r["volume"]) for r in hist]
    s.close, s.open, s.high, s.low, s.volume = last["close"], last["open"], last["high"], last["low"], int(last["volume"])
    s.prev_close = float(last["ldcp"]) if last["ldcp"] else (closes[-2] if len(closes) > 1 else None)
    if s.prev_close:
        s.change_pct = (s.close / s.prev_close - 1.0) * 100.0
    s.avg_volume = ind.average(vols[:-1], cfg.volume_avg_period)
    if s.avg_volume:
        s.volume_ratio = s.volume / s.avg_volume
    s.sma_short = ind.sma(closes, cfg.sma_short)
    s.sma_long = ind.sma(closes, cfg.sma_long)
    s.rsi = ind.rsi(closes, cfg.rsi_period)
    s.ret_1w = ind.pct_change(closes, WEEK)
    s.ret_1m = ind.pct_change(closes, MONTH)
    s.ret_3m = ind.pct_change(closes, QUARTER)
    if len(closes) >= YEAR:
        highs = [float(r["high"]) or float(r["close"]) for r in hist]
        lows = [float(r["low"]) or float(r["close"]) for r in hist if (float(r["low"]) or float(r["close"])) > 0]
        s.high_52w = ind.highest(highs, YEAR)
        s.low_52w = ind.lowest(lows, YEAR)
        if s.high_52w:
            s.off_high_pct = (1.0 - s.close / s.high_52w) * 100.0
        if s.low_52w:
            s.above_low_pct = (s.close / s.low_52w - 1.0) * 100.0
    if s.close <= 0:
        s.problems.append("close price is zero")
    if s.sma_long is None:
        s.problems.append(f"only {len(closes)} days of history; {cfg.sma_long}-day average not available")
    s.ok = s.close > 0
    s.sentences = _sentences(s, cfg)
    return s


def build(db: DB, cfg: Settings, as_of: date) -> DailyAnalysis:
    as_of_iso = as_of.isoformat()
    problems: list[str] = []
    latest = db.latest_date()
    if latest is None:
        problems.append("database is empty")
    elif latest != as_of_iso:
        problems.append(f"no market data for {as_of_iso}; latest stored day is {latest}")
    snaps = [analyse_symbol(db, st, as_of_iso, cfg) for st in cfg.watchlist]
    for s in snaps:
        for p in s.problems:
            problems.append(f"{s.symbol}: {p}")
    return DailyAnalysis(
        as_of=as_of_iso,
        generated_for=as_of_iso,
        data_ok=(latest == as_of_iso) and all(s.ok for s in snaps),
        data_problems=problems,
        snapshots=snaps,
    )
