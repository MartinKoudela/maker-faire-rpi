import time
from dataclasses import asdict

from flask import Flask, Response, jsonify, render_template, request

from maker_vision import config
from maker_vision.counter import PeopleCounter
from maker_vision.describe import OPENAI_AVAILABLE, Describer
from maker_vision.heatmap import Heatmap
from maker_vision.pipeline import Pipeline
from maker_vision.settings import CLOUD_MODES, SettingsStore
from maker_vision.system import SystemMonitor
from maker_vision.usage import UsageCounter


def create_app(
    pipeline: Pipeline,
    settings: SettingsStore,
    usage: UsageCounter,
    describer: Describer,
    counter: PeopleCounter,
    system: SystemMonitor,
    heatmap: Heatmap,
) -> Flask:
    app = Flask(__name__)

    def mjpeg():
        last_frame_id = 0
        min_interval = 1.0 / config.STREAM_MAX_FPS
        last_sent = 0.0
        while True:
            frame = pipeline.wait_for_frame(last_frame_id)
            if frame.jpeg is None or frame.frame_id == last_frame_id:
                continue
            wait = min_interval - (time.monotonic() - last_sent)
            if wait > 0:
                time.sleep(wait)
                frame = pipeline.latest_frame()
            last_frame_id = frame.frame_id
            last_sent = time.monotonic()
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame.jpeg + b"\r\n"

    def cloud_state() -> dict:
        current = settings.get()
        return {
            **asdict(current),
            "usage": usage.snapshot(),
            "api_key": config.OPENAI_API_KEY is not None,
            "openai_package": OPENAI_AVAILABLE,
            "busy": describer.state()["busy"],
        }

    @app.route("/")
    def display():
        return render_template("display.html")

    @app.route("/controls")
    def controls():
        return render_template("controls.html")

    @app.route("/stream")
    def stream():
        return Response(mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/detections")
    def detections():
        snapshot = pipeline.latest_detection()
        if snapshot.image is None:
            return jsonify({"frame_width": config.CAMERA_WIDTH, "frame_height": config.CAMERA_HEIGHT, "boxes": []})

        tracker_ids = snapshot.detections.tracker_id
        keypoints = snapshot.detections.data.get("keypoints") if snapshot.detections.data else None
        boxes = []
        for index, (xyxy, track_id) in enumerate(zip(snapshot.detections.xyxy, tracker_ids if tracker_ids is not None else [])):
            box = {"track_id": int(track_id), "xyxy": [round(float(v), 1) for v in xyxy]}
            if keypoints is not None:
                box["keypoints"] = [[round(float(x), 1), round(float(y), 1), round(float(c), 2)] for x, y, c in keypoints[index]]
            boxes.append(box)
        return jsonify({
            "frame_width": snapshot.image.shape[1],
            "frame_height": snapshot.image.shape[0],
            "boxes": boxes,
        })

    @app.route("/api/status")
    def status():
        frame = pipeline.latest_frame()
        detection = pipeline.latest_detection()
        return jsonify({
            "frame_id": frame.frame_id,
            **pipeline.stats(),
            "frame_age": round(time.time() - frame.captured_at, 2) if frame.captured_at else None,
            "people_now": len(detection.detections),
            "cloud": cloud_state(),
            "counter": counter.snapshot(),
            "system": system.snapshot(),
        })

    @app.route("/api/counter", methods=["GET"])
    def counter_state():
        return jsonify({**counter.snapshot(), "line": settings.get().count_line})

    @app.route("/api/counter/reset", methods=["POST"])
    def counter_reset():
        counter.reset()
        return jsonify(counter.snapshot())

    @app.route("/api/heatmap.png")
    def heatmap_png():
        return Response(heatmap.render_png(), mimetype="image/png", headers={"Cache-Control": "no-store"})

    @app.route("/api/heatmap/clear", methods=["POST"])
    def heatmap_clear():
        heatmap.clear()
        return jsonify({"status": "cleared"})

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
        frame = pipeline.latest_frame()
        if frame.image is None:
            return jsonify({"error": "no_frame"}), 503
        reason = describer.request(frame.image, "manual")
        if reason is not None:
            return jsonify({"error": reason}), 409
        return jsonify({"status": "queued"}), 202

    return app
