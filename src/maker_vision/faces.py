import cv2
import numpy as np

from maker_vision import config


class FaceBlurrer:
    def __init__(self) -> None:
        self._detector = cv2.FaceDetectorYN.create(
            str(config.FACE_MODEL_PATH),
            "",
            (config.FACE_INPUT_WIDTH, config.FACE_INPUT_WIDTH),
            config.FACE_SCORE_THRESHOLD,
            0.3,
            50,
        )
        self._input_size: tuple[int, int] | None = None

    def detect(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        scale = config.FACE_INPUT_WIDTH / width
        small = cv2.resize(frame, (config.FACE_INPUT_WIDTH, round(height * scale)))
        size = (small.shape[1], small.shape[0])
        if size != self._input_size:
            self._detector.setInputSize(size)
            self._input_size = size

        _, faces = self._detector.detect(small)
        if faces is None:
            return np.empty((0, 4), dtype=np.float32)
        return faces[:, :4] / scale

    def blur(self, frame: np.ndarray, faces: np.ndarray) -> np.ndarray:
        if len(faces) == 0:
            return frame
        output = frame.copy()
        height, width = frame.shape[:2]
        for x, y, w, h in faces:
            pad_w, pad_h = w * config.FACE_PADDING, h * config.FACE_PADDING
            x1, y1 = max(int(x - pad_w), 0), max(int(y - pad_h), 0)
            x2, y2 = min(int(x + w + pad_w), width), min(int(y + h + pad_h), height)
            if x2 <= x1 or y2 <= y1:
                continue
            region = output[y1:y2, x1:x2]
            blocks_w = max((x2 - x1) // config.FACE_PIXEL_SIZE, 1)
            blocks_h = max((y2 - y1) // config.FACE_PIXEL_SIZE, 1)
            tiny = cv2.resize(region, (blocks_w, blocks_h), interpolation=cv2.INTER_LINEAR)
            output[y1:y2, x1:x2] = cv2.resize(tiny, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
        return output
