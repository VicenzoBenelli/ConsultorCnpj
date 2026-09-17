import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


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
def migrated_database() -> None:
    run_alembic("upgrade")
    yield
    run_alembic("downgrade")


def test_initial_migration_creates_schema_indexes_and_seed() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    inspector = inspect(engine)

    assert {"consulta_jobs", "consulta_cnpjs", "external_api_control"}.issubset(inspector.get_table_names())
    assert {index["name"] for index in inspector.get_indexes("consulta_cnpjs")} >= {
        "ix_consulta_cnpjs_job_id",
        "ix_consulta_cnpjs_queue",
    }
    with engine.connect() as connection:
        provider = connection.execute(text("SELECT provider FROM external_api_control")).scalar_one()
    assert provider == "cnpjws_public"
    engine.dispose()


def test_postgresql_constraints_reject_invalid_cnpj() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    job_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO consulta_jobs (id, total) VALUES (:id, :total)"), {"id": job_id, "total": 1})

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO consulta_cnpjs (id, job_id, cnpj, input_order) VALUES (:id, :job_id, :cnpj, :input_order)"),
                {"id": uuid.uuid4(), "job_id": job_id, "cnpj": "not-a-cnpj", "input_order": 0},
            )
    engine.dispose()

