# People Counter MVP

## Goal

Build a Raspberry Pi 5 application that uses a Raspberry Pi Camera Module to estimate the number of people visible in a classroom and log that count every 5 seconds.

The first version should deliberately stay simple. Do **not** implement tracking, standing/sitting classification, break detection, MQTT, dashboards, microphones, lux sensors, or other IoT features yet.

The purpose of this MVP is only to prove that:

- the camera pipeline works,
- person detection works,
- the current number of visible people can be estimated,
- the aggregate count can be logged reliably every 5 seconds.

## Platform

Assume:

- Raspberry Pi 5
- Raspberry Pi OS 64-bit with Desktop
- Raspberry Pi Camera Module
- Python 3
- local display available for debugging

## Technology

Use Python.

For the camera:

- `Picamera2`

For person detection:

- use a lightweight pretrained object detector,
- prefer an Ultralytics YOLO nano model for the first prototype,
- use the pretrained `person` class,
- do not train a custom model yet.

For image handling / preview:

- OpenCV
- NumPy as needed

If `opencv-python` conflicts with the Raspberry Pi system OpenCV / Picamera2 stack, prefer the Raspberry Pi OS packaged OpenCV rather than forcing a pip package that breaks camera integration.

## Privacy Requirements

The system is intended to produce anonymous aggregate classroom occupancy data.

Therefore:

- do not save raw images,
- do not save video,
- do not log individual detections,
- do not assign persistent person IDs,
- do not implement face recognition,
- do not implement person re-identification,
- only persist the aggregate people count.

## Core Data Flow

```text
Picamera2 frame
    ↓
person detector
    ↓
filter class = person
    ↓
filter detections below confidence threshold
    ↓
count remaining detections
    ↓
draw bounding boxes + current count on preview
    ↓
every 5 seconds:
append timestamp + count to CSV
```

## Logging

The application must append one aggregate count sample every 5 seconds.

Each sample must contain at minimum:

```text
timestamp
people_count
```

Use ISO 8601 timestamps.

Store the data in:

```text
data/people_count.csv
```

Example:

```csv
timestamp,people_count
2026-10-06T15:30:00+02:00,4
2026-10-06T15:30:05+02:00,5
2026-10-06T15:30:10+02:00,5
```

Requirements:

- create the CSV file automatically if it does not exist,
- create the header automatically,
- append new rows,
- never overwrite previous samples during normal startup.

## Timing

Make the logging interval configurable:

```python
LOG_INTERVAL_SECONDS = 5
```

Do not tie logging directly to inference frequency.

Inference may run continuously or at a higher frequency, but logging should use elapsed monotonic time so samples are written approximately every 5 seconds regardless of frame rate.

## Detection Configuration

Make the confidence threshold configurable:

```python
CONFIDENCE_THRESHOLD = 0.5
```

Only detections classified as `person` and above the threshold contribute to the count.

## Live Preview

The application should display a live camera preview during development.

The preview should show:

- camera image,
- bounding box around each detected person,
- confidence score for each detected person,
- large text showing the current count, for example:

```text
People: 7
```

Optionally also show:

- FPS,
- inference time.

Do not persist the annotated frames.

## Suggested Project Structure

Keep the implementation simple:

```text
people-counter/
├── main.py
├── camera.py
├── detector.py
├── logger.py
├── config.py
├── requirements.txt
├── README.md
└── data/
```

### `camera.py`

Responsibilities:

- initialize Picamera2,
- configure the camera,
- start camera capture,
- return frames,
- cleanly stop the camera.

### `detector.py`

Responsibilities:

- load the pretrained model,
- run inference,
- keep only `person` detections,
- apply confidence threshold,
- return bounding boxes,
- return confidence values,
- return aggregate person count.

### `logger.py`

Responsibilities:

- create the data directory if needed,
- create the CSV file if needed,
- create the CSV header if needed,
- append timestamp + people count.

### `config.py`

Contain simple configuration values such as:

```python
CONFIDENCE_THRESHOLD = 0.5
LOG_INTERVAL_SECONDS = 5
CSV_PATH = "data/people_count.csv"
```

### `main.py`

Responsibilities:

- initialize camera,
- initialize detector,
- run the application loop,
- perform inference,
- display the preview,
- maintain logging timing,
- append the current count every 5 seconds,
- handle clean shutdown.

## Implementation Constraints

Keep the first version deliberately small.

Do not introduce:

- databases,
- MQTT,
- web servers,
- async frameworks,
- dependency injection,
- elaborate class hierarchies,
- tracking frameworks,
- persistent detection IDs,
- custom model training.

Plain Python modules and functions are sufficient.

## Shutdown

The program must exit cleanly when the user presses `Ctrl+C`.

On shutdown:

- stop Picamera2,
- release resources,
- close OpenCV windows.

## Dependencies

Start with approximately:

```text
picamera2
ultralytics
numpy
```

OpenCV may already be installed through Raspberry Pi OS. Prefer the system-provided version if that avoids Picamera2 compatibility issues.

## Camera Sanity Check

Before running the people counter, confirm that the camera itself works:

```bash
rpicam-hello
```

For a continuous preview:

```bash
rpicam-hello -t 0
```

To list detected cameras:

```bash
rpicam-hello --list-cameras
```

## Virtual Environment

Use a Python virtual environment for project dependencies where practical.

Example:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If Picamera2 is installed system-wide and is not visible from the venv, create the venv with system site packages instead:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```

Then install project-specific packages inside the venv.

## README Requirements

Create a `README.md` containing:

- project purpose,
- hardware assumptions,
- Python / venv setup,
- required packages,
- camera sanity test,
- how to run the application,
- location of the CSV output,
- how to change the confidence threshold,
- how to change the logging interval,
- note that raw images/video are not persisted.

## Acceptance Criteria

The MVP is complete when all of the following are true:

1. The camera starts successfully.
2. A live preview is displayed.
3. Visible people receive bounding boxes.
4. Only the `person` class contributes to the count.
5. The current people count is clearly shown in the preview.
6. One aggregate people count is appended to CSV every 5 seconds.
7. Timestamps are stored in ISO 8601 format.
8. No raw images or video are stored.
9. No persistent person IDs are created.
10. The application exits cleanly with `Ctrl+C`.

## Non-Goals for This MVP

Do not implement these yet:

- standing / sitting classification,
- person tracking,
- break detection,
- classroom activity score,
- MQTT,
- BLE sensor integration,
- CO₂ integration,
- microphone / noise measurements,
- lux measurements,
- database,
- dashboard,
- LED indicator,
- custom training.

Those can be added after the camera and people-counting pipeline has been validated.
