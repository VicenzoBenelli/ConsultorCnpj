import os
import subprocess
import sys
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.models import ConsultaCnpj, ConsultaCnpjStatus, ConsultaJob, ConsultaJobStatus
from app.services.jobs import create_job


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration tests require a dedicated database.",
)

VALID_CNPJ = "12345678000195"
SECOND_VALID_CNPJ = "04252011000110"


def run_alembic(command: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = TEST_DATABASE_URL or ""
    subprocess.run(
        [sys.executable, "-m", "alembic", command, "head" if command == "upgrade" else "base"],
        check=True,
        env=environment,
    )


@pytest.fixture(scope="module", autouse=True)
def configured_postgresql() -> Iterator[None]:
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL or ""
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    run_alembic("upgrade")
    yield
    get_engine().dispose()
    run_alembic("downgrade")
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url


def test_creates_pending_job_with_deduplicated_items() -> None:
    session = get_session_factory()()
    try:
        job = create_job(session, [VALID_CNPJ, SECOND_VALID_CNPJ])
        assert job.status == ConsultaJobStatus.PENDING.value
        assert job.total == 2
        items = session.scalars(
            select(ConsultaCnpj).where(ConsultaCnpj.job_id == job.id).order_by(ConsultaCnpj.input_order)
        ).all()
    finally:
        session.close()

    assert [(item.cnpj, item.input_order, item.status, item.attempt_count) for item in items] == [
        (VALID_CNPJ, 0, ConsultaCnpjStatus.PENDING.value, 0),
        (SECOND_VALID_CNPJ, 1, ConsultaCnpjStatus.PENDING.value, 0),
    ]


def test_same_cnpj_is_allowed_in_different_jobs() -> None:
    session = get_session_factory()()
    try:
        first_job = create_job(session, [VALID_CNPJ])
        second_job = create_job(session, [VALID_CNPJ])
        first_job_id = first_job.id
        second_job_id = second_job.id
    finally:
        session.close()

    assert first_job_id != second_job_id


def test_same_cnpj_is_unique_within_one_job() -> None:
    session = get_session_factory()()
    try:
        job = create_job(session, [VALID_CNPJ])
        job_id = job.id
    finally:
        session.close()

    session = get_session_factory()()
    try:
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(ConsultaCnpj(job_id=job_id, cnpj=VALID_CNPJ, input_order=1))
    finally:
        session.close()


def test_transaction_rolls_back_entire_job_when_an_item_insert_fails(monkeypatch) -> None:
    count_session = get_session_factory()()
    try:
        before = count_session.scalar(select(func.count()).select_from(ConsultaJob))
    finally:
        count_session.close()

    session = get_session_factory()()
    original_add_all = session.add_all

    def add_invalid_item(items: list[ConsultaCnpj]) -> None:
        original_add_all(items)
        session.add(ConsultaCnpj(job_id=items[0].job_id, cnpj="invalid", input_order=999))

    monkeypatch.setattr(session, "add_all", add_invalid_item)
    try:
        with pytest.raises(IntegrityError):
            create_job(session, [VALID_CNPJ])
    finally:
        session.close()

    count_session = get_session_factory()()
    try:
        after = count_session.scalar(select(func.count()).select_from(ConsultaJob))
    finally:
        count_session.close()

    assert after == before


def test_http_endpoints_use_postgresql_and_return_aggregated_counts() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            json={"cnpjs": f"{VALID_CNPJ}, {SECOND_VALID_CNPJ}, 12.345.678/0001-95"},
        )
        assert created.status_code == 201
        job_id = created.json()["id"]
        assert created.json()["total"] == 2

        session = get_session_factory()()
        try:
            with session.begin():
                items = session.scalars(
                    select(ConsultaCnpj).where(ConsultaCnpj.job_id == UUID(job_id)).order_by(ConsultaCnpj.input_order)
                ).all()
                items[0].status = ConsultaCnpjStatus.SUCCESS.value
                items[1].status = ConsultaCnpjStatus.FAILED.value
        finally:
            session.close()

        response = client.get(f"/api/jobs/{job_id}")
        missing = client.get(f"/api/jobs/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["success"] == 1
    assert response.json()["failed"] == 1
    assert response.json()["processed"] == 2
    assert missing.status_code == 404
