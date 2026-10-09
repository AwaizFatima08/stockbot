#!/usr/bin/env bash
# Allow a Google account to use the Stock Guru app from anywhere.  Usage: allow-user.sh email@gmail.com
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -eq 1 ] || { echo "usage: $0 email@gmail.com"; exit 1; }
exec .venv/bin/python -m stockbot allow-user "$1"
