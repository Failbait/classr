# Revised CV Milestone: Activity / Movement Before Posture

## Decision

Do **not** prioritize seated-vs-standing classification yet.

For the project's actual goal — detecting likely class breaks or collective activity changes — temporal movement of detected people is a more direct and useful signal than trying to infer posture from a single frame.

Keep posture as optional later work.

---

## Why

A single-frame seated/standing heuristic is fragile because:

- people are partially hidden by desks
- bounding-box height depends heavily on distance from the camera
- seated people can lean, stretch, or turn
- standing people can be partially occluded
- synthetic benchmark images make posture geometry less trustworthy

Movement is more directly related to the event we care about:

```text
students getting up
students walking
students returning to seats
collective transition into/out of a break
```

Therefore the next CV output should be aggregate activity rather than posture.

---

## Goal

Extend the existing person-detection pipeline so it produces:

```text
occupancy
moving_count
moving_ratio
activity_score
```

Optionally also expose:

```text
stable_count
```

Example:

```json
{
  "occupancy": 18,
  "moving_count": 11,
  "moving_ratio": 0.61,
  "activity_score": 0.73
}
```

The result should remain aggregate and privacy-preserving.

---

## Important Privacy Constraint

Do not add persistent identity tracking.

Short-lived frame-to-frame matching is acceptable only for estimating motion.

Do not:

- identify people
- store names
- persist person IDs
- perform face recognition
- perform re-identification

Any temporary track identifier must exist only in memory and expire quickly.

---

## Pipeline

Keep the existing detector unchanged.

Use:

```text
camera frame
    ↓
RF-DETR person detections
    ↓
current bounding boxes
    ↓
match boxes to previous frame(s)
    ↓
measure displacement / geometry change
    ↓
aggregate movement signal
```

---

## Frame-to-Frame Matching

Use simple short-term matching.

Preferred first implementation:

```text
IoU + centroid distance
```

For each detection in the current frame, find the most plausible detection from the previous frame.

A match should only be accepted if it satisfies configurable limits such as:

```text
minimum IoU
and/or
maximum normalized centroid distance
```

Do not introduce a full tracking framework unless this simple method proves insufficient.

Hungarian assignment may be used if convenient, but keep the implementation small.

---

## Motion Per Person

For each matched detection calculate:

```text
centroid displacement
bbox width change
bbox height change
bbox area change
```

Normalize centroid displacement by the person's bounding-box size so that a person in the back of the classroom is comparable to someone close to the camera.

Example:

```python
normalized_motion = centroid_distance / max(bbox_width, bbox_height)
```

This is more useful than raw pixel displacement.

---

## Movement Classification

Classify each matched person temporarily as:

```text
MOVING
STABLE
```

Use a configurable threshold.

Example concept:

```python
if normalized_motion > MOTION_THRESHOLD:
    moving = True
```

Do not hard-code the final threshold until it is tested.

---

## Temporal Window

Do not base activity on only one pair of frames.

Maintain a short rolling window, for example:

```text
3–10 seconds
```

The system may run person detection around:

```text
1–3 FPS
```

for activity estimation.

This does not need video-rate inference.

Use a rolling median or EMA to make the aggregate activity signal stable.

---

## Aggregate Metrics

For each update calculate:

```text
occupancy
matched_count
moving_count
moving_ratio
activity_score
```

Where:

```text
moving_ratio = moving_count / matched_count
```

if at least one person is matched.

Do not divide by total occupancy if many detections are unmatched due to scene transitions.

---

## Activity Score

Start simple.

A useful first version:

```text
activity_score = smoothed moving_ratio
```

Optionally include normalized movement magnitude:

```text
activity_score =
    weighted combination of:
    - moving_ratio
    - mean normalized displacement
```

Keep the result in:

```text
0.0 – 1.0
```

Do not over-engineer the formula.

---

## Scene Transitions

Collective standing/walking may cause temporary detection matching failures.

Treat a sudden increase in:

```text
unmatched detections
```

as additional evidence of activity rather than automatically discarding the frame.

However, keep this secondary to matched-box motion.

---

## Optional Optical Flow

Do not use optical flow in the first implementation.

If bounding-box motion proves too coarse, a later improvement may calculate optical flow or frame-difference energy inside person bounding boxes.

Do not add this unless needed.

---

## Preview

During development show:

```text
People: 18
Moving: 11
Moving ratio: 0.61
Activity: 0.73
```

Optionally draw a small movement vector or label on matched boxes.

Do not store live preview frames.

---

## Logging

Extend the aggregate log with:

```csv
timestamp,people_count,moving_count,moving_ratio,activity_score
2026-10-11T14:32:05+02:00,18,11,0.611,0.73
```

Do not persist temporary track IDs.

---

## Break Detection Preparation

This milestone should prepare the later break detector.

A likely later rule could use:

```text
occupancy
activity_score
moving_ratio
```

Example concept:

```text
if occupancy > minimum
and activity_score rises sharply
and remains high for several seconds:
    possible break transition
```

A break can later be confirmed by observing activity falling again after the transition.

Do not implement final break detection in this milestone.

---

## Posture Detection

Seated-vs-standing classification becomes optional.

Only add posture later if:

- movement alone cannot distinguish relevant states
- the report benefits from an additional standing-ratio signal
- real-world tests show that posture improves break detection

If posture is later added, combine it with activity rather than replacing activity.

---

## Non-Goals

Do not add:

- persistent tracking
- face recognition
- re-identification
- pose estimation
- posture classification
- optical flow in v1
- MQTT
- BLE
- dashboard
- final break-event logic

---

## Acceptance Criteria

This milestone is complete when:

1. existing RF-DETR person detection remains unchanged
2. detections are matched across adjacent frames
3. matched people receive a normalized motion measurement
4. aggregate moving count is produced
5. moving ratio is produced
6. activity score is produced
7. activity is smoothed over a short temporal window
8. no persistent identities are created
9. live frames are not stored
10. output can be logged alongside occupancy

---

## Recommended Order

Implement in this order:

```text
1. previous-frame detection buffer
2. IoU / centroid matching
3. normalized centroid displacement
4. MOVING / STABLE classification
5. aggregate moving ratio
6. smoothed activity score
7. test on short real video clips
```

The objective is to detect aggregate classroom activity, not to track individuals.
