#!/usr/bin/env bash
# Run the benchmark for the top candidates, each with annotated images in its own folder.
# Green boxes = counted, orange = rejected candidates. Results: benchmark/results/<name>/
cd "$(dirname "$0")"
source .venv/bin/activate

run() {  # name, then benchmark.py args
  local name="$1"; shift
  echo "=== $name"
  python benchmark.py "$@" --out-dir "benchmark/results/$name" | grep -E "expected=|Mean absolute|Mean signed|Exact-count|Empty-room|Mean inference"
}

run rfdetr_small_native --model rfdetr-small --imgsz 0   --conf 0.4 --dedupe 0.85 --small-conf 0.3
run yolo26s_640         --model yolo26s.pt   --imgsz 640 --conf 0.3 --dedupe 0.85 --small-conf 0.3
run yolo11s_768         --model yolo11s.pt   --imgsz 768 --conf 0.5 --dedupe 0.85 --small-conf 0.3
