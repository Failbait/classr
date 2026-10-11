"""Live readout for bench-testing the sensors: python -m sensors.calibrate

Prints lux and the raw microphone dBFS next to the normalized level, so NOISE_FLOOR_DBFS /
NOISE_CEILING_DBFS in config.py can be set from a quiet room and a hand clap. Scalars only."""

import time

import config
from sensors import open_light_sensor
from sensors.microphone import rms_dbfs


def main() -> None:
    import sounddevice as sd

    light = open_light_sensor(config)
    frames = int(config.NOISE_SAMPLE_RATE * config.NOISE_WINDOW_SECONDS)
    print("Ctrl+C to stop. dBFS: quiet room -> NOISE_FLOOR, hand clap -> NOISE_CEILING.")
    with sd.InputStream(device=config.NOISE_DEVICE, samplerate=config.NOISE_SAMPLE_RATE,
                        channels=config.NOISE_CHANNELS, dtype="int32") as stream:
        while True:
            data, _ = stream.read(frames)
            db = rms_dbfs((data[:, config.NOISE_CHANNEL_INDEX] / 2147483648.0).tolist())
            lux = light.read_lux() if light else None
            print(f"[LUX] {'n/a' if lux is None else f'{lux:8.1f}'}   [NOISE] {db:6.1f} dBFS")
            time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
