#!/usr/bin/env bash
# Run the offline detector benchmark. Extra args pass through (e.g. --manifest path.csv).
cd "$(dirname "$0")"
source .venv/bin/activate
exec python benchmark.py "$@"
