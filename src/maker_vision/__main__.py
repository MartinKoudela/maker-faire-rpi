from maker_vision import config
from maker_vision.pipeline import Pipeline
from maker_vision.web import create_app


def main() -> None:
    pipeline = Pipeline()
    pipeline.start()
    try:
        create_app(pipeline).run(host=config.WEB_HOST, port=config.WEB_PORT, threaded=True)
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
