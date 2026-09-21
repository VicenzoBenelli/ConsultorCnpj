import os
import subprocess
import sys
from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import delete, select

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


@pytest.fixture(autouse=True)
def clean_phase4_state() -> Iterator[None]:
    def clear_jobs() -> None:
        with get_session_factory()() as session:
            with session.begin():
                session.execute(delete(ConsultaCnpj))
                session.execute(delete(ConsultaJob))

    clear_jobs()
    yield
    clear_jobs()


def test_postgresql_results_and_export_preserve_input_order() -> None:
    cnpjs = ["04252011000110", "12345678000195", "11444777000161"]
    with get_session_factory()() as session:
        job = create_job(session, cnpjs)
        job_id = job.id

    with get_session_factory()() as session:
        with session.begin():
            job = session.get(ConsultaJob, job_id)
            assert job is not None
            items = session.scalars(
                select(ConsultaCnpj)
                .where(ConsultaCnpj.job_id == job_id)
                .order_by(ConsultaCnpj.input_order)
            ).all()
            job.status = ConsultaJobStatus.COMPLETED.value
            items[0].status = ConsultaCnpjStatus.SUCCESS.value
            items[0].razao_social = "Empresa Teste"
            items[0].telefone = "01123456789"
            items[0].email = "contato@example.com"
            items[1].status = ConsultaCnpjStatus.NOT_FOUND.value
            items[2].status = ConsultaCnpjStatus.FAILED.value

    with TestClient(app) as client:
        results_response = client.get(f"/api/jobs/{job_id}/results")
        export_response = client.get(f"/api/jobs/{job_id}/export.xlsx")

    assert results_response.status_code == 200
    assert [item["cnpj"] for item in results_response.json()["results"]] == cnpjs
    assert [item["status"] for item in results_response.json()["results"]] == [
        "SUCCESS",
        "NOT_FOUND",
        "FAILED",
    ]
    assert export_response.status_code == 200
    assert export_response.headers["content-disposition"] == f'attachment; filename="consulta-cnpj-{job_id}.xlsx"'

    workbook = load_workbook(BytesIO(export_response.content))
    worksheet = workbook.active
    assert list(worksheet.values)[1:] == [
        ("Empresa Teste", "04252011000110", "01123456789", "contato@example.com"),
        (None, "12345678000195", None, None),
        (None, "11444777000161", None, None),
    ]
