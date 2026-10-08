import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from detector import containment, select_detections


def det(bbox, conf):
    return {"bbox": bbox, "confidence": conf, "class_name": "person"}


@pytest.fixture(autouse=True)
def rules(monkeypatch):
    monkeypatch.setattr(config, "CONFIDENCE_THRESHOLD", 0.4)
    monkeypatch.setattr(config, "SMALL_BOX_CONFIDENCE", 0.3)
    monkeypatch.setattr(config, "SMALL_BOX_HEIGHT_FRACTION", 0.12)
    monkeypatch.setattr(config, "DEDUPE_CONTAINMENT", 0.85)


def test_containment_full_partial_none():
    assert containment((0, 0, 10, 10), (0, 0, 20, 20)) == 1.0
    assert containment((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5
    assert containment((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_small_box_accepted_at_lower_confidence():
    small = det((0, 0, 30, 100), 0.33)   # 100 px tall in a 1000 px frame = small
    large = det((100, 0, 300, 400), 0.33)
    accepted, rejected = select_detections([small, large], 1000)
    assert accepted == [small] and rejected == [large]


def test_small_box_rule_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "SMALL_BOX_CONFIDENCE", 0)
    accepted, rejected = select_detections([det((0, 0, 30, 100), 0.33)], 1000)
    assert accepted == [] and len(rejected) == 1


def test_duplicate_box_inside_higher_scoring_box_is_dropped():
    full = det((250, 450, 400, 700), 0.8)
    upper = det((255, 458, 385, 572), 0.45)
    accepted, rejected = select_detections([upper, full], 1000)
    assert accepted == [full] and rejected == [upper]


def test_partially_overlapping_neighbours_are_both_kept():
    a = det((0, 0, 100, 200), 0.9)
    b = det((60, 0, 160, 200), 0.8)  # 40% overlap
    accepted, _ = select_detections([a, b], 1000)
    assert len(accepted) == 2


def test_dedupe_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "DEDUPE_CONTAINMENT", 0)
    accepted, _ = select_detections([det((0, 0, 100, 100), 0.9), det((10, 10, 50, 50), 0.8)], 1000)
    assert len(accepted) == 2
