import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logger import HEADER, build_header, init_csv, log_state
from activity import ActivityState
from posture import Posture, summarize_postures


IDLE = ActivityState(0, 0, 0, 0.0, 0.0, 0, 0, 0.0)


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
    log_state(path, summary(4), 0.0, IDLE)
    init_csv(path)  # simulated restart
    log_state(path, summary(5), 0.0, IDLE)
    rows = read_rows(path)
    assert rows[0] == HEADER
    assert [r[1] for r in rows[1:]] == ["4", "5"]


def test_timestamp_is_iso8601(tmp_path):
    path = tmp_path / "people_count.csv"
    log_state(path, summary(1), 0.0, IDLE, now=datetime(2026, 10, 6, 15, 30, tzinfo=timezone.utc))
    assert read_rows(path)[1][0] == "2026-10-06T15:30:00+00:00"
    datetime.fromisoformat(read_rows(path)[1][0])


def test_row_contains_posture_aggregates(tmp_path):
    path = tmp_path / "people_count.csv"
    mixed = summarize_postures([Posture.SEATED] * 14 + [Posture.STANDING] * 3 + [Posture.UNKNOWN])
    log_state(path, mixed, 0.1, IDLE)
    row = dict(zip(HEADER, read_rows(path)[1]))
    assert (row["people_count"], row["seated_count"], row["standing_count"],
            row["unknown_count"]) == ("18", "14", "3", "1")
    assert row["standing_ratio"] == "0.167" and row["standing_ratio_smoothed"] == "0.100"


def test_row_contains_activity_aggregates(tmp_path):
    path = tmp_path / "people_count.csv"
    activity = ActivityState(
        occupancy=18, matched_count=17, moving_count=11, moving_ratio=0.647, mean_motion=0.182,
        new_count=2, lost_count=1, activity_score=0.71)
    log_state(path, summary(18), 0.0, activity)
    row = dict(zip(HEADER, read_rows(path)[1]))
    assert [row[k] for k in ("matched_count", "moving_count", "moving_ratio", "mean_motion",
                             "new_count", "lost_count", "activity_score")] \
        == ["17", "11", "0.647", "0.182", "2", "1", "0.710"]


def test_row_contains_environment_columns(tmp_path):
    from classroom_state import ClassroomState
    path = tmp_path / "people_count.csv"
    state = ClassroomState(datetime(2026, 10, 11, tzinfo=timezone.utc), 12, 0.18, 387.44, 0.2349)
    log_state(path, summary(12), 0.0, IDLE, classroom=state)
    row = dict(zip(HEADER, read_rows(path)[1]))
    assert row["ambient_light_lux"] == "387.4" and row["ambient_noise_level"] == "0.235"


def test_unavailable_sensors_are_blank(tmp_path):
    from classroom_state import ClassroomState
    path = tmp_path / "people_count.csv"
    state = ClassroomState(datetime(2026, 10, 11, tzinfo=timezone.utc), 3, 0.0, None, None)
    log_state(path, summary(3), 0.0, IDLE, classroom=state)
    row = dict(zip(HEADER, read_rows(path)[1]))
    assert row["ambient_light_lux"] == "" and row["ambient_noise_level"] == ""
    log_state(path, summary(3), 0.0, IDLE)  # no state at all also yields blanks
    assert read_rows(path)[2][-2:] == ["", ""]


LABELS = ("s1", "s2")
ENV_HEADER = build_header(LABELS)


class Reading:
    def __init__(self, co2_ppm, temperature_c, humidity_percent):
        self.co2_ppm, self.temperature_c, self.humidity_percent = \
            co2_ppm, temperature_c, humidity_percent


def env_state(environment):
    from classroom_state import ClassroomState
    return ClassroomState(datetime(2026, 10, 12, tzinfo=timezone.utc), 12, 0.18, 387.4, 0.23,
                          environment=environment)


def test_header_has_three_columns_per_labelled_node():
    assert ENV_HEADER[:len(HEADER)] == HEADER
    assert ENV_HEADER[len(HEADER):] == [
        "co2_ppm_s1", "temperature_c_s1", "humidity_percent_s1",
        "co2_ppm_s2", "temperature_c_s2", "humidity_percent_s2"]


def test_row_contains_each_nodes_environment_columns(tmp_path):
    path = tmp_path / "people_count.csv"
    state = env_state({"s1": Reading(812, 22.47, 39.81), "s2": Reading(1200, 23.5, 55.0)})
    log_state(path, summary(12), 0.0, IDLE, classroom=state, env_labels=LABELS)
    row = dict(zip(ENV_HEADER, read_rows(path)[1]))
    assert (row["co2_ppm_s1"], row["temperature_c_s1"], row["humidity_percent_s1"]) \
        == ("812", "22.47", "39.81")
    assert (row["co2_ppm_s2"], row["temperature_c_s2"], row["humidity_percent_s2"]) \
        == ("1200", "23.50", "55.00")


def test_one_missing_node_leaves_only_its_columns_blank(tmp_path):
    path = tmp_path / "people_count.csv"
    state = env_state({"s1": Reading(812, 22.47, 39.81), "s2": None})
    log_state(path, summary(12), 0.0, IDLE, classroom=state, env_labels=LABELS)
    row = dict(zip(ENV_HEADER, read_rows(path)[1]))
    assert row["co2_ppm_s1"] == "812"
    assert [row[c] for c in ENV_HEADER[-3:]] == ["", "", ""]


def test_no_environment_at_all_leaves_every_node_column_blank(tmp_path):
    path = tmp_path / "people_count.csv"
    log_state(path, summary(3), 0.0, IDLE, classroom=env_state({}), env_labels=LABELS)
    log_state(path, summary(3), 0.0, IDLE, env_labels=LABELS)  # no state object either
    rows = read_rows(path)
    assert rows[1][-6:] == [""] * 6 and rows[2][-6:] == [""] * 6


def test_header_change_when_a_node_is_added_rotates_the_old_file(tmp_path):
    path = tmp_path / "people_count.csv"
    init_csv(path, env_labels=("s1",))
    init_csv(path, env_labels=LABELS)
    assert read_rows(path) == [ENV_HEADER]
    assert len(list(tmp_path.glob("people_count.csv.old-*"))) == 1


def test_old_header_file_is_rotated_not_corrupted(tmp_path):
    path = tmp_path / "people_count.csv"
    path.write_text("timestamp,people_count\n2026-10-11T00:00:00+00:00,4\n")
    init_csv(path)
    assert read_rows(path) == [HEADER]
    backups = list(tmp_path.glob("people_count.csv.old-*"))
    assert len(backups) == 1 and "2026-10-11" in backups[0].read_text()
