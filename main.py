"""People counter MVP: count visible people and log the count periodically."""

import argparse
import os
import signal
import time

import config
from logger import init_csv, log_count
from overlay import draw_detections


class _Stop(Exception):
    pass


def _raise_stop(signum, frame):
    raise _Stop


def draw_overlay(cv2, frame, detections, fps):
    annotated = draw_detections(cv2, frame, detections)
    cv2.putText(annotated, f"People: {len(detections)}", (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 4)
    cv2.putText(annotated, f"{fps:.1f} FPS", (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return annotated


WINDOW_NAME = "People counter"


def toggle_fullscreen(cv2):
    current = cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
    target = cv2.WINDOW_NORMAL if current == cv2.WINDOW_FULLSCREEN else cv2.WINDOW_FULLSCREEN
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, target)


def has_display():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def run(show_preview):
    # Imported here so --help works on machines without the Pi stack.
    import cv2
    from camera import read_frame, start_camera, stop_camera
    from detector import detect_people, load_model

    if show_preview and not has_display():
        print("No display found (SSH session?); running without preview. "
              "To show it on the Pi's screen use: DISPLAY=:0 ./run.sh")
        show_preview = False

    if show_preview:
        # WINDOW_NORMAL makes the window resizable/fullscreen-able (default is fixed size).
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        if config.START_FULLSCREEN:
            cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    init_csv(config.CSV_PATH)
    model = load_model()
    camera = start_camera()
    next_log = time.monotonic() + config.LOG_INTERVAL_SECONDS
    last_tick = time.monotonic()
    fps = 0.0
    boxes = []
    print(f"Running. Logging to {config.CSV_PATH} every "
          f"{config.LOG_INTERVAL_SECONDS}s. Ctrl+C to stop.")

    try:
        while True:
            frame = read_frame(camera)
            boxes = detect_people(model, frame)

            now = time.monotonic()
            fps = 1.0 / max(now - last_tick, 1e-6)
            last_tick = now

            if now >= next_log:
                log_count(config.CSV_PATH, len(boxes))
                next_log += config.LOG_INTERVAL_SECONDS

            if show_preview:
                cv2.imshow(WINDOW_NAME, draw_overlay(cv2, frame, boxes, fps))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("f"):
                    toggle_fullscreen(cv2)
                elif key in (ord("q"), 27):
                    break
    finally:
        stop_camera(camera)
        cv2.destroyAllWindows()
        print("Stopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-preview", action="store_true",
                        help="run without a display (e.g. over SSH)")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, _raise_stop)
    try:
        run(show_preview=not args.no_preview)
    except (KeyboardInterrupt, _Stop):
        pass


if __name__ == "__main__":
    main()
