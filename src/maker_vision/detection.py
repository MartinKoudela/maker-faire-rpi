import cv2
import ncnn
import numpy as np
import supervision as sv

from maker_vision import config

COCO_PERSON_CLASS_ID = 0


class PersonDetector:
    def __init__(self) -> None:
        self._net = ncnn.Net()
        self._net.load_param(str(config.YOLO_MODEL_PATH / "model.ncnn.param"))
        self._net.load_model(str(config.YOLO_MODEL_PATH / "model.ncnn.bin"))
        self._tracker = sv.ByteTrack()

    def detect(self, frame: np.ndarray) -> sv.Detections:
        boxes_xyxy, confidences = self._infer(frame)
        detections = sv.Detections(
            xyxy=boxes_xyxy,
            confidence=confidences,
            class_id=np.full(len(confidences), COCO_PERSON_CLASS_ID, dtype=int),
        )
        detections = detections.with_nms(threshold=config.NMS_IOU_THRESHOLD)
        return self._tracker.update_with_detections(detections)

    def reset_tracker(self) -> None:
        self._tracker.reset()

    def _infer(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        blob, scale = self._preprocess(frame)

        with self._net.create_extractor() as extractor:
            extractor.input("in0", ncnn.Mat(blob).clone())
            _, output = extractor.extract("out0")
            output = np.array(output)

        return self._postprocess(output, scale)

    @staticmethod
    def _preprocess(frame: np.ndarray) -> tuple[np.ndarray, float]:
        input_size = config.YOLO_INPUT_SIZE
        height, width = frame.shape[:2]
        scale = input_size / max(height, width)
        resized = cv2.resize(frame, (round(width * scale), round(height * scale)))
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        padded = cv2.copyMakeBorder(
            resized,
            top=0,
            bottom=input_size - resized.shape[0],
            left=0,
            right=input_size - resized.shape[1],
            borderType=cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )

        blob = padded.astype(np.float32) / 255.0
        blob = np.ascontiguousarray(blob.transpose(2, 0, 1))
        return blob, scale

    @staticmethod
    def _postprocess(output: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
        predictions = output.T
        confidences = predictions[:, 4 + COCO_PERSON_CLASS_ID]

        keep = confidences >= config.DETECTION_CONFIDENCE
        boxes_cxcywh, confidences = predictions[keep, :4], confidences[keep]

        cx, cy, w, h = boxes_cxcywh.T
        boxes_xyxy = np.stack(
            [(cx - w / 2) / scale, (cy - h / 2) / scale, (cx + w / 2) / scale, (cy + h / 2) / scale],
            axis=1,
        ).reshape(-1, 4)
        return boxes_xyxy.astype(np.float32), confidences.astype(np.float32)
