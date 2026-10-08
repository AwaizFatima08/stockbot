"""Load settings.toml and watchlist.toml. Secrets come only from the environment."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    sector: str


@dataclass(frozen=True)
class Settings:
    root: Path
    timezone: str
    data_dir: Path
    reports_dir: Path
    raw_dir: Path
    snapshots_dir: Path
    db_path: Path
    backfill_delay_seconds: float
    user_agent: str
    sma_short: int
    sma_long: int
    rsi_period: int
    volume_avg_period: int
    history_days: int
    ai_enabled: bool
    ai_model: str
    universe_size: int = 100
    charts_enabled: bool = True
    chart_sessions: int = 120
    email: dict = field(default_factory=dict)
    watchlist: tuple[Stock, ...] = field(default_factory=tuple)

    @property
    def baserates_dir(self) -> Path:
        return self.data_dir / "baserates"

    @property
    def gemini_api_key(self) -> str | None:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        return key or None


def _read_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load(root: Path | None = None) -> Settings:
    root = root or ROOT
    cfg = _read_toml(root / "config" / "settings.toml")
    wl = _read_toml(root / "config" / "watchlist.toml")

    general = cfg.get("general", {})
    fetch = cfg.get("fetch", {})
    analysis = cfg.get("analysis", {})
    ai = cfg.get("ai", {})

    data_dir = root / general.get("data_dir", "data")
    reports_dir = root / general.get("reports_dir", "reports")

    stocks = []
    seen = set()
    for s in wl.get("stocks", []):
        sym = str(s["symbol"]).strip().upper()
        if not sym:
            raise ValueError("watchlist.toml: empty symbol")
        if sym in seen:
            raise ValueError(f"watchlist.toml: duplicate symbol {sym}")
        seen.add(sym)
        stocks.append(Stock(sym, str(s.get("name", sym)), str(s.get("sector", ""))))
    if not stocks:
        raise ValueError("watchlist.toml has no stocks")

    return Settings(
        root=root,
        timezone=general.get("timezone", "Asia/Karachi"),
        data_dir=data_dir,
        reports_dir=reports_dir,
        raw_dir=data_dir / "raw" / "mkt_summary",
        snapshots_dir=data_dir / "snapshots",
        db_path=data_dir / "stockbot.db",
        backfill_delay_seconds=float(fetch.get("backfill_delay_seconds", 1.5)),
        user_agent=str(fetch.get("user_agent", "StockGuru/0.1")),
        sma_short=int(analysis.get("sma_short", 20)),
        sma_long=int(analysis.get("sma_long", 50)),
        rsi_period=int(analysis.get("rsi_period", 14)),
        volume_avg_period=int(analysis.get("volume_avg_period", 20)),
        history_days=int(analysis.get("history_days", 400)),
        ai_enabled=bool(ai.get("enabled", True)),
        ai_model=str(ai.get("model", "gemini-2.5-flash")),
        universe_size=int(cfg.get("baserates", {}).get("universe_size", 100)),
        charts_enabled=bool(cfg.get("charts", {}).get("enabled", True)),
        chart_sessions=int(cfg.get("charts", {}).get("sessions", 120)),
        email=dict(cfg.get("email", {})),
        watchlist=tuple(stocks),
    )
