"""Person detection with a pretrained Ultralytics YOLO nano model.

Shared by the live camera app (main.py) and the offline benchmark (benchmark.py).
"""

from ultralytics import YOLO

import config


def load_model():
    return YOLO(config.MODEL_NAME)


def detect_people(model, frame):
    """Return person detections above the confidence threshold.

    Each detection is {"bbox": (x1, y1, x2, y2), "confidence": float, "class_name": "person"}.
    """
    results = model.predict(
        frame,
        classes=[config.PERSON_CLASS_ID],
        conf=config.CONFIDENCE_THRESHOLD,
        imgsz=config.INFERENCE_IMAGE_SIZE,
        verbose=False,
    )
    boxes = results[0].boxes
    return [
        {
            "bbox": tuple(int(v) for v in xyxy),
            "confidence": float(conf),
            "class_name": "person",
        }
        for xyxy, conf in zip(boxes.xyxy.tolist(), boxes.conf.tolist())
    ]
