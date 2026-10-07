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
creates `.venv` (with system site packages), installs `ultralytics` + `numpy`,
downloads the `yolo11n.pt` model, and checks the camera. Needs internet once.

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
