import threading
import time
import traceback
from datetime import date

from maker_vision import config

try:
    from gpiozero import MotionSensor
    GPIOZERO_AVAILABLE = True
except Exception:
    MotionSensor = None
    GPIOZERO_AVAILABLE = False


class PirSensor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sensor = None
        self._error: str | None = None
        self._motion = False
        self._last_motion = 0.0
        self._triggers = 0
        self._day = date.today().isoformat()

    def start(self) -> None:
        if config.PIR_PIN is None:
            self._error = "disabled"
            return
        if not GPIOZERO_AVAILABLE:
            self._error = "missing_gpiozero"
            return
        try:
            self._sensor = MotionSensor(config.PIR_PIN)
        except Exception as error:
            traceback.print_exc()
            self._error = type(error).__name__
            return
        self._sensor.when_motion = self._on_motion
        self._sensor.when_no_motion = self._on_no_motion
        if self._sensor.motion_detected:
            self._on_motion()

    def snapshot(self) -> dict:
        with self._lock:
            self._rollover()
            held = self._last_motion and time.time() - self._last_motion < config.PIR_HOLD_SECONDS
            return {
                "available": self._sensor is not None,
                "error": self._error,
                "pin": config.PIR_PIN,
                "motion": bool(self._motion or held),
                "seconds_since_motion": round(time.time() - self._last_motion, 1) if self._last_motion else None,
                "triggers_today": self._triggers,
            }

    def _on_motion(self) -> None:
        with self._lock:
            self._rollover()
            self._motion = True
            self._last_motion = time.time()
            self._triggers += 1

    def _on_no_motion(self) -> None:
        with self._lock:
            self._motion = False
            self._last_motion = time.time()

    def _rollover(self) -> None:
        today = date.today().isoformat()
        if today != self._day:
            self._day = today
            self._triggers = 0
