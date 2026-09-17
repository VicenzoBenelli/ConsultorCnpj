import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ConsultaCnpj, ConsultaCnpjStatus, ConsultaJob, ConsultaJobStatus


@dataclass(frozen=True)
class JobStatus:
    id: uuid.UUID
    status: str
    total: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    pending: int
    processing: int
    success: int
    not_found: int
    failed: int

    @property
    def processed(self) -> int:
        return self.success + self.not_found + self.failed


def create_job(session: Session, cnpjs: list[str]) -> ConsultaJob:
    with session.begin():
        job = ConsultaJob(status=ConsultaJobStatus.PENDING.value, total=len(cnpjs))
        session.add(job)
        session.flush()
        session.add_all(
            [
                ConsultaCnpj(
                    job_id=job.id,
                    cnpj=cnpj,
                    input_order=input_order,
                    status=ConsultaCnpjStatus.PENDING.value,
                    attempt_count=0,
                )
                for input_order, cnpj in enumerate(cnpjs)
            ]
        )
        session.flush()
    return job


def get_job_status(session: Session, job_id: uuid.UUID) -> JobStatus | None:
    job = session.get(ConsultaJob, job_id)
    if job is None:
        return None

    counts = session.execute(
        select(
            func.count().filter(ConsultaCnpj.status == ConsultaCnpjStatus.PENDING.value).label("pending"),
            func.count().filter(ConsultaCnpj.status == ConsultaCnpjStatus.PROCESSING.value).label("processing"),
            func.count().filter(ConsultaCnpj.status == ConsultaCnpjStatus.SUCCESS.value).label("success"),
            func.count().filter(ConsultaCnpj.status == ConsultaCnpjStatus.NOT_FOUND.value).label("not_found"),
            func.count().filter(ConsultaCnpj.status == ConsultaCnpjStatus.FAILED.value).label("failed"),
        ).where(ConsultaCnpj.job_id == job_id)
    ).one()
    return JobStatus(
        id=job.id,
        status=job.status,
        total=job.total,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        pending=counts.pending,
        processing=counts.processing,
        success=counts.success,
        not_found=counts.not_found,
        failed=counts.failed,
    )
