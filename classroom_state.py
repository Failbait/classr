"""Aggregate in-memory classroom state. Transport-agnostic: no MQTT/BLE/IO in here."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ClassroomState:
    timestamp: datetime
    occupancy: int | None
    activity_score: float | None
    ambient_light_lux: float | None
    ambient_noise_level: float | None  # relative 0..1, NOT calibrated dBA
    # node label -> reading (co2_ppm, temperature_c, humidity_percent attributes) or None if that
    # node is unavailable; empty when no environmental nodes are configured.
    environment: dict = field(default_factory=dict)
