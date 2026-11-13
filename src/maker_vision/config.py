import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
CAMERA_ROTATE_180 = _env_bool("CAMERA_ROTATE_180", False)
VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "").strip() or None

YOLO_MODEL_PATH = MODELS_DIR / "yolo11n_ncnn_model"
POSE_MODEL_PATH = MODELS_DIR / "yolo11n-pose_ncnn_model"
YOLO_INPUT_SIZE = int(os.environ.get("YOLO_INPUT_SIZE", "640"))
YOLO_THREADS = int(os.environ.get("YOLO_THREADS", "4"))
DETECTION_CONFIDENCE = 0.5
NMS_IOU_THRESHOLD = 0.45

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or None
OPENAI_MODELS = [m.strip() for m in os.environ.get("OPENAI_MODELS", "gpt-5.1").split(",") if m.strip()]
CLOUD_MAX_IMAGE_DIMENSION = 1024
CLOUD_REQUEST_TIMEOUT_SECONDS = 15.0
DEFAULT_DAILY_LIMIT = 300
MAX_DAILY_LIMIT = 5000
AUTO_TRIGGER_COOLDOWN_SECONDS = 30.0

FACE_MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
FACE_INPUT_WIDTH = 640
FACE_SCORE_THRESHOLD = 0.6
FACE_PADDING = 0.35
FACE_MAX_AGE_SECONDS = 1.0
FACE_PIXEL_SIZE = 14

HEATMAP_WIDTH = 128
HEATMAP_HEIGHT = 72
HEATMAP_HALF_LIFE_SECONDS = float(os.environ.get("HEATMAP_HALF_LIFE_SECONDS", "900"))
HEATMAP_BLUR_SIGMA = 3.0
HEATMAP_MIN_PEAK = 0.5
HEATMAP_MAX_OPACITY = 0.55
HEATMAP_RENDER_SECONDS = 1.0

COUNT_MIN_FRAMES = 5
COUNT_LINE_MARGIN = 0.02
COUNT_TRACK_FORGET_SECONDS = 10.0
DEFAULT_COUNT_LINE = (0.5, 0.05, 0.5, 0.95)

WATCHDOG_TIMEOUT_SECONDS = 10.0
WATCHDOG_STARTUP_GRACE_SECONDS = 30.0
SYSTEM_POLL_SECONDS = 5.0
HEALTH_LOG_SECONDS = 60.0

STREAM_WIDTH = int(os.environ.get("STREAM_WIDTH", "1280"))
STREAM_JPEG_QUALITY = int(os.environ.get("STREAM_JPEG_QUALITY", "75"))
STREAM_MAX_FPS = 30

PROJECT_URL = os.environ.get("PROJECT_URL", "").strip() or None
PROJECT_LABEL = os.environ.get("PROJECT_LABEL", "").strip() or None

WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))
