from maker_vision import config
from maker_vision.describe import AutoTrigger, Describer
from maker_vision.pipeline import Pipeline
from maker_vision.settings import SettingsStore
from maker_vision.usage import UsageCounter
from maker_vision.web import create_app


def main() -> None:
    settings = SettingsStore(config.DATA_DIR / "settings.json")
    usage = UsageCounter(config.DATA_DIR / "usage.json")
    pipeline = Pipeline()
    describer = Describer(settings, usage)

    pipeline.start()
    describer.start()
    AutoTrigger(pipeline, describer, settings).start()

    try:
        create_app(pipeline, settings, usage, describer).run(host=config.WEB_HOST, port=config.WEB_PORT, threaded=True)
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
