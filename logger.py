"""Append aggregate occupancy/posture counts to a CSV file. Nothing else is persisted."""

import csv
from datetime import datetime
from pathlib import Path

HEADER = ["timestamp", "people_count", "seated_count", "standing_count", "unknown_count",
          "standing_ratio", "standing_ratio_smoothed"]


def init_csv(path):
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)
    return csv_path


def log_state(path, summary, standing_ratio_smoothed, now=None):
    """Append one row from a posture.summarize_postures() dict."""
    timestamp = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    row = [timestamp, summary["occupancy"], summary["seated_count"], summary["standing_count"],
           summary["unknown_count"], f"{summary['standing_ratio']:.3f}",
           f"{standing_ratio_smoothed:.3f}"]
    with init_csv(path).open("a", newline="") as f:
        csv.writer(f).writerow(row)
