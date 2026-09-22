import signal
from types import SimpleNamespace

from app.worker import main


def test_cli_worker_registers_signals_and_delegates_to_runner(monkeypatch) -> None:
    registered: list[int] = []
    received_events: list[object] = []

    monkeypatch.setattr("app.worker.main.get_settings", lambda: SimpleNamespace(log_level="INFO"))
    monkeypatch.setattr("app.worker.main.signal.signal", lambda signum, _handler: registered.append(signum))
    monkeypatch.setattr("app.worker.main.run_worker", lambda stop_event: received_events.append(stop_event))

    main.run()

    assert registered == [signal.SIGINT, signal.SIGTERM]
    assert len(received_events) == 1
