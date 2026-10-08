"""Offline benchmark: run the live detector over static images with known counts."""

import argparse
import csv
import sys
import time
from pathlib import Path

import config
from overlay import draw_detections

DEFAULT_MANIFEST = "benchmark/manifest.csv"
RESULTS_DIR = Path("benchmark/results")
RESULT_FIELDS = ["filename", "scenario", "expected_count", "detected_count", "signed_error",
                 "absolute_error", "percentage_error", "inference_time_ms"]


class BenchmarkError(Exception):
    pass


def load_manifest(manifest_path):
    path = Path(manifest_path)
    if not path.is_file():
        raise BenchmarkError(f"Manifest not found: {path}")
    cases = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        missing = {"filename", "expected_count", "scenario"} - set(reader.fieldnames or [])
        if missing:
            raise BenchmarkError(f"{path}: missing columns {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            try:
                expected = int(row["expected_count"])
                if expected < 0 or not row["filename"].strip():
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise BenchmarkError(f"{path} line {line_no}: malformed row {row}") from None
            cases.append({"filename": row["filename"].strip(), "expected": expected,
                          "scenario": row["scenario"]})
    if not cases:
        raise BenchmarkError(f"{path}: no test cases")
    return cases


def compute_metrics(expected, detected):
    signed = detected - expected
    percentage = None if expected == 0 else round(abs(signed) / expected * 100, 1)
    return {"signed_error": signed, "absolute_error": abs(signed), "percentage_error": percentage}


def summarize(rows):
    n = len(rows)
    exact = sum(1 for r in rows if r["absolute_error"] == 0)
    return {
        "images": n,
        "mae": sum(r["absolute_error"] for r in rows) / n,
        "mean_signed_error": sum(r["signed_error"] for r in rows) / n,
        "empty_false_positives": sum(r["detected_count"] for r in rows
                                    if r["expected_count"] == 0),
        "max_error": max(r["absolute_error"] for r in rows),
        "exact": exact,
        "exact_pct": exact / n * 100,
        "mean_ms": sum(r["inference_time_ms"] for r in rows) / n,
    }


def measure(analyze, model, image, case):
    """Run the shared detector on one image; return (result row, accepted, rejected)."""
    start = time.perf_counter()
    detections, rejected = analyze(model, image)
    elapsed_ms = (time.perf_counter() - start) * 1000
    detected = len(detections)
    row = {"filename": case["filename"], "scenario": case["scenario"],
           "expected_count": case["expected"], "detected_count": detected,
           "inference_time_ms": round(elapsed_ms, 1),
           **compute_metrics(case["expected"], detected)}
    return row, detections, rejected


def annotate(cv2, image, detections, rejected, expected, signed):
    # Orange = candidates that did NOT count (low confidence or duplicate); green = counted.
    annotated = draw_detections(cv2, image, rejected, color=(0, 165, 255))
    annotated = draw_detections(cv2, annotated, detections)
    for i, text in enumerate([f"Expected: {expected}", f"Detected: {len(detections)}",
                              f"Error: {signed:+d}"]):
        cv2.putText(annotated, text, (20, 45 + i * 45), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
                    (0, 0, 255), 3)
    return annotated


def write_results(rows):
    with (RESULTS_DIR / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row[k] is None else row[k]) for k in RESULT_FIELDS})


def run(manifest_path):
    cases = load_manifest(manifest_path)
    image_dir = Path(manifest_path).parent / "images"
    for case in cases:  # fail before loading the model if any file is missing
        if not (image_dir / case["filename"]).is_file():
            raise BenchmarkError(f"Image not found: {image_dir / case['filename']}")

    import cv2
    from detector import analyze, load_model

    try:
        model = load_model()
    except Exception as exc:
        raise BenchmarkError(f"Detector failed to initialize: {exc}") from exc

    # Untimed warm-up: the first inference is far slower (model/runtime init).
    analyze(model, cv2.imread(str(image_dir / cases[0]["filename"])))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, case in enumerate(cases, start=1):
        path = image_dir / case["filename"]
        image = cv2.imread(str(path))
        if image is None:
            raise BenchmarkError(f"Could not load image: {path}")

        row, detections, rejected = measure(analyze, model, image, case)
        detected = row["detected_count"]
        elapsed_ms = row["inference_time_ms"]
        rows.append(row)

        out = RESULTS_DIR / f"{path.stem}_detected.png"
        cv2.imwrite(str(out), annotate(cv2, image, detections, rejected, case["expected"],
                                       row["signed_error"]))
        print(f"[{i}/{len(cases)}] {case['filename']:<20} expected={case['expected']:<3} "
              f"detected={detected:<3} error={row['signed_error']:+d}   {elapsed_ms:.1f} ms")

    write_results(rows)
    print_summary(summarize(rows))


def print_summary(s):
    print(f"\nBenchmark complete (model={config.MODEL_NAME}, conf={config.CONFIDENCE_THRESHOLD}, "
          f"imgsz={config.INFERENCE_IMAGE_SIZE})\n")
    print(f"Images tested:         {s['images']}")
    print(f"Mean absolute error:   {s['mae']:.2f} people")
    print(f"Mean signed error:     {s['mean_signed_error']:+.2f} people (negative = undercount)")
    print(f"Maximum error:         {s['max_error']} people")
    print(f"Exact-count accuracy:  {s['exact']}/{s['images']} ({s['exact_pct']:.1f}%)")
    print(f"Empty-room detections: {s['empty_false_positives']}")
    print(f"Mean inference time:   {s['mean_ms']:.1f} ms")
    print(f"\nResults: {RESULTS_DIR / 'results.csv'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    # Temporary overrides of the shared config.py values, for comparing settings.
    parser.add_argument("--conf", type=float, help="override CONFIDENCE_THRESHOLD")
    parser.add_argument("--imgsz", type=int, help="override INFERENCE_IMAGE_SIZE")
    parser.add_argument("--model", help="override MODEL_NAME (e.g. yolo11s.pt)")
    parser.add_argument("--dedupe", type=float, help="override DEDUPE_CONTAINMENT (0 = off)")
    parser.add_argument("--small-conf", type=float, help="override SMALL_BOX_CONFIDENCE (0 = off)")
    args = parser.parse_args()
    if args.conf is not None:
        config.CONFIDENCE_THRESHOLD = args.conf
    if args.imgsz is not None:
        config.INFERENCE_IMAGE_SIZE = args.imgsz
    if args.model:
        config.MODEL_NAME = args.model
    if args.dedupe is not None:
        config.DEDUPE_CONTAINMENT = args.dedupe
    if args.small_conf is not None:
        config.SMALL_BOX_CONFIDENCE = args.small_conf
    try:
        run(args.manifest)
    except BenchmarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
