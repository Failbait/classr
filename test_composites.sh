#!/usr/bin/env bash
# Run the benchmark on the composite images (held-out set) with annotated output.
# Uses the live settings from config.py; extra args override, e.g. ./test_composites.sh --model rfdetr-small --imgsz 0 --conf 0.4
cd "$(dirname "$0")"
source .venv/bin/activate
exec python benchmark.py --manifest benchmark_composites/manifest.csv \
  --out-dir benchmark/results/composites "$@"
