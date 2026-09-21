import os
import subprocess
import sys
import pytest
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID
from collections.abc import Iterator
from app.db.session import get_session_factory
from app.models import ConsultaCnpj, ConsultaJob, ExternalApiControl

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.models import ConsultaCnpj, ConsultaCnpjStatus, ConsultaJob, ConsultaJobStatus, ExternalApiControl
from app.services.jobs import create_job
from app.worker.queue import claim_next, complete_item, recover_expired_leases, reschedule_after_rate_limit, schedule_retry
from app.worker.rate_limit import block_provider, request_permission


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration tests require a dedicated database.",
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
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


def create_pending_job(cnpjs: list[str]) -> tuple[UUID, list[str]]:
    session = get_session_factory()()
    try:
        job = create_job(session, cnpjs)
        return job.id, cnpjs
    finally:
        session.close()


def test_claim_marks_processing_starts_job_and_skips_future_item() -> None:
    job_id, _ = create_pending_job([VALID_CNPJ, SECOND_VALID_CNPJ])
    session = get_session_factory()()
    try:
        with session.begin():
            future_item = session.scalars(
                select(ConsultaCnpj).where(ConsultaCnpj.job_id == job_id, ConsultaCnpj.cnpj == SECOND_VALID_CNPJ)
            ).one()
            future_item.next_attempt_at = NOW + timedelta(minutes=1)
    finally:
        session.close()

    session = get_session_factory()()
    try:
        claimed = claim_next(session, NOW, 60)
    finally:
        session.close()

    assert claimed is not None
    assert claimed.cnpj == VALID_CNPJ
    assert claimed.status == ConsultaCnpjStatus.PROCESSING.value
    assert claimed.lease_expires_at == NOW + timedelta(seconds=60)
    session = get_session_factory()()
    try:
        job = session.get(ConsultaJob, job_id)
        job_status = job.status if job is not None else None
    finally:
        session.close()
    assert job_status == ConsultaJobStatus.RUNNING.value


def test_claims_do_not_duplicate_and_expired_leases_are_recovered() -> None:
    create_pending_job([VALID_CNPJ, SECOND_VALID_CNPJ])
    first_session = get_session_factory()()
    second_session = get_session_factory()()
    try:
        first = claim_next(first_session, NOW, 60)
        second = claim_next(second_session, NOW, 60)
    finally:
        first_session.close()
        second_session.close()

    assert first is not None and second is not None
    assert first.id != second.id
    session = get_session_factory()()
    try:
        recovered = recover_expired_leases(session, NOW + timedelta(seconds=61))
    finally:
        session.close()
    assert recovered >= 2


def test_rate_gate_revalidates_after_429_without_future_slot_reservation() -> None:
    first = get_session_factory()()
    try:
        permission = request_permission(first, NOW, 21)
    finally:
        first.close()
    assert permission.granted

    inspect_session = get_session_factory()()
    try:
        control = inspect_session.get(ExternalApiControl, "cnpjws_public")
        next_request_at = control.next_request_at if control is not None else None
    finally:
        inspect_session.close()
    assert next_request_at == NOW + timedelta(seconds=21)

    waiting = get_session_factory()()
    try:
        before_429 = request_permission(waiting, NOW, 21)
    finally:
        waiting.close()
    assert not before_429.granted
    assert before_429.available_at == NOW + timedelta(seconds=21)

    limiter = get_session_factory()()
    try:
        blocked_until = block_provider(limiter, NOW + timedelta(seconds=1), 60)
    finally:
        limiter.close()

    revalidated = get_session_factory()()
    try:
        after_429 = request_permission(revalidated, before_429.available_at, 21)
    finally:
        revalidated.close()
    assert not after_429.granted
    assert after_429.available_at == blocked_until


def test_429_reschedules_without_consuming_attempt_budget() -> None:
    create_pending_job([VALID_CNPJ])
    session = get_session_factory()()
    try:
        claimed = claim_next(session, NOW, 60)
    finally:
        session.close()
    assert claimed is not None
    blocked_until = NOW + timedelta(seconds=60)
    session = get_session_factory()()
    try:
        reschedule_after_rate_limit(session, claimed.id, blocked_until, "wait")
    finally:
        session.close()
    session = get_session_factory()()
    try:
        item = session.get(ConsultaCnpj, claimed.id)
    finally:
        session.close()
    assert item is not None
    assert item.status == ConsultaCnpjStatus.PENDING.value
    assert item.attempt_count == 0
    assert item.next_attempt_at == blocked_until


def test_retry_policy_and_terminal_job_completion() -> None:
    job_id, _ = create_pending_job([VALID_CNPJ])
    for expected_attempt, expected_next in ((1, NOW + timedelta(minutes=1)), (2, NOW + timedelta(minutes=6))):
        session = get_session_factory()()
        try:
            claimed = claim_next(session, NOW if expected_attempt == 1 else NOW + timedelta(minutes=1), 60)
        finally:
            session.close()
        assert claimed is not None
        session = get_session_factory()()
        try:
            terminal = schedule_retry(
                session,
                claimed.id,
                NOW if expected_attempt == 1 else NOW + timedelta(minutes=1),
                http_status=None,
                error_message="timeout",
                max_attempts=3,
            )
        finally:
            session.close()
        assert not terminal
        session = get_session_factory()()
        try:
            item = session.get(ConsultaCnpj, claimed.id)
        finally:
            session.close()
        assert item is not None and item.attempt_count == expected_attempt and item.next_attempt_at == expected_next

    session = get_session_factory()()
    try:
        claimed = claim_next(session, NOW + timedelta(minutes=6), 60)
    finally:
        session.close()
    assert claimed is not None
    session = get_session_factory()()
    try:
        assert schedule_retry(session, claimed.id, NOW + timedelta(minutes=6), http_status=500, error_message="error", max_attempts=3)
    finally:
        session.close()
    session = get_session_factory()()
    try:
        job = session.get(ConsultaJob, job_id)
        item = session.get(ConsultaCnpj, claimed.id)
    finally:
        session.close()
    assert item is not None and item.status == ConsultaCnpjStatus.FAILED.value and item.attempt_count == 3
    assert job is not None and job.status == ConsultaJobStatus.COMPLETED.value

    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def clean_phase3_state() -> Iterator[None]:
    session = get_session_factory()()

    try:
        with session.begin():
            session.query(ConsultaCnpj).delete()
            session.query(ConsultaJob).delete()

            control = session.get(ExternalApiControl, "cnpjws_public")
            if control is not None:
                control.next_request_at = None
                control.blocked_until = None
    finally:
        session.close()

    yield

    session = get_session_factory()()

    try:
        with session.begin():
            session.query(ConsultaCnpj).delete()
            session.query(ConsultaJob).delete()

            control = session.get(ExternalApiControl, "cnpjws_public")
            if control is not None:
                control.next_request_at = None
                control.blocked_until = None
    finally:
        session.close()
