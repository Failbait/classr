"""Configuration values for the people counter."""

CONFIDENCE_THRESHOLD = 0.4  # RF-DETR scores lower than YOLO; 0.4 was best in the benchmark
LOG_INTERVAL_SECONDS = 5
CSV_PATH = "data/people_count.csv"

MODEL_NAME = "rfdetr-small"  # or a YOLO file such as "yolo11s.pt"
PERSON_CLASS_ID = 0  # COCO class 0 = person
INFERENCE_IMAGE_SIZE = 0  # 0 = RF-DETR native size; for YOLO use e.g. 1280

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

CAMERA_RESOLUTION = (1280, 720)

START_FULLSCREEN = False  # press "f" in the preview to toggle at runtime

CAPTURE_DIR = "captures"  # --save-frame output (git-ignored; contains images of people)
