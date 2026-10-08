"""SQLite storage. One table of end-of-day prices for the whole market plus a
fetch log, so every run is auditable (design doc section 6: logging)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from stockbot.sources.psx_daily import EodRow

SCHEMA = """
CREATE TABLE IF NOT EXISTS eod (
    date        TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    sector_code TEXT,
    name        TEXT,
    open        REAL, high REAL, low REAL, close REAL,
    volume      INTEGER,
    ldcp        REAL,
    PRIMARY KEY (date, symbol)
);
CREATE INDEX IF NOT EXISTS eod_symbol_date ON eod(symbol, date);

CREATE TABLE IF NOT EXISTS fetch_log (
    date       TEXT PRIMARY KEY,
    status     TEXT NOT NULL,   -- 'ok' | 'holiday' | 'error'
    rows       INTEGER,
    fetched_at TEXT NOT NULL,
    message    TEXT
);
"""


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- writes -----------------------------------------------------------
    def upsert_eod(self, rows: list[EodRow]) -> int:
        with self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO eod VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(r.date, r.symbol, r.sector_code, r.name, r.open, r.high, r.low, r.close, r.volume, r.ldcp) for r in rows],
            )
        return len(rows)

    def log_fetch(self, date_iso: str, status: str, rows: int = 0, message: str = "") -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO fetch_log VALUES (?,?,?,?,?)",
                (date_iso, status, rows, datetime.now(timezone.utc).isoformat(timespec="seconds"), message),
            )

    # --- reads ------------------------------------------------------------
    def fetch_status(self, date_iso: str) -> str | None:
        r = self.conn.execute("SELECT status FROM fetch_log WHERE date=?", (date_iso,)).fetchone()
        return r["status"] if r else None

    def latest_date(self) -> str | None:
        r = self.conn.execute("SELECT MAX(date) AS d FROM eod").fetchone()
        return r["d"]

    def trading_dates(self) -> list[str]:
        return [r["date"] for r in self.conn.execute("SELECT DISTINCT date FROM eod ORDER BY date")]

    def history(self, symbol: str, up_to: str, n: int) -> list[sqlite3.Row]:
        """Last n rows for symbol with date <= up_to, oldest first."""
        rows = self.conn.execute(
            "SELECT * FROM eod WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol.upper(), up_to, n),
        ).fetchall()
        return list(reversed(rows))

    def row(self, symbol: str, date_iso: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM eod WHERE symbol=? AND date=?", (symbol.upper(), date_iso)).fetchone()

    def counts(self) -> dict:
        r = self.conn.execute("SELECT COUNT(*) AS rows, COUNT(DISTINCT date) AS days, MIN(date) AS first, MAX(date) AS last FROM eod").fetchone()
        return dict(r)
