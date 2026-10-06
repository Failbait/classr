"""Person detection with a pretrained Ultralytics YOLO nano model."""

from ultralytics import YOLO

import config


def load_model():
    return YOLO(config.MODEL_NAME)


def detect_people(model, frame):
    """Return a list of (x1, y1, x2, y2, confidence) for persons above threshold."""
    results = model.predict(
        frame,
        classes=[config.PERSON_CLASS_ID],
        conf=config.CONFIDENCE_THRESHOLD,
        imgsz=config.INFERENCE_IMAGE_SIZE,
        verbose=False,
    )
    boxes = results[0].boxes
    return [
        (*(int(v) for v in xyxy), float(conf))
        for xyxy, conf in zip(boxes.xyxy.tolist(), boxes.conf.tolist())
    ]
