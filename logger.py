"""Append aggregate people counts to a CSV file. Nothing else is persisted."""

import csv
from datetime import datetime
from pathlib import Path

HEADER = ["timestamp", "people_count"]


def init_csv(path):
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)
    return csv_path


def log_count(path, people_count, now=None):
    timestamp = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    with init_csv(path).open("a", newline="") as f:
        csv.writer(f).writerow([timestamp, people_count])
