from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.models import ConsultaCnpjStatus
from app.services.cnpj_ws import CnpjWsResponse
from app.worker.processor import WorkerProcessor
from app.worker.rate_limit import RateGateResult


class NoopSession:
    def __enter__(self) -> "NoopSession":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None


class FakeClient:
    def __init__(self, response: CnpjWsResponse) -> None:
        self.response = response
        self.cnpjs: list[str] = []

    def fetch(self, cnpj: str) -> CnpjWsResponse:
        self.cnpjs.append(cnpj)
        return self.response


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        worker_lease_seconds=60,
        cnpjws_rate_limit_interval_seconds=21,
        cnpjws_timeout_seconds=15,
        cnpjws_max_attempts=3,
        cnpjws_429_cooldown_seconds=60,
    )


def test_processor_persists_success_after_gate_permission(monkeypatch) -> None:
    item_id = uuid4()
    now = datetime(2026, 9, 21, tzinfo=UTC)
    client = FakeClient(
        CnpjWsResponse(
            200,
            {"razao_social": "Empresa", "estabelecimento": {"cnpj": "12345678000195", "ddd1": "83", "telefone1": "33334444"}},
        )
    )
    completed: dict[str, object] = {}
    monkeypatch.setattr("app.worker.processor.claim_next", lambda session, current, lease: SimpleNamespace(id=item_id))
    monkeypatch.setattr("app.worker.processor.request_permission", lambda session, current, interval: RateGateResult(True, current))
    monkeypatch.setattr("app.worker.processor.extend_lease", lambda *args: True)
    monkeypatch.setattr("app.worker.processor.mark_request_started", lambda *args: "12345678000195")
    monkeypatch.setattr("app.worker.processor.complete_item", lambda *args, **kwargs: completed.update(kwargs))

    processor = WorkerProcessor(lambda: NoopSession(), client, settings(), now=lambda: now, sleep=lambda _: None)
    assert processor.process_one()

    assert client.cnpjs == ["12345678000195"]
    assert completed["status"] == ConsultaCnpjStatus.SUCCESS.value
    assert completed["telefone"] == "8333334444"


def test_processor_429_blocks_and_reschedules_without_retry(monkeypatch) -> None:
    item_id = uuid4()
    now = datetime(2026, 9, 21, tzinfo=UTC)
    client = FakeClient(CnpjWsResponse(429, None, "wait"))
    rescheduled: dict[str, object] = {}
    monkeypatch.setattr("app.worker.processor.claim_next", lambda session, current, lease: SimpleNamespace(id=item_id))
    monkeypatch.setattr("app.worker.processor.request_permission", lambda session, current, interval: RateGateResult(True, current))
    monkeypatch.setattr("app.worker.processor.extend_lease", lambda *args: True)
    monkeypatch.setattr("app.worker.processor.mark_request_started", lambda *args: "12345678000195")
    monkeypatch.setattr("app.worker.processor.block_provider", lambda session, current, cooldown: now)
    monkeypatch.setattr("app.worker.processor.reschedule_after_rate_limit", lambda *args: rescheduled.update(details=args[3]))

    WorkerProcessor(lambda: NoopSession(), client, settings(), now=lambda: now, sleep=lambda _: None).process_one()

    assert rescheduled["details"] == "wait"


def test_processor_stops_before_waiting_for_rate_gate(monkeypatch) -> None:
    item_id = uuid4()
    client = FakeClient(CnpjWsResponse(200, {}))
    monkeypatch.setattr("app.worker.processor.request_permission", lambda *args: (_ for _ in ()).throw(AssertionError()))

    processor = WorkerProcessor(
        lambda: NoopSession(),
        client,
        settings(),
        should_stop=lambda: True,
    )

    processor._wait_for_rate_gate(item_id)

    assert client.cnpjs == []
