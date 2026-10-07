"""Sweep detector settings over the benchmark images and compare against the baseline.

Uses the same detector (detector.detect_people) and metrics (benchmark.py) as the live app;
only the config.py values are varied in-process.
"""

import argparse
import csv
import sys
from pathlib import Path

import config
from benchmark import (DEFAULT_MANIFEST, BenchmarkError, load_manifest, measure, summarize)

OUT_DIR = Path("benchmark/results/sweep")
BASELINE = ("yolo11s.pt", 1280, 0.5)
HARD_SCENARIOS = {"distant", "occlusion", "dense"}
DEFAULT_MODELS = ["yolo11s.pt", "yolo26s.pt", "yolo26n.pt"]
DEFAULT_IMGSZ = [640, 960, 1280, 1600, 1920]
DEFAULT_CONFS = [0.4, 0.5, 0.6, 0.7]


def hard_case_mae(rows):
    hard = [r["absolute_error"] for r in rows if r["scenario"] in HARD_SCENARIOS]
    return sum(hard) / len(hard) if hard else 0.0


def rank_key(entry):
    """Selection order: MAE, exact accuracy, hard-case MAE, empty false positives, time."""
    s = entry["summary"]
    return (round(s["mae"], 6), -s["exact"], round(entry["hard_mae"], 6),
            s["empty_false_positives"], s["mean_ms"])


def evaluate(detect_people, model, images, cases):
    """Warm up (untimed), then measure every image under the current config values."""
    detect_people(model, images[0])
    return [measure(detect_people, model, img, case)[0] for img, case in zip(images, cases)]


def load_images(cv2, manifest):
    cases = load_manifest(manifest)
    image_dir = Path(manifest).parent / "images"
    images = []
    for case in cases:
        path = image_dir / case["filename"]
        if not path.is_file():
            raise BenchmarkError(f"Image not found: {path}")
        image = cv2.imread(str(path))
        if image is None:
            raise BenchmarkError(f"Could not load image: {path}")
        images.append(image)
    return cases, images


def sweep(models, sizes, confs, manifest):
    import cv2
    from detector import detect_people, load_model

    cases, images = load_images(cv2, manifest)
    entries = []
    for model_name in models:
        config.MODEL_NAME = model_name
        try:
            model = load_model()
        except Exception as exc:
            print(f"SKIP {model_name}: {exc}", file=sys.stderr)
            continue
        for imgsz in sizes:
            for conf in confs:
                config.INFERENCE_IMAGE_SIZE, config.CONFIDENCE_THRESHOLD = imgsz, conf
                rows = evaluate(detect_people, model, images, cases)
                entry = {"model": model_name, "imgsz": imgsz, "conf": conf, "rows": rows,
                         "summary": summarize(rows), "hard_mae": hard_case_mae(rows)}
                entries.append(entry)
                print(f"{model_name} imgsz={imgsz} conf={conf}: "
                      f"MAE={entry['summary']['mae']:.2f}", flush=True)
    return entries


def write_outputs(entries):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "per_image.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "imgsz", "conf", "filename", "scenario", "expected_count",
                    "detected_count", "signed_error", "absolute_error", "inference_time_ms"])
        for e in entries:
            for r in e["rows"]:
                w.writerow([e["model"], e["imgsz"], e["conf"], r["filename"], r["scenario"],
                            r["expected_count"], r["detected_count"], r["signed_error"],
                            r["absolute_error"], r["inference_time_ms"]])
    with (OUT_DIR / "summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "model", "imgsz", "conf", "mae", "mean_signed_error", "exact",
                    "exact_pct", "hard_case_mae", "empty_false_positives", "mean_ms"])
        for rank, e in enumerate(sorted(entries, key=rank_key), start=1):
            s = e["summary"]
            w.writerow([rank, e["model"], e["imgsz"], e["conf"], f"{s['mae']:.2f}",
                        f"{s['mean_signed_error']:+.2f}", s["exact"], f"{s['exact_pct']:.1f}",
                        f"{e['hard_mae']:.2f}", s["empty_false_positives"], f"{s['mean_ms']:.0f}"])


def print_table(entries, top):
    ranked = sorted(entries, key=rank_key)
    base = next((e for e in entries if (e["model"], e["imgsz"], e["conf"]) == BASELINE), None)
    header = (f"{'#':>3} {'model':<11} {'imgsz':>5} {'conf':>4} {'MAE':>5} {'signed':>6} "
              f"{'exact':>5} {'hardMAE':>7} {'emptyFP':>7} {'ms':>6}")
    print("\n" + header)
    shown = ranked[:top]
    if base is not None and base not in shown:
        shown.append(base)
    for e in shown:
        s = e["summary"]
        tag = "  <- baseline" if e is base else ""
        print(f"{ranked.index(e) + 1:>3} {e['model']:<11} {e['imgsz']:>5} {e['conf']:>4} "
              f"{s['mae']:>5.2f} {s['mean_signed_error']:>+6.2f} {s['exact']}/{s['images']:<3} "
              f"{e['hard_mae']:>7.2f} {s['empty_false_positives']:>7} {s['mean_ms']:>6.0f}{tag}")
    print_verdict(entries, base)


def print_verdict(entries, base):
    if base is None:
        print("\nBaseline (yolo11s @ 1280 @ 0.5) not in sweep; no verdict.")
        return
    best26 = min((e for e in entries if e["model"].startswith("yolo26s")),
                 key=rank_key, default=None)
    if best26 is None:
        print("\nNo yolo26s results; cannot compare.")
        return
    wins = rank_key(best26) < rank_key(base)
    print(f"\nBest yolo26s: imgsz={best26['imgsz']} conf={best26['conf']} "
          f"MAE={best26['summary']['mae']:.2f} exact={best26['summary']['exact']}/8")
    print(f"Baseline:     MAE={base['summary']['mae']:.2f} exact={base['summary']['exact']}/8")
    print("VERDICT: yolo26s " + ("BEATS" if wins else "does NOT beat") + " the yolo11s baseline.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument("--imgsz", nargs="+", type=int, default=DEFAULT_IMGSZ)
    p.add_argument("--conf", nargs="+", type=float, default=DEFAULT_CONFS)
    p.add_argument("--top", type=int, default=10)
    args = p.parse_args()
    try:
        entries = sweep(args.models, args.imgsz, args.conf, args.manifest)
        if not entries:
            raise BenchmarkError("no configuration produced results")
    except BenchmarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    write_outputs(entries)
    print_table(entries, args.top)
    print(f"\nWrote {OUT_DIR}/summary.csv and {OUT_DIR}/per_image.csv")


if __name__ == "__main__":
    main()
