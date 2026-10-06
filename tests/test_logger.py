import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logger import HEADER, init_csv, log_count


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def test_creates_file_dir_and_header(tmp_path):
    path = tmp_path / "data" / "people_count.csv"
    init_csv(path)
    assert read_rows(path) == [HEADER]


def test_appends_and_never_overwrites(tmp_path):
    path = tmp_path / "people_count.csv"
    log_count(path, 4)
    init_csv(path)  # simulated restart
    log_count(path, 5)
    rows = read_rows(path)
    assert rows[0] == HEADER
    assert [r[1] for r in rows[1:]] == ["4", "5"]


def test_timestamp_is_iso8601(tmp_path):
    path = tmp_path / "people_count.csv"
    log_count(path, 1, now=datetime(2026, 10, 6, 15, 30, tzinfo=timezone.utc))
    assert read_rows(path)[1][0] == "2026-10-06T15:30:00+00:00"
    datetime.fromisoformat(read_rows(path)[1][0])
