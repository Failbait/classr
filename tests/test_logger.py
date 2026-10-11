import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logger import HEADER, init_csv, log_state
from posture import Posture, summarize_postures


def summary(n):
    return summarize_postures([Posture.SEATED] * n)


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def test_creates_file_dir_and_header(tmp_path):
    path = tmp_path / "data" / "people_count.csv"
    init_csv(path)
    assert read_rows(path) == [HEADER]


def test_appends_and_never_overwrites(tmp_path):
    path = tmp_path / "people_count.csv"
    log_state(path, summary(4), 0.0)
    init_csv(path)  # simulated restart
    log_state(path, summary(5), 0.0)
    rows = read_rows(path)
    assert rows[0] == HEADER
    assert [r[1] for r in rows[1:]] == ["4", "5"]


def test_timestamp_is_iso8601(tmp_path):
    path = tmp_path / "people_count.csv"
    log_state(path, summary(1), 0.0, now=datetime(2026, 10, 6, 15, 30, tzinfo=timezone.utc))
    assert read_rows(path)[1][0] == "2026-10-06T15:30:00+00:00"
    datetime.fromisoformat(read_rows(path)[1][0])


def test_row_contains_posture_aggregates(tmp_path):
    path = tmp_path / "people_count.csv"
    mixed = summarize_postures([Posture.SEATED] * 14 + [Posture.STANDING] * 3 + [Posture.UNKNOWN])
    log_state(path, mixed, 0.1)
    row = dict(zip(HEADER, read_rows(path)[1]))
    assert (row["people_count"], row["seated_count"], row["standing_count"],
            row["unknown_count"]) == ("18", "14", "3", "1")
    assert row["standing_ratio"] == "0.167" and row["standing_ratio_smoothed"] == "0.100"
