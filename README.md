# Stock Guru (stockbot)

Personal PSX decision-support agent. It fetches official end-of-day data,
computes transparent statistics and writes a plain-language daily note.
It never places orders and never gives buy/sell instructions or price
targets. Design: `docs/psx_agent_design.md`.

**V1 scope:** statistical data + analysis + feedback on that analysis.
The YouTube Analyst Digest (design section 4.6) is out of scope for V1.

## Status: Phase 1 (watchlist, daily EOD data, indicators, daily note)

| Piece | State |
|---|---|
| Data source | PSX Data Portal daily *Market Summary (Closing)* ZIP, one file per trading day, archive back to at least 2020 |
| Storage | SQLite `data/stockbot.db` (whole market, ~500 equities/day) + raw ZIPs in `data/raw/` + fetch log |
| Indicators | SMA20, SMA50, RSI14, volume vs 20-day average, 1w/1m/3m returns, 52-week range |
| Daily note | Markdown in `reports/daily/YYYY-MM-DD.md`; JSON snapshot in `data/snapshots/` (feeds the Phase 3 self-scoring log) |
| AI narrative | Optional, Gemini via `stockbot/ai/gemini.py` (the only AI touch-point); off until `GEMINI_API_KEY` is set |
| Scheduling | systemd timer Mon-Fri 18:30 PKT (`systemd/`), not yet installed |
| Delivery | file only for now; PDF + email come later |

## Usage

```bash
.venv/bin/python -m stockbot status
.venv/bin/python -m stockbot backfill --start 2025-07-01     # polite: 1.5 s between files
.venv/bin/python -m stockbot fetch                           # latest weekday
.venv/bin/python -m stockbot note --date 2026-10-08 --no-ai  # note without the AI narrative
.venv/bin/python -m stockbot run                             # what the timer does: fetch + note
.venv/bin/python -m unittest discover -s tests -v
```

Exit codes: 0 ok, 1 fetch error, 2 note written but data problems (read the top of the note).

## Setup on the NAS

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp secrets.env.example secrets.env && chmod 600 secrets.env   # add GEMINI_API_KEY
sudo cp systemd/stockbot-daily.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now stockbot-daily.timer
```

`scripts/backup.sh` mirrors the project to `/mnt/storage/project_backups/stockbot_backup`
and then to Google Drive (`gdrive:stockbot` via rclone). The systemd service runs it after
every daily run.

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

`config/watchlist.toml` currently holds a **placeholder** list of 10 liquid names across
sectors. Homi's own 10-stock trial list replaces it before the 3-month paper-trading period
starts. FATIMA stays off the list until the employer insider-trading policy is checked.
