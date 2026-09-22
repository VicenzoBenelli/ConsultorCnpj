import threading

from app.worker.embedded import EmbeddedWorker


def test_embedded_worker_starts_once_and_stops_cooperatively() -> None:
    started = threading.Event()

    def runner(stop_event: threading.Event) -> None:
        started.set()
        stop_event.wait()

    worker = EmbeddedWorker(runner)

    assert worker.start() is True
    assert started.wait(1)
    assert worker.start() is False
    assert worker.stop() is True


def test_embedded_worker_logs_fatal_runner_error(caplog) -> None:
    def runner(_stop_event: threading.Event) -> None:
        raise RuntimeError("unexpected worker failure")

    worker = EmbeddedWorker(runner)

    assert worker.start() is True
    assert worker.stop() is True
    assert "Embedded worker stopped after a fatal error" in caplog.text


def test_embedded_worker_uses_limited_join(monkeypatch) -> None:
    joins: list[int] = []
    threads: list[object] = []

    class FakeThread:
        def __init__(self, *, target: object, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon
            self.alive = False
            threads.append(self)

        def start(self) -> None:
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

        def join(self, timeout: int) -> None:
            joins.append(timeout)
            self.alive = False

    monkeypatch.setattr("app.worker.embedded.threading.Thread", FakeThread)
    worker = EmbeddedWorker(lambda _stop_event: None, join_timeout=20)

    assert worker.start() is True
    assert worker.stop() is True
    assert joins == [20]
    assert threads[0].name == "embedded-cnpj-worker"
    assert threads[0].daemon is True
