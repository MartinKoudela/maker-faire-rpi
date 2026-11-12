import base64
import json
import queue
import threading
import time
from collections import deque

import cv2
import numpy as np

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

OPENAI_AVAILABLE = OpenAI is not None

from maker_vision import config
from maker_vision.pipeline import Pipeline
from maker_vision.settings import SettingsStore
from maker_vision.usage import UsageCounter

SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "activity": {"type": "string"},
                },
                "required": ["description", "activity"],
                "additionalProperties": False,
            },
        },
        "objects": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "people", "objects"],
    "additionalProperties": False,
}

INSTRUCTIONS = (
    "You are the eyes of a camera at a Maker Faire booth. Visitors press a button "
    "and your answer is shown on a big screen next to the live video. Look at the "
    "photo and describe what you see.\n"
    "\n"
    "Write everything in natural Czech. Use only Czech words, never English words "
    "or mixed forms like 'světlé/dark'. Everything is read from a distance on a big "
    "screen, so keep it short.\n"
    "- summary: one or two short sentences about the whole scene with a bit of "
    "wow effect for the visitors: a friendly, witty remark about what someone is "
    "holding or doing, or about something interesting in the scene. Playful, never "
    "mocking or about how someone looks.\n"
    "- people: one entry per clearly visible person, ordered left to right, at most "
    "5 people. description = one short sentence, about 10 to 15 words: clothing "
    "type and brightness, glasses, hats, bags, visible logos or text, held objects. "
    "activity = a few words about what they are doing right now (mává, dívá se do "
    "kamery, drží telefon...).\n"
    "- objects: at most 5 of the most interesting objects in the scene, short Czech "
    "names, most interesting first. Skip ordinary furniture and walls unless there "
    "is nothing else.\n"
    "\n"
    "Camera caveat: this is a NoIR camera without an infrared-cut filter. Colors "
    "are unreliable and black or dark fabric often looks pink, purple or "
    "lavender. Never confidently name pink or purple clothing; prefer dark/light "
    "and garment type over exact color.\n"
    "\n"
    "Never guess gender, age, ethnicity, body shape or attractiveness. Only state "
    "what you clearly see. If the image is empty or unclear, say so in the summary "
    "and return empty lists."
)


def encode_image(frame: np.ndarray) -> str:
    height, width = frame.shape[:2]
    largest = max(height, width)
    if largest > config.CLOUD_MAX_IMAGE_DIMENSION:
        scale = config.CLOUD_MAX_IMAGE_DIMENSION / largest
        frame = cv2.resize(frame, (round(width * scale), round(height * scale)))

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("failed to encode frame as JPEG")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


class Describer:
    def __init__(self, settings: SettingsStore, usage: UsageCounter) -> None:
        self._settings = settings
        self._usage = usage
        self._jobs: queue.Queue = queue.Queue()
        self._results: deque = deque(maxlen=10)
        self._lock = threading.Lock()
        self._busy = False
        self._client = None
        self._next_id = 1

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="describer").start()

    def request(self, frame: np.ndarray, source: str) -> str | None:
        settings = self._settings.get()
        if settings.cloud_mode == "off":
            return "cloud_off"
        if source == "auto" and settings.cloud_mode != "auto":
            return "auto_disabled"
        if OpenAI is None:
            return "missing_openai_package"
        if config.OPENAI_API_KEY is None:
            return "missing_api_key"

        with self._lock:
            if self._busy:
                return "busy"
            if not self._usage.try_reserve(settings.daily_limit):
                return "daily_limit"
            self._busy = True

        self._jobs.put((frame.copy(), source, settings.model, time.time()))
        return None

    def state(self) -> dict:
        with self._lock:
            return {"busy": self._busy, "results": list(self._results)}

    def _loop(self) -> None:
        while True:
            frame, source, model, requested_at = self._jobs.get()
            record = {
                "source": source,
                "model": model,
                "time": time.strftime("%H:%M:%S", time.localtime(requested_at)),
            }
            started = time.monotonic()
            try:
                record.update(status="ok", **self._describe(frame, model))
            except Exception as error:
                record.update(status="error", error=f"{type(error).__name__}: {error}")
                print(f"[describe] {source}: {record['error']}")
            record["duration"] = round(time.monotonic() - started, 1)

            with self._lock:
                record["id"] = self._next_id
                self._next_id += 1
                self._results.appendleft(record)
                self._busy = False

    def _describe(self, frame: np.ndarray, model: str) -> dict:
        response = self._get_client().responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": INSTRUCTIONS},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{encode_image(frame)}"},
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "scene_description",
                    "schema": SCENE_SCHEMA,
                    "strict": True,
                }
            },
        )
        if response.usage is not None:
            self._usage.add_tokens(response.usage.input_tokens, response.usage.output_tokens)
        return json.loads(response.output_text)

    def _get_client(self):
        if self._client is None:
            self._client = OpenAI(
                api_key=config.OPENAI_API_KEY,
                timeout=config.CLOUD_REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            )
        return self._client


class AutoTrigger:
    def __init__(self, pipeline: Pipeline, describer: Describer, settings: SettingsStore) -> None:
        self._pipeline = pipeline
        self._describer = describer
        self._settings = settings

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="auto-trigger").start()

    def _loop(self) -> None:
        seen_ids: set[int] = set()
        last_frame_id = 0
        last_trigger = float("-inf")

        while True:
            snapshot = self._pipeline.wait_for_new(last_frame_id)
            last_frame_id = snapshot.frame_id
            track_ids = snapshot.detections.tracker_id
            if snapshot.frame is None or track_ids is None:
                continue

            new_ids = {int(track_id) for track_id in track_ids} - seen_ids
            if not new_ids:
                continue
            seen_ids.update(new_ids)

            if self._settings.get().cloud_mode != "auto":
                continue
            if time.monotonic() - last_trigger < config.AUTO_TRIGGER_COOLDOWN_SECONDS:
                continue
            if self._describer.request(snapshot.frame, "auto") is None:
                last_trigger = time.monotonic()
