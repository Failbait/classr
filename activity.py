"""Aggregate classroom activity from person boxes in consecutive detections.

Detector-agnostic: it only needs a list of {"bbox": (x1, y1, x2, y2)} per sample. Boxes are matched
one-to-one between neighbouring samples, only to measure how far each moved; nothing keeps an
identity, and the previous boxes are dropped after ACTIVITY_MAX_GAP_SECONDS. Only aggregates leave
this module.
"""

import math
import statistics
from dataclasses import dataclass, replace

import config


@dataclass(frozen=True)
class ActivityState:
    occupancy: int
    matched_count: int
    moving_count: int
    moving_ratio: float
    mean_motion: float
    new_count: int
    lost_count: int
    activity_score: float


@dataclass(frozen=True)
class _Box:
    bbox: tuple
    missed: int = 0  # consecutive samples without a match

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    @property
    def center(self):
        return ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)

    @property
    def scale(self):
        return max(self.width, self.height, 1)


def _iou(a, b):
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    inter = ix * iy
    union = ((a[2] - a[0]) * (a[3] - a[1])) + ((b[2] - b[0]) * (b[3] - b[1])) - inter
    return inter / union if union > 0 else 0.0


def _displacement(prev, cur):
    """Centroid displacement of a box, in units of its previous size."""
    (px, py), (cx, cy) = prev.center, cur.center
    return ((cx - px) / prev.scale, (cy - py) / prev.scale)


def match_boxes(previous, current):
    """Greedy one-to-one matching, best pairs first. Returns [(prev_index, cur_index)]."""
    pairs = []
    for i, prev in enumerate(previous):
        for j, cur in enumerate(current):
            dx, dy = _displacement(prev, cur)
            distance = math.hypot(dx, dy)
            iou = _iou(prev.bbox, cur.bbox)
            if distance <= config.ACTIVITY_MATCH_MAX_DISTANCE or iou >= config.ACTIVITY_MATCH_MIN_IOU:
                pairs.append((distance - iou, i, j))
    used_prev, used_cur, matches = set(), set(), []
    for _, i, j in sorted(pairs):
        if i not in used_prev and j not in used_cur:
            used_prev.add(i)
            used_cur.add(j)
            matches.append((i, j))
    return matches


def _size_change(prev, cur):
    return max(abs(cur.width - prev.width) / max(prev.width, 1),
               abs(cur.height - prev.height) / max(prev.height, 1))


def motion_values(previous, current, matches):
    """Normalized motion per match: centroid shift (minus any small global shift) or size change."""
    shifts = [_displacement(previous[i], current[j]) for i, j in matches]
    shift_x = shift_y = 0.0
    if len(shifts) >= config.ACTIVITY_GLOBAL_SHIFT_MIN_MATCHES:
        median_x = statistics.median(s[0] for s in shifts)
        median_y = statistics.median(s[1] for s in shifts)
        if math.hypot(median_x, median_y) <= config.ACTIVITY_GLOBAL_SHIFT_MAX:  # camera shake
            shift_x, shift_y = median_x, median_y
    return [max(math.hypot(dx - shift_x, dy - shift_y),
                config.ACTIVITY_SIZE_WEIGHT * _size_change(previous[i], current[j]))
            for (i, j), (dx, dy) in zip(matches, shifts)]


class ActivityEstimator:
    def __init__(self):
        self._boxes = []
        self._last_time = None
        self._score = 0.0

    def update(self, detections, timestamp):
        current = [_Box(tuple(d["bbox"])) for d in detections]
        if self._last_time is None or timestamp - self._last_time > config.ACTIVITY_MAX_GAP_SECONDS:
            self._boxes, self._score = current, 0.0
            self._last_time = timestamp
            return self._state(len(current), [], 0, 0, 0.0)

        matches = match_boxes(self._boxes, current)
        motions = motion_values(self._boxes, current, matches)
        moving = sum(m >= config.ACTIVITY_MOVING_THRESHOLD for m in motions)
        matched_prev = {i for i, _ in matches}
        matched_cur = {j for _, j in matches}

        new_count = len(current) - len(matched_cur)
        survivors, lost_count = [], 0
        for i, box in enumerate(self._boxes):
            if i in matched_prev:
                continue
            if box.missed >= config.ACTIVITY_LOST_GRACE_SAMPLES:
                lost_count += 1
            else:
                survivors.append(replace(box, missed=box.missed + 1))  # maybe just a missed detection

        elapsed = timestamp - self._last_time
        self._boxes = current + survivors
        self._last_time = timestamp
        return self._state(len(current), motions, moving, new_count, elapsed, lost_count)

    def _state(self, occupancy, motions, moving, new_count, elapsed, lost_count=0):
        matched = len(motions)
        mean_motion = sum(motions) / matched if matched else 0.0
        population = matched + new_count + lost_count
        changed = (moving + new_count + lost_count) / population if population else 0.0
        motion_level = min(mean_motion / config.ACTIVITY_MOTION_SATURATION, 1.0)
        raw = min(config.ACTIVITY_W_RATIO * changed + config.ACTIVITY_W_MOTION * motion_level, 1.0)
        alpha = 1 - math.exp(-elapsed / config.ACTIVITY_SMOOTHING_SECONDS) if elapsed > 0 else 0.0
        self._score = self._score + alpha * (raw - self._score)
        return ActivityState(
            occupancy=occupancy, matched_count=matched, moving_count=moving,
            moving_ratio=moving / matched if matched else 0.0, mean_motion=mean_motion,
            new_count=new_count, lost_count=lost_count, activity_score=self._score)
