import logging
import threading

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.cnpj_ws import CnpjWsClient
from app.worker.processor import WorkerProcessor


LOGGER = logging.getLogger(__name__)


def run_worker(stop_event: threading.Event) -> None:
    """Run the synchronous worker loop without owning process signal handlers."""
    settings = get_settings()
    client = CnpjWsClient(settings.cnpjws_base_url, settings.cnpjws_timeout_seconds)
    processor = WorkerProcessor(
        get_session_factory(),
        client,
        settings,
        sleep=stop_event.wait,
        should_stop=stop_event.is_set,
    )

    LOGGER.info("Worker started")
    try:
        while not stop_event.is_set():
            try:
                processor.recover_leases()
                if not processor.process_one():
                    stop_event.wait(settings.worker_poll_interval_seconds)
            except SQLAlchemyError:
                LOGGER.exception("Worker database operation failed; retrying")
                stop_event.wait(settings.worker_poll_interval_seconds)
    finally:
        client.close()
        LOGGER.info("Worker stopped")
