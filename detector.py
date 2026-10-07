"""Person detection with pretrained detectors (Ultralytics YOLO or RF-DETR).

Shared by the live camera app (main.py) and the offline benchmark (benchmark.py/sweep.py).
The backend is chosen by config.MODEL_NAME: "rfdetr-<nano|small|medium>" selects RF-DETR,
anything else is loaded as an Ultralytics model file (e.g. "yolo11s.pt").
"""

import config

RFDETR_PREFIX = "rfdetr-"
RFDETR_CLASSES = {"nano": "RFDETRNano", "small": "RFDETRSmall", "medium": "RFDETRMedium"}


def load_model():
    if config.MODEL_NAME.startswith(RFDETR_PREFIX):
        return _load_rfdetr(config.MODEL_NAME[len(RFDETR_PREFIX):])
    from ultralytics import YOLO
    return YOLO(config.MODEL_NAME)


def _load_rfdetr(size):
    if size not in RFDETR_CLASSES:
        raise ValueError(f"Unknown RF-DETR size '{size}', expected one of {sorted(RFDETR_CLASSES)}")
    import rfdetr  # optional dependency, see requirements-rfdetr.txt
    return getattr(rfdetr, RFDETR_CLASSES[size])()


def detect_people(model, frame):
    """Return person detections above the confidence threshold.

    frame is a BGR image (OpenCV / Picamera2). Each detection is
    {"bbox": (x1, y1, x2, y2), "confidence": float, "class_name": "person"}.
    """
    if type(model).__module__.startswith("rfdetr"):
        return _detect_rfdetr(model, frame)
    return _detect_yolo(model, frame)


def _detect_yolo(model, frame):
    results = model.predict(
        frame,
        classes=[config.PERSON_CLASS_ID],
        conf=config.CONFIDENCE_THRESHOLD,
        imgsz=config.INFERENCE_IMAGE_SIZE,
        verbose=False,
    )
    boxes = results[0].boxes
    return [
        _detection(xyxy, conf)
        for xyxy, conf in zip(boxes.xyxy.tolist(), boxes.conf.tolist())
    ]


def _rfdetr_shape(model):
    """Square inference shape from INFERENCE_IMAGE_SIZE, or None for the model's native size.

    RF-DETR needs sizes divisible by patch_size * num_windows, so round to that multiple.
    """
    size = config.INFERENCE_IMAGE_SIZE
    if not size:
        return None
    model_config = getattr(model, "model_config", None)
    step = int(getattr(model_config, "patch_size", 16)) * int(getattr(model_config, "num_windows", 1))
    rounded = max(step, round(size / step) * step)
    return (rounded, rounded)


def _detect_rfdetr(model, frame):
    import numpy as np

    rgb = np.ascontiguousarray(frame[:, :, ::-1])  # RF-DETR expects RGB
    result = model.predict(rgb, threshold=config.CONFIDENCE_THRESHOLD,
                           shape=_rfdetr_shape(model), include_source_image=False)
    names = result.data.get("class_name", [])
    return [
        _detection(xyxy, conf)
        for xyxy, conf, name in zip(result.xyxy.tolist(), result.confidence.tolist(), names)
        if name == "person"
    ]


def _detection(xyxy, conf):
    return {
        "bbox": tuple(int(v) for v in xyxy),
        "confidence": float(conf),
        "class_name": "person",
    }
