"""Person detection with pretrained detectors (Ultralytics YOLO or RF-DETR).

Shared by the live camera app (main.py) and the offline benchmark (benchmark.py/sweep.py).
The backend is chosen by config.MODEL_NAME: "rfdetr-<nano|small|medium>" selects RF-DETR,
anything else is loaded as an Ultralytics model file (e.g. "yolo11s.pt").

Every backend returns raw candidates down to a low confidence floor; select_detections()
then applies the counting rules (confidence, small-box leniency, duplicate removal).
"""

import config

RFDETR_PREFIX = "rfdetr-"
RFDETR_CLASSES = {"nano": "RFDETRNano", "small": "RFDETRSmall", "medium": "RFDETRMedium"}


def load_model():
    if config.MODEL_NAME.startswith(RFDETR_PREFIX):
        return _load_rfdetr(config.MODEL_NAME[len(RFDETR_PREFIX):])
    from ultralytics import YOLO
    return YOLO(config.MODEL_NAME, task="detect")  # also loads exported *_ncnn_model folders


def _load_rfdetr(size):
    if size not in RFDETR_CLASSES:
        raise ValueError(f"Unknown RF-DETR size '{size}', expected one of {sorted(RFDETR_CLASSES)}")
    import rfdetr  # optional dependency, see requirements-rfdetr.txt
    return getattr(rfdetr, RFDETR_CLASSES[size])()


def detect_people(model, frame):
    """Return the person detections that count. frame is a BGR image."""
    return analyze(model, frame)[0]


def analyze(model, frame):
    """Return (accepted, rejected) detections.

    Each detection is {"bbox": (x1, y1, x2, y2), "confidence": float, "class_name": "person"}.
    "rejected" are candidates above CANDIDATE_FLOOR that did not count; used for debugging.
    """
    if type(model).__module__.startswith("rfdetr"):
        candidates = _candidates_rfdetr(model, frame)
    else:
        candidates = _candidates_yolo(model, frame)
    return select_detections(candidates, frame.shape[0])


def _model_floor():
    floors = [config.CANDIDATE_FLOOR, config.CONFIDENCE_THRESHOLD]
    if config.SMALL_BOX_CONFIDENCE > 0:
        floors.append(config.SMALL_BOX_CONFIDENCE)
    return min(floors)


# ---- counting rules (backend independent) ----

def select_detections(candidates, frame_height):
    ordered = sorted(candidates, key=lambda d: d["confidence"], reverse=True)
    confident, rejected = [], []
    for det in ordered:
        (confident if _passes_confidence(det, frame_height) else rejected).append(det)

    accepted = []
    for det in confident:
        if _is_duplicate(det, accepted):
            rejected.append(det)
        else:
            accepted.append(det)
    return accepted, rejected


def _passes_confidence(det, frame_height):
    if det["confidence"] >= config.CONFIDENCE_THRESHOLD:
        return True
    x1, y1, x2, y2 = det["bbox"]
    is_small = (y2 - y1) <= config.SMALL_BOX_HEIGHT_FRACTION * frame_height
    return (config.SMALL_BOX_CONFIDENCE > 0 and is_small
            and det["confidence"] >= config.SMALL_BOX_CONFIDENCE)


def _is_duplicate(det, kept):
    if config.DEDUPE_CONTAINMENT <= 0:
        return False
    return any(containment(det["bbox"], other["bbox"]) >= config.DEDUPE_CONTAINMENT
               for other in kept)


def containment(box, other):
    """Fraction of the smaller box that lies inside the other box."""
    ix = min(box[2], other[2]) - max(box[0], other[0])
    iy = min(box[3], other[3]) - max(box[1], other[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    smaller = min((box[2] - box[0]) * (box[3] - box[1]),
                  (other[2] - other[0]) * (other[3] - other[1]))
    return (ix * iy) / smaller if smaller > 0 else 0.0


# ---- backends: raw person candidates above the floor ----

def _candidates_yolo(model, frame):
    results = model.predict(
        frame,
        classes=[config.PERSON_CLASS_ID],
        conf=_model_floor(),
        imgsz=config.INFERENCE_IMAGE_SIZE,
        verbose=False,
    )
    boxes = results[0].boxes
    return [_detection(xyxy, conf)
            for xyxy, conf in zip(boxes.xyxy.tolist(), boxes.conf.tolist())]


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


def _candidates_rfdetr(model, frame):
    import numpy as np

    rgb = np.ascontiguousarray(frame[:, :, ::-1])  # RF-DETR expects RGB
    result = model.predict(rgb, threshold=_model_floor(),
                           shape=_rfdetr_shape(model), include_source_image=False)
    names = result.data.get("class_name", [])
    return [_detection(xyxy, conf)
            for xyxy, conf, name in zip(result.xyxy.tolist(), result.confidence.tolist(), names)
            if name == "person"]


def _detection(xyxy, conf):
    return {
        "bbox": tuple(int(v) for v in xyxy),
        "confidence": float(conf),
        "class_name": "person",
    }
