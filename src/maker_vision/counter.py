import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from maker_vision import config
from maker_vision.pipeline import Pipeline, Snapshot
from maker_vision.settings import SettingsStore
from maker_vision.storage import load_json, save_json


@dataclass
class _Track:
    frames: int = 0
    counted: bool = False
    side: int = 0
    last_seen: float = 0.0


def line_side(line: tuple[float, float, float, float], x: float, y: float) -> int:
    x1, y1, x2, y2 = line
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    t = ((x - x1) * dx + (y - y1) * dy) / length_sq
    if not 0.0 <= t <= 1.0:
        return 0
    distance = (dx * (y - y1) - dy * (x - x1)) / math.sqrt(length_sq)
    if abs(distance) < config.COUNT_LINE_MARGIN:
        return 0
    return 1 if distance > 0 else -1


class PeopleCounter:
    def __init__(self, pipeline: Pipeline, settings: SettingsStore, path: Path) -> None:
        self._pipeline = pipeline
        self._settings = settings
        self._path = path
        self._lock = threading.Lock()
        self._tracks: dict[int, _Track] = {}
        self._now = 0
        self._load(load_json(path, {}))

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="people-counter").start()

    def snapshot(self) -> dict:
        with self._lock:
            self._roll_day()
            return {
                "now": self._now,
                "unique_today": self._unique,
                "peak_today": self._peak,
                "line_in": self._line_in,
                "line_out": self._line_out,
                "hourly": dict(self._hourly),
            }

    def reset(self) -> None:
        with self._lock:
            self._load({"day": datetime.now().date().isoformat()})
            for track in self._tracks.values():
                track.counted = track.frames >= config.COUNT_MIN_FRAMES
            self._save()

    def _loop(self) -> None:
        last_frame_id = 0
        while True:
            snapshot = self._pipeline.wait_for_new(last_frame_id)
            if snapshot.frame_id == last_frame_id or snapshot.frame is None:
                continue
            last_frame_id = snapshot.frame_id
            self._process(snapshot)

    def _process(self, snapshot: Snapshot) -> None:
        height, width = snapshot.frame.shape[:2]
        line = self._settings.get().count_line
        track_ids = snapshot.detections.tracker_id
        now = time.monotonic()
        changed = False

        with self._lock:
            self._roll_day()
            self._now = len(snapshot.detections)
            if self._now > self._peak:
                self._peak = self._now
                changed = True

            if track_ids is not None:
                for xyxy, track_id in zip(snapshot.detections.xyxy, track_ids):
                    track = self._tracks.setdefault(int(track_id), _Track())
                    track.frames += 1
                    track.last_seen = now

                    if not track.counted and track.frames >= config.COUNT_MIN_FRAMES:
                        track.counted = True
                        self._unique += 1
                        hour = f"{datetime.now().hour:02d}"
                        self._hourly[hour] = self._hourly.get(hour, 0) + 1
                        changed = True

                    x1, y1, x2, y2 = xyxy
                    side = line_side(line, (x1 + x2) / 2 / width, (y1 + y2) / 2 / height)
                    if side == 0:
                        continue
                    if track.counted and track.side != 0 and side != track.side:
                        if side < 0:
                            self._line_in += 1
                        else:
                            self._line_out += 1
                        changed = True
                    track.side = side

            stale = [tid for tid, track in self._tracks.items() if now - track.last_seen > config.COUNT_TRACK_FORGET_SECONDS]
            for track_id in stale:
                del self._tracks[track_id]

            if changed:
                self._save()

    def _load(self, data: dict) -> None:
        self._day = data.get("day", "")
        self._unique = int(data.get("unique_today", 0))
        self._peak = int(data.get("peak_today", 0))
        self._line_in = int(data.get("line_in", 0))
        self._line_out = int(data.get("line_out", 0))
        self._hourly = {str(k): int(v) for k, v in data.get("hourly", {}).items()}

    def _roll_day(self) -> None:
        today = datetime.now().date().isoformat()
        if self._day != today:
            self._load({"day": today})

    def _save(self) -> None:
        save_json(self._path, {
            "day": self._day,
            "unique_today": self._unique,
            "peak_today": self._peak,
            "line_in": self._line_in,
            "line_out": self._line_out,
            "hourly": self._hourly,
        })
