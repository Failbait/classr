"""People counter: count visible people, classify posture, log aggregates periodically."""

import argparse
import logging
import os
import signal
import time

from dataclasses import replace
from datetime import datetime

import config
from activity import ActivityEstimator, ActivityState
from classroom_state import ClassroomState
from logger import init_csv, log_state
from overlay import draw_detections
from sensors import open_environment_client, open_light_sensor, open_noise_sensor
from sensors.sampler import EnvironmentSampler
from posture import (GeometryPostureClassifier, StandingRatioSmoother, classify_detections,
                     summarize_postures)


class _Stop(Exception):
    pass


def _raise_stop(signum, frame):
    raise _Stop


def draw_overlay(cv2, frame, detections, summary, activity, fps):
    annotated = draw_detections(cv2, frame, detections)
    lines = [f"People: {summary['occupancy']}", f"Seated: {summary['seated_count']}",
             f"Standing: {summary['standing_count']}", f"Unknown: {summary['unknown_count']}",
             f"Standing ratio: {summary['standing_ratio']:.2f}",
             f"Matched: {activity.matched_count}", f"Moving: {activity.moving_count}",
             f"Moving ratio: {activity.moving_ratio:.2f}",
             f"Activity: {activity.activity_score:.2f}"]
    for i, text in enumerate(lines):
        cv2.putText(annotated, text, (20, 60 + i * 48), cv2.FONT_HERSHEY_SIMPLEX,
                    1.6 if i == 0 else 1.0, (0, 0, 255), 3)
    cv2.putText(annotated, f"{fps:.1f} FPS", (20, 60 + len(lines) * 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return annotated


WINDOW_NAME = "People counter"


def print_readings(state):
    lux = "n/a" if state.ambient_light_lux is None else f"{state.ambient_light_lux:.1f} lux"
    noise = "n/a" if state.ambient_noise_level is None else f"level={state.ambient_noise_level:.2f}"
    print(f"[CV] occupancy={state.occupancy} activity={state.activity_score:.2f}")
    print(f"[LUX] {lux}")
    print(f"[NOISE] {noise}")
    for label, env in state.environment.items():
        if env is None:
            print(f"[ENV {label}] n/a")
        else:
            print(f"[ENV {label}] CO2={env.co2_ppm} ppm temp={env.temperature_c:.2f} C "
                  f"humidity={env.humidity_percent:.2f} %")


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
        # WINDOW_NORMAL makes the window resizable/fullscreen-able; KEEPRATIO stops it stretching.
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        if config.START_FULLSCREEN:
            cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Column layout follows the config, not what is reachable, so a node that is down just logs blanks.
    env_labels = tuple(config.ENV_NODES) if config.ENV_BLE_ENABLED else ()
    init_csv(config.CSV_PATH, env_labels)
    sampler = EnvironmentSampler(
        open_light_sensor(config), open_noise_sensor(config),
        light_interval=config.LIGHT_INTERVAL_SECONDS,
        noise_stale_seconds=config.NOISE_STALE_SECONDS)
    sampler.start()
    env_node = open_environment_client(config)
    model = load_model()
    camera = start_camera()
    next_log = time.monotonic() + config.LOG_INTERVAL_SECONDS
    last_tick = time.monotonic()
    fps = 0.0
    classifier = GeometryPostureClassifier()
    smoother = StandingRatioSmoother()
    estimator = ActivityEstimator()
    activity = ActivityState(0, 0, 0, 0.0, 0.0, 0, 0, 0.0)
    new_total = lost_total = 0  # summed over samples since the last log row
    smoothed = 0.0
    summary = summarize_postures([])
    people = []
    first_frame = True
    print(f"Running. Logging to {config.CSV_PATH} every "
          f"{config.LOG_INTERVAL_SECONDS}s. Ctrl+C to stop.")

    try:
        while True:
            frame = read_frame(camera)
            if first_frame:
                print(f"Camera frame: {frame.shape[1]}x{frame.shape[0]}")
                first_frame = False
            people = classify_detections(classifier, frame, detect_people(model, frame))
            summary = summarize_postures(p["posture"] for p in people)
            smoothed = smoother.update(summary["standing_ratio"])
            now = time.monotonic()
            activity = estimator.update(people, now)
            new_total += activity.new_count
            lost_total += activity.lost_count

            fps = 1.0 / max(now - last_tick, 1e-6)
            last_tick = now

            if now >= next_log:
                lux, noise = sampler.snapshot()
                classroom = ClassroomState(
                    datetime.now().astimezone(), summary["occupancy"], activity.activity_score,
                    lux, noise, env_node.snapshot() if env_node else {})
                log_state(config.CSV_PATH, summary, smoothed,
                          replace(activity, new_count=new_total, lost_count=lost_total),
                          classroom=classroom, env_labels=env_labels)
                print_readings(classroom)
                new_total = lost_total = 0
                next_log += config.LOG_INTERVAL_SECONDS

            if show_preview:
                cv2.imshow(WINDOW_NAME, draw_overlay(cv2, frame, people, summary, activity, fps))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("f"):
                    toggle_fullscreen(cv2)
                elif key in (ord("q"), 27):
                    break
    finally:
        if env_node:
            env_node.stop()
        sampler.stop()
        stop_camera(camera)
        cv2.destroyAllWindows()
        print("Stopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-preview", action="store_true",
                        help="run without a display (e.g. over SSH)")
    parser.add_argument("--save-frame", action="store_true",
                        help="capture still frames for building benchmark images, then exit "
                             "(no detection, no logging)")
    parser.add_argument("--delay", type=int, default=10,
                        help="--save-frame: seconds before the first capture (default 10)")
    parser.add_argument("--count", type=int, default=1,
                        help="--save-frame: number of frames to save (default 1)")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="--save-frame: seconds between frames (default 3)")
    parser.add_argument("--out-dir", default=config.CAPTURE_DIR,
                        help=f"--save-frame: output folder (default {config.CAPTURE_DIR})")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.count < 1 or args.delay < 0 or args.interval < 0:
        parser.error("--count must be >= 1; --delay and --interval must be >= 0")
    signal.signal(signal.SIGTERM, _raise_stop)
    try:
        if args.save_frame:
            from capture import capture_frames
            capture_frames(args.out_dir, args.delay, args.count, args.interval)
            return
        run(show_preview=not args.no_preview)
    except (KeyboardInterrupt, _Stop):
        pass


if __name__ == "__main__":
    main()
