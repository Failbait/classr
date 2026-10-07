# Benchmark Testing Mode for People Counter

## Goal

Add an offline benchmark/testing mode to the existing Raspberry Pi people-counting project.

The benchmark mode must evaluate the exact same person detector used by the live camera application against a small set of static classroom images with known expected people counts.

The purpose is to make detector changes measurable instead of subjective.

Do not duplicate detection logic. The benchmark runner must call the existing detector implementation directly.

---

## Scope

Add:

- a `benchmark/` folder
- a `manifest.csv`
- a `benchmark.py` runner
- annotated benchmark output images
- a `results.csv`
- aggregate summary metrics printed to the console

Do not change the live camera behavior unless required to make the detector reusable.

Do not add tracking, databases, MQTT, dashboards, or custom training.

---

## Suggested Structure

Use something like:

```text
people-counter/
├── benchmark/
│   ├── images/
│   │   ├── 00_empty.png
│   │   ├── 05_seated.png
│   │   ├── 10_seated.png
│   │   ├── 12_back_rows.png
│   │   ├── 15_seated.png
│   │   ├── 15_mixed.png
│   │   ├── 18_occluded.png
│   │   └── 20_seated.png
│   ├── results/
│   └── manifest.csv
├── benchmark.py
├── detector.py
├── camera.py
├── logger.py
├── config.py
└── main.py
```

If the current project structure differs, adapt this to the existing layout rather than forcing an unnecessary reorganization.

---

## Ground Truth Manifest

Create:

```text
benchmark/manifest.csv
```

Format:

```csv
filename,expected_count,scenario
00_empty.png,0,empty
05_seated.png,5,sparse
10_seated.png,10,normal
12_back_rows.png,12,distant
15_seated.png,15,normal
15_mixed.png,15,mixed_standing
18_occluded.png,18,occlusion
20_seated.png,20,dense
```

The expected count must be treated as explicit ground truth provided by the manifest.

Do not try to infer the expected count from filenames.

---

## Reuse Existing Detector

The benchmark runner must use the same detection path as the live application.

For example, if the live application currently does:

```python
detections = detector.detect(frame)
```

the benchmark must do the same:

```python
image = cv2.imread(path)
detections = detector.detect(image)
```

Do not reimplement:

- model loading
- class filtering
- confidence filtering
- person counting
- bounding box parsing

inside `benchmark.py`.

If `detector.py` currently mixes detection logic with preview rendering or camera-specific code, refactor it minimally so the detector can accept an arbitrary image/frame and return structured detection results.

---

## Detector Result Shape

Prefer a reusable result format such as:

```python
[
    {
        "bbox": (x1, y1, x2, y2),
        "confidence": 0.87,
        "class_name": "person",
    },
    ...
]
```

The exact internal structure can differ if the project already has one.

The benchmark only needs to be able to determine:

```text
detected_count = number of valid person detections
```

---

## Benchmark Runner

Create:

```text
benchmark.py
```

It must:

1. Load the detector once.
2. Read `benchmark/manifest.csv`.
3. Process every image listed in the manifest.
4. Measure inference time for each image.
5. Count detected people.
6. Compare detected count with expected count.
7. Save an annotated result image.
8. Write one row to `benchmark/results/results.csv`.
9. Print a summary after all images have been processed.

Do not reload the model for every image.

---

## Per-Image Metrics

For each benchmark image calculate:

```text
expected_count
detected_count
signed_error
absolute_error
inference_time_ms
```

Where:

```text
signed_error = detected_count - expected_count
absolute_error = abs(detected_count - expected_count)
```

For non-zero expected counts, also calculate:

```text
percentage_error
```

as:

```text
absolute_error / expected_count * 100
```

For the empty-room case, percentage error should be blank/null rather than dividing by zero.

---

## Results CSV

Create:

```text
benchmark/results/results.csv
```

Example:

```csv
filename,scenario,expected_count,detected_count,signed_error,absolute_error,percentage_error,inference_time_ms
00_empty.png,empty,0,0,0,0,,118.4
05_seated.png,sparse,5,5,0,0,0.0,121.7
10_seated.png,normal,10,9,-1,1,10.0,119.2
```

Overwrite the benchmark results file on each benchmark run.

This is test output, unlike the live occupancy log, so preserving every historical benchmark run is not required for the MVP.

---

## Annotated Output Images

Save annotated images to:

```text
benchmark/results/
```

For example:

```text
00_empty_detected.png
05_seated_detected.png
10_seated_detected.png
```

Each annotated image should show:

- person bounding boxes
- confidence score for each detection
- detected count
- expected count
- signed error

Example overlay:

```text
Expected: 15
Detected: 13
Error: -2
```

These images are for debugging the synthetic benchmark and may be saved.

Do not change the live application privacy rule that real camera frames are not persisted.

---

## Aggregate Metrics

At the end of a benchmark run, print:

### Mean Absolute Error

```text
MAE = mean(abs(detected_count - expected_count))
```

### Maximum Absolute Error

```text
max(abs(detected_count - expected_count))
```

### Exact Count Accuracy

```text
number of images where detected_count == expected_count
/
total number of benchmark images
```

Print both fraction and percentage.

Example:

```text
Benchmark complete

Images tested:         8
Mean absolute error:   1.38 people
Maximum error:         4 people
Exact-count accuracy:  3/8 (37.5%)
Mean inference time:   124.6 ms
```

Also print mean inference time.

---

## Console Output During Run

Print one concise line per test image.

Example:

```text
[1/8] 00_empty.png       expected=0   detected=0   error=+0   117.2 ms
[2/8] 05_seated.png      expected=5   detected=5   error=+0   121.8 ms
[3/8] 10_seated.png      expected=10  detected=9   error=-1   119.4 ms
```

This should make it easy to inspect results without opening the CSV.

---

## Configuration

The benchmark must use the same detector configuration as the live application, including:

- model
- confidence threshold
- inference image size
- person-class filtering

Do not define a second set of detector parameters in `benchmark.py`.

Use the existing `config.py` or detector configuration source.

This is important because benchmark results should represent the configuration actually used by the application.

---

## Timing

Measure only detector inference/processing time, not:

- image file loading
- annotation drawing
- CSV writing

Use:

```python
time.perf_counter()
```

or another monotonic high-resolution timer.

---

## Error Handling

The benchmark should fail clearly if:

- `manifest.csv` is missing
- a referenced image does not exist
- an image cannot be loaded
- the detector cannot initialize

Do not silently skip missing images unless explicitly requested.

A malformed row should report which row/file caused the issue.

---

## Optional CLI

If it fits cleanly, support:

```bash
python benchmark.py
```

Optionally support:

```bash
python benchmark.py --manifest benchmark/manifest.csv
```

Do not add a large CLI framework for this.

---

## README Update

Add a short benchmark section to the README explaining:

### How to run

```bash
python benchmark.py
```

### Input

```text
benchmark/manifest.csv
benchmark/images/
```

### Output

```text
benchmark/results/results.csv
benchmark/results/*_detected.png
```

### Purpose

Explain that this benchmark uses synthetic/static classroom images to compare detector configurations and identify failure cases such as:

- distant people
- partial occlusion
- dense seating
- standing/mixed scenes

Also clearly state that synthetic benchmark performance must not be presented as real-world classroom accuracy.

---

## Acceptance Criteria

The benchmark feature is complete when:

1. `python benchmark.py` runs without using the camera.
2. It loads the detector only once.
3. It reads all test cases from `manifest.csv`.
4. It uses the exact same detector implementation as the live app.
5. It calculates detected count for every image.
6. It compares detected count against expected count.
7. It saves annotated output images.
8. It writes `benchmark/results/results.csv`.
9. It prints MAE.
10. It prints maximum absolute error.
11. It prints exact-count accuracy.
12. It prints mean inference time.
13. Missing benchmark files produce clear errors.
14. No detection logic is duplicated in `benchmark.py`.

---

## Important Design Constraint

The benchmark exists to evaluate detector changes.

Therefore the architecture should remain:

```text
Live camera frame ───────┐
                         ▼
                    detector.py
                         │
                         ▼
                    people count


Benchmark image ─────────┐
                         ▼
                    detector.py
                         │
                         ▼
                 compare with ground truth
```

There must be one detector implementation, not separate live and benchmark detectors.
