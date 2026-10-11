#!/usr/bin/env bash
# Run the benchmark on every photo set with the live settings from config.py.
# Annotated images and results.csv go to benchmark/results/ (photos) and
# benchmark/results/composites/ (composites). Extra args are passed to both runs.
cd "$(dirname "$0")"
source .venv/bin/activate

echo "=== Photos (benchmark/manifest.csv)"
python benchmark.py --manifest benchmark/manifest.csv --out-dir benchmark/results "$@"
echo
echo "=== Composites (benchmark_composites/manifest.csv)"
python benchmark.py --manifest benchmark_composites/manifest.csv --out-dir benchmark/results/composites "$@"
