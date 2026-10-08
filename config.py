"""Configuration values for the people counter."""

CONFIDENCE_THRESHOLD = 0.3  # tuned for yolo26s on the benchmark sets
LOG_INTERVAL_SECONDS = 5
CSV_PATH = "data/people_count.csv"

MODEL_NAME = "yolo26s.pt"  # or "rfdetr-small", another YOLO file, ...
PERSON_CLASS_ID = 0  # COCO class 0 = person
INFERENCE_IMAGE_SIZE = 1600  # YOLO: multiple of 32. Packed rows needed >= 1600 px (0 = RF-DETR native)

# --- Post-filtering of raw detections (applied to every backend, see detector.py) ---
# The model is queried down to CANDIDATE_FLOOR; rules below decide which candidates count.
CANDIDATE_FLOOR = 0.2
# Far-away people are small and score lower: accept small boxes at a lower confidence.
# SMALL_BOX_CONFIDENCE = 0 disables the rule.
SMALL_BOX_HEIGHT_FRACTION = 0.12  # box height / image height at or below this = "small"
SMALL_BOX_CONFIDENCE = 0.3
# Drop a box when this fraction of it lies inside a higher-scoring box (duplicate boxes on
# one person, e.g. upper-body + full-body). 0 disables the rule.
DEDUPE_CONTAINMENT = 0.85

# imx708 sensor modes: 1536x864 is a centre CROP of the sensor (narrower view), so the live
# stream asks for the 2304x1296 mode (full field of view) and the ISP scales it down to
# CAMERA_RESOLUTION. The detectors shrink frames to 512-768 px anyway.
CAMERA_SENSOR_MODE = (2304, 1296)
CAMERA_RESOLUTION = (1536, 864)
# The camera is mounted upside down: rotate frames 180 degrees (live and --save-frame).
CAMERA_ROTATE_180 = True
# Focus: None = one autofocus cycle at startup, then lock (stops focus hunting).
# Or a fixed lens position in dioptres (1 / distance in metres; 0 = infinity, e.g. 0.25 = 4 m).
CAMERA_LENS_POSITION = None
# --save-frame uses the full sensor for the sharpest source images (e.g. for composites).
CAPTURE_RESOLUTION = (4608, 2592)

START_FULLSCREEN = False  # press "f" in the preview to toggle at runtime

CAPTURE_DIR = "captures"  # --save-frame output (git-ignored; contains images of people)
