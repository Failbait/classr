import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sensors.microphone import Ema, level_from_samples, normalize_db, rms_dbfs
from sensors.sampler import EnvironmentSampler
from sensors.light import AutoGainLux


class FakeLight:
    def __init__(self, values):
        self.values = list(values)

    def read_lux(self):
        value = self.values.pop(0) if len(self.values) > 1 else self.values[0]  # last repeats
        if isinstance(value, Exception):
            raise value
        return value


class FakeNoise:
    def __init__(self, values):
        self.values = list(values)

    def read_level(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


# --- microphone maths -------------------------------------------------------------------

def test_rms_dbfs_of_full_scale_square_is_zero():
    assert rms_dbfs([1.0, -1.0] * 100) == 0.0


def test_rms_dbfs_removes_dc_offset():
    assert rms_dbfs([0.3] * 100) < -100  # a constant is silence, not signal


def test_rms_dbfs_of_empty_or_silent_is_floor():
    assert rms_dbfs([]) <= -120
    assert rms_dbfs([0.0] * 10) <= -120


def test_louder_signal_reads_higher():
    quiet = [0.001 * (-1) ** i for i in range(200)]
    loud = [0.1 * (-1) ** i for i in range(200)]
    assert rms_dbfs(loud) > rms_dbfs(quiet) + 30


def test_normalize_db_clamps_and_scales():
    assert normalize_db(-90, floor_db=-70, ceiling_db=-20) == 0.0
    assert normalize_db(-10, floor_db=-70, ceiling_db=-20) == 1.0
    assert normalize_db(-45, floor_db=-70, ceiling_db=-20) == 0.5


def test_level_from_samples_orders_quiet_speech_clap():
    def tone(amp):
        return [amp * (-1) ** i for i in range(400)]
    quiet, speech, clap = (level_from_samples(tone(a), -70, -20) for a in (0.0005, 0.02, 0.3))
    assert quiet < speech < clap


def test_ema_first_value_passes_through_then_smooths():
    ema = Ema(alpha=0.5)
    assert ema.update(1.0) == 1.0
    assert ema.update(0.0) == 0.5


# --- light ------------------------------------------------------------------------------

class FakeTsl:
    """Mimics the adafruit driver: saturates (RuntimeError) above a lux limit per gain."""

    GAIN_LOW, GAIN_MED, GAIN_HIGH = 0, 16, 32

    def __init__(self, true_lux):
        self.gain = self.GAIN_MED
        self.true_lux = true_lux

    @property
    def lux(self):
        if self.gain == self.GAIN_HIGH and self.true_lux > 100:
            raise RuntimeError("Overflow reading light channel!")
        if self.gain == self.GAIN_MED and self.true_lux > 2000:
            raise RuntimeError("Overflow reading light channel!")
        return self.true_lux


def test_auto_gain_steps_down_on_saturation():
    sensor = AutoGainLux(FakeTsl(5000.0), gains=(32, 16, 0))
    assert sensor.read_lux() == 5000.0


def test_auto_gain_returns_none_when_always_saturated():
    class Saturated:
        gain = 16

        @property
        def lux(self):
            raise RuntimeError("Overflow reading light channel!")

    assert AutoGainLux(Saturated(), gains=(0, 16)).read_lux() is None


# --- sampler: sensor failure must never propagate ----------------------------------------

def test_sampler_snapshot_is_none_without_sensors():
    sampler = EnvironmentSampler(light=None, noise=None)
    assert sampler.snapshot() == (None, None)


def test_sampler_survives_read_exceptions_and_reports_latest():
    light = FakeLight([RuntimeError("i2c"), 12.5])
    sampler = EnvironmentSampler(light=light, noise=FakeNoise([0.2, 0.4]), light_interval=0.01)
    sampler.start()
    time.sleep(0.2)
    sampler.stop()
    lux, noise = sampler.snapshot()
    assert lux == 12.5
    assert noise == 0.4


class CountingTsl:
    """Records gain writes; lux comes from a scripted list."""

    def __init__(self, lux_values):
        self._values = list(lux_values)
        self.gain_writes = []
        self._gain = None

    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, value):
        self.gain_writes.append(value)
        self._gain = value

    @property
    def lux(self):
        value = self._values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_auto_gain_does_not_rewrite_gain_when_unchanged():
    device = CountingTsl([100.0, 101.0, 99.0])
    sensor = AutoGainLux(device, gains=(32, 16, 0), start_index=1)
    for _ in range(3):
        sensor.read_lux()
    assert device.gain_writes == [16]  # written once, then left alone


def test_auto_gain_negative_lux_is_rejected():
    sensor = AutoGainLux(CountingTsl([-624.9]), gains=(32, 16, 0), start_index=1)
    assert sensor.read_lux() is None


def test_auto_gain_steps_up_when_dim_and_down_on_saturation():
    device = CountingTsl([0.8, 40.0, RuntimeError("Overflow"), 900.0])
    sensor = AutoGainLux(device, gains=(32, 16, 0), start_index=1)
    sensor.read_lux()  # dim at MED -> next read should use the more sensitive gain
    assert sensor.read_lux() == 40.0 and device.gain_writes == [16, 32]
    assert sensor.read_lux() == 900.0 and device.gain_writes == [16, 32, 16]
