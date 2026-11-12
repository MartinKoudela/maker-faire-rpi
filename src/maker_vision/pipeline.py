import threading
import time
import traceback
from dataclasses import dataclass

import cv2
import numpy as np
import supervision as sv

from maker_vision import config
from maker_vision.capture import create_camera, read_frame
from maker_vision.detection import PersonDetector


@dataclass(frozen=True)
class Snapshot:
    frame_id: int
    frame: np.ndarray | None
    jpeg: bytes | None
    detections: sv.Detections
    captured_at: float
    fps: float


EMPTY_SNAPSHOT = Snapshot(
    frame_id=0,
    frame=None,
    jpeg=None,
    detections=sv.Detections.empty(),
    captured_at=0.0,
    fps=0.0,
)


class Pipeline:
    def __init__(self) -> None:
        self._camera = create_camera()
        self._detector = PersonDetector()
        self._condition = threading.Condition()
        self._snapshot = EMPTY_SNAPSHOT
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._camera.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pipeline")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._camera.stop()

    def snapshot(self) -> Snapshot:
        with self._condition:
            return self._snapshot

    def wait_for_new(self, last_frame_id: int, timeout: float = 1.0) -> Snapshot:
        with self._condition:
            self._condition.wait_for(lambda: self._snapshot.frame_id != last_frame_id, timeout=timeout)
            return self._snapshot

    def _loop(self) -> None:
        fps = 0.0
        last_tick = time.monotonic()

        while self._running:
            try:
                frame = read_frame(self._camera)
                detections = self._detector.detect(frame)
                ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_JPEG_QUALITY])
            except Exception:
                traceback.print_exc()
                time.sleep(0.5)
                continue

            now = time.monotonic()
            elapsed = max(now - last_tick, 1e-6)
            last_tick = now
            fps = 1.0 / elapsed if fps == 0.0 else fps * 0.9 + (1.0 / elapsed) * 0.1

            with self._condition:
                self._snapshot = Snapshot(
                    frame_id=self._snapshot.frame_id + 1,
                    frame=frame,
                    jpeg=buffer.tobytes() if ok else self._snapshot.jpeg,
                    detections=detections,
                    captured_at=time.time(),
                    fps=fps,
                )
                self._condition.notify_all()
