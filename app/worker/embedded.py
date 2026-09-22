import logging
import threading
from collections.abc import Callable

from app.worker.runner import run_worker


LOGGER = logging.getLogger(__name__)
JOIN_TIMEOUT_SECONDS = 20
WorkerRunner = Callable[[threading.Event], None]


class EmbeddedWorker:
    """Owns one cooperative worker thread for a FastAPI process."""

    def __init__(self, runner: WorkerRunner = run_worker, *, join_timeout: int = JOIN_TIMEOUT_SECONDS) -> None:
        self._runner = runner
        self._join_timeout = join_timeout
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stopping = False

    def start(self) -> bool:
        with self._lock:
            if self._stopping or (self._thread is not None and self._thread.is_alive()):
                return False

            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run,
                name="embedded-cnpj-worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            self._stopping = True
            thread = self._thread
            stop_event = self._stop_event

        if thread is None:
            return True

        stop_event.set()
        thread.join(self._join_timeout)
        stopped = not thread.is_alive()
        if not stopped:
            LOGGER.warning("Embedded worker did not stop within %s seconds", self._join_timeout)
        return stopped

    def _run(self) -> None:
        try:
            self._runner(self._stop_event)
        except Exception:
            LOGGER.exception("Embedded worker stopped after a fatal error")
