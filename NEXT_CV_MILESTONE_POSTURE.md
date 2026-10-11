# Next CV Milestone: Seated vs Standing Detection

## Context

The current classroom CV pipeline can already detect and count people reliably enough for the project.

Current direction:

```text
Camera Module 3
    ↓
Raspberry Pi 5
    ↓
RF-DETR Small person detection
    ↓
aggregate occupancy count
```

The next CV milestone is to estimate whether detected people are:

```text
SEATED
STANDING
UNKNOWN
```

The output must remain **aggregate and privacy-preserving**.

Do not add identity recognition, persistent person tracking, face analysis, or raw image storage.

---

## Goal

Extend the existing people-counting pipeline so each detected person is classified as:

```text
SEATED
STANDING
UNKNOWN
```

Then expose aggregate classroom state:

```text
occupancy
seated_count
standing_count
unknown_count
standing_ratio
```

Example:

```json
{
  "occupancy": 18,
  "seated_count": 14,
  "standing_count": 3,
  "unknown_count": 1,
  "standing_ratio": 0.176
}
```

Where:

```text
standing_ratio = standing_count / occupancy
```

If occupancy is zero:

```text
standing_ratio = 0
```

---

## Important Scope Constraint

Do **not** jump straight to a large pose-estimation architecture unless it is clearly needed.

Start with the simplest approach that can work for this fixed classroom camera.

The implementation should be structured so the posture classifier can later be replaced without changing the rest of the pipeline.

---

## Detection Pipeline

Keep the existing person detector unchanged.

The pipeline should become:

```text
camera frame
    ↓
RF-DETR person detection
    ↓
person bounding boxes
    ↓
posture classification per person
    ↓
SEATED / STANDING / UNKNOWN
    ↓
aggregate classroom state
```

Do not duplicate person detection logic.

---

## Suggested Architecture

Add a dedicated posture component.

Example:

```text
people-counter/
├── main.py
├── detector.py
├── posture.py
├── config.py
├── logger.py
└── ...
```

Suggested interface:

```python
from enum import Enum

class Posture(str, Enum):
    SEATED = "seated"
    STANDING = "standing"
    UNKNOWN = "unknown"


class PostureClassifier:
    def classify(
        self,
        frame,
        bbox,
    ) -> Posture:
        ...
```

The rest of the application should not care how the posture classifier works internally.

---

## First Implementation: Geometry-Based Heuristic

Start with a simple heuristic using the detected person bounding box.

Possible useful signals:

```text
bbox width
bbox height
bbox aspect ratio
bbox bottom position
bbox height relative to image height
bbox height relative to expected person size at that image location
```

Because the camera is fixed, perspective is predictable.

A standing person generally produces a taller visible body box than a seated person at approximately the same image depth.

Do not use one global pixel-height threshold for the entire frame, because people at the back of the classroom are naturally much smaller.

---

## Perspective-Aware Heuristic

Use the vertical image location of the person as a simple depth proxy.

For example:

```text
bbox_bottom_y_normalized
```

can be used to determine whether the person is:

```text
near
middle
far
```

Then use different standing/seated geometry thresholds for each zone.

Example concept only:

```text
near:
    standing if height > near_threshold

middle:
    standing if height > middle_threshold

far:
    standing if height > far_threshold
```

Do not hard-code arbitrary values without making them configurable.

Store thresholds in `config.py`.

---

## Better Option if Geometry Is Not Reliable Enough

If the simple geometry heuristic performs poorly, add a lightweight secondary classifier that receives a crop of each detected person.

Input:

```text
person crop from original frame
```

Output:

```text
SEATED
STANDING
UNKNOWN
```

Keep this as a second stage.

Do not replace the RF-DETR person detector.

Do not train a custom model unless the heuristic clearly fails and there is enough real/synthetic labeled data to justify it.

---

## UNKNOWN Class

The classifier must support:

```text
UNKNOWN
```

Use UNKNOWN when posture cannot be determined reliably.

Examples:

- heavy occlusion
- only head/shoulders visible
- person partially outside frame
- detection box clearly truncated
- geometry falls between seated and standing thresholds
- classifier confidence too low

Do not force every person into seated or standing.

This is important because aggregate posture should be conservative rather than confidently wrong.

---

## Aggregate Output

After classifying all detections:

```python
occupancy = len(detections)
seated_count = ...
standing_count = ...
unknown_count = ...
```

Then:

```python
standing_ratio = (
    standing_count / occupancy
    if occupancy > 0
    else 0.0
)
```

Also consider an optional known-only ratio:

```python
known_count = seated_count + standing_count

standing_ratio_known = (
    standing_count / known_count
    if known_count > 0
    else 0.0
)
```

This may be useful later for break detection.

---

## Preview Overlay

During development, draw posture labels on the existing preview.

Example:

```text
person 0.87 | seated
person 0.81 | standing
person 0.52 | unknown
```

Also show aggregate state:

```text
People: 18
Seated: 14
Standing: 3
Unknown: 1
Standing ratio: 0.18
```

Do not save live camera frames.

---

## Logging

Extend the existing log with posture aggregates.

Example:

```csv
timestamp,people_count,seated_count,standing_count,unknown_count,standing_ratio
2026-10-11T14:32:05+02:00,18,14,3,1,0.176
```

Keep the existing logging interval.

Do not log per-person identities.

Do not persist bounding boxes unless explicitly enabled for benchmark/debug use.

---

## Benchmarking

Create a small posture benchmark.

Do not reuse the current occupancy benchmark as if it automatically provides posture ground truth.

Add explicit posture ground truth for test images.

Suggested manifest:

```csv
filename,expected_occupancy,expected_seated,expected_standing,expected_unknown
```

Example:

```csv
05_seated.png,5,5,0,0
13_mixed.png,13,9,4,0
```

If the exact generated posture in a synthetic image is ambiguous, mark ambiguous people as unknown rather than inventing labels.

---

## Metrics

For the aggregate benchmark, report at least:

```text
seated_count_error
standing_count_error
unknown_count_error
standing_ratio_error
```

If per-person ground-truth posture boxes are later available, also report:

```text
posture classification accuracy
standing precision
standing recall
seated precision
seated recall
```

Do not overcomplicate the first version.

---

## Real-World Validation

Synthetic images are useful for development but should not be treated as authoritative real-world accuracy.

If possible, validate with a small number of real classroom frames containing a few volunteers in:

```text
seated positions
standing positions
mixed positions
partial occlusion
front / middle / back rows
```

Even a small real set is more valuable than a large synthetic-only posture benchmark.

---

## Temporal Smoothing

Do not add complex tracking.

However, aggregate smoothing is allowed.

For example:

```text
standing_ratio_smoothed
```

can use:

```text
median of last 3–5 samples
```

or a simple EMA.

Do not smooth individual identities across frames.

---

## Break-Detection Preparation

This milestone should expose enough aggregate state for later break detection.

Do **not** implement break detection yet.

Future logic may use:

```text
occupancy
standing_ratio
standing_ratio_smoothed
activity_level
```

Example later:

```text
if occupancy > minimum
and standing_ratio rises sharply
and remains elevated:
    likely_break_start
```

But keep that out of this task.

---

## Non-Goals

Do not add:

- persistent tracking
- face recognition
- person re-identification
- skeletal pose tracking unless clearly needed
- break detection
- MQTT
- BLE
- dashboard
- database changes
- raw image storage
- custom model training unless justified by failed heuristics

---

## Acceptance Criteria

This milestone is complete when:

1. existing person detection still works unchanged
2. each detected person receives one of:
   - `SEATED`
   - `STANDING`
   - `UNKNOWN`
3. aggregate seated/standing/unknown counts are produced
4. standing ratio is calculated
5. preview shows posture labels during development
6. aggregate posture values are logged
7. ambiguous detections can become UNKNOWN
8. the implementation does not use persistent identities
9. no live frames are stored
10. a small posture benchmark can be run separately from the occupancy benchmark

---

## Implementation Priority

Implement in this order:

```text
1. clean posture-classifier interface
2. perspective-aware geometry heuristic
3. aggregate counts and ratios
4. benchmark
5. only if needed: lightweight crop-based classifier
```

Do not start with the most complex solution.

The objective is a robust aggregate classroom signal, not perfect human-pose understanding.
