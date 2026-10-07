# Next Detector Benchmark Step

## What the YOLO11 sweep shows

The current YOLO11 benchmark strongly suggests that the best configuration tested so far is:

```text
model: yolo11s.pt
imgsz: 1280
confidence: 0.50
```

Results:

```text
Mean absolute error:    1.00 people
Exact-count accuracy:   4/8 (50.0%)
Mean inference time:    258.8 ms
```

This is currently the best overall choice because:

- it ties for the lowest MAE in the sweep
- it has the best exact-count accuracy
- it is much faster than `yolo11m` at the same resolution
- its inference time is easily acceptable for an occupancy system that only needs updates every few seconds

The other configuration with MAE 1.00 was:

```text
yolo11m.pt
imgsz=1280
conf=0.50
```

but it only achieved 2/8 exact counts and took about 555 ms, so it is inferior to `yolo11s @ 1280`.

---

## Important finding: lower confidence is making results worse

Across almost all tested configurations, lowering confidence from `0.50` to `0.25` or `0.15` made counting accuracy substantially worse.

This means the current benchmark is not primarily suffering from detections being rejected by an overly high threshold.

Instead, the lower thresholds are probably introducing additional false positives and duplicate/weak detections.

Therefore:

- do not continue tuning toward very low confidence thresholds
- focus the next sweep around the region near `0.50`

---

## Next benchmark sweep

Keep the existing benchmark infrastructure.

Do not change the live application yet.

Benchmark the following models:

```text
yolo11s.pt
yolo26s.pt
```

Optionally also include:

```text
yolo26n.pt
```

There is no strong reason to benchmark YOLO11m further unless YOLO26s performs poorly.

---

## Resolution sweep

Test:

```text
640
960
1280
1600
1920
```

The most interesting range is likely:

```text
960–1600
```

because `1280` was clearly strong for YOLO11s and `1920` did not improve it enough to justify the extra compute.

---

## Confidence sweep

Use a tighter confidence sweep centered around the currently successful value:

```text
0.40
0.50
0.60
0.70
```

Do not include `0.15` or `0.25` in the next primary sweep unless needed for comparison.

---

## Models/configurations to prioritize

Start with:

```text
yolo11s @ 1280 @ 0.50
yolo26s @ 1280 @ 0.50
```

Then expand around those.

The first question to answer is simply:

> Does YOLO26s beat the current YOLO11s baseline on this classroom benchmark?

---

## Keep the current baseline

Treat this as the baseline to beat:

```text
YOLO11s
imgsz=1280
conf=0.50

MAE: 1.00
Exact-count accuracy: 50%
Mean inference time: ~259 ms
```

All future detector changes should be compared against this.

---

## Add per-scenario comparison

The aggregate MAE is useful, but it can hide where a model fails.

For every configuration, retain per-image output and specifically compare:

```text
00_empty.png
05_seated.png
09_seated.png
10_back_rows.png
13_mixed.png
15_seated.png
16_occluded.png
18_seated.png
```

Pay particular attention to:

```text
10_back_rows.png
16_occluded.png
18_seated.png
```

These are the most relevant difficult cases.

A model should not be selected solely because it improves easy images.

---

## Add signed-error summary

In addition to MAE, calculate:

```text
mean_signed_error
```

where:

```text
signed_error = detected_count - expected_count
```

This helps distinguish:

```text
systematic undercounting
```

from:

```text
systematic overcounting
```

A model with MAE 1.0 that consistently undercounts by one behaves differently from one that alternates between large over- and under-counts.

---

## Add false-positive count for empty room

Keep reporting the detection count for `00_empty.png`.

A detector configuration that improves occupied-room counts but starts detecting people in the empty classroom should be treated with caution.

---

## Warm-up requirement

Perform at least one unmeasured inference after loading each model/configuration before recording inference timing.

Do not include model load or first-run initialization in the reported mean inference time.

---

## Selection criteria

Rank candidates in this order:

1. lowest MAE
2. highest exact-count accuracy
3. good performance on distant / occluded scenarios
4. zero false positives in the empty room
5. inference time

Inference time is a secondary concern because the system does not require video-rate inference.

A configuration taking 300–800 ms is perfectly acceptable if occupancy is only updated every few seconds.

---

## Do not add yet

Do not add:

- tracking
- pose estimation
- custom training
- SAHI / tiled inference
- temporal smoothing
- MQTT changes
- database changes

First determine whether a better pretrained detector configuration solves enough of the problem.

---

## Acceptance criteria

This step is complete when:

1. `yolo11s` and `yolo26s` are benchmarked against the same images.
2. The current `yolo11s @ 1280 @ 0.50` result is preserved as the baseline.
3. Confidence values around 0.50 are tested.
4. Resolutions around 1280 are tested.
5. Per-image results are preserved.
6. Mean signed error is reported.
7. Empty-room false positives are reported.
8. A final comparison table clearly identifies whether YOLO26s beats the current baseline.
