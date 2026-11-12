import time

from flask import Flask, Response, jsonify, render_template

from maker_vision import config
from maker_vision.pipeline import Pipeline


def create_app(pipeline: Pipeline) -> Flask:
    app = Flask(__name__)

    def mjpeg():
        last_frame_id = 0
        min_interval = 1.0 / config.STREAM_MAX_FPS
        while True:
            snapshot = pipeline.wait_for_new(last_frame_id)
            if snapshot.jpeg is None or snapshot.frame_id == last_frame_id:
                continue
            last_frame_id = snapshot.frame_id
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + snapshot.jpeg + b"\r\n"
            time.sleep(min_interval)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/stream")
    def stream():
        return Response(mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/detections")
    def detections():
        snapshot = pipeline.snapshot()
        if snapshot.frame is None:
            return jsonify({"frame_width": config.CAMERA_WIDTH, "frame_height": config.CAMERA_HEIGHT, "boxes": []})

        tracker_ids = snapshot.detections.tracker_id
        boxes = [
            {"track_id": int(track_id), "xyxy": [round(float(v), 1) for v in xyxy]}
            for xyxy, track_id in zip(snapshot.detections.xyxy, tracker_ids if tracker_ids is not None else [])
        ]
        return jsonify({
            "frame_width": snapshot.frame.shape[1],
            "frame_height": snapshot.frame.shape[0],
            "boxes": boxes,
        })

    @app.route("/api/status")
    def status():
        snapshot = pipeline.snapshot()
        return jsonify({
            "frame_id": snapshot.frame_id,
            "fps": round(snapshot.fps, 1),
            "frame_age": round(time.time() - snapshot.captured_at, 2) if snapshot.captured_at else None,
            "people_now": len(snapshot.detections),
        })

    return app
