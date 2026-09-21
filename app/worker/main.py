import logging
import signal
import threading

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.cnpj_ws import CnpjWsClient
from app.worker.processor import WorkerProcessor


def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    stop_event = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        logging.getLogger(__name__).info("Worker stopping after signal %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    client = CnpjWsClient(settings.cnpjws_base_url, settings.cnpjws_timeout_seconds)
    processor = WorkerProcessor(get_session_factory(), client, settings, sleep=stop_event.wait)
    logging.getLogger(__name__).info("Worker started")
    try:
        while not stop_event.is_set():
            processor.recover_leases()
            if not processor.process_one():
                stop_event.wait(settings.worker_poll_interval_seconds)
    finally:
        client.close()
        logging.getLogger(__name__).info("Worker stopped")


if __name__ == "__main__":
    run()
