# Updated CV Spec: Activity-First Break Detection with YOLO26s

## Context

The current detector is:

```text
YOLO26s
```

It already provides person detections and occupancy counts.

The next CV goal is **not** to understand human posture perfectly. The actual project requirement is to estimate when a classroom transitions into or out of a break.

For that use case, the primary new CV signal should be **aggregate movement/activity over time**.

Seated-vs-standing classification may still be useful later, but it should be treated as an optional secondary signal rather than the next mandatory milestone.

---

## Architectural Decision

Use this pipeline:

```text
Camera Module 3
    ↓
YOLO26s person detection
    ↓
short-lived frame-to-frame box matching
    ↓
per-detection motion estimation
    ↓
aggregate classroom activity
    ↓
later: break-state inference
```

Do **not** prioritize posture classification before this activity signal is tested.

The reason is application-driven:

```text
break detection is fundamentally a temporal state-change problem
```

The useful events are things like:

```text
many students getting up
many students walking
students leaving their places
students returning
activity settling again
```

Those are directly observable from temporal motion.

A single-frame seated/standing classifier answers a different question:

```text
"What posture does this person appear to have right now?"
```

That can be useful, but it is less directly tied to the event we need to detect.

---

## Why Activity Comes Before Posture

### Activity is directly related to the target event

A class break normally creates a strong temporal transition:

```text
low activity
→ sudden collective activity
→ sustained movement
→ possibly lower occupancy / changed positions
→ activity falls again
```

That pattern is useful even if some people remain seated or a standing person does not move much.

### Posture is more fragile in this camera setup

Single-frame seated/standing inference is difficult because:

- desks occlude lower bodies
- distance changes visible person size substantially
- seated people can lean or stretch
- standing people can be partially hidden
- a bounding box is not a reliable proxy for full body geometry
- perspective changes across the classroom
- the current benchmark images are synthetic composites

A perspective-aware posture heuristic is possible, but it introduces several assumptions that are not necessary to test break transitions.

### Activity can remain detector-agnostic

The activity layer should consume generic person detections.

It must not depend on YOLO26s-specific internals.

That gives this separation:

```text
detector
    ↓
generic boxes
    ↓
activity estimator
```

If the detector changes later, the activity system does not need to be rewritten.

---

# Goal

Add an aggregate activity estimator that exposes:

```text
occupancy
matched_count
moving_count
moving_ratio
mean_motion
activity_score
```

Example:

```json
{
  "occupancy": 18,
  "matched_count": 17,
  "moving_count": 11,
  "moving_ratio": 0.647,
  "mean_motion": 0.182,
  "activity_score": 0.71
}
```

The activity layer must remain privacy-preserving.

Do not create persistent identities.

---

# Existing Detector

Keep the current YOLO26s detection path unchanged unless a small interface cleanup is required.

Conceptually:

```python
detections = detector.detect(frame)
```

The activity module should consume results such as:

```python
[
    {
        "bbox": (x1, y1, x2, y2),
        "confidence": 0.87,
    },
    ...
]
```

Do not duplicate YOLO inference logic in the activity module.

---

# New Module

Add a dedicated activity component.

For example:

```text
people-counter/
├── main.py
├── detector.py
├── activity.py
├── logger.py
├── config.py
└── ...
```

Suggested interface:

```python
class ActivityEstimator:
    def update(self, detections, timestamp):
        ...
```

Returning something like:

```python
@dataclass
class ActivityState:
    occupancy: int
    matched_count: int
    moving_count: int
    moving_ratio: float
    mean_motion: float
    activity_score: float
```

---

# Matching Across Frames

Use short-lived frame-to-frame matching only.

Do not implement persistent identity tracking.

Start with:

```text
IoU
+
normalized centroid distance
```

For each detection in the current frame, match it to the most plausible previous detection.

A detection pair may be considered a candidate match based on configurable conditions such as:

```text
minimum IoU
maximum centroid distance
```

If several assignments compete, use one-to-one assignment.

Hungarian matching is acceptable if convenient, but do not introduce a large tracking framework solely for this.

---

# Motion Measurement

For every matched person calculate:

```text
centroid displacement
bbox width change
bbox height change
bbox area change
```

The primary motion value should be normalized for person scale.

For example:

```python
motion = centroid_distance / max(previous_box_width, previous_box_height)
```

This is important because:

```text
10 px movement for a small back-row person
```

can be much more significant than:

```text
10 px movement for a large foreground person
```

Do not use raw pixel displacement as the only measure.

---

# Moving vs Stable

Each matched person can temporarily be classified as:

```text
MOVING
STABLE
```

using a configurable normalized-motion threshold.

Example concept:

```python
moving = normalized_motion >= MOTION_THRESHOLD
```

Do not hard-code a final threshold from intuition.

The threshold must be tunable in `config.py`.

---

# Detector Jitter

The system must distinguish real movement from normal bounding-box jitter.

A stationary classroom must not appear active simply because YOLO26s shifts boxes by a few pixels between frames.

Therefore test explicitly against small perturbations such as:

```text
1–3% of bounding-box dimensions
```

and choose thresholds that keep this activity low.

---

# Temporal Smoothing

Activity should not depend on a single pair of frames.

Maintain a short window such as:

```text
3–10 seconds
```

Use a simple smoothing method:

```text
EMA
```

or:

```text
rolling median
```

The objective is stable aggregate activity, not individual trajectories.

---

# Update Rate

The existing detector does not need to run at video frame rate.

A target around:

```text
1–3 detections per second
```

is enough to begin testing activity.

Do not optimize for 30 FPS.

The exact sampling rate should remain configurable.

---

# Aggregate Signals

Calculate:

```text
occupancy
matched_count
moving_count
moving_ratio
mean_motion
```

Where:

```python
moving_ratio = (
    moving_count / matched_count
    if matched_count > 0
    else 0.0
)
```

Do not divide by total occupancy when a large number of detections are unmatched.

---

# Activity Score

Start with a simple score.

A first implementation may use:

```text
activity_score = smoothed moving_ratio
```

A slightly richer version may combine:

```text
moving_ratio
+
mean normalized motion
```

For example conceptually:

```python
activity_score = clamp(
    W_RATIO * moving_ratio
    + W_MOTION * normalized_mean_motion,
    0.0,
    1.0,
)
```

Keep weights configurable.

Do not over-engineer this.

---

# Unmatched Detections

People entering, leaving, standing up into visibility, or becoming occluded may create unmatched boxes.

Treat a sudden increase in:

```text
new detections
lost detections
```

as a possible secondary activity signal.

Do not make unmatched detections the primary activity calculation.

Track aggregate counts such as:

```text
new_count
lost_count
```

if useful.

---

# Privacy Constraints

This system must not perform persistent tracking.

Allowed:

```text
temporary in-memory matching between adjacent or recent frames
```

Not allowed:

```text
persistent person IDs
face recognition
re-identification
identity storage
person-specific historical trajectories
```

Any temporary matching state should expire quickly.

---

# Preview

During development, show aggregate activity:

```text
People: 18
Matched: 17
Moving: 11
Moving ratio: 0.65
Activity: 0.71
```

Optionally show:

```text
stable / moving
```

labels or short movement vectors for debugging.

Do not save live frames.

---

# Logging

Extend aggregate logging with:

```csv
timestamp,people_count,matched_count,moving_count,moving_ratio,mean_motion,activity_score
2026-10-11T14:32:05+02:00,18,17,11,0.647,0.182,0.71
```

Do not log temporary IDs.

---

# Testing Strategy

The current benchmark images are static composite images.

Do not generate fake AI video sequences as the primary test.

AI-generated sequential frames can introduce:

- changing body anatomy
- changing clothing detail
- changing furniture
- inconsistent occlusion
- artificial detector instability

Instead, test the activity module separately from YOLO26s.

---

## Test Layer 1: Deterministic Box Sequences

Create synthetic bounding-box sequences directly.

Examples:

### Stable

```text
frame 1: boxes
frame 2: same boxes with tiny jitter
frame 3: same boxes with tiny jitter
```

Expected:

```text
moving_ratio near zero
activity low
```

### One moving person

```text
17 stable
1 moved clearly
```

Expected:

```text
low moving_ratio
low aggregate activity
```

### Small group

```text
13 stable
5 moving
```

Expected:

```text
moderate activity
```

### Break-like transition

```text
3 stable
15 moving
```

Expected:

```text
high moving ratio
high activity
```

### Entering / leaving

Add or remove several boxes across frames.

Expected:

```text
new/lost counts rise
activity should reflect the transition
```

---

## Test Layer 2: Use Real YOLO26s Boxes from Composite Images

Export detections from the current composite benchmark to JSON.

Example:

```json
{
  "filename": "18_seated.png",
  "detections": [
    {
      "bbox": [100, 120, 170, 310],
      "confidence": 0.82
    }
  ]
}
```

Use these boxes as realistic starting geometry.

Then generate test frames by shifting only the boxes.

Example:

```text
frame 0: original detections
frame 1: tiny jitter
frame 2: 2 people move
frame 3: 8 people move
frame 4: most people move
```

This tests movement logic using realistic classroom box sizes and perspective without requiring fake video imagery.

---

## Perspective-Preserving Synthetic Motion

Scale synthetic displacement by bounding-box size.

Example:

```python
dx = bbox_width * movement_fraction
dy = bbox_height * movement_fraction
```

Suggested test magnitudes:

```text
jitter:           0.00–0.03
small movement:   0.05–0.10
clear movement:   0.15–0.30
large movement:   0.30+
```

These values are test fixtures, not final runtime thresholds.

---

# Real-World Sanity Test

After deterministic testing works, validate with a short real clip.

A full classroom is not required.

One person can test:

```text
sit still
stand up
walk
stop
sit again
```

Then repeat with 2–3 people if practical.

This test is only intended to verify that:

```text
real detector jitter
real motion
real occlusion
```

behave roughly as expected.

---

# Break Detection Comes After Activity

Do not implement final break detection in this task.

This milestone should expose the signals needed later:

```text
occupancy
moving_ratio
activity_score
new_count
lost_count
```

A later break detector can evaluate transitions such as:

```text
stable classroom
→ rapid activity increase
→ sustained activity
→ settling into a new state
```

The break logic should be implemented as a separate state machine.

---

# Posture Detection

Do not delete the idea of seated-vs-standing detection.

Treat it as an optional later enhancement.

Add it only if real testing shows that activity alone cannot distinguish the states we care about.

If posture is later implemented, it should become an additional signal:

```text
activity_score
standing_ratio
occupancy
```

rather than replacing activity.

---

# Non-Goals

Do not add in this milestone:

```text
persistent tracking
person re-identification
face recognition
pose estimation
seated/standing classification
optical flow
break state machine
MQTT
BLE
database
dashboard
```

---

# Acceptance Criteria

This milestone is complete when:

1. YOLO26s person detection remains the existing detector.
2. The activity module is detector-agnostic.
3. Detections can be matched across adjacent/recent frames.
4. Motion is normalized for bounding-box scale.
5. Small detector jitter does not produce high activity.
6. Moving count is produced.
7. Moving ratio is produced.
8. Mean motion is produced.
9. A smoothed activity score is produced.
10. Entering/leaving detections are handled sensibly.
11. No persistent identities are created.
12. No live frames are stored.
13. Activity logic can be unit-tested without YOLO26s.
14. Existing composite-image detections can be used as realistic test fixtures.
15. One short real-world clip can be used as a final sanity check.

---

# Implementation Order

Implement in this order:

```text
1. detector-independent activity interface
2. previous-frame / short-window detection buffer
3. one-to-one box matching
4. normalized motion metric
5. jitter threshold
6. MOVING / STABLE decision
7. moving ratio
8. smoothed activity score
9. deterministic box tests
10. composite-box fixtures
11. short real-world sanity test
```

Do not start with posture classification.

The design objective is to measure **collective classroom state transitions**, not to perfectly classify individual human poses.
