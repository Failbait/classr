#!/usr/bin/env bash
# Compare detector settings. Prints one summary line per combination. Takes a few minutes.
# Usage: ./sweep_benchmark.sh
cd "$(dirname "$0")"
source .venv/bin/activate
for model in yolo11n.pt yolo11s.pt; do
  for imgsz in 640 1280; do
    for conf in 0.5 0.35 0.25 0.15; do
      echo "== model=$model imgsz=$imgsz conf=$conf"
      python benchmark.py --model "$model" --imgsz "$imgsz" --conf "$conf" \
        | grep -E "Mean absolute|Maximum error|Exact-count|Mean inference"
    done
  done
done
