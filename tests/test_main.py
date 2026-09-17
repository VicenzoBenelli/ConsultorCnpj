import asyncio
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.main import app, health, readiness


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


def test_application_initializes_with_health_and_ready_routes() -> None:
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/ready" in paths


def test_health_does_not_require_database_configuration() -> None:
    assert health() == {"status": "ok"}
    assert get("/health") == (200, {"status": "ok"})


def test_ready_returns_ok_when_database_query_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("app.main.get_session_factory", lambda: HealthySession())

    assert readiness() == {"status": "ok"}
    assert get("/ready") == (200, {"status": "ok"})


def test_ready_returns_503_when_database_query_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.main.get_session_factory", lambda: UnavailableSession())

    with pytest.raises(HTTPException) as raised:
        readiness()

    assert raised.value.status_code == 503
    assert raised.value.detail == "database unavailable"
    assert get("/ready") == (503, {"detail": "database unavailable"})
