import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from activity import ActivityEstimator

STEP_SECONDS = 1.4


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    for name, value in {
        "ACTIVITY_MOVING_THRESHOLD": 0.15, "ACTIVITY_MATCH_MAX_DISTANCE": 1.0,
        "ACTIVITY_MATCH_MIN_IOU": 0.3, "ACTIVITY_MAX_GAP_SECONDS": 10.0,
        "ACTIVITY_LOST_GRACE_SAMPLES": 1, "ACTIVITY_SIZE_WEIGHT": 0.5,
        "ACTIVITY_GLOBAL_SHIFT_MIN_MATCHES": 5, "ACTIVITY_GLOBAL_SHIFT_MAX": 0.1, "ACTIVITY_W_RATIO": 0.7,
        "ACTIVITY_W_MOTION": 0.3, "ACTIVITY_MOTION_SATURATION": 0.5,
        "ACTIVITY_SMOOTHING_SECONDS": 5.0,
    }.items():
        monkeypatch.setattr(config, name, value)


def grid(n, w=60, h=120):
    """n boxes laid out in rows, 2 box-widths apart."""
    return [(20 + (i % 6) * 2 * w, 20 + (i // 6) * 2 * h, 20 + (i % 6) * 2 * w + w,
             20 + (i // 6) * 2 * h + h) for i in range(n)]


def shifted(box, dx_frac, dy_frac=0.0):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return (round(x1 + w * dx_frac), round(y1 + h * dy_frac),
            round(x2 + w * dx_frac), round(y2 + h * dy_frac))


def dets(boxes):
    return [{"bbox": b, "confidence": 0.9} for b in boxes]


def run(frames):
    estimator = ActivityEstimator()
    return [estimator.update(dets(f), i * STEP_SECONDS) for i, f in enumerate(frames)]


def jitter(boxes, amount, seed):
    rng = random.Random(seed)
    return [shifted(b, rng.uniform(-amount, amount), rng.uniform(-amount, amount)) for b in boxes]


def test_first_sample_has_no_activity():
    state = run([grid(5)])[0]
    assert (state.occupancy, state.matched_count, state.new_count, state.activity_score) == (5, 0, 0, 0.0)


def test_stable_room_with_jitter_stays_quiet():
    base = grid(18)
    states = run([jitter(base, 0.03, seed) for seed in range(8)])
    assert all(s.moving_count == 0 for s in states)
    assert states[-1].activity_score < 0.1
    assert states[-1].matched_count == 18


def test_one_person_moving_is_low_activity():
    base = grid(18)
    moved = [shifted(base[0], 0.6, 0.0), *base[1:]]
    state = run([base, moved])[1]
    assert state.moving_count == 1
    assert state.moving_ratio == pytest.approx(1 / 18)
    assert state.activity_score < 0.2


def test_break_like_transition_is_high_activity():
    base = grid(18)
    frames = [base]
    for step in range(1, 5):  # 15 of 18 keep walking, 3 stay put
        frames.append([shifted(b, 0.5 * step, 0.2 * step) if i >= 3 else b
                       for i, b in enumerate(base)])
    final = run(frames)[-1]
    assert final.moving_ratio == pytest.approx(15 / 18)
    assert final.activity_score > 0.4


def test_small_group_is_in_between():
    base = grid(18)
    group = [shifted(b, 0.4) if i < 5 else b for i, b in enumerate(base)]
    one = [shifted(b, 0.4) if i < 1 else b for i, b in enumerate(base)]
    many = [shifted(b, 0.4) for b in base]
    scores = [run([base, f])[1].activity_score for f in (one, group, many)]
    assert scores[0] < scores[1] < scores[2]


def test_small_global_camera_shift_is_compensated(monkeypatch):
    monkeypatch.setattr(config, "ACTIVITY_MOVING_THRESHOLD", 0.05)
    base = grid(18)
    state = run([base, [shifted(b, 0.16) for b in jitter(base, 0.01, 1)]])[1]  # ~0.08 of a box
    assert state.moving_count == 0


def test_people_leaving_and_entering_are_counted():
    base = grid(18)
    states = run([base, base[:10], base[:10], base[:10]])
    assert [s.lost_count for s in states] == [0, 0, 8, 0]  # lost after the 1-sample grace
    states = run([base[:10], base[:10], base])
    assert states[2].new_count == 8 and states[2].occupancy == 18


def test_single_missed_detection_is_not_lost_or_new():
    base = grid(18)
    states = run([base, base[1:], base])
    assert sum(s.lost_count + s.new_count for s in states) == 0
    assert states[2].matched_count == 18


def test_standing_up_counts_as_motion():
    seated = (100, 300, 160, 420)
    standing = (100, 180, 160, 420)  # top rises, bottom fixed
    state = run([[seated], [standing]])[1]
    assert state.moving_count == 1


def test_long_gap_resets_matching():
    estimator = ActivityEstimator()
    estimator.update(dets(grid(5)), 0.0)
    state = estimator.update(dets(grid(5)), 60.0)
    assert state.matched_count == 0 and state.new_count == 0


def test_activity_decays_when_room_settles():
    base = grid(18)
    moved = [shifted(b, 0.5) for b in base]
    states = run([base, moved] + [moved] * 6)
    assert states[1].activity_score > states[-1].activity_score
    assert states[-1].activity_score < 0.05


def test_empty_room():
    states = run([[], []])
    assert states[1].occupancy == 0 and states[1].moving_ratio == 0.0 and states[1].activity_score == 0.0
