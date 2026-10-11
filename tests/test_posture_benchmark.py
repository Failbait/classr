import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from posture import Posture, summarize_postures
from posture_benchmark import PostureBenchmarkError, compare, load_manifest

HEADER = "filename,expected_occupancy,expected_seated,expected_standing,expected_unknown\n"


def write(tmp_path, body):
    path = tmp_path / "manifest.csv"
    path.write_text(HEADER + body)
    return path


def test_loads_valid_manifest(tmp_path):
    cases = load_manifest(write(tmp_path, "a.png,13,9,4,0\n"))
    assert cases[0]["expected_standing"] == 4


def test_rejects_counts_that_do_not_add_up(tmp_path):
    with pytest.raises(PostureBenchmarkError):
        load_manifest(write(tmp_path, "a.png,13,9,3,0\n"))


def test_repo_manifest_is_valid():
    assert load_manifest(Path(__file__).resolve().parent.parent / "benchmark_posture/manifest.csv")


def test_compare_reports_signed_errors():
    case = {"filename": "a.png", "expected_occupancy": 10, "expected_seated": 8,
            "expected_standing": 2, "expected_unknown": 0}
    summary = summarize_postures([Posture.SEATED] * 6 + [Posture.STANDING] * 3 + [Posture.UNKNOWN])
    row = compare(case, summary)
    assert (row["seated_count_error"], row["standing_count_error"], row["unknown_count_error"]) \
        == (-2, 1, 1)
    assert row["standing_ratio_error"] == 0.1
