import logging
import signal
import threading

from app.core.config import get_settings
from app.worker.runner import run_worker


def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    stop_event = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        logging.getLogger(__name__).info("Worker stopping after signal %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    run_worker(stop_event)


if __name__ == "__main__":
    run()
