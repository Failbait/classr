# Next Milestone: SCD30 Environmental Node over BLE

## Context

The system currently has working:

```text
YOLO26s occupancy detection
aggregate activity / movement estimation
ambient light sensing
ambient sound-level sensing
```

The next milestone should introduce the first **wireless constrained sensor node**.

Use:

```text
SCD30
  ↓ I²C
STM32WB55
  ↓ BLE GATT
Raspberry Pi 5
```

This is the most important next architectural step because it adds:

- a separate embedded sensor node
- a real wireless IoT link
- a clear gateway role for the Raspberry Pi
- CO₂, temperature, and humidity

Do not add MQTT yet.

First prove the BLE path end-to-end.

---

# Goal

Make one STM32WB55 + SCD30 node periodically send:

```text
CO₂ ppm
temperature °C
relative humidity %
```

to the Raspberry Pi over BLE.

The Pi should:

1. discover the node
2. connect
3. subscribe to measurements
4. decode values
5. expose them in the unified classroom state
6. log them alongside the existing CV, light, and sound signals

---

# End-to-End Path

```text
SCD30
  ↓
I²C
  ↓
STM32WB55
  ↓
BLE GATT notifications
  ↓
Raspberry Pi 5
  ↓
ClassroomState
  ↓
local logging
```

---

# STM32WB55 Responsibilities

The WB55 should:

1. initialize the SCD30 over I²C
2. start periodic measurements
3. poll/check when a new measurement is available
4. read:
   - CO₂
   - temperature
   - humidity
5. encode the latest values into one BLE payload
6. notify subscribed clients
7. remain functional even if no BLE client is connected

Keep all application logic off the WB55.

Do not calculate air-quality state, warnings, averages, or break logic here.

---

# Sampling Interval

Use approximately:

```text
5 seconds
```

for environmental updates.

This is sufficient for:

```text
CO₂
temperature
humidity
```

and avoids unnecessary traffic.

---

# BLE GATT Service

Create one custom service.

Recommended structure:

```text
Environmental Service
└── Measurement Characteristic
```

The measurement characteristic should support:

```text
READ
NOTIFY
```

Using READ makes manual debugging easier.

---

# BLE Payload

Use one compact binary payload instead of JSON.

Recommended packed structure:

```c
typedef struct __attribute__((packed)) {
    uint16_t co2_ppm;
    int16_t temperature_centi_c;
    uint16_t humidity_centi_percent;
} EnvironmentalSample;
```

Meaning:

```text
co2_ppm
    integer ppm

temperature_centi_c
    temperature °C × 100

humidity_centi_percent
    relative humidity % × 100
```

Example:

```text
CO₂:          812 ppm
Temperature:  22.47 °C
Humidity:     39.81 %
```

becomes:

```text
812
2247
3981
```

Use little-endian encoding consistently.

---

# Advertising

Use a recognizable device name:

```text
CLASSR-ENV-01
```

Also advertise the environmental service UUID if convenient.

The Pi should ideally discover by service UUID rather than permanently depending on the human-readable name.

---

# Raspberry Pi Client

Use Python and Bleak.

Add a dedicated sensor module, for example:

```text
sensors/
├── __init__.py
├── light.py
├── microphone.py
└── ble_environment.py
```

Suggested decoded model:

```python
@dataclass
class EnvironmentalSample:
    timestamp: datetime
    co2_ppm: int
    temperature_c: float
    humidity_percent: float
```

The Raspberry Pi should assign the timestamp.

The WB55 does not need wall-clock time.

---

# BLE Client Behavior

The Pi should:

```text
scan
→ connect
→ subscribe
→ receive notifications
→ decode payload
→ update latest environmental state
```

If the connection is lost:

```text
mark sensor unavailable
continue the rest of the application
retry connection after a short interval
```

Suggested reconnect interval:

```text
5–10 seconds
```

Do not build complex exponential backoff for this prototype.

---

# Unified Classroom State

Extend the existing state to include:

```python
@dataclass
class ClassroomState:
    timestamp: datetime

    occupancy: int | None
    activity_score: float | None

    ambient_light_lux: float | None
    ambient_noise_level: float | None

    co2_ppm: int | None
    temperature_c: float | None
    humidity_percent: float | None
```

Do not couple this object to BLE or future MQTT transport details.

---

# Logging

Extend the aggregate log.

Example:

```csv
timestamp,people_count,activity_score,ambient_light_lux,ambient_noise_level,co2_ppm,temperature_c,humidity_percent
2026-10-12T14:32:05+02:00,12,0.18,387.4,0.23,812,22.47,39.81
```

If BLE data is unavailable:

```text
leave environmental fields blank/null
```

Do not stop logging other sensors.

---

# Debugging

Useful temporary output:

```text
[BLE] found CLASSR-ENV-01
[BLE] connected
[ENV] CO2=812 ppm temp=22.47 C humidity=39.81 %
```

Do not flood the console with every internal BLE event.

---

# Failure Handling

## WB55

Handle:

```text
SCD30 not detected
I²C read failure
invalid measurement
BLE not connected
```

A sensor read failure should not crash the BLE stack.

## Raspberry Pi

Handle:

```text
device not found
connection timeout
disconnect
invalid payload length
malformed measurement
```

The rest of the application must continue running.

---

# Testing

A full classroom is not needed.

## CO₂

Test:

```text
normal room
briefly breathe near sensor
move sensor near open window / fresher air
```

Expected:

```text
CO₂ changes plausibly
```

Do not breathe directly into the sensor for extended periods.

## Temperature

Test:

```text
room temperature
warm hand near sensor
cooler location
```

Expected:

```text
temperature changes slowly
```

## Humidity

Test:

```text
normal room
briefly breathe near sensor
move away again
```

Expected:

```text
humidity responds and settles
```

## BLE Reliability

Verify:

```text
power WB55 off
Pi keeps running

power WB55 back on
Pi reconnects automatically
```

Also verify that reconnecting does not create duplicate subscriptions.

---

# Non-Goals

Do not add yet:

```text
second SCD30 node
MQTT
Mosquitto
CoAP
database
dashboard
LED strip
break-state logic
cloud
```

---

# Acceptance Criteria

This milestone is complete when:

1. SCD30 is read reliably by WB55 over I²C.
2. WB55 advertises a BLE environmental service.
3. Pi discovers the node.
4. Pi connects automatically.
5. Pi receives periodic notifications.
6. CO₂ decodes correctly.
7. temperature decodes correctly.
8. humidity decodes correctly.
9. BLE disconnect does not crash the application.
10. Pi reconnects after the node returns.
11. the values appear in `ClassroomState`.
12. the values are logged alongside occupancy, activity, light, and sound.

---

# After This Milestone

Once this is stable, the next architectural milestone should be:

```text
MQTT on the Raspberry Pi
```

At that point the Pi becomes the explicit gateway between:

```text
BLE sensor nodes
local Pi sensors
CV inference
```

and:

```text
MQTT consumers
dashboard
database
LED indicator
```

Possible future topics:

```text
classroom/01/vision/occupancy
classroom/01/vision/activity

classroom/01/environment/light
classroom/01/environment/noise

classroom/01/sensors/front/co2
classroom/01/sensors/front/temperature
classroom/01/sensors/front/humidity
```

But do not introduce MQTT until this first BLE node works reliably.
