import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from posture import GeometryPostureClassifier, Posture, summarize_postures

FRAME_W, FRAME_H = 1600, 1000


@pytest.fixture(autouse=True)
def zones(monkeypatch):
    # (max bottom_y fraction, seated if height frac <= a, standing if height frac >= b)
    monkeypatch.setattr(config, "POSTURE_ZONES", [(0.4, 0.10, 0.16), (0.7, 0.20, 0.30), (1.0, 0.35, 0.50)])
    monkeypatch.setattr(config, "POSTURE_EDGE_MARGIN_PX", 4)
    monkeypatch.setattr(config, "POSTURE_MIN_ASPECT", 0.8)


def classify(bbox):
    return GeometryPostureClassifier().classify(None, bbox, (FRAME_H, FRAME_W))


def test_short_box_is_seated_tall_box_is_standing():
    assert classify((500, 400, 560, 530)) is Posture.SEATED      # middle zone, h 0.13
    assert classify((500, 300, 600, 820)) is Posture.STANDING    # near zone, h 0.52


def test_thresholds_depend_on_depth():
    # Same pixel height is standing in the far zone but seated in the near zone.
    far = classify((500, 100, 560, 260))     # bottom 0.26 zone 1, h 0.16
    near = classify((500, 600, 600, 800))  # bottom 0.80 zone 3, h 0.20
    assert far is Posture.STANDING
    assert near is Posture.SEATED


def test_between_thresholds_is_unknown():
    assert classify((500, 100, 560, 240)) is Posture.UNKNOWN  # zone 1, h 0.14


def test_box_touching_frame_edge_is_unknown():
    assert classify((0, 600, 100, 1000)) is Posture.UNKNOWN
    assert classify((1500, 100, 1600, 260)) is Posture.UNKNOWN


def test_very_wide_box_is_unknown():
    assert classify((500, 500, 900, 600)) is Posture.UNKNOWN  # width/height = 4


def test_summary_counts_and_ratios():
    s = summarize_postures([Posture.SEATED] * 14 + [Posture.STANDING] * 3 + [Posture.UNKNOWN])
    assert s == {"occupancy": 18, "seated_count": 14, "standing_count": 3,
                 "unknown_count": 1, "standing_ratio": pytest.approx(3 / 18),
                 "standing_ratio_known": pytest.approx(3 / 17)}


def test_summary_empty_room_has_zero_ratios():
    s = summarize_postures([])
    assert s["occupancy"] == 0 and s["standing_ratio"] == 0.0 and s["standing_ratio_known"] == 0.0


def test_smoother_takes_median_of_recent_window():
    from posture import StandingRatioSmoother
    smoother = StandingRatioSmoother(window=3)
    assert smoother.update(0.0) == 0.0
    assert smoother.update(0.9) == 0.45
    assert smoother.update(0.1) == 0.1
    assert smoother.update(0.1) == 0.1   # window now [0.9, 0.1, 0.1]
