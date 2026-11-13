import threading
import time

import cv2
import numpy as np

from maker_vision import config
from maker_vision.pipeline import DetectionSnapshot, Pipeline


class Heatmap:
    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._grid = np.zeros((config.HEATMAP_HEIGHT, config.HEATMAP_WIDTH), dtype=np.float32)
        self._last_update = time.monotonic()
        self._cached_png: bytes | None = None
        self._cached_at = 0.0

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="heatmap").start()

    def clear(self) -> None:
        with self._lock:
            self._grid.fill(0.0)
            self._cached_png = None

    def render_png(self) -> bytes:
        with self._lock:
            if self._cached_png is not None and time.monotonic() - self._cached_at < config.HEATMAP_RENDER_SECONDS:
                return self._cached_png
            grid = self._grid.copy()

        blurred = cv2.GaussianBlur(grid, (0, 0), config.HEATMAP_BLUR_SIGMA)
        peak = float(blurred.max())
        normalized = blurred / peak if peak > config.HEATMAP_MIN_PEAK else np.zeros_like(blurred)
        colors = cv2.applyColorMap((normalized * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        alpha = (np.clip(normalized * 1.6, 0.0, 1.0) * 255 * config.HEATMAP_MAX_OPACITY).astype(np.uint8)
        image = np.dstack([colors, alpha])
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
        now = time.monotonic()

        with self._lock:
            elapsed = now - self._last_update
            self._last_update = now
            self._grid *= 0.5 ** (elapsed / config.HEATMAP_HALF_LIFE_SECONDS)

            for x1, y1, x2, y2 in snapshot.detections.xyxy:
                cx, cy = (x1 + x2) / 2 * scale_x, (y1 + y2) / 2 * scale_y
                half_w = max((x2 - x1) * scale_x * 0.3, 1.0)
                half_h = max((y2 - y1) * scale_y * 0.3, 1.0)
                gx1, gx2 = int(max(cx - half_w, 0)), int(min(cx + half_w, config.HEATMAP_WIDTH))
                gy1, gy2 = int(max(cy - half_h, 0)), int(min(cy + half_h, config.HEATMAP_HEIGHT))
                if gx2 > gx1 and gy2 > gy1:
                    self._grid[gy1:gy2, gx1:gx2] += elapsed
