import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import ConsultaCnpj, ConsultaCnpjStatus, ConsultaJob, ConsultaJobStatus


TERMINAL_STATUSES = (
    ConsultaCnpjStatus.SUCCESS.value,
    ConsultaCnpjStatus.NOT_FOUND.value,
    ConsultaCnpjStatus.FAILED.value,
)


def recover_expired_leases(session: Session, now: datetime) -> int:
    with session.begin():
        result = session.execute(
            update(ConsultaCnpj)
            .where(
                ConsultaCnpj.status == ConsultaCnpjStatus.PROCESSING.value,
                ConsultaCnpj.lease_expires_at.is_not(None),
                ConsultaCnpj.lease_expires_at <= now,
            )
            .values(
                status=ConsultaCnpjStatus.PENDING.value,
                processing_started_at=None,
                lease_expires_at=None,
            )
        )
    return result.rowcount or 0


def claim_next(session: Session, now: datetime, lease_seconds: int) -> ConsultaCnpj | None:
    with session.begin():
        item = session.scalars(
            select(ConsultaCnpj)
            .where(
                ConsultaCnpj.status == ConsultaCnpjStatus.PENDING.value,
                or_(ConsultaCnpj.next_attempt_at.is_(None), ConsultaCnpj.next_attempt_at <= now),
            )
            .order_by(ConsultaCnpj.next_attempt_at.asc().nullsfirst(), ConsultaCnpj.created_at, ConsultaCnpj.input_order)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if item is None:
            return None

        item.status = ConsultaCnpjStatus.PROCESSING.value
        item.processing_started_at = now
        item.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job = session.get(ConsultaJob, item.job_id)
        if job is not None and job.status == ConsultaJobStatus.PENDING.value:
            job.status = ConsultaJobStatus.RUNNING.value
            job.started_at = now
        session.flush()
        session.expunge(item)
        return item


def extend_lease(session: Session, item_id: uuid.UUID, expires_at: datetime) -> bool:
    with session.begin():
        item = session.scalars(
            select(ConsultaCnpj).where(ConsultaCnpj.id == item_id).with_for_update()
        ).first()
        if item is None or item.status != ConsultaCnpjStatus.PROCESSING.value:
            return False
        if item.lease_expires_at is None or item.lease_expires_at < expires_at:
            item.lease_expires_at = expires_at
        return True


def mark_request_started(session: Session, item_id: uuid.UUID, now: datetime) -> str | None:
    with session.begin():
        item = session.scalars(
            select(ConsultaCnpj).where(ConsultaCnpj.id == item_id).with_for_update()
        ).first()
        if (
            item is None
            or item.status != ConsultaCnpjStatus.PROCESSING.value
            or item.lease_expires_at is None
            or item.lease_expires_at <= now
        ):
            return None
        item.last_attempt_at = now
        return item.cnpj


def complete_item(
    session: Session,
    item_id: uuid.UUID,
    now: datetime,
    *,
    status: str,
    http_status: int | None,
    razao_social: str | None = None,
    telefone: str | None = None,
    email: str | None = None,
    error_message: str | None = None,
) -> None:
    with session.begin():
        item = session.scalars(select(ConsultaCnpj).where(ConsultaCnpj.id == item_id).with_for_update()).one()
        item.status = status
        item.http_status = http_status
        item.razao_social = razao_social
        item.telefone = telefone
        item.email = email
        item.error_message = error_message
        item.next_attempt_at = None
        item.processing_started_at = None
        item.lease_expires_at = None
        _complete_job_if_finished(session, item.job_id, now)


def schedule_retry(
    session: Session,
    item_id: uuid.UUID,
    now: datetime,
    *,
    http_status: int | None,
    error_message: str,
    max_attempts: int,
) -> bool:
    with session.begin():
        item = session.scalars(select(ConsultaCnpj).where(ConsultaCnpj.id == item_id).with_for_update()).one()
        item.attempt_count += 1
        item.http_status = http_status
        item.error_message = error_message
        item.processing_started_at = None
        item.lease_expires_at = None
        if item.attempt_count >= max_attempts:
            item.status = ConsultaCnpjStatus.FAILED.value
            item.next_attempt_at = None
            _complete_job_if_finished(session, item.job_id, now)
            return True
        delay = timedelta(minutes=1 if item.attempt_count == 1 else 5)
        item.status = ConsultaCnpjStatus.PENDING.value
        item.next_attempt_at = now + delay
        return False


def reschedule_after_rate_limit(
    session: Session, item_id: uuid.UUID, blocked_until: datetime, details: str | None
) -> None:
    with session.begin():
        item = session.scalars(select(ConsultaCnpj).where(ConsultaCnpj.id == item_id).with_for_update()).one()
        item.status = ConsultaCnpjStatus.PENDING.value
        item.http_status = 429
        item.error_message = _sanitize(details) or "CNPJ.ws rate limit reached"
        item.next_attempt_at = blocked_until
        item.processing_started_at = None
        item.lease_expires_at = None


def _complete_job_if_finished(session: Session, job_id: uuid.UUID, now: datetime) -> None:
    session.flush()

    has_open_item = session.scalars(
        select(ConsultaCnpj.id).where(
            ConsultaCnpj.job_id == job_id,
            ConsultaCnpj.status.not_in(TERMINAL_STATUSES),
        ).limit(1)
    ).first()
    if has_open_item is None:
        job = session.get(ConsultaJob, job_id)
        if job is not None and job.status != ConsultaJobStatus.COMPLETED.value:
            job.status = ConsultaJobStatus.COMPLETED.value
            job.finished_at = now


def _sanitize(message: str | None) -> str | None:
    if message is None:
        return None
    return message.strip()[:1000] or None
