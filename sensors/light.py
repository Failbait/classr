"""TSL2591 ambient-light sensor over I2C, behind the small LightSensor interface."""

import logging
import time

log = logging.getLogger(__name__)


class AutoGainLux:
    """Wraps an adafruit TSL2591 with sticky auto-gain.

    The gain register is only rewritten when it has to change (each write restarts the sensor's
    integration, so rewriting it every read returns mixed, garbage data). It steps down when the
    channel saturates (driver raises RuntimeError) and up when the room is very dim. Negative lux
    (the driver's formula on inconsistent channel data) is rejected as None."""

    DIM_LUX = 3.0  # below this at the current gain, use the next more sensitive gain next time

    def __init__(self, device, gains, start_index: int = 0, settle_seconds: float = 0.0):
        self._device = device
        self._gains = tuple(gains)  # ordered from most to least sensitive
        self._index = start_index
        self._settle_seconds = settle_seconds  # about two integration cycles after a gain change
        self._applied = None

    def _apply(self, index: int) -> None:
        if self._applied != index:
            self._device.gain = self._gains[index]
            self._applied = index
            if self._settle_seconds:
                time.sleep(self._settle_seconds)

    def read_lux(self) -> float | None:
        for index in range(self._index, len(self._gains)):
            self._apply(index)
            try:
                lux = float(self._device.lux)
            except RuntimeError:  # saturated at this gain
                continue
            self._index = index
            if lux < 0:
                return None
            if lux < self.DIM_LUX and index > 0:
                self._index = index - 1  # take effect on the next read
            return lux
        self._index = len(self._gains) - 1
        return None


def open_tsl2591() -> AutoGainLux:
    import adafruit_tsl2591
    import board
    import busio

    device = adafruit_tsl2591.TSL2591(busio.I2C(board.SCL, board.SDA))
    device.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
    gains = (adafruit_tsl2591.GAIN_HIGH, adafruit_tsl2591.GAIN_MED,
             adafruit_tsl2591.GAIN_LOW)
    sensor = AutoGainLux(device, gains, start_index=1, settle_seconds=0.25)
    if sensor.read_lux() is None:
        raise RuntimeError("TSL2591 found but returns no reading")
    return sensor
