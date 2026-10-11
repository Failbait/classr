"""Background polling of the optional sensors. Exposes only the latest scalar values."""

import logging
import threading
import time

log = logging.getLogger(__name__)


class EnvironmentSampler:
    """Polls light (every light_interval s) and noise (as fast as its window allows) in one
    daemon thread. Sensor exceptions are logged and swallowed; the CV loop never sees them."""

    def __init__(self, light, noise, light_interval: float = 1.0, noise_stale_seconds: float = 3.0):
        self._light = light
        self._noise = noise
        self._light_interval = light_interval
        self._noise_stale = noise_stale_seconds
        self._lock = threading.Lock()
        self._lux: float | None = None
        self._noise_level: float | None = None
        self._noise_at = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="env-sampler", daemon=True)

    def start(self) -> None:
        if self._light is not None or self._noise is not None:
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        close = getattr(self._noise, "close", None)
        if close:
            close()

    def snapshot(self) -> tuple[float | None, float | None]:
        """(lux, noise_level); None where a sensor is missing, failing, or stale."""
        with self._lock:
            noise = self._noise_level
            if noise is not None and time.monotonic() - self._noise_at > self._noise_stale:
                noise = None
            return self._lux, noise

    def _run(self) -> None:
        next_light = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if self._light is not None and now >= next_light:
                self._poll_light()
                next_light = now + self._light_interval
            if self._noise is not None:
                self._poll_noise()  # blocks for one audio window
            else:
                self._stop.wait(0.05)

    def _poll_light(self) -> None:
        try:
            lux = self._light.read_lux()
        except Exception as exc:
            log.warning("Light read failed: %s", exc)
            lux = None
        with self._lock:
            self._lux = lux

    def _poll_noise(self) -> None:
        try:
            level = self._noise.read_level()
        except Exception as exc:
            log.warning("Noise read failed: %s", exc)
            level = None
            self._stop.wait(0.1)  # avoid a hot loop if the device keeps failing
        with self._lock:
            self._noise_level = level
            self._noise_at = time.monotonic()
