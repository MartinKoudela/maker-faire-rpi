import time
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from maker_vision import config


class FrameSource(Protocol):
    def start(self) -> None: ...

    def read(self) -> np.ndarray: ...

    def stop(self) -> None: ...


class PicameraSource:
    def __init__(self) -> None:
        from libcamera import Transform
        from picamera2 import Picamera2

        self._camera = Picamera2()
        video_config = self._camera.create_video_configuration(
            main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT), "format": "RGB888"},
            transform=Transform(hflip=config.CAMERA_ROTATE_180, vflip=config.CAMERA_ROTATE_180),
            controls={"FrameRate": config.CAMERA_FPS},
        )
        self._camera.configure(video_config)

    def start(self) -> None:
        self._camera.start()

    def read(self) -> np.ndarray:
        return self._camera.capture_array("main")

    def stop(self) -> None:
        self._camera.stop()


class VideoFileSource:
    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"VIDEO_SOURCE not found: {path}")
        self._path = path
        self._capture: cv2.VideoCapture | None = None
        self._fps = 25.0
        self._started_at = 0.0
        self._position = 0

    def start(self) -> None:
        self._capture = cv2.VideoCapture(str(self._path))
        if not self._capture.isOpened():
            raise RuntimeError(f"cannot open video: {self._path}")
        self._fps = self._capture.get(cv2.CAP_PROP_FPS) or 25.0
        self._rewind()

    def read(self) -> np.ndarray:
        target = int((time.monotonic() - self._started_at) * self._fps)
        if target < self._position:
            time.sleep((self._position - target) / self._fps)
        while self._position < target:
            if not self._capture.grab():
                self._rewind()
                break
            self._position += 1

        ok, frame = self._capture.read()
        if not ok:
            self._rewind()
            ok, frame = self._capture.read()
            if not ok:
                raise RuntimeError(f"cannot read video: {self._path}")
        self._position += 1
        return self._fit(frame)

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.release()

    def _rewind(self) -> None:
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._started_at = time.monotonic()
        self._position = 0

    @staticmethod
    def _fit(frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        scale = min(config.CAMERA_WIDTH / width, config.CAMERA_HEIGHT / height, 1.0)
        if scale < 1.0:
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
        return frame


def create_source() -> FrameSource:
    if config.VIDEO_SOURCE:
        path = Path(config.VIDEO_SOURCE).expanduser()
        if not path.is_absolute():
            path = config.BASE_DIR / path
        return VideoFileSource(path)
    return PicameraSource()
