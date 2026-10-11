"""Offline posture benchmark: aggregate seated/standing/unknown counts vs ground truth.

Separate from the occupancy benchmark. The manifest lists image paths relative to the manifest
folder and the expected posture counts per image (mark ambiguous people as unknown).
"""

import argparse
import csv
import sys
from pathlib import Path

from overlay import draw_detections
from posture import GeometryPostureClassifier, classify_detections, summarize_postures

DEFAULT_MANIFEST = "benchmark_posture/manifest.csv"
RESULTS_DIR = Path("benchmark_posture/results")
COUNT_FIELDS = ["expected_occupancy", "expected_seated", "expected_standing", "expected_unknown"]


class PostureBenchmarkError(Exception):
    pass


def load_manifest(manifest_path):
    path = Path(manifest_path)
    if not path.is_file():
        raise PostureBenchmarkError(f"Manifest not found: {path}")
    cases = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        missing = {"filename", *COUNT_FIELDS} - set(reader.fieldnames or [])
        if missing:
            raise PostureBenchmarkError(f"{path}: missing columns {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            try:
                counts = {k: int(row[k]) for k in COUNT_FIELDS}
                if min(counts.values()) < 0 or not row["filename"].strip():
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise PostureBenchmarkError(f"{path} line {line_no}: malformed row {row}") from None
            if counts["expected_seated"] + counts["expected_standing"] + counts["expected_unknown"] \
                    != counts["expected_occupancy"]:
                raise PostureBenchmarkError(
                    f"{path} line {line_no}: seated+standing+unknown != occupancy")
            cases.append({"filename": row["filename"].strip(), **counts})
    if not cases:
        raise PostureBenchmarkError(f"{path}: no test cases")
    return cases


def ratio(standing, occupancy):
    return standing / occupancy if occupancy else 0.0


def compare(case, summary):
    """Signed errors (detected - expected) for one image."""
    return {
        "filename": case["filename"],
        "occupancy_error": summary["occupancy"] - case["expected_occupancy"],
        "seated_count_error": summary["seated_count"] - case["expected_seated"],
        "standing_count_error": summary["standing_count"] - case["expected_standing"],
        "unknown_count_error": summary["unknown_count"] - case["expected_unknown"],
        "standing_ratio_error": round(summary["standing_ratio"] - ratio(
            case["expected_standing"], case["expected_occupancy"]), 3),
    }


def mean_absolute(rows, key):
    return sum(abs(r[key]) for r in rows) / len(rows)


def run(manifest_path):
    cases = load_manifest(manifest_path)
    base = Path(manifest_path).parent
    for case in cases:
        if not (base / case["filename"]).is_file():
            raise PostureBenchmarkError(f"Image not found: {base / case['filename']}")

    import cv2
    from detector import detect_people, load_model

    model = load_model()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    classifier = GeometryPostureClassifier()
    rows = []
    for i, case in enumerate(cases, start=1):
        image = cv2.imread(str(base / case["filename"]))
        if image is None:
            raise PostureBenchmarkError(f"Could not load image: {base / case['filename']}")
        people = classify_detections(classifier, image, detect_people(model, image))
        summary = summarize_postures(p["posture"] for p in people)
        row = compare(case, summary)
        rows.append(row)
        cv2.imwrite(str(RESULTS_DIR / f"{Path(case['filename']).stem}_posture.png"),
                    annotate(cv2, image, people, summary, case))
        print(f"[{i}/{len(cases)}] {Path(case['filename']).name:<24} "
              f"seated {summary['seated_count']}/{case['expected_seated']}  "
              f"standing {summary['standing_count']}/{case['expected_standing']}  "
              f"unknown {summary['unknown_count']}/{case['expected_unknown']}  "
              f"(detected/expected)")
    print_summary(rows)


def annotate(cv2, image, people, summary, case):
    annotated = draw_detections(cv2, image, people)
    lines = [f"Seated {summary['seated_count']}/{case['expected_seated']}",
             f"Standing {summary['standing_count']}/{case['expected_standing']}",
             f"Unknown {summary['unknown_count']}/{case['expected_unknown']}"]
    for i, text in enumerate(lines):
        cv2.putText(annotated, text, (20, 45 + i * 45), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
                    (0, 0, 255), 3)
    return annotated


def print_summary(rows):
    print(f"\nPosture benchmark: {len(rows)} images (mean absolute error)")
    print(f"Annotated images: {RESULTS_DIR}/")
    for key in ("occupancy_error", "seated_count_error", "standing_count_error",
                "unknown_count_error", "standing_ratio_error"):
        signed = sum(r[key] for r in rows) / len(rows)
        print(f"{key:<22} {mean_absolute(rows, key):.2f}   (mean signed {signed:+.2f})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        run(args.manifest)
    except PostureBenchmarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
