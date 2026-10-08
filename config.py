"""Configuration values for the people counter."""

CONFIDENCE_THRESHOLD = 0.4  # RF-DETR scores lower than YOLO; 0.4 was best in the benchmark
LOG_INTERVAL_SECONDS = 5
CSV_PATH = "data/people_count.csv"

MODEL_NAME = "rfdetr-small"  # or a YOLO file such as "yolo11s.pt"
PERSON_CLASS_ID = 0  # COCO class 0 = person
INFERENCE_IMAGE_SIZE = 0  # 0 = RF-DETR native size; for YOLO use e.g. 1280

CAMERA_RESOLUTION = (1280, 720)

START_FULLSCREEN = False  # press "f" in the preview to toggle at runtime
