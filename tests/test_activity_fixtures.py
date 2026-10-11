"""Activity logic on real detector box layouts (tests/fixtures/benchmark_boxes.json).

Create the fixture on the Pi with: python export_boxes.py
"""

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from activity import ActivityEstimator

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "benchmark_boxes.json"
STEP_SECONDS = 1.4
MIN_BOXES = 8


def load_layouts():
    if not FIXTURE.is_file():
        return []
    layouts = json.loads(FIXTURE.read_text())
    return [(e["filename"], [tuple(d["bbox"]) for d in e["detections"]])
            for e in layouts if len(e["detections"]) >= MIN_BOXES]


LAYOUTS = load_layouts()
pytestmark = pytest.mark.skipif(not LAYOUTS, reason="run export_boxes.py on the Pi first")


def shift(box, dx_frac, dy_frac):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return (round(x1 + w * dx_frac), round(y1 + h * dy_frac),
            round(x2 + w * dx_frac), round(y2 + h * dy_frac))


def jittered(boxes, amount, rng):
    return [shift(b, rng.uniform(-amount, amount), rng.uniform(-amount, amount)) for b in boxes]


def run(frames):
    estimator = ActivityEstimator()
    return [estimator.update([{"bbox": b} for b in f], i * STEP_SECONDS)
            for i, f in enumerate(frames)]


def walk(box, steps):
    """Move a box 0.4 of its own size (max of width/height) per sample."""
    x1, y1, x2, y2 = box
    d = round(0.4 * steps * max(x2 - x1, y2 - y1))
    return (x1 + d, y1, x2 + d, y2)


def with_movers(boxes, movers, step):
    """First `movers` boxes have walked `step` samples (alternating directions); the rest sit still."""
    return [walk(b, step if i % 2 else -step) if i < movers else b for i, b in enumerate(boxes)]


@pytest.mark.parametrize("name,boxes", LAYOUTS)
def test_jitter_only_stays_quiet(name, boxes):
    rng = random.Random(7)
    states = run([jittered(boxes, 0.02, rng) for _ in range(8)])
    assert states[-1].moving_count <= max(1, len(boxes) // 20)
    assert states[-1].activity_score < 0.15


@pytest.mark.parametrize("name,boxes", LAYOUTS)
def test_activity_grows_with_number_of_movers(name, boxes):
    n = len(boxes)
    scores = []
    for movers in (n // 10, n // 2, n):
        frames = [with_movers(boxes, movers, step) for step in range(5)]
        scores.append(run(frames)[-1].activity_score)
    assert scores[0] < scores[1] < scores[2]


@pytest.mark.parametrize("name,boxes", LAYOUTS)
def test_most_movers_show_up_as_change(name, boxes):
    # A walker next to another walker can be paired with the wrong box or left unmatched, so
    # count moving + new + lost (all of which feed activity_score), not moving alone.
    n = len(boxes)
    final = run([with_movers(boxes, n // 2, step) for step in range(2)])[-1]
    assert final.moving_count + final.new_count + final.lost_count >= 0.6 * (n // 2)
