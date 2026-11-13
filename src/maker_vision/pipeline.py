import threading
import time
import traceback
from dataclasses import dataclass

import cv2
import numpy as np
import supervision as sv

from maker_vision import config
from maker_vision.capture import create_source
from maker_vision.detection import PersonDetector
from maker_vision.faces import FaceBlurrer
from maker_vision.settings import SettingsStore

NO_FACES = np.empty((0, 4), dtype=np.float32)


@dataclass(frozen=True)
class FrameSnapshot:
    frame_id: int
    image: np.ndarray | None
    jpeg: bytes | None
    captured_at: float


@dataclass(frozen=True)
class DetectionSnapshot:
    detection_id: int
    image: np.ndarray | None
    detections: sv.Detections
    faces: np.ndarray
    detected_at: float


EMPTY_FRAME = FrameSnapshot(frame_id=0, image=None, jpeg=None, captured_at=0.0)
EMPTY_DETECTION = DetectionSnapshot(
    detection_id=0,
    image=None,
    detections=sv.Detections.empty(),
    faces=NO_FACES,
    detected_at=0.0,
)


class RateMeter:
    def __init__(self) -> None:
        self._last: float | None = None
        self._interval = 0.0

    @property
    def value(self) -> float:
        return 1.0 / self._interval if self._interval > 0 else 0.0

    def tick(self) -> None:
        now = time.monotonic()
        if self._last is not None:
            interval = now - self._last
            self._interval = interval if self._interval == 0.0 else self._interval * 0.95 + interval * 0.05
        self._last = now


class Timings:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, float] = {}

    def add(self, name: str, seconds: float) -> None:
        ms = seconds * 1000
        with self._lock:
            previous = self._values.get(name)
            self._values[name] = ms if previous is None else previous * 0.9 + ms * 0.1

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {name: round(value, 1) for name, value in self._values.items()}


class Pipeline:
    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings
        self._source = create_source()
        self._detector = PersonDetector()
        self._faces = FaceBlurrer()
        self._frame_condition = threading.Condition()
        self._detection_condition = threading.Condition()
        self._frame = EMPTY_FRAME
        self._detection = EMPTY_DETECTION
        self._stream_rate = RateMeter()
        self._detect_rate = RateMeter()
        self._timings = Timings()
        self._running = False
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        self._source.start()
        self._running = True
        self._threads = [
            threading.Thread(target=self._capture_loop, daemon=True, name="capture"),
            threading.Thread(target=self._detect_loop, daemon=True, name="detect"),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._running = False
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._source.stop()

    def latest_frame(self) -> FrameSnapshot:
        with self._frame_condition:
            return self._frame

    def wait_for_frame(self, last_frame_id: int, timeout: float = 1.0) -> FrameSnapshot:
        with self._frame_condition:
            self._frame_condition.wait_for(lambda: self._frame.frame_id != last_frame_id, timeout=timeout)
            return self._frame

    def latest_detection(self) -> DetectionSnapshot:
        with self._detection_condition:
            return self._detection

    def wait_for_detection(self, last_detection_id: int, timeout: float = 1.0) -> DetectionSnapshot:
        with self._detection_condition:
            self._detection_condition.wait_for(
                lambda: self._detection.detection_id != last_detection_id, timeout=timeout
            )
            return self._detection

    def stats(self) -> dict:
        return {
            "stream_fps": round(self._stream_rate.value, 1),
            "detect_fps": round(self._detect_rate.value, 1),
            "timings_ms": self._timings.snapshot(),
        }

    def _capture_loop(self) -> None:
        while self._running:
            try:
                started = time.perf_counter()
                image = self._source.read()
                captured = time.perf_counter()

                shown = image
                if self._settings.get().blur_faces:
                    detection = self.latest_detection()
                    if time.time() - detection.detected_at < config.FACE_MAX_AGE_SECONDS:
                        shown = self._faces.blur(image, detection.faces)
                if shown.shape[1] > config.STREAM_WIDTH:
                    scale = config.STREAM_WIDTH / shown.shape[1]
                    shown = cv2.resize(shown, (config.STREAM_WIDTH, round(shown.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)
                blurred = time.perf_counter()

                ok, buffer = cv2.imencode(".jpg", shown, [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_JPEG_QUALITY])
                encoded = time.perf_counter()
            except Exception:
                traceback.print_exc()
                time.sleep(0.5)
                continue

            self._timings.add("capture", captured - started)
            self._timings.add("blur_resize", blurred - captured)
            self._timings.add("encode", encoded - blurred)
            self._stream_rate.tick()

            with self._frame_condition:
                self._frame = FrameSnapshot(
                    frame_id=self._frame.frame_id + 1,
                    image=image,
                    jpeg=buffer.tobytes() if ok else self._frame.jpeg,
                    captured_at=time.time(),
                )
                self._frame_condition.notify_all()

    def _detect_loop(self) -> None:
        last_frame_id = 0
        while self._running:
            frame = self.wait_for_frame(last_frame_id)
            if frame.image is None or frame.frame_id == last_frame_id:
                continue
            last_frame_id = frame.frame_id
            blur_faces = self._settings.get().blur_faces

            try:
                started = time.perf_counter()
                detections = self._detector.detect(frame.image)
                detected = time.perf_counter()
                faces = self._faces.detect(frame.image) if blur_faces else NO_FACES
                faced = time.perf_counter()
            except Exception:
                traceback.print_exc()
                time.sleep(0.5)
                continue

            self._timings.add("yolo", detected - started)
            if blur_faces:
                self._timings.add("faces", faced - detected)
            self._detect_rate.tick()

            with self._detection_condition:
                self._detection = DetectionSnapshot(
                    detection_id=self._detection.detection_id + 1,
                    image=frame.image,
                    detections=detections,
                    faces=faces,
                    detected_at=time.time(),
                )
                self._detection_condition.notify_all()
