"""Configuration values for the people counter."""

CONFIDENCE_THRESHOLD = 0.3  # tuned for yolo26s on the benchmark sets
LOG_INTERVAL_SECONDS = 5
CSV_PATH = "data/people_count.csv"

MODEL_NAME = "yolo26s_ncnn_model"  # NCNN export of yolo26s.pt at INFERENCE_IMAGE_SIZE (python export_ncnn.py); or "yolo26s.pt", "rfdetr-small"
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

# --- Posture (seated / standing / unknown), geometry heuristic in posture.py ---
# Depth proxy = box bottom y / frame height. Each zone is (max_bottom_y, seated_max, standing_min),
# the last two being box height / frame height: <= seated_max is SEATED, >= standing_min is
# STANDING, in between is UNKNOWN. PLACEHOLDER values: calibrate on real frames of the mounted camera.
POSTURE_ZONES = [(0.40, 0.10, 0.16), (0.70, 0.20, 0.30), (1.00, 0.35, 0.50)]  # far, middle, near
POSTURE_EDGE_MARGIN_PX = 4  # box this close to the frame edge is truncated -> UNKNOWN
POSTURE_MIN_ASPECT = 0.8  # height / width below this (very wide box) -> UNKNOWN
POSTURE_SMOOTHING_WINDOW = 5  # median of the last N standing_ratio samples (aggregate only)

# --- Activity (aggregate movement between detections), see activity.py ---
# Motion is a box's centroid displacement divided by its previous size (max of width/height),
# so far-away people are not under-counted. PLACEHOLDER thresholds: tune on real recordings.
ACTIVITY_MOVING_THRESHOLD = 0.15  # normalized motion >= this = MOVING (detector jitter is ~0.03)
ACTIVITY_MATCH_MAX_DISTANCE = 1.0  # max normalized centroid distance for a frame-to-frame match
ACTIVITY_MATCH_MIN_IOU = 0.3  # ...or any pair overlapping at least this much
ACTIVITY_MAX_GAP_SECONDS = 10.0  # forget the previous detections after this long (privacy, staleness)
ACTIVITY_LOST_GRACE_SAMPLES = 1  # a box must be missing this many extra samples to count as lost
ACTIVITY_SIZE_WEIGHT = 0.5  # box width/height change (e.g. standing up) counts this much as motion
ACTIVITY_GLOBAL_SHIFT_MIN_MATCHES = 5  # need this many matches to estimate a camera shift
ACTIVITY_GLOBAL_SHIFT_MAX = 0.1  # median shift above this is real crowd movement, not camera shake
ACTIVITY_W_RATIO = 0.7  # activity_score = W_RATIO * changed fraction + W_MOTION * motion level
ACTIVITY_W_MOTION = 0.3
ACTIVITY_MOTION_SATURATION = 0.5  # mean normalized motion that counts as the maximum
ACTIVITY_SMOOTHING_SECONDS = 5.0  # EMA time constant for activity_score

# --- Local environment sensors (sensors/), both optional: a missing sensor never stops the CV ---
LIGHT_ENABLED = True  # TSL2591 over I2C (GPIO2 SDA / GPIO3 SCL)
LIGHT_INTERVAL_SECONDS = 1.0
LIGHT_SMOOTHING_ALPHA = 1.0  # EMA weight of the newest lux sample; 1.0 = raw value

NOISE_ENABLED = True  # INMP441 over I2S (see README / setup notes for the dtoverlay)
NOISE_DEVICE = None  # sounddevice device name or index; None = system default input
NOISE_SAMPLE_RATE = 48000
NOISE_CHANNELS = 2  # the I2S card is stereo; INMP441 with L/R tied to GND sends on the left
NOISE_CHANNEL_INDEX = 0  # 0 = left, 1 = right
NOISE_WINDOW_SECONDS = 0.4  # raw samples live in memory only this long, then are discarded
# ambient_noise_level = (dBFS - FLOOR) / (CEILING - FLOOR), clamped to 0..1. PLACEHOLDER values:
# measured with python -m sensors.calibrate: quiet room ~ -82, talking ~ -35..-25, loud ~ -21.
NOISE_FLOOR_DBFS = -80.0
NOISE_CEILING_DBFS = -20.0
NOISE_SMOOTHING_ALPHA = 0.5  # EMA weight of the newest window; short on purpose, spikes matter
NOISE_STALE_SECONDS = 3.0  # a level older than this is reported as unavailable (None)

# --- BLE environmental node (STM32WB55 + SCD30), see sensors/ble_environment.py ---
ENV_BLE_ENABLED = True
# label -> advertised BLE name. Discovery is by name (the nodes share one service UUID, and the
# UUID does not fit in the advertisement). The label becomes the CSV column suffix, e.g. co2_ppm_s1.
# Each board's name is APPBLE_NODE_NAME in firmware/.../BLE_EnvNode/STM32_WPAN/App/app_ble.c.
ENV_NODES = {"s1": "classr-s1", "s2": "classr-s2"}
# Must match STM32_WPAN/App/envs.c. Service 0000a000-..., base 0000xxxx-4A34-4B2A-9D0C-53574F495430. Each characteristic is
# READ + NOTIFY, 2 bytes little-endian: CO2 u16 ppm, temperature i16 degC*100, humidity u16 %RH*100.
ENV_CO2_UUID = "0000a001-4a34-4b2a-9d0c-53574f495430"
ENV_TEMPERATURE_UUID = "0000a002-4a34-4b2a-9d0c-53574f495430"
ENV_HUMIDITY_UUID = "0000a003-4a34-4b2a-9d0c-53574f495430"
ENV_SCAN_SECONDS = 8.0
ENV_RETRY_SECONDS = 5.0  # fixed delay between (re)connection attempts, no backoff
ENV_STALE_SECONDS = 15.0  # a field not refreshed for this long (node samples every 2 s) = unavailable
