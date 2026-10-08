#!/usr/bin/env bash
# 1) mirror the project to the local backup folder, 2) sync that to Google Drive.
# Excludes the virtualenv and caches. Includes data/ (DB + raw files) and reports/.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="/mnt/storage/project_backups/stockbot_backup"
GDRIVE_REMOTE="gdrive:stockbot"
EXCL=(--exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude '.pytest_cache')

mkdir -p "$DST"
rsync -a --delete "${EXCL[@]}" "$SRC/" "$DST/"
echo "local backup: $DST ($(du -sh "$DST" | cut -f1))"
if command -v rclone >/dev/null && rclone listremotes | grep -q '^gdrive:'; then
  rclone sync "$DST" "$GDRIVE_REMOTE" --exclude '.git/**' --exclude '.venv/**' --fast-list --transfers 8 --checkers 16 -q
  echo "google drive: $GDRIVE_REMOTE synced"
else
  echo "rclone gdrive remote not available; skipped Google Drive sync" >&2
fi
