"""Picamera2 wrapper: start, grab frames, stop."""

from picamera2 import Picamera2

import config


def start_camera():
    camera = Picamera2()
    # "RGB888" yields BGR-ordered pixels, which is what OpenCV and YOLO expect.
    camera_config = camera.create_preview_configuration(
        main={"size": config.CAMERA_RESOLUTION, "format": "RGB888"}
    )
    camera.configure(camera_config)
    camera.start()
    return camera


def read_frame(camera):
    return camera.capture_array()


def stop_camera(camera):
    camera.stop()
    camera.close()
