import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConsultaCnpj, ConsultaJob


@dataclass(frozen=True)
class JobResultItem:
    cnpj: str
    status: str
    razao_social: str | None
    telefone: str | None
    email: str | None


@dataclass(frozen=True)
class JobResults:
    id: uuid.UUID
    status: str
    total: int
    items: list[JobResultItem]


def get_job_results(session: Session, job_id: uuid.UUID) -> JobResults | None:
    job = session.get(ConsultaJob, job_id)
    if job is None:
        return None

    items = session.scalars(
        select(ConsultaCnpj)
        .where(ConsultaCnpj.job_id == job_id)
        .order_by(ConsultaCnpj.input_order.asc())
    ).all()

    return JobResults(
        id=job.id,
        status=job.status,
        total=job.total,
        items=[
            JobResultItem(
                cnpj=item.cnpj,
                status=item.status,
                razao_social=item.razao_social,
                telefone=item.telefone,
                email=item.email,
            )
            for item in items
        ],
    )
