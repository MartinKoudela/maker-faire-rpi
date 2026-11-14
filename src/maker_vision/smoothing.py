import math

import numpy as np
import supervision as sv

from maker_vision import config


def _alpha(dt: float, cutoff: np.ndarray | float) -> np.ndarray | float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float) -> None:
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff
        self._value: np.ndarray | None = None
        self._speed: np.ndarray | None = None
        self._time = 0.0

    def __call__(self, value: np.ndarray, now: float, reset: np.ndarray | None = None) -> np.ndarray:
        if self._value is None:
            self._value = value.copy()
            self._speed = np.zeros_like(value)
            self._time = now
            return value.copy()
        dt = max(now - self._time, 1e-3)
        self._time = now
        if reset is not None and reset.any():
            self._value[reset] = value[reset]
            self._speed[reset] = 0.0
        speed = (value - self._value) / dt
        self._speed += _alpha(dt, self._d_cutoff) * (speed - self._speed)
        cutoff = self._min_cutoff + self._beta * np.abs(self._speed)
        self._value += _alpha(dt, cutoff) * (value - self._value)
        return self._value.copy()


class _TrackState:
    def __init__(self) -> None:
        self.box = OneEuroFilter(config.SMOOTH_MIN_CUTOFF, config.SMOOTH_BETA, config.SMOOTH_D_CUTOFF)
        self.keypoints = OneEuroFilter(config.SMOOTH_MIN_CUTOFF, config.SMOOTH_BETA, config.SMOOTH_D_CUTOFF)
        self.confidence: np.ndarray | None = None
        self.last_seen = 0.0


class TrackSmoother:
    def __init__(self) -> None:
        self._tracks: dict[int, _TrackState] = {}

    def apply(self, detections: sv.Detections, now: float) -> sv.Detections:
        if len(detections) == 0 or detections.tracker_id is None:
            self._forget(now)
            return detections

        boxes = detections.xyxy.copy()
        keypoints = detections.data.get("keypoints") if detections.data else None
        keypoints = keypoints.copy() if keypoints is not None else None

        for index, track_id in enumerate(detections.tracker_id):
            state = self._tracks.setdefault(int(track_id), _TrackState())
            state.last_seen = now
            boxes[index] = state.box(boxes[index].astype(np.float64), now)
            if keypoints is None:
                continue
            raw = keypoints[index]
            confidence = raw[:, 2].astype(np.float64)
            hidden = None
            if state.confidence is not None:
                hidden = np.repeat((state.confidence < config.SMOOTH_HIDDEN_CONFIDENCE)[:, None], 2, axis=1)
                confidence = state.confidence + config.SMOOTH_CONFIDENCE_ALPHA * (confidence - state.confidence)
            state.confidence = confidence
            raw[:, :2] = state.keypoints(raw[:, :2].astype(np.float64), now, hidden)
            raw[:, 2] = confidence

        self._forget(now)
        smoothed = detections[np.arange(len(detections))]
        smoothed.xyxy = boxes.astype(np.float32)
        if keypoints is not None:
            smoothed.data["keypoints"] = keypoints.astype(np.float32)
        return smoothed

    def _forget(self, now: float) -> None:
        for track_id in [tid for tid, state in self._tracks.items() if now - state.last_seen > 2.0]:
            del self._tracks[track_id]
