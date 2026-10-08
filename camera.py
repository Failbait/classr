"""Picamera2 wrapper: start, grab frames, stop."""

from libcamera import Transform
from picamera2 import Picamera2

import config


def _transform():
    # hflip + vflip = 180 degree rotation (camera mounted upside down).
    return Transform(hflip=config.CAMERA_ROTATE_180, vflip=config.CAMERA_ROTATE_180)


def start_camera():
    camera = Picamera2()
    # "RGB888" yields BGR-ordered pixels, which is what OpenCV and YOLO expect.
    # Requesting the sensor mode explicitly keeps the full field of view; the ISP then
    # scales it to the main stream size.
    camera_config = camera.create_preview_configuration(
        main={"size": config.CAMERA_RESOLUTION, "format": "RGB888"},
        sensor={"output_size": config.CAMERA_SENSOR_MODE, "bit_depth": 10},
        transform=_transform(),
    )
    camera.configure(camera_config)
    camera.start()
    return camera


def start_still_camera(resolution=config.CAPTURE_RESOLUTION):
    """Full-resolution still configuration (single buffer, so large sizes fit in camera memory)."""
    camera = Picamera2()
    camera.configure(camera.create_still_configuration(
        main={"size": resolution, "format": "RGB888"}, transform=_transform()))
    camera.start()
    return camera


def read_frame(camera):
    return camera.capture_array()


def stop_camera(camera):
    camera.stop()
    camera.close()
