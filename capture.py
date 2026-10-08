"""Opt-in still-frame capture for building benchmark images from the real camera.

Saves raw frames (no overlay). Nothing is detected or logged in this mode, and it only runs
when explicitly requested with --save-frame. Delete captures once they are no longer needed.
"""

import time
from datetime import datetime
from pathlib import Path

from camera import read_frame, start_still_camera, stop_camera


def frame_path(out_dir, now, index):
    return Path(out_dir) / f"frame_{now.strftime('%Y%m%d_%H%M%S')}_{index:02d}.png"


def capture_frames(out_dir, delay, count, interval):
    import cv2

    camera = start_still_camera()
    saved = []
    try:
        for remaining in range(int(delay), 0, -1):
            print(f"Capturing in {remaining}...", flush=True)
            time.sleep(1)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        for index in range(1, count + 1):
            path = frame_path(out_dir, datetime.now(), index)
            frame = read_frame(camera)
            if not cv2.imwrite(str(path), frame):
                raise RuntimeError(f"Could not write {path}")
            saved.append(path)
            print(f"Saved {path} {frame.shape[1]}x{frame.shape[0]} ({index}/{count})", flush=True)
            if index < count:
                time.sleep(interval)
    finally:
        stop_camera(camera)
    return saved
