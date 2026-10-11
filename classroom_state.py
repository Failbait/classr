"""Aggregate in-memory classroom state. Transport-agnostic: no MQTT/BLE/IO in here."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClassroomState:
    timestamp: datetime
    occupancy: int | None
    activity_score: float | None
    ambient_light_lux: float | None
    ambient_noise_level: float | None  # relative 0..1, NOT calibrated dBA
