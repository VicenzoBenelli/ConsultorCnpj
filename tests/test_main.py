import asyncio
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.main import app, health, lifespan, readiness


def get(path: str) -> tuple[int, dict[str, str]]:
    messages: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    scope: dict[str, object] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    asyncio.run(app(scope, receive, send))
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = next(message for message in messages if message["type"] == "http.response.body")
    return int(start["status"]), json.loads(bytes(body["body"]))


class HealthySession:
    def __enter__(self) -> "HealthySession":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def execute(self, statement: object) -> None:
        assert str(statement) == str(text("SELECT 1"))


class UnavailableSession:
    def __enter__(self) -> "UnavailableSession":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def execute(self, statement: object) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("database down"))


class SessionFactory:
    def __init__(self, session: HealthySession | UnavailableSession) -> None:
        self.session = session
        self.calls = 0

    def __call__(self) -> HealthySession | UnavailableSession:
        self.calls += 1
        return self.session


def test_application_initializes_with_health_and_ready_routes() -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/health" in paths
    assert "/ready" in paths


def test_health_does_not_require_database_configuration() -> None:
    assert health() == {"status": "ok"}
    assert get("/health") == (200, {"status": "ok"})


def test_lifespan_does_not_start_embedded_worker_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.main.get_settings", lambda: type("Settings", (), {"run_embedded_worker": False})())
    monkeypatch.setattr("app.main.EmbeddedWorker", lambda: pytest.fail("embedded worker must stay disabled"))

    async def exercise_lifespan() -> None:
        async with lifespan(app):
            assert getattr(app.state, "embedded_worker", None) is None

    asyncio.run(exercise_lifespan())


def test_lifespan_starts_and_stops_embedded_worker_when_enabled(monkeypatch) -> None:
    instances: list[object] = []

    class FakeEmbeddedWorker:
        def __init__(self) -> None:
            self.started = 0
            self.stopped = 0
            instances.append(self)

        def start(self) -> bool:
            self.started += 1
            return True

        def stop(self) -> bool:
            self.stopped += 1
            return True

    monkeypatch.setattr("app.main.get_settings", lambda: type("Settings", (), {"run_embedded_worker": True})())
    monkeypatch.setattr("app.main.EmbeddedWorker", FakeEmbeddedWorker)

    async def exercise_lifespan() -> None:
        async with lifespan(app):
            assert len(instances) == 1
            assert app.state.embedded_worker is instances[0]

    asyncio.run(exercise_lifespan())

    worker = instances[0]
    assert worker.started == 1
    assert worker.stopped == 1
    assert app.state.embedded_worker is None


def test_ready_returns_ok_when_database_query_succeeds(monkeypatch) -> None:
    session_factory = SessionFactory(HealthySession())
    monkeypatch.setattr("app.main.get_session_factory", lambda: session_factory)

    assert readiness() == {"status": "ok"}
    assert get("/ready") == (200, {"status": "ok"})
    assert session_factory.calls == 2


def test_ready_returns_503_when_database_query_fails(monkeypatch) -> None:
    session_factory = SessionFactory(UnavailableSession())
    monkeypatch.setattr("app.main.get_session_factory", lambda: session_factory)

    with pytest.raises(HTTPException) as raised:
        readiness()

    assert raised.value.status_code == 503
    assert raised.value.detail == "database unavailable"
    assert get("/ready") == (503, {"detail": "database unavailable"})
    assert session_factory.calls == 2
