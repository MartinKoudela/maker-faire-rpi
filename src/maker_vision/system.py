import os
import subprocess
import threading
import time
from pathlib import Path

from maker_vision import config
from maker_vision.pipeline import Pipeline

THERMAL_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
THROTTLE_FLAGS = {
    0: "under_voltage",
    1: "freq_capped",
    2: "throttled",
    3: "soft_temp_limit",
}


def read_temperature() -> float | None:
    try:
        return round(int(THERMAL_PATH.read_text().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def read_throttled() -> dict | None:
    try:
        output = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout
        value = int(output.strip().split("=")[1], 16)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None
    return {
        "now": [name for bit, name in THROTTLE_FLAGS.items() if value & (1 << bit)],
        "since_boot": [name for bit, name in THROTTLE_FLAGS.items() if value & (1 << (bit + 16))],
    }


class SystemMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.monotonic()
        self._state: dict = {}

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="system-monitor").start()

    def snapshot(self) -> dict:
        with self._lock:
            return {**self._state, "uptime": round(time.monotonic() - self._started_at)}

    def _loop(self) -> None:
        while True:
            state = {
                "temperature": read_temperature(),
                "throttled": read_throttled(),
                "load": round(os.getloadavg()[0], 2),
            }
            with self._lock:
                self._state = state
            time.sleep(config.SYSTEM_POLL_SECONDS)


class Watchdog:
    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="watchdog").start()

    def _loop(self) -> None:
        started_at = time.monotonic()
        while True:
            time.sleep(2.0)
            checks = {
                "frame": self._pipeline.latest_frame().captured_at,
                "detection": self._pipeline.latest_detection().detected_at,
            }
            for name, last in checks.items():
                if last == 0.0:
                    if time.monotonic() - started_at > config.WATCHDOG_STARTUP_GRACE_SECONDS:
                        self._die(f"no {name} since start")
                elif time.time() - last > config.WATCHDOG_TIMEOUT_SECONDS:
                    self._die(f"no new {name} for {time.time() - last:.0f} s")

    @staticmethod
    def _die(reason: str) -> None:
        print(f"[watchdog] {reason}, exiting so systemd can restart the service", flush=True)
        os._exit(1)
