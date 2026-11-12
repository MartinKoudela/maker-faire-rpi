import time
from dataclasses import asdict

from flask import Flask, Response, jsonify, render_template, request

from maker_vision import config
from maker_vision.describe import Describer
from maker_vision.pipeline import Pipeline
from maker_vision.settings import CLOUD_MODES, SettingsStore
from maker_vision.usage import UsageCounter


def create_app(pipeline: Pipeline, settings: SettingsStore, usage: UsageCounter, describer: Describer) -> Flask:
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

    def cloud_state() -> dict:
        current = settings.get()
        return {
            **asdict(current),
            "usage": usage.snapshot(),
            "api_key": config.OPENAI_API_KEY is not None,
            "busy": describer.state()["busy"],
        }

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
            "cloud": cloud_state(),
        })

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        return jsonify({
            "settings": asdict(settings.get()),
            "options": {"cloud_mode": list(CLOUD_MODES), "model": config.OPENAI_MODELS, "max_daily_limit": config.MAX_DAILY_LIMIT},
        })

    @app.route("/api/settings", methods=["POST"])
    def update_settings():
        changes = request.get_json(silent=True)
        if not isinstance(changes, dict):
            return jsonify({"error": "expected JSON object"}), 400
        try:
            updated = settings.update(changes)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"settings": asdict(updated)})

    @app.route("/api/describe", methods=["GET"])
    def describe_state():
        return jsonify({**describer.state(), "cloud": cloud_state()})

    @app.route("/api/describe", methods=["POST"])
    def describe():
        snapshot = pipeline.snapshot()
        if snapshot.frame is None:
            return jsonify({"error": "no_frame"}), 503
        reason = describer.request(snapshot.frame, "manual")
        if reason is not None:
            return jsonify({"error": reason}), 409
        return jsonify({"status": "queued"}), 202

    return app
