"""Append aggregate occupancy/posture counts to a CSV file. Nothing else is persisted."""

import csv
from datetime import datetime
from pathlib import Path

HEADER = ["timestamp", "people_count", "seated_count", "standing_count", "unknown_count",
          "standing_ratio", "standing_ratio_smoothed", "matched_count", "moving_count",
          "moving_ratio", "mean_motion", "new_count", "lost_count", "activity_score",
          "ambient_light_lux", "ambient_noise_level"]
ENV_FIELDS = ("co2_ppm", "temperature_c", "humidity_percent")
ENV_DIGITS = (0, 2, 2)


def build_header(env_labels=()):
    """Base columns plus three environment columns per labelled node, e.g. co2_ppm_s1."""
    return HEADER + [f"{name}_{label}" for label in env_labels for name in ENV_FIELDS]


def _rotate_if_header_changed(csv_path, header):
    """Move a file written with an older column layout aside so rows never misalign."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return
    with csv_path.open(newline="") as f:
        if next(csv.reader(f), None) == header:
            return
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    csv_path.rename(csv_path.with_name(f"{csv_path.name}.old-{stamp}"))


def init_csv(path, env_labels=()):
    header = build_header(env_labels)
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_header_changed(csv_path, header)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", newline="") as f:
            csv.writer(f).writerow(header)
    return csv_path


def _fmt(value, digits):
    return "" if value is None else f"{value:.{digits}f}"


def _env_cells(classroom, env_labels):
    """Three cells per labelled node, blank for a node (or the whole state) that is unavailable."""
    cells = []
    for label in env_labels:
        reading = classroom.environment.get(label) if classroom else None
        cells += [""] * len(ENV_FIELDS) if reading is None else [
            _fmt(getattr(reading, name), digits) for name, digits in zip(ENV_FIELDS, ENV_DIGITS)]
    return cells


def log_state(path, summary, standing_ratio_smoothed, activity, now=None, classroom=None,
              env_labels=()):
    """Append one row from a posture.summarize_postures() dict and an activity.ActivityState.

    classroom (ClassroomState, optional) supplies the light/noise and per-node environment
    columns; env_labels must match the labels the file was initialised with."""
    timestamp = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    row = [timestamp, summary["occupancy"], summary["seated_count"], summary["standing_count"],
           summary["unknown_count"], f"{summary['standing_ratio']:.3f}",
           f"{standing_ratio_smoothed:.3f}", activity.matched_count, activity.moving_count,
           f"{activity.moving_ratio:.3f}", f"{activity.mean_motion:.3f}", activity.new_count,
           activity.lost_count, f"{activity.activity_score:.3f}",
           _fmt(classroom and classroom.ambient_light_lux, 1),
           _fmt(classroom and classroom.ambient_noise_level, 3),
           *_env_cells(classroom, env_labels)]
    with init_csv(path, env_labels).open("a", newline="") as f:
        csv.writer(f).writerow(row)
