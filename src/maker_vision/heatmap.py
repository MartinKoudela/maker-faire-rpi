import threading
import time

import cv2
import numpy as np

from maker_vision import config
from maker_vision.pipeline import DetectionSnapshot, Pipeline

COLOR_STOPS = (
    (0.0, (255, 120, 40), 0.0),
    (0.3, (255, 120, 40), 0.45),
    (0.65, (255, 200, 40), 0.7),
    (0.9, (255, 245, 190), 0.85),
    (1.0, (255, 255, 255), 0.9),
)


def _build_palette() -> np.ndarray:
    palette = np.zeros((256, 4), dtype=np.uint8)
    positions = [stop[0] for stop in COLOR_STOPS]
    for index in range(256):
        t = index / 255
        for channel in range(3):
            palette[index, channel] = round(np.interp(t, positions, [stop[1][channel] for stop in COLOR_STOPS]))
        palette[index, 3] = round(np.interp(t, positions, [stop[2] for stop in COLOR_STOPS]) * 255)
    return palette


class Heatmap:
    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._grid = np.zeros((config.HEATMAP_HEIGHT, config.HEATMAP_WIDTH), dtype=np.float32)
        self._feet: dict[int, tuple[float, float, float]] = {}
        self._palette = _build_palette()
        self._last_update = time.monotonic()
        self._cached_png: bytes | None = None
        self._cached_at = 0.0

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="heatmap").start()

    def clear(self) -> None:
        with self._lock:
            self._grid.fill(0.0)
            self._feet.clear()
            self._cached_png = None

    def render_png(self) -> bytes:
        with self._lock:
            if self._cached_png is not None and time.monotonic() - self._cached_at < config.HEATMAP_RENDER_SECONDS:
                return self._cached_png
            grid = self._grid.copy()

        blurred = cv2.GaussianBlur(grid, (0, 0), config.HEATMAP_BLUR_SIGMA)
        active = blurred[blurred > config.HEATMAP_NOISE_FLOOR]
        if active.size:
            reference = max(float(np.percentile(active, config.HEATMAP_REFERENCE_PERCENTILE)), config.HEATMAP_MIN_PEAK)
            unit = config.HEATMAP_LOG_UNIT
            normalized = np.clip(np.log1p(blurred / unit) / np.log1p(reference / unit), 0.0, 1.0)
            normalized[blurred <= config.HEATMAP_NOISE_FLOOR] = 0.0
        else:
            normalized = np.zeros_like(blurred)
        image = self._palette[(normalized * 255).astype(np.uint8)]
        ok, buffer = cv2.imencode(".png", image)
        png = buffer.tobytes() if ok else b""

        with self._lock:
            self._cached_png = png
            self._cached_at = time.monotonic()
        return png

    def _loop(self) -> None:
        last_detection_id = 0
        while True:
            snapshot = self._pipeline.wait_for_detection(last_detection_id)
            if snapshot.detection_id == last_detection_id or snapshot.image is None:
                continue
            last_detection_id = snapshot.detection_id
            self._update(snapshot)

    def _update(self, snapshot: DetectionSnapshot) -> None:
        height, width = snapshot.image.shape[:2]
        scale_x = config.HEATMAP_WIDTH / width
        scale_y = config.HEATMAP_HEIGHT / height
        max_step = config.HEATMAP_MAX_STEP * config.HEATMAP_WIDTH
        now = time.monotonic()
        track_ids = snapshot.detections.tracker_id

        with self._lock:
            elapsed = now - self._last_update
            self._last_update = now
            self._grid *= 0.5 ** (elapsed / config.HEATMAP_HALF_LIFE_SECONDS)
            weight = min(elapsed, config.HEATMAP_MAX_STEP_SECONDS)

            layer = np.zeros_like(self._grid)
            for index, (x1, _, x2, y2) in enumerate(snapshot.detections.xyxy):
                if y2 > height * config.HEATMAP_FEET_VISIBLE_LIMIT:
                    continue
                foot = ((x1 + x2) / 2 * scale_x, y2 * scale_y)
                track_id = int(track_ids[index]) if track_ids is not None else None
                previous = self._feet.get(track_id) if track_id is not None else None
                start = foot
                if previous is not None and now - previous[2] < 1.0 and np.hypot(foot[0] - previous[0], foot[1] - previous[1]) < max_step:
                    start = previous[:2]
                cv2.line(
                    layer,
                    (round(start[0]), round(start[1])),
                    (round(foot[0]), round(foot[1])),
                    1.0,
                    config.HEATMAP_TRAIL_THICKNESS,
                    cv2.LINE_AA,
                )
                if track_id is not None:
                    self._feet[track_id] = (foot[0], foot[1], now)

            self._grid += layer * weight
            for track_id in [tid for tid, foot in self._feet.items() if now - foot[2] > 2.0]:
                del self._feet[track_id]
