# Stock Guru (stockbot)

Personal PSX decision-support agent. It fetches official end-of-day data,
computes transparent statistics and writes a plain-language daily note.
It never places orders and never gives buy/sell instructions or price
targets. Design: `docs/psx_agent_design.md`.

**V1 scope:** statistical data + analysis + feedback on that analysis.
The YouTube Analyst Digest (design section 4.6) is out of scope for V1.

## Status: Phases 1-3 built (8 Oct 2026), paper-trading period not yet started

| Piece | State |
|---|---|
| Data source | PSX Data Portal daily *Market Summary (Closing)* ZIP, one file per trading day, archive back to at least 2020 |
| Storage | SQLite `data/stockbot.db` (whole market, ~500 equities/day) + raw ZIPs in `data/raw/` + fetch log |
| Indicators | SMA20, SMA50, RSI14, volume vs 20-day average, 1w/1m/3m returns, 52-week range |
| Company data | PSX company page per watchlist stock, daily: P/E, market cap, free float, 4y sales/profit/EPS, quarterly EPS, ratios, announcements; AGM date parsed from the notice PDF; ex-dividend dates from XD markers in the daily files (`sources/psx_company.py`, `sources/psx_agm.py`, `corporate.py`) |
| Payouts | ksestocks.com Book Closures page, once a day: declared cash dividend (pct of face value -> Rs per share), bonus and right percentages, book-closure dates; accumulated in the `payouts` table from 8 Oct 2026 (`sources/ksestocks.py`). PSX notices remain the authority |
| Long term / next week | multi-year CAGR, volatility, drawdown, positive-window share, EPS growth (`analysis/longterm.py`); weekly-move distribution + conditional levels + base rates (`analysis/outlook.py`). Statistics, never forecasts |
| Candlestick patterns | Pure OHLC rules: doji, hammer, shooting star, bullish/bearish engulfing, gaps, strong candles (`analysis/patterns.py`) |
| Setups + base rates | 14 transparent setups (`analysis/setups.py`); for each one that fires, what happened 5/10/20 sessions after past occurrences, per stock and across the 100 most-traded equities. Windows broken by a >30% day move (corporate action / bad data) or a hole in history are discarded |
| Annotated charts | 120-session candlestick PNG per stock with SMA20/50, volume, patterns and levels marked, one-line caption (`reports/charts/<date>/`) |
| Holdings | optional `config/holdings.toml` (git-ignored); weights and P/L in the note; only symbols and percentages ever go to the AI |
| Daily note | Markdown + PDF in `reports/daily/`; JSON snapshot in `data/snapshots/` |
| Self-scoring log | every note logs the trend label and setups per stock (`signals` table); `scorecard` reports hit rates and median moves 5/10/20 sessions later; written automatically every Friday |
| AI narrative | Optional, Gemini via `stockbot/ai/gemini.py` (the only AI touch-point); off until `GEMINI_API_KEY` (an AI Studio key, `AIza...`) is in `secrets.env` |
| Scheduling | systemd timer Mon-Fri 18:30 PKT (`systemd/`), not yet installed (needs sudo) |
| Delivery | files; email of the PDF is implemented but off until `[email]` in settings.toml and `SMTP_PASSWORD` are filled in |

## Phone app (Android)

`app/` is a Flutter app that reads a small LAN API on the NAS (`python -m stockbot serve`,
systemd unit `systemd/stockbot-api.service`, port 8787, token in `secrets.env` as
`STOCKBOT_API_TOKEN`). Screens: Today (daily performance), per-stock tabs (Today, Chart &
trends with candlesticks, History since 2020, Corporate: AGM date / ex-dividend dates /
results / announcements, Next week: base rates + typical weekly move + levels, Long term:
multi-year price stats + reported EPS/sales/profit/ratios), Scorecard, Watchlist editor
(replace any of the 10 stocks; the NAS rewrites `config/watchlist.toml` and regenerates),
Settings (server address + token). The phone must reach the NAS (home Wi-Fi or VPN).

Build: `cd app && flutter build apk --release` -> `app/build/app/outputs/flutter-apk/app-release.apk`.
Data pipeline for the app: `python -m stockbot export` writes `data/app/` (done automatically by `run`).

Data sources in use and candidates to add: `docs/data-sources.md`.

## Usage

```bash
.venv/bin/python -m stockbot status
.venv/bin/python -m stockbot backfill --start 2025-07-01     # polite: 1.5 s between files
.venv/bin/python -m stockbot fetch                           # latest weekday
.venv/bin/python -m stockbot note --date 2026-10-08 --no-ai  # note without the AI narrative
.venv/bin/python -m stockbot run                             # what the timer does: fetch + note (+ scorecard on Fridays)
.venv/bin/python -m stockbot scorecard                       # how past readings fared
.venv/bin/python -m unittest discover -s tests -v
```

Exit codes: 0 ok, 1 fetch error, 2 note written but data problems (read the top of the note).

## Setup on the NAS

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp secrets.env.example secrets.env && chmod 600 secrets.env   # add GEMINI_API_KEY
sudo cp systemd/stockbot-daily.* systemd/stockbot-api.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now stockbot-daily.timer stockbot-api.service
```

`scripts/backup.sh` mirrors the project to `/mnt/storage/project_backups/stockbot_backup`
and then to Google Drive (`gdrive:stockbot` via rclone). The systemd service runs it after
every daily run.

## Reading the base rates

"PSO: 27 past occurrences; price was higher 5 sessions later 33% of the time (median -1.1%, worst -6.4%, best +9.8%)"
means exactly that and nothing more. A hit rate near 50% with a median near 0% says the setup carried no
information in the past. Small samples (under ~20) are shown but mean little. These are not forecasts.

## Data notes

- File format (`closing11.lis`): `DATE|SYMBOL|SECTOR|NAME|OPEN|HIGH|LOW|CLOSE|VOLUME|LDCP|||`.
  Rows with `-` in the symbol are futures contracts and are skipped.
- Non-trading days return HTTP 404 and are logged as `holiday`.
- For thinly traded stocks PSX's CLOSE can fall outside the day's HIGH/LOW range
  (it is not always the last trade). These are logged as warnings, not errors.
- **Terms of use:** the portal's terms restrict automated and systematic retrieval
  and allow a single copy for personal, non-commercial use. This project downloads one
  official file per trading day and never re-fetches a day. Whether to ask PSX for
  written permission is an open decision (design section 7).

## Watchlist

`config/watchlist.toml` holds Homi's 10-stock trial list (8 Oct 2026): OCTOPUS, AVN, TREET, FCL,
WAVESAPP, WAVES, FATIMA, FFC, CNERGY, HUBC. FATIMA is on the list at Homi's request; the design doc's
insider-trading-policy note (section 7) still applies.
