"""Export the detector's person boxes for the benchmark images to a JSON test fixture.

Run on the Pi (needs the model), commit the result. tests/test_activity_fixtures.py then replays
these realistic box layouts with synthetic motion, without needing YOLO. Boxes only, no images.
"""

import argparse
import json
from pathlib import Path

DEFAULT_DIRS = ["benchmark/images", "benchmark_composites/images"]
DEFAULT_OUT = "tests/fixtures/benchmark_boxes.json"


def export(image_dirs, out_path):
    import cv2
    from detector import detect_people, load_model

    model = load_model()
    entries = []
    for directory in image_dirs:
        for path in sorted(Path(directory).glob("*.png")):
            image = cv2.imread(str(path))
            if image is None:
                raise SystemExit(f"Could not load image: {path}")
            detections = detect_people(model, image)
            entries.append({
                "filename": path.name,
                "width": image.shape[1],
                "height": image.shape[0],
                "detections": [{"bbox": list(d["bbox"]), "confidence": round(d["confidence"], 3)}
                               for d in detections],
            })
            print(f"{path.name:<28} {len(detections)} boxes")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, indent=1))
    print(f"\nWrote {len(entries)} images to {out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dirs", nargs="+", default=DEFAULT_DIRS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    export(args.dirs, args.out)


if __name__ == "__main__":
    main()
