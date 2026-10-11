"""Append aggregate occupancy/posture counts to a CSV file. Nothing else is persisted."""

import csv
from datetime import datetime
from pathlib import Path

HEADER = ["timestamp", "people_count", "seated_count", "standing_count", "unknown_count",
          "standing_ratio", "standing_ratio_smoothed", "matched_count", "moving_count",
          "moving_ratio", "mean_motion", "new_count", "lost_count", "activity_score",
          "ambient_light_lux", "ambient_noise_level"]


def init_csv(path):
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)
    return csv_path


def _fmt(value, digits):
    return "" if value is None else f"{value:.{digits}f}"


def log_state(path, summary, standing_ratio_smoothed, activity, now=None, classroom=None):
    """Append one row from a posture.summarize_postures() dict and an activity.ActivityState.

    classroom (ClassroomState, optional) supplies the environment columns; blank if absent/None."""
    timestamp = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    row = [timestamp, summary["occupancy"], summary["seated_count"], summary["standing_count"],
           summary["unknown_count"], f"{summary['standing_ratio']:.3f}",
           f"{standing_ratio_smoothed:.3f}", activity.matched_count, activity.moving_count,
           f"{activity.moving_ratio:.3f}", f"{activity.mean_motion:.3f}", activity.new_count,
           activity.lost_count, f"{activity.activity_score:.3f}",
           _fmt(classroom and classroom.ambient_light_lux, 1),
           _fmt(classroom and classroom.ambient_noise_level, 3)]
    with init_csv(path).open("a", newline="") as f:
        csv.writer(f).writerow(row)
