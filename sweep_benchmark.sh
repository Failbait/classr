#!/usr/bin/env bash
# Sweep models / image sizes / confidences and print a ranked comparison table.
# Extra args pass through, e.g. ./sweep_benchmark.sh --models yolo26s.pt --imgsz 1280
cd "$(dirname "$0")"
source .venv/bin/activate
exec python sweep.py "$@"
