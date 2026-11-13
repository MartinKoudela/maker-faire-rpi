from maker_vision import config
from maker_vision.counter import PeopleCounter
from maker_vision.describe import AutoTrigger, Describer
from maker_vision.pipeline import Pipeline
from maker_vision.settings import SettingsStore
from maker_vision.system import SystemMonitor, Watchdog
from maker_vision.usage import UsageCounter
from maker_vision.web import create_app


def main() -> None:
    settings = SettingsStore(config.DATA_DIR / "settings.json")
    usage = UsageCounter(config.DATA_DIR / "usage.json")
    pipeline = Pipeline(settings)
    describer = Describer(settings, usage)
    counter = PeopleCounter(pipeline, settings, config.DATA_DIR / "counter.json")
    system = SystemMonitor()

    pipeline.start()
    describer.start()
    counter.start()
    AutoTrigger(pipeline, describer, settings).start()
    system.start()
    Watchdog(pipeline).start()

    try:
        create_app(pipeline, settings, usage, describer, counter, system).run(host=config.WEB_HOST, port=config.WEB_PORT, threaded=True)
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
