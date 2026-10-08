"""Self-scoring log (design 4.5, mandatory).

Every daily note logs, per watchlist stock: the trend label and the setups
that fired, with the close. Later, `scorecard` looks back and reports what
actually happened 5/10/20 sessions on. Scored honestly: a bullish setup
"hit" if the price was higher, a bearish one if lower; the trend label is
scored the same way. This measures the rules, not Homi."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stockbot.analysis import setups as su
from stockbot.storage.db import DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    date   TEXT NOT NULL,
    symbol TEXT NOT NULL,
    kind   TEXT NOT NULL,   -- 'setup' | 'trend'
    key    TEXT NOT NULL,   -- setup key, or 'uptrend' / 'downtrend' / 'mixed'
    bias   TEXT NOT NULL,   -- 'bullish' | 'bearish' | 'neutral'
    close  REAL NOT NULL,
    PRIMARY KEY (date, symbol, kind, key)
);
"""
HORIZONS = (5, 10, 20)


def ensure(db: DB) -> None:
    db.conn.executescript(SCHEMA)


def log_signals(db: DB, date_iso: str, symbol: str, close: float, trend_key: str, setup_keys: list[str]) -> None:
    ensure(db)
    bias = {"uptrend": "bullish", "downtrend": "bearish"}.get(trend_key, "neutral")
    rows = [(date_iso, symbol, "trend", trend_key, bias, close)]
    rows += [(date_iso, symbol, "setup", k, su.SETUPS[k].bias, close) for k in setup_keys if k in su.SETUPS]
    with db.conn:
        db.conn.executemany("INSERT OR REPLACE INTO signals VALUES (?,?,?,?,?,?)", rows)


@dataclass
class Outcome:
    date: str
    symbol: str
    kind: str
    key: str
    bias: str
    close: float
    returns: dict[int, float | None]  # horizon -> % change, None if not yet known

    def hit(self, h: int) -> bool | None:
        r = self.returns.get(h)
        if r is None or self.bias == "neutral":
            return None
        return r > 0 if self.bias == "bullish" else r < 0


def outcomes(db: DB, up_to: str) -> list[Outcome]:
    ensure(db)
    dates = db.trading_dates()
    idx = {d: i for i, d in enumerate(dates)}
    out = []
    for r in db.conn.execute("SELECT * FROM signals WHERE date<=? ORDER BY date, symbol", (up_to,)):
        i = idx.get(r["date"])
        rets: dict[int, float | None] = {}
        for h in HORIZONS:
            rets[h] = None
            if i is not None and i + h < len(dates) and dates[i + h] <= up_to:
                row = db.row(r["symbol"], dates[i + h])
                if row and row["close"] and r["close"]:
                    rets[h] = (row["close"] / r["close"] - 1.0) * 100.0
        out.append(Outcome(r["date"], r["symbol"], r["kind"], r["key"], r["bias"], r["close"], rets))
    return out


def scorecard_markdown(outs: list[Outcome], as_of: str) -> str:
    lines = [f"# Stock Guru scorecard - as of {as_of}", "",
             "How past daily-note readings fared. 'Hit' = price moved in the direction the reading conventionally describes "
             "(up for bullish, down for bearish). A hit rate near 50% means the reading carried no information.", ""]
    if not outs:
        return "\n".join(lines + ["No logged signals yet."])
    # aggregate by (kind, key)
    groups: dict[tuple[str, str], list[Outcome]] = {}
    for o in outs:
        groups.setdefault((o.kind, o.key), []).append(o)
    lines += ["| Reading | Logged | " + " | ".join(f"Hit rate {h}d (n)" for h in HORIZONS) + " | " + " | ".join(f"Median {h}d" for h in HORIZONS) + " |",
              "|---|---|" + "---|" * (2 * len(HORIZONS))]
    for (kind, key), lst in sorted(groups.items()):
        label = su.SETUPS[key].label if key in su.SETUPS else f"Trend: {key}"
        cells_hit, cells_med = [], []
        for h in HORIZONS:
            hits = [o.hit(h) for o in lst if o.hit(h) is not None]
            rets = sorted(o.returns[h] for o in lst if o.returns[h] is not None)
            cells_hit.append(f"{100*sum(hits)/len(hits):.0f}% ({len(hits)})" if hits else "- (0)")
            cells_med.append(f"{rets[len(rets)//2]:+.1f}%" if rets else "-")
        lines.append(f"| {label} | {len(lst)} | " + " | ".join(cells_hit) + " | " + " | ".join(cells_med) + " |")
    pending = sum(1 for o in outs if all(v is None for v in o.returns.values()))
    lines += ["", f"{len(outs)} readings logged; {pending} too recent to score at any horizon.", ""]
    # most recent resolved readings, newest first
    recent = [o for o in outs if o.returns[5] is not None][-30:]
    if recent:
        lines += ["## Latest resolved readings", "", "| Date | Symbol | Reading | 5d | 10d | 20d |", "|---|---|---|---|---|---|"]
        for o in reversed(recent):
            label = su.SETUPS[o.key].label if o.key in su.SETUPS else o.key
            f = lambda v: "-" if v is None else f"{v:+.1f}%"
            lines.append(f"| {o.date} | {o.symbol} | {label} | {f(o.returns[5])} | {f(o.returns[10])} | {f(o.returns[20])} |")
        lines.append("")
    return "\n".join(lines)


def write_scorecard(db: DB, reports_dir: Path, as_of: str) -> Path:
    outs = outcomes(db, as_of)
    d = reports_dir / "scorecards"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{as_of}.md"
    p.write_text(scorecard_markdown(outs, as_of), encoding="utf-8")
    return p
