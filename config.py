"""Configuration values for the people counter."""

CONFIDENCE_THRESHOLD = 0.5
LOG_INTERVAL_SECONDS = 5
CSV_PATH = "data/people_count.csv"

MODEL_NAME = "yolo11s.pt"
PERSON_CLASS_ID = 0  # COCO class 0 = person
INFERENCE_IMAGE_SIZE = 1280  # small seated people need high resolution (tuned via benchmark)

CAMERA_RESOLUTION = (1280, 720)

START_FULLSCREEN = False  # press "f" in the preview to toggle at runtime
