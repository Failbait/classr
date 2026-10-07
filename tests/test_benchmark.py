import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark import BenchmarkError, compute_metrics, load_manifest, summarize


def test_metrics_nonzero_expected():
    assert compute_metrics(10, 9) == {"signed_error": -1, "absolute_error": 1,
                                      "percentage_error": 10.0}


def test_metrics_empty_room_has_no_percentage():
    assert compute_metrics(0, 2)["percentage_error"] is None


def test_summarize():
    rows = [{"absolute_error": 0, "inference_time_ms": 100.0},
            {"absolute_error": 4, "inference_time_ms": 200.0}]
    s = summarize(rows)
    assert (s["mae"], s["max_error"], s["exact"], s["exact_pct"], s["mean_ms"]) == (2.0, 4, 1, 50.0, 150.0)


def test_manifest_loads(tmp_path):
    m = tmp_path / "m.csv"
    m.write_text("filename,expected_count,scenario\na.png,3,x\n")
    assert load_manifest(m) == [{"filename": "a.png", "expected": 3, "scenario": "x"}]


def test_manifest_missing(tmp_path):
    with pytest.raises(BenchmarkError, match="not found"):
        load_manifest(tmp_path / "nope.csv")


def test_manifest_malformed_row_reports_line(tmp_path):
    m = tmp_path / "m.csv"
    m.write_text("filename,expected_count,scenario\na.png,abc,x\n")
    with pytest.raises(BenchmarkError, match="line 2"):
        load_manifest(m)
