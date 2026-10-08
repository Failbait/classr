"""Sweep detector settings over the benchmark images and compare against the baseline.

Uses the same detector (detector.detect_people) and metrics (benchmark.py) as the live app;
only the config.py values are varied in-process.
"""

import argparse
import csv
import itertools
import sys
from pathlib import Path

import config
from benchmark import (DEFAULT_MANIFEST, BenchmarkError, load_manifest, measure, summarize)

OUT_DIR = Path("benchmark/results/sweep")
BASELINE = ("yolo11s.pt", 1280, 0.5, 0, 0)  # model, imgsz, conf, dedupe off, small-box rule off
HARD_SCENARIOS = {"distant", "occlusion", "dense"}
DEFAULT_MODELS = ["yolo11s.pt", "yolo26s.pt", "yolo26n.pt"]
DEFAULT_IMGSZ = [640, 960, 1280, 1600, 1920]
RFDETR_IMGSZ = [0, 672, 896, 1120]  # 0 = model's native size; others rounded to a valid multiple
DEFAULT_CONFS = [0.4, 0.5, 0.6, 0.7]


def hard_case_mae(rows):
    hard = [r["absolute_error"] for r in rows if r["scenario"] in HARD_SCENARIOS]
    return sum(hard) / len(hard) if hard else 0.0


def rank_key(entry):
    """Selection order: MAE, exact accuracy, hard-case MAE, empty false positives, time."""
    s = entry["summary"]
    return (round(s["mae"], 6), -s["exact"], round(entry["hard_mae"], 6),
            s["empty_false_positives"], s["mean_ms"])


def evaluate(analyze, model, images, cases):
    """Warm up (untimed), then measure every image under the current config values."""
    analyze(model, images[0])
    return [measure(analyze, model, img, case)[0] for img, case in zip(images, cases)]


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


def sweep(models, sizes, rfdetr_sizes, confs, dedupes, small_confs, manifest):
    import cv2
    from detector import analyze, load_model

    cases, images = load_images(cv2, manifest)
    entries = []
    for model_name in models:
        config.MODEL_NAME = model_name
        try:
            model = load_model()
        except Exception as exc:
            print(f"SKIP {model_name}: {exc}", file=sys.stderr)
            continue
        is_rfdetr = model_name.startswith("rfdetr-")
        model_sizes = (rfdetr_sizes or RFDETR_IMGSZ) if is_rfdetr else (sizes or DEFAULT_IMGSZ)
        for imgsz in model_sizes:
            for conf, dedupe, small in itertools.product(confs, dedupes, small_confs):
                config.INFERENCE_IMAGE_SIZE, config.CONFIDENCE_THRESHOLD = imgsz, conf
                config.DEDUPE_CONTAINMENT, config.SMALL_BOX_CONFIDENCE = dedupe, small
                rows = evaluate(analyze, model, images, cases)
                entry = {"model": model_name, "imgsz": imgsz, "conf": conf,
                         "dedupe": dedupe, "small": small, "rows": rows,
                         "summary": summarize(rows), "hard_mae": hard_case_mae(rows)}
                entries.append(entry)
                print(f"{model_name} imgsz={imgsz} conf={conf} dedupe={dedupe} small={small}: "
                      f"MAE={entry['summary']['mae']:.2f}", flush=True)
    return entries


def write_outputs(entries):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "per_image.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "imgsz", "conf", "dedupe", "small_conf", "filename", "scenario", "expected_count",
                    "detected_count", "signed_error", "absolute_error", "inference_time_ms"])
        for e in entries:
            for r in e["rows"]:
                w.writerow([e["model"], e["imgsz"], e["conf"], e["dedupe"], e["small"], r["filename"], r["scenario"],
                            r["expected_count"], r["detected_count"], r["signed_error"],
                            r["absolute_error"], r["inference_time_ms"]])
    with (OUT_DIR / "summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "model", "imgsz", "conf", "dedupe", "small_conf", "mae", "mean_signed_error", "exact",
                    "exact_pct", "hard_case_mae", "empty_false_positives", "mean_ms"])
        for rank, e in enumerate(sorted(entries, key=rank_key), start=1):
            s = e["summary"]
            w.writerow([rank, e["model"], e["imgsz"], e["conf"], e["dedupe"], e["small"], f"{s['mae']:.2f}",
                        f"{s['mean_signed_error']:+.2f}", s["exact"], f"{s['exact_pct']:.1f}",
                        f"{e['hard_mae']:.2f}", s["empty_false_positives"], f"{s['mean_ms']:.0f}"])


def parse_reference(text):
    try:
        model, imgsz, conf, dedupe, small = text.split(",")
        return (model, int(imgsz), float(conf), float(dedupe), float(small))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected model,imgsz,conf,dedupe,small (e.g. rfdetr-small,0,0.4,0.85,0.3)")


def print_table(entries, top, reference):
    ranked = sorted(entries, key=rank_key)
    base = next((e for e in entries
                 if (e["model"], e["imgsz"], e["conf"], e["dedupe"], e["small"]) == reference), None)
    header = (f"{'#':>3} {'model':<13} {'imgsz':>5} {'conf':>4} {'dedup':>5} {'small':>5} {'MAE':>5} {'signed':>6} "
              f"{'exact':>5} {'hardMAE':>7} {'emptyFP':>7} {'ms':>6}")
    print("\n" + header)
    shown = ranked[:top]
    if base is not None and base not in shown:
        shown.append(base)
    for e in shown:
        s = e["summary"]
        tag = "  <- reference" if e is base else ""
        print(f"{ranked.index(e) + 1:>3} {e['model']:<13} {e['imgsz']:>5} {e['conf']:>4} "
              f"{e['dedupe']:>5} {e['small']:>5} "
              f"{s['mae']:>5.2f} {s['mean_signed_error']:>+6.2f} {s['exact']}/{s['images']:<3} "
              f"{e['hard_mae']:>7.2f} {s['empty_false_positives']:>7} {s['mean_ms']:>6.0f}{tag}")
    print_verdict(entries, base, reference)


def print_verdict(entries, base, reference):
    if base is None:
        print(f"\nReference {reference} not in sweep; no verdict.")
        return
    print(f"\nReference {reference}: MAE={base['summary']['mae']:.2f} "
          f"exact={base['summary']['exact']}/8 {base['summary']['mean_ms']:.0f} ms")
    for model in sorted({e["model"] for e in entries} - {base["model"]}):
        best = min((e for e in entries if e["model"] == model), key=rank_key)
        verdict = "BEATS" if rank_key(best) < rank_key(base) else "does NOT beat"
        print(f"Best {model}: imgsz={best['imgsz']} conf={best['conf']} "
              f"dedupe={best['dedupe']} small={best['small']} "
              f"MAE={best['summary']['mae']:.2f} exact={best['summary']['exact']}/8"
              f"  {best['summary']['mean_ms']:.0f} ms -> {verdict} the reference")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument("--imgsz", nargs="+", type=int,
                   help="image sizes for YOLO models (multiples of 32)")
    p.add_argument("--rfdetr-imgsz", nargs="+", type=int,
                   help="image sizes for RF-DETR models (0 = native; default 0 672 896 1120)")
    p.add_argument("--reference", type=parse_reference, default=BASELINE,
                   help="config to compare against: model,imgsz,conf,dedupe,small "
                        "(default yolo11s.pt,1280,0.5,0,0)")
    p.add_argument("--conf", nargs="+", type=float, default=DEFAULT_CONFS)
    p.add_argument("--dedupe", nargs="+", type=float, default=[0, config.DEDUPE_CONTAINMENT],
                   help="DEDUPE_CONTAINMENT values to try (0 = off)")
    p.add_argument("--small-conf", nargs="+", type=float, default=[0, config.SMALL_BOX_CONFIDENCE],
                   help="SMALL_BOX_CONFIDENCE values to try (0 = off)")
    p.add_argument("--top", type=int, default=10)
    args = p.parse_args()
    try:
        entries = sweep(args.models, args.imgsz, args.rfdetr_imgsz, args.conf, args.dedupe, args.small_conf,
                         args.manifest)
        if not entries:
            raise BenchmarkError("no configuration produced results")
    except BenchmarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    write_outputs(entries)
    print_table(entries, args.top, args.reference)
    print(f"\nWrote {OUT_DIR}/summary.csv and {OUT_DIR}/per_image.csv")


if __name__ == "__main__":
    main()
