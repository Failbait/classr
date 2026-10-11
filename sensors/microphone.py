"""INMP441 (I2S) noise level.

PRIVACY: raw audio is processed locally in volatile memory. Only one scalar (0..1) leaves
this module, and the sample buffer is dropped as soon as that scalar is computed. There is no
code path that writes, queues, or returns samples; do not add one.
"""

import math

SILENCE_DBFS = -120.0  # reported for an empty or perfectly silent window


class Ema:
    """Exponential moving average. alpha = weight of the newest value (1.0 = no smoothing)."""

    def __init__(self, alpha: float):
        self._alpha = alpha
        self._value: float | None = None

    def update(self, x: float) -> float:
        self._value = x if self._value is None else self._alpha * x + (1 - self._alpha) * self._value
        return self._value


def rms_dbfs(samples) -> float:
    """RMS of float samples in -1..1 (DC offset removed) as dB relative to full scale."""
    n = len(samples)
    if n == 0:
        return SILENCE_DBFS
    mean = sum(samples) / n
    rms = math.sqrt(sum((s - mean) ** 2 for s in samples) / n)
    return max(20 * math.log10(rms), SILENCE_DBFS) if rms > 0 else SILENCE_DBFS


def normalize_db(db: float, floor_db: float, ceiling_db: float) -> float:
    return min(max((db - floor_db) / (ceiling_db - floor_db), 0.0), 1.0)


def level_from_samples(samples, floor_db: float, ceiling_db: float) -> float:
    return normalize_db(rms_dbfs(samples), floor_db, ceiling_db)


class I2sNoiseSensor:
    """Reads one short window from the sound card per call and returns a smoothed 0..1 level."""

    def __init__(self, stream, config):
        self._stream = stream
        self._frames = int(config.NOISE_SAMPLE_RATE * config.NOISE_WINDOW_SECONDS)
        self._channel = config.NOISE_CHANNEL_INDEX
        self._floor = config.NOISE_FLOOR_DBFS
        self._ceiling = config.NOISE_CEILING_DBFS
        self._ema = Ema(config.NOISE_SMOOTHING_ALPHA)

    def read_level(self) -> float | None:
        try:
            data, _overflowed = self._stream.read(self._frames)
        except Exception:
            return None  # transient capture error: caller retries next interval
        # 24-bit sample left-justified in int32 -> float -1..1. `data` goes out of scope on return.
        samples = (data[:, self._channel] / 2147483648.0).tolist()
        return self._ema.update(level_from_samples(samples, self._floor, self._ceiling))

    def close(self) -> None:
        self._stream.stop()
        self._stream.close()


def open_microphone(config) -> I2sNoiseSensor:
    import sounddevice as sd

    stream = sd.InputStream(device=config.NOISE_DEVICE, samplerate=config.NOISE_SAMPLE_RATE,
                            channels=config.NOISE_CHANNELS, dtype="int32")
    stream.start()
    sensor = I2sNoiseSensor(stream, config)
    if sensor.read_level() is None:
        stream.close()
        raise RuntimeError("microphone opened but delivers no audio")
    return sensor
