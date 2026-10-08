# People Counter MVP

Counts the people visible to a Raspberry Pi camera and appends the aggregate
count to a CSV every 5 seconds. Anonymous by design: **no images or video are
saved, no per-person data or IDs are stored.** Only `timestamp,people_count`.

## Hardware
Raspberry Pi 5, Raspberry Pi OS 64-bit (Desktop), Raspberry Pi Camera Module.

## Setup (on the Pi)
```bash
git clone <this repo> && cd classr
./setup.sh
```
`setup.sh` installs the apt packages (`python3-picamera2`, `python3-opencv`),
creates `.venv` (with system site packages), installs `rfdetr` + `ultralytics` + `numpy`,
downloads the model set in `config.py` (RF-DETR small), and checks the camera. Needs internet once.

## Camera sanity check
```bash
rpicam-hello --list-cameras
rpicam-hello -t 0
```

## Run
```bash
./run.sh               # with live preview (needs the Pi desktop)
./run.sh --no-preview  # headless / over SSH
```
Press `Ctrl+C` to stop; the camera and windows are released cleanly.

## Output
`data/people_count.csv`, ISO 8601 timestamps, appended across restarts:
```csv
timestamp,people_count
2026-10-06T15:30:00+02:00,4
```

## Configuration (`config.py`)
- `CONFIDENCE_THRESHOLD = 0.5` — minimum detection confidence
- `LOG_INTERVAL_SECONDS = 5` — logging interval (monotonic time, independent of FPS)

## Tests
```bash
pip install pytest && pytest
```

## Troubleshooting
- `ModuleNotFoundError: picamera2` — the venv must be created with `--system-site-packages` (setup.sh does this).
- `cv2` import/numpy errors — `pip uninstall opencv-python opencv-python-headless` to use the apt OpenCV.
- No preview window over SSH — use `--no-preview`.

## Benchmark (offline detector test)
Runs the **same detector as the live app** (`detector.py`, same `config.py` settings)
over static images with known people counts. No camera needed.

```bash
./run_benchmark.sh                                   # uses benchmark/manifest.csv
./run_benchmark.sh --manifest path/to/manifest.csv
```
(`run_benchmark.sh` activates `.venv` and calls `python benchmark.py`.)

- **Input:** `benchmark/manifest.csv` (`filename,expected_count,scenario`) and the images in `benchmark/images/`. Add the images listed in the manifest there; the run fails with a clear error if any is missing.
- **Output:** `benchmark/results/results.csv` (overwritten each run) and annotated `benchmark/results/*_detected.png`.
- **Console:** one line per image, then MAE, max error, exact-count accuracy and mean inference time.

Use it to compare detector settings (model, confidence, image size) and find failure
cases: distant people, partial occlusion, dense seating, standing/mixed scenes.

**Note:** the benchmark uses synthetic/static images. Its numbers must not be presented
as real-world classroom accuracy. Annotated benchmark images may be saved; this does not
change the rule that live camera frames are never persisted.

## RF-DETR backend (optional, for benchmarking)
Set `MODEL_NAME = "rfdetr-small"` (or `rfdetr-nano` / `rfdetr-medium`) in `config.py`, or
sweep it: `./sweep_benchmark.sh --models yolo11s.pt rfdetr-small --conf 0.4 0.5 0.6`.
Install the extra dependency first: `pip install -r requirements-rfdetr.txt`.
For RF-DETR, `INFERENCE_IMAGE_SIZE = 0` means the model's native resolution; other values
are rounded to the nearest size the model accepts.

### Checking for false positives
`./run_benchmark.sh` saves every benchmark image with its boxes and confidence scores to
`benchmark/results/<name>_detected.png`. Open them to check for false positives (boxes on
chairs, bags, laptops) and misses. In these images **green** boxes were counted and **orange** boxes are candidates that were
rejected (low confidence, or a duplicate of a higher-scoring box). Only the static benchmark images are saved; the live app
still never saves camera frames.

### Post-filtering rules (`config.py`)
- `SMALL_BOX_CONFIDENCE` / `SMALL_BOX_HEIGHT_FRACTION`: small (far-away) boxes are accepted at a lower confidence than `CONFIDENCE_THRESHOLD`. `0` disables.
- `DEDUPE_CONTAINMENT`: a box is dropped when this fraction of it lies inside a higher-scoring box. `0` disables.
- Compare variants: `./sweep_benchmark.sh --models rfdetr-small --rfdetr-imgsz 0 --conf 0.4 --dedupe 0 0.85 --small-conf 0 0.3`.

## Capturing test frames from the real camera (`--save-frame`)
Opt-in mode for building benchmark images from the mounted camera. It saves raw still frames
and exits; nothing is detected or logged, and normal runs never save images.
```bash
./run.sh --save-frame                       # one frame after a 10 s countdown
./run.sh --save-frame --delay 20 --count 5 --interval 4
```
Frames are saved at the full sensor resolution (4608×2592, `CAPTURE_RESOLUTION`), roughly 20 MB each as PNG, so keep `--count` modest. For benchmark cases, export the finished image at 1536×864 (the live `CAMERA_RESOLUTION`) so the benchmark matches the live pipeline.
Frames go to `captures/` (git-ignored; they contain images of people, so delete them when done).
To use one as a benchmark case: copy it to `benchmark/images/`, add a row to
`benchmark/manifest.csv` with the count you verified by eye, and re-run the benchmark.
Copy from the Pi with e.g. `scp classr@classr.local:/home/classr/classr/captures/*.png ~/Downloads/captures/`.

## Comparing detector models
Same rules (confidence, small-box, duplicate filter) apply to every backend. Compare at similar
cost per frame (~1 s on the Pi): `--imgsz` is for YOLO, `--rfdetr-imgsz` for RF-DETR (0 = native 512),
and `--reference` is the config the others are judged against. Numbers first:
```bash
./sweep_benchmark.sh --models rfdetr-small yolo11s.pt yolo26s.pt yolo11n.pt yolo26n.pt \
  --rfdetr-imgsz 0 --imgsz 512 640 768 --conf 0.3 0.4 0.5 --dedupe 0.85 --small-conf 0 0.3 \
  --reference rfdetr-small,0,0.4,0.85,0.3
```
Then annotated images for a chosen setting, one folder per model so nothing is overwritten:
```bash
./run_benchmark.sh --model yolo11s.pt --imgsz 640 --conf 0.4 --out-dir benchmark/results/yolo11s
./run_benchmark.sh --model yolo26s.pt --imgsz 640 --conf 0.4 --out-dir benchmark/results/yolo26s
```

## NCNN export (faster inference on the Pi)
NCNN usually runs YOLO faster than PyTorch on the Pi's CPU. The exported model has a fixed
input size, so it is exported at `INFERENCE_IMAGE_SIZE` and must be re-exported if you change
the model or size. On the Pi:
```bash
source .venv/bin/activate
python export_ncnn.py                 # creates e.g. yolo26s_ncnn_model/ (needs internet once for pnnx/ncnn)
./run_benchmark.sh --model yolo26s_ncnn_model --out-dir benchmark/results/yolo26s_ncnn
./test_composites.sh --model yolo26s_ncnn_model --out-dir benchmark/results/composites_ncnn
```
Check that the counts match the PyTorch runs and compare the mean inference time, then set
`MODEL_NAME = "yolo26s_ncnn_model"` in `config.py`.
