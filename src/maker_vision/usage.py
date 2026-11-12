import threading
from datetime import date
from pathlib import Path

from maker_vision.storage import load_json, save_json


class UsageCounter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        data = load_json(path, {})
        self._day = data.get("day", "")
        self._calls = int(data.get("calls", 0))
        self._input_tokens = int(data.get("input_tokens", 0))
        self._output_tokens = int(data.get("output_tokens", 0))

    def try_reserve(self, limit: int) -> bool:
        with self._lock:
            self._roll_day()
            if self._calls >= limit:
                return False
            self._calls += 1
            self._save()
            return True

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self._roll_day()
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._save()

    def snapshot(self) -> dict:
        with self._lock:
            self._roll_day()
            return {
                "day": self._day,
                "calls": self._calls,
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
            }

    def _roll_day(self) -> None:
        today = date.today().isoformat()
        if self._day != today:
            self._day = today
            self._calls = 0
            self._input_tokens = 0
            self._output_tokens = 0

    def _save(self) -> None:
        save_json(self._path, {
            "day": self._day,
            "calls": self._calls,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
        })
