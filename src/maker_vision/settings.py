import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from maker_vision import config
from maker_vision.storage import load_json, save_json

CLOUD_MODES = ("off", "manual", "auto")


@dataclass(frozen=True)
class Settings:
    cloud_mode: str
    daily_limit: int
    model: str
    count_line: tuple[float, float, float, float]
    blur_faces: bool


DEFAULT_SETTINGS = Settings(
    cloud_mode="off",
    daily_limit=config.DEFAULT_DAILY_LIMIT,
    model=config.OPENAI_MODELS[0],
    count_line=config.DEFAULT_COUNT_LINE,
    blur_faces=False,
)


def _parse_line(value) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("count_line must be [x1, y1, x2, y2]")
    points = []
    for number in value:
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not 0.0 <= number <= 1.0:
            raise ValueError("count_line values must be numbers 0-1")
        points.append(float(number))
    if abs(points[0] - points[2]) + abs(points[1] - points[3]) < 0.05:
        raise ValueError("count_line is too short")
    return tuple(points)


def _apply(base: Settings, changes: dict) -> Settings:
    values = asdict(base)
    for key, value in changes.items():
        if key == "cloud_mode":
            if value not in CLOUD_MODES:
                raise ValueError(f"cloud_mode must be one of {CLOUD_MODES}")
        elif key == "daily_limit":
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= config.MAX_DAILY_LIMIT:
                raise ValueError(f"daily_limit must be an integer 0-{config.MAX_DAILY_LIMIT}")
        elif key == "model":
            if value not in config.OPENAI_MODELS:
                raise ValueError(f"model must be one of {config.OPENAI_MODELS}")
        elif key == "count_line":
            value = _parse_line(value)
        elif key == "blur_faces":
            if not isinstance(value, bool):
                raise ValueError("blur_faces must be true or false")
        else:
            raise ValueError(f"unknown setting: {key}")
        values[key] = value
    return Settings(**values)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        try:
            self._settings = _apply(DEFAULT_SETTINGS, load_json(path, {}))
        except ValueError:
            self._settings = DEFAULT_SETTINGS

    def get(self) -> Settings:
        with self._lock:
            return self._settings

    def update(self, changes: dict) -> Settings:
        with self._lock:
            self._settings = _apply(self._settings, changes)
            save_json(self._path, asdict(self._settings))
            return self._settings
