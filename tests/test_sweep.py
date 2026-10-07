import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sweep import hard_case_mae, rank_key


def entry(mae, exact, hard, fp, ms):
    return {"summary": {"mae": mae, "exact": exact, "empty_false_positives": fp, "mean_ms": ms},
            "hard_mae": hard}


def test_rank_prefers_lower_mae_then_more_exact():
    assert rank_key(entry(1.0, 4, 2, 0, 900)) < rank_key(entry(1.2, 8, 0, 0, 1))
    assert rank_key(entry(1.0, 4, 2, 0, 900)) < rank_key(entry(1.0, 2, 0, 0, 1))


def test_rank_penalises_empty_room_false_positive_before_time():
    assert rank_key(entry(1.0, 4, 1, 0, 900)) < rank_key(entry(1.0, 4, 1, 2, 100))


def test_hard_case_mae_only_counts_hard_scenarios():
    rows = [{"scenario": "dense", "absolute_error": 4}, {"scenario": "empty", "absolute_error": 0},
            {"scenario": "occlusion", "absolute_error": 2}]
    assert hard_case_mae(rows) == 3.0
