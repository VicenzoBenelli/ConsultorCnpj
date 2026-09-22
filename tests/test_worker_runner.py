import threading
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.worker.runner import run_worker


class FakeClient:
    def __init__(self, *_: object) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def worker_settings() -> SimpleNamespace:
    return SimpleNamespace(
        cnpjws_base_url="https://example.test",
        cnpjws_timeout_seconds=15,
        worker_poll_interval_seconds=5,
    )


def test_runner_retries_sqlalchemy_errors(monkeypatch, caplog) -> None:
    clients: list[FakeClient] = []

    class Processor:
        calls = 0

        def __init__(
            self,
            _session_factory: object,
            _client: object,
            _settings: object,
            *,
            sleep: object,
            should_stop: object,
        ) -> None:
            self.stop_event = sleep.__self__

        def recover_leases(self) -> int:
            type(self).calls += 1
            if type(self).calls == 1:
                raise OperationalError("SELECT 1", {}, RuntimeError("database unavailable"))
            self.stop_event.set()
            return 0

        def process_one(self) -> bool:
            return False

    def make_client(*args: object) -> FakeClient:
        client = FakeClient(*args)
        clients.append(client)
        return client

    monkeypatch.setattr("app.worker.runner.get_settings", worker_settings)
    monkeypatch.setattr("app.worker.runner.get_session_factory", lambda: object())
    monkeypatch.setattr("app.worker.runner.CnpjWsClient", make_client)
    monkeypatch.setattr("app.worker.runner.WorkerProcessor", Processor)

    run_worker(threading.Event())

    assert Processor.calls == 2
    assert clients[0].closed is True
    assert "database operation failed; retrying" in caplog.text


def test_runner_propagates_unexpected_errors(monkeypatch) -> None:
    clients: list[FakeClient] = []

    class Processor:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def recover_leases(self) -> int:
            raise RuntimeError("programming error")

        def process_one(self) -> bool:
            return False

    def make_client(*args: object) -> FakeClient:
        client = FakeClient(*args)
        clients.append(client)
        return client

    monkeypatch.setattr("app.worker.runner.get_settings", worker_settings)
    monkeypatch.setattr("app.worker.runner.get_session_factory", lambda: object())
    monkeypatch.setattr("app.worker.runner.CnpjWsClient", make_client)
    monkeypatch.setattr("app.worker.runner.WorkerProcessor", Processor)

    with pytest.raises(RuntimeError, match="programming error"):
        run_worker(threading.Event())

    assert clients[0].closed is True
