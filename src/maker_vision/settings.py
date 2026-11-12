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


DEFAULT_SETTINGS = Settings(
    cloud_mode="off",
    daily_limit=config.DEFAULT_DAILY_LIMIT,
    model=config.OPENAI_MODELS[0],
)


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
