"""Drawing helpers shared by the live preview and the benchmark."""

POSTURE_COLORS = {"seated": (0, 200, 0), "standing": (255, 120, 0), "unknown": (0, 165, 255)}


def draw_detections(cv2, frame, detections, color=(0, 255, 0)):
    """Return a copy of frame with a box and label for each detection.

    A detection with a "posture" field is coloured and labelled by it.
    """
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        posture = det.get("posture")
        box_color = POSTURE_COLORS[posture.value] if posture else color
        label = f"{det['confidence']:.2f}" + (f" | {posture.value}" if posture else "")
        cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2)
        cv2.putText(annotated, label, (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
    return annotated
