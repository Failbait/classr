# Next Milestone: Add Local Environment Sensors on the Raspberry Pi

## Context

The CV side is now mostly complete:

```text
Camera Module 3
    ↓
YOLO26s
    ↓
occupancy
    ↓
aggregate activity / movement
```

A live classroom activity test is not currently possible, so do not block further project progress on that.

Available hardware now includes:

- one ambient-light sensor
- one digital microphone
- Raspberry Pi 5

The next milestone should therefore add **local environmental sensing directly to the Pi**.

This is intentionally simpler than starting the remote BLE CO₂ node immediately.

The immediate sensor pipeline becomes:

```text
light sensor ─I²C─────────┐
                           │
digital microphone ─I²S───┤
                           ▼
                    Raspberry Pi 5
                           │
                   normalized state
                           │
                        local log
```

No raw audio may be stored.

---

# Goal

Add two environmental signals:

```text
ambient_light_lux
ambient_noise_level
```

and integrate them into the same aggregate classroom state/log as:

```text
occupancy
activity_score
```

The result should look conceptually like:

```json
{
  "occupancy": 12,
  "activity_score": 0.18,
  "ambient_light_lux": 387.4,
  "ambient_noise_level": 0.23
}
```

Do not add MQTT, dashboard, BLE, CO₂, database, or break-state logic yet.

---

# Light Sensor

## Hardware

Use the available digital lux sensor.

If it is the TSL2591 discussed previously, use it over I²C.

Typical Pi wiring:

```text
TSL2591 VCC → 3.3 V
TSL2591 GND → GND
TSL2591 SDA → GPIO 2 / SDA
TSL2591 SCL → GPIO 3 / SCL
```

Do not assume the exact sensor model in code without confirming the actual connected part.

Design the software behind a small light-sensor interface so the driver can be swapped if necessary.

---

## Light Sensor Output

Expose:

```text
ambient_light_lux: float
```

Example:

```text
387.4 lux
```

Sample much more slowly than audio.

Suggested initial interval:

```text
1 sample / second
```

or slower.

Light conditions do not require high-frequency sampling.

---

# Microphone

## Objective

The microphone is **not** for recording speech.

It should only generate an aggregate scalar describing environmental sound level.

Do not store:

- audio files
- PCM history
- speech
- frequency-domain recordings
- raw microphone streams

Raw audio samples may exist briefly in memory only while calculating the current aggregate level.

---

## Microphone Input

Use the digital microphone discussed previously via I²S.

Keep microphone acquisition in a dedicated module.

Conceptually:

```text
I²S microphone
    ↓
short in-memory sample buffer
    ↓
RMS / level calculation
    ↓
discard samples
```

---

# Noise Metric

Do **not** label the value `dBA` unless the microphone has been calibrated and proper frequency weighting is implemented.

For the first version use:

```text
ambient_noise_level
```

as a normalized relative signal.

Recommended range:

```text
0.0 – 1.0
```

Alternatively keep an internal RMS value and normalize it for application output.

---

## RMS

For a short sample window:

```python
rms = sqrt(mean(samples ** 2))
```

Use a window of approximately:

```text
250–500 ms
```

Then discard the raw samples.

---

## Normalization

Map RMS to a useful normalized range.

Do not assume fixed calibration is universally correct.

Make the normalization floor and ceiling configurable.

Conceptually:

```python
normalized = clamp(
    (rms - noise_floor) / (noise_ceiling - noise_floor),
    0.0,
    1.0,
)
```

The initial floor/ceiling may be established experimentally in:

```text
quiet room
normal conversation
louder activity
```

This is a relative classroom activity signal, not a certified acoustic measurement.

---

# Smoothing

Both environmental signals may be smoothed lightly.

For microphone:

```text
short EMA
```

is appropriate.

For lux:

```text
EMA or raw value
```

is fine.

Avoid over-smoothing noise because sudden changes may later contribute to break/activity inference.

---

# Software Structure

Keep hardware access separate from application state.

For example:

```text
people-counter/
├── main.py
├── detector.py
├── activity.py
├── logger.py
├── config.py
├── sensors/
│   ├── __init__.py
│   ├── light.py
│   └── microphone.py
└── ...
```

Adapt to the actual repository rather than reorganizing unnecessarily.

Suggested interfaces:

```python
class LightSensor:
    def read_lux(self) -> float | None:
        ...
```

and:

```python
class NoiseSensor:
    def read_level(self) -> float | None:
        ...
```

The main application should not depend directly on a specific sensor library.

---

# Failure Handling

Sensor failure must not stop CV.

If light or microphone initialization fails:

```text
log an error
mark that sensor unavailable
continue running occupancy/activity
```

If a read temporarily fails:

```text
return None
continue application
retry next interval
```

Do not terminate the whole system because one sensor is missing.

---

# Unified Classroom State

Create or extend an aggregate in-memory state.

For example:

```python
@dataclass
class ClassroomState:
    timestamp: datetime
    occupancy: int | None
    activity_score: float | None
    ambient_light_lux: float | None
    ambient_noise_level: float | None
```

Do not put transport-specific logic such as MQTT inside this data structure.

This state will later be extended with:

```text
CO₂
temperature
humidity
break state
```

---

# Logging

Extend local logging to include the new values.

Example:

```csv
timestamp,people_count,activity_score,ambient_light_lux,ambient_noise_level
2026-10-11T14:32:05+02:00,12,0.18,387.4,0.23
```

If a sensor is unavailable, write blank/null for that field.

Do not store microphone sample buffers.

---

# Console Debugging

During development, concise output is useful:

```text
[CV] occupancy=12 activity=0.18
[LUX] 387.4 lux
[NOISE] level=0.23
```

Do not print audio sample arrays.

---

# Testing Without a Full Classroom

These sensors can be tested immediately.

## Light

Test at least:

```text
sensor covered
normal room lighting
phone flashlight / bright light
```

Expected:

```text
lux rises and falls sensibly
```

Exact calibration is not required for the prototype.

## Noise

Test:

```text
quiet room
normal speech nearby
hand clap / louder noise
```

Expected:

```text
quiet < speech < clap
```

The metric does not need to represent calibrated decibels.

---

# Privacy Requirement

The microphone implementation must make the privacy design explicit:

```text
raw audio is processed locally in volatile memory
only a scalar noise level leaves the microphone module
raw audio is immediately discarded
no audio recording functionality exists
```

This is an architectural requirement, not merely a UI promise.

---

# Non-Goals

Do not add yet:

- speech recognition
- audio recording
- calibrated dBA
- CO₂ sensor
- STM32WB55
- BLE
- MQTT
- Mosquitto
- database
- dashboard
- LED strip
- break-state logic
- cloud services

---

# Acceptance Criteria

This milestone is complete when:

1. the Pi reads the available lux sensor
2. lux is exposed as a numeric value
3. the Pi receives samples from the digital microphone
4. microphone samples are converted to a relative scalar noise level
5. raw audio is discarded immediately
6. no audio is stored
7. CV continues if either sensor is unavailable
8. occupancy, activity, lux, and noise can coexist in one classroom state
9. all aggregate values can be logged together
10. quiet/speech/loud noise tests produce sensible relative values
11. covered/normal/bright light tests produce sensible lux changes

---

# After This Milestone

The next milestone should be the remote environmental node:

```text
SCD30
    ↓ I²C
STM32WB55
    ↓ BLE GATT
Raspberry Pi
```

That introduces the project's constrained wireless sensor path and gives:

```text
CO₂
temperature
humidity
```

Once both local sensors and the BLE node exist, introduce MQTT and a normalized topic/state model.
