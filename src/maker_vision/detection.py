from pathlib import Path

import cv2
import ncnn
import numpy as np
import supervision as sv

from maker_vision import config

COCO_PERSON_CLASS_ID = 0
POSE_KEYPOINTS = 17


def load_net(model_dir: Path) -> ncnn.Net:
    net = ncnn.Net()
    net.opt.num_threads = config.YOLO_THREADS
    net.load_param(str(model_dir / "model.ncnn.param"))
    net.load_model(str(model_dir / "model.ncnn.bin"))
    return net


class PersonDetector:
    def __init__(self) -> None:
        self._net = load_net(config.YOLO_MODEL_PATH)
        self._pose_net = load_net(config.POSE_MODEL_PATH)
        self._tracker = sv.ByteTrack()

    def detect(self, frame: np.ndarray, pose: bool = False) -> sv.Detections:
        blob, scale = self._preprocess(frame)
        output = self._run(self._pose_net if pose else self._net, blob)
        predictions = output.T
        confidences = predictions[:, 4 + COCO_PERSON_CLASS_ID]
        keep = confidences >= config.DETECTION_CONFIDENCE
        predictions, confidences = predictions[keep], confidences[keep]

        data = {}
        if pose:
            keypoints = predictions[:, 5:5 + POSE_KEYPOINTS * 3].reshape(-1, POSE_KEYPOINTS, 3).copy()
            keypoints[:, :, :2] /= scale
            data["keypoints"] = keypoints.astype(np.float32)

        detections = sv.Detections(
            xyxy=self._boxes(predictions[:, :4], scale),
            confidence=confidences.astype(np.float32),
            class_id=np.full(len(confidences), COCO_PERSON_CLASS_ID, dtype=int),
            data=data,
        )
        detections = detections.with_nms(threshold=config.NMS_IOU_THRESHOLD)
        return self._tracker.update_with_detections(detections)

    def reset_tracker(self) -> None:
        self._tracker.reset()

    @staticmethod
    def _run(net: ncnn.Net, blob: np.ndarray) -> np.ndarray:
        with net.create_extractor() as extractor:
            extractor.input("in0", ncnn.Mat(blob).clone())
            _, output = extractor.extract("out0")
            return np.array(output)

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
    def _boxes(boxes_cxcywh: np.ndarray, scale: float) -> np.ndarray:
        cx, cy, w, h = boxes_cxcywh.T
        boxes_xyxy = np.stack(
            [(cx - w / 2) / scale, (cy - h / 2) / scale, (cx + w / 2) / scale, (cy + h / 2) / scale],
            axis=1,
        ).reshape(-1, 4)
        return boxes_xyxy.astype(np.float32)
