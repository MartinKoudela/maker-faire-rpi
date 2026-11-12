import numpy as np
from libcamera import Transform
from picamera2 import Picamera2

from maker_vision import config


def create_camera() -> Picamera2:
    camera = Picamera2()
    video_config = camera.create_video_configuration(
        main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT), "format": "RGB888"},
        transform=Transform(hflip=config.CAMERA_ROTATE_180, vflip=config.CAMERA_ROTATE_180),
    )
    camera.configure(video_config)
    return camera


def read_frame(camera: Picamera2) -> np.ndarray:
    return camera.capture_array("main")
