#!/usr/bin/env bash
# Daily job wrapper used by systemd (and for manual runs).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f secrets.env ]; then set -a; . ./secrets.env; set +a; fi
mkdir -p data/logs
exec .venv/bin/python -m stockbot run "$@" 2>&1 | tee -a "data/logs/run-$(date +%Y-%m).log"
