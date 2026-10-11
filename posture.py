"""Per-person posture (seated / standing / unknown) and aggregate classroom state.

The classifier only sees a frame and a person box and returns a Posture, so it can later be
replaced (e.g. by a crop-based model) without touching main.py, the logger or the benchmark.
Nothing is remembered between frames: postures are never tied to an identity.
"""

from enum import Enum

import config


class Posture(str, Enum):
    SEATED = "seated"
    STANDING = "standing"
    UNKNOWN = "unknown"


class GeometryPostureClassifier:
    """Perspective-aware heuristic on the person box.

    The box bottom's vertical position is the depth proxy: it picks a zone from
    config.POSTURE_ZONES, and the box height (as a fraction of frame height) is compared with
    that zone's seated/standing thresholds. In between, or when the box is truncated by the
    frame edge or implausibly wide, the answer is UNKNOWN.
    """

    def classify(self, frame, bbox, frame_shape=None):
        height, width = frame_shape[:2] if frame_shape is not None else frame.shape[:2]
        x1, y1, x2, y2 = bbox
        box_w, box_h = x2 - x1, y2 - y1
        if box_h <= 0 or box_w <= 0 or self._truncated(bbox, width, height):
            return Posture.UNKNOWN
        if box_h / box_w < config.POSTURE_MIN_ASPECT:
            return Posture.UNKNOWN

        seated_max, standing_min = self._thresholds(y2 / height)
        height_fraction = box_h / height
        if height_fraction <= seated_max:
            return Posture.SEATED
        if height_fraction >= standing_min:
            return Posture.STANDING
        return Posture.UNKNOWN

    @staticmethod
    def _truncated(bbox, width, height):
        margin = config.POSTURE_EDGE_MARGIN_PX
        x1, y1, x2, y2 = bbox
        return x1 <= margin or y1 <= margin or x2 >= width - margin or y2 >= height - margin

    @staticmethod
    def _thresholds(bottom_fraction):
        for max_bottom, seated_max, standing_min in config.POSTURE_ZONES:
            if bottom_fraction <= max_bottom:
                return seated_max, standing_min
        return config.POSTURE_ZONES[-1][1:]


def classify_detections(classifier, frame, detections):
    """Return the detections as new dicts with a "posture" field added."""
    return [{**det, "posture": classifier.classify(frame, det["bbox"])} for det in detections]


def summarize_postures(postures):
    postures = list(postures)
    occupancy = len(postures)
    seated = sum(p is Posture.SEATED for p in postures)
    standing = sum(p is Posture.STANDING for p in postures)
    known = seated + standing
    return {
        "occupancy": occupancy,
        "seated_count": seated,
        "standing_count": standing,
        "unknown_count": occupancy - known,
        "standing_ratio": standing / occupancy if occupancy else 0.0,
        "standing_ratio_known": standing / known if known else 0.0,
    }


class StandingRatioSmoother:
    """Median of the last N aggregate standing ratios. Aggregate only, no per-person state."""

    def __init__(self, window=None):
        self._window = window or config.POSTURE_SMOOTHING_WINDOW
        self._samples = []

    def update(self, ratio):
        self._samples = [*self._samples, ratio][-self._window:]
        ordered = sorted(self._samples)
        mid = len(ordered) // 2
        return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
