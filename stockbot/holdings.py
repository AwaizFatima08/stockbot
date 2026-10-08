"""Portfolio holdings supplied by the user as a simple TOML file (design 4.3).

config/holdings.toml is git-ignored (personal). Quantities and values never
leave this machine: the AI payload gets symbols and weights only (design
open question 5, resolved conservatively)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Position:
    symbol: str
    shares: float
    avg_cost: float


def load(root: Path) -> list[Position]:
    path = root / "config" / "holdings.toml"
    if not path.exists():
        return []
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    out = []
    for p in data.get("positions", []):
        sym = str(p["symbol"]).strip().upper()
        shares = float(p.get("shares", 0))
        cost = float(p.get("avg_cost", 0))
        if sym and shares > 0:
            out.append(Position(sym, shares, cost))
    return out


def value(positions: list[Position], last_close: dict[str, float]) -> list[dict]:
    """Per-position market value and P/L where a close is known."""
    rows = []
    for p in positions:
        close = last_close.get(p.symbol)
        mv = close * p.shares if close else None
        cost = p.avg_cost * p.shares
        rows.append({
            "symbol": p.symbol, "shares": p.shares, "avg_cost": p.avg_cost, "close": close,
            "market_value": mv, "cost_value": cost,
            "pl_pct": ((close / p.avg_cost - 1.0) * 100.0) if (close and p.avg_cost) else None,
        })
    total = sum(r["market_value"] or 0.0 for r in rows)
    for r in rows:
        r["weight_pct"] = (r["market_value"] / total * 100.0) if (total and r["market_value"]) else None
    return rows
