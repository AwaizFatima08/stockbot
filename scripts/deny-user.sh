#!/usr/bin/env bash
# Remove a Google account from the Stock Guru allow-list.  Usage: deny-user.sh email@gmail.com
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -eq 1 ] || { echo "usage: $0 email@gmail.com"; exit 1; }
exec .venv/bin/python -m stockbot deny-user "$1"
