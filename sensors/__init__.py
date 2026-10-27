"""Local environment sensors. The application only depends on the two protocols below."""

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class LightSensor(Protocol):
    def read_lux(self) -> float | None: ...


class NoiseSensor(Protocol):
    def read_level(self) -> float | None: ...


def open_light_sensor(config) -> LightSensor | None:
    """Return a ready light sensor, or None (logged) if disabled or unavailable."""
    if not config.LIGHT_ENABLED:
        return None
    try:
        from sensors.light import open_tsl2591
        return open_tsl2591()
    except Exception as exc:  # any hardware/driver failure must not stop the CV
        log.error("Light sensor unavailable: %s", exc)
        return None


def open_noise_sensor(config) -> NoiseSensor | None:
    """Return a ready microphone level sensor, or None (logged) if disabled or unavailable."""
    if not config.NOISE_ENABLED:
        return None
    try:
        from sensors.microphone import open_microphone
        return open_microphone(config)
    except Exception as exc:
        log.error("Microphone unavailable: %s", exc)
        return None


def open_environment_client(config):
    """Return a started BLE environmental hub (all configured nodes), or None (logged) if disabled or unavailable.

    The client retries forever in the background, so a missing node is not an error here."""
    if not config.ENV_BLE_ENABLED:
        return None
    try:
        from sensors.ble_environment import BleEnvironmentHub
        hub = BleEnvironmentHub(
            config.ENV_NODES,
            (config.ENV_CO2_UUID, config.ENV_TEMPERATURE_UUID, config.ENV_HUMIDITY_UUID),
            config.ENV_RETRY_SECONDS, config.ENV_STALE_SECONDS, config.ENV_SCAN_SECONDS)
        hub.start()
        return hub
    except Exception as exc:  # e.g. bleak not installed
        log.error("BLE environment client unavailable: %s", exc)
        return None
