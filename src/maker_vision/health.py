import json
import threading
import time
from pathlib import Path

from maker_vision import config
from maker_vision.counter import PeopleCounter
from maker_vision.pipeline import Pipeline
from maker_vision.system import SystemMonitor
from maker_vision.usage import UsageCounter

PROC_STATUS = Path("/proc/self/status")


def read_rss_mb() -> float | None:
    try:
        for line in PROC_STATUS.read_text().splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
    except (OSError, ValueError, IndexError):
        return None
    return None


class HealthLog:
    def __init__(self, pipeline: Pipeline, system: SystemMonitor, counter: PeopleCounter, usage: UsageCounter) -> None:
        self._pipeline = pipeline
        self._system = system
        self._counter = counter
        self._usage = usage

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="health-log").start()

    def _loop(self) -> None:
        while True:
            time.sleep(config.HEALTH_LOG_SECONDS)
            frame = self._pipeline.latest_frame()
            stats = self._pipeline.stats()
            system = self._system.snapshot()
            counter = self._counter.snapshot()
            throttled = system.get("throttled") or {}
            entry = {
                "time": time.strftime("%H:%M:%S"),
                "uptime_min": round(system["uptime"] / 60),
                "stream_fps": stats["stream_fps"],
                "detect_fps": stats["detect_fps"],
                "ms": stats["timings_ms"],
                "frame_age": round(time.time() - frame.captured_at, 1) if frame.captured_at else None,
                "temp": system.get("temperature"),
                "throttled": throttled.get("now", []),
                "load": system.get("load"),
                "rss_mb": read_rss_mb(),
                "threads": threading.active_count(),
                "people_now": counter["now"],
                "unique_today": counter["unique_today"],
                "cloud_calls": self._usage.snapshot()["calls"],
            }
            print(f"[health] {json.dumps(entry)}", flush=True)
