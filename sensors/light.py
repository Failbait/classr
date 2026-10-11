"""TSL2591 ambient-light sensor over I2C, behind the small LightSensor interface."""

import logging
import time

log = logging.getLogger(__name__)


class AutoGainLux:
    """Wraps an adafruit TSL2591. Tries the most sensitive gain first and steps down on
    saturation (the driver raises RuntimeError), so dim and bright rooms both read sensibly."""

    def __init__(self, device, gains, settle_seconds: float = 0.0):
        self._device = device
        self._gains = tuple(gains)  # ordered from most to least sensitive
        self._settle_seconds = settle_seconds  # one integration cycle after a gain change

    def read_lux(self) -> float | None:
        for gain in self._gains:
            self._device.gain = gain
            if self._settle_seconds:
                time.sleep(self._settle_seconds)
            try:
                return float(self._device.lux)
            except RuntimeError:  # saturated at this gain
                continue
        return None


def open_tsl2591() -> AutoGainLux:
    import adafruit_tsl2591
    import board
    import busio

    device = adafruit_tsl2591.TSL2591(busio.I2C(board.SCL, board.SDA))
    device.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
    gains = (adafruit_tsl2591.GAIN_HIGH, adafruit_tsl2591.GAIN_MED,
             adafruit_tsl2591.GAIN_LOW)
    sensor = AutoGainLux(device, gains, settle_seconds=0.12)
    if sensor.read_lux() is None:
        raise RuntimeError("TSL2591 found but returns no reading")
    return sensor
