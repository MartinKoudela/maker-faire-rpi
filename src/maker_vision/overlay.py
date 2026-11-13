import cv2
import numpy as np
import supervision as sv

BOX_COLOR = (255, 140, 79)
SKELETON_COLOR = (235, 235, 235)
TEXT_COLOR = (255, 255, 255)
KEYPOINT_MIN_CONFIDENCE = 0.5
SKELETON = (
    (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6),
)
FONT = cv2.FONT_HERSHEY_DUPLEX


def draw_detections(image: np.ndarray, detections: sv.Detections, scale: float) -> None:
    if len(detections) == 0:
        return
    unit = image.shape[1] / 1280
    keypoints = detections.data.get("keypoints") if detections.data else None
    tracker_ids = detections.tracker_id
    for index, xyxy in enumerate(detections.xyxy):
        if keypoints is not None:
            _draw_skeleton(image, keypoints[index], scale, unit)
        track_id = int(tracker_ids[index]) if tracker_ids is not None else None
        _draw_box(image, xyxy * scale, track_id, unit)


def _draw_box(image: np.ndarray, xyxy: np.ndarray, track_id: int | None, unit: float) -> None:
    x1, y1, x2, y2 = (int(round(v)) for v in xyxy)
    cv2.rectangle(image, (x1, y1), (x2, y2), BOX_COLOR, max(int(round(2.5 * unit)), 1), cv2.LINE_AA)
    if track_id is None:
        return
    text = f"#{track_id}"
    font_scale = 0.55 * unit
    thickness = max(int(round(unit)), 1)
    (text_w, text_h), _ = cv2.getTextSize(text, FONT, font_scale, thickness)
    pad = int(round(6 * unit))
    height = text_h + pad * 2
    top = max(y1 - height, 0)
    cv2.rectangle(image, (x1, top), (x1 + text_w + pad * 2, top + height), BOX_COLOR, -1)
    cv2.putText(image, text, (x1 + pad, top + pad + text_h), FONT, font_scale, TEXT_COLOR, thickness, cv2.LINE_AA)


def _draw_skeleton(image: np.ndarray, keypoints: np.ndarray, scale: float, unit: float) -> None:
    points = [(int(round(x * scale)), int(round(y * scale)), c) for x, y, c in keypoints]
    line = max(int(round(3.5 * unit)), 1)
    for a, b in SKELETON:
        ax, ay, ac = points[a]
        bx, by, bc = points[b]
        if ac < KEYPOINT_MIN_CONFIDENCE or bc < KEYPOINT_MIN_CONFIDENCE:
            continue
        cv2.line(image, (ax, ay), (bx, by), SKELETON_COLOR, line, cv2.LINE_AA)
    radius = max(int(round(4.5 * unit)), 2)
    for x, y, c in points:
        if c < KEYPOINT_MIN_CONFIDENCE:
            continue
        cv2.circle(image, (x, y), radius, BOX_COLOR, -1, cv2.LINE_AA)
        cv2.circle(image, (x, y), radius, TEXT_COLOR, max(int(round(1.5 * unit)), 1), cv2.LINE_AA)
