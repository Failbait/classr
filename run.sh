#!/usr/bin/env bash
# Start the people counter. Extra args are passed through (e.g. ./run.sh --no-preview).
cd "$(dirname "$0")"
source .venv/bin/activate
exec python main.py "$@"
