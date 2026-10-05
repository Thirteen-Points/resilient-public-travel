#!/usr/bin/env bash
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="${P4_PYTHON:-$REPO/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  echo 'Set P4_PYTHON to your prepared Python executable; offline launch never installs dependencies.' >&2
  exit 1
fi
cd "$REPO"
exec "$PYTHON_BIN" scripts/offline_demo.py "$@"
