import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import ConsultaJobStatus
from app.schemas.jobs import (
    CreateJobRequest,
    CreateJobResponse,
    JobResultResponse,
    JobResultsResponse,
    JobStatusResponse,
)
from app.services.cnpj_input import CnpjBatchValidationError, parse_cnpj_batch
from app.services.excel_export import build_job_export
from app.services.jobs import create_job, get_job_status
from app.services.results import get_job_results


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=CreateJobResponse, status_code=status.HTTP_201_CREATED)
def create_job_endpoint(payload: CreateJobRequest, session: Session = Depends(get_db)) -> CreateJobResponse:
    try:
        cnpjs = parse_cnpj_batch(payload.cnpjs, get_settings().max_cnpjs_per_job)
    except CnpjBatchValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CNPJ_BATCH", "errors": [item.as_dict() for item in error.errors]},
        ) from error

    try:
        job = create_job(session, cnpjs)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal server error",
        ) from error
    return CreateJobResponse(id=job.id, status=job.status, total=job.total, created_at=job.created_at)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_endpoint(job_id: uuid.UUID, session: Session = Depends(get_db)) -> JobStatusResponse:
    job_status = get_job_status(session, job_id)
    if job_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return JobStatusResponse(
        id=job_status.id,
        status=job_status.status,
        total=job_status.total,
        created_at=job_status.created_at,
        started_at=job_status.started_at,
        finished_at=job_status.finished_at,
        pending=job_status.pending,
        processing=job_status.processing,
        success=job_status.success,
        not_found=job_status.not_found,
        failed=job_status.failed,
        processed=job_status.processed,
    )


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results_endpoint(job_id: uuid.UUID, session: Session = Depends(get_db)) -> JobResultsResponse:
    try:
        job_results = get_job_results(session, job_id)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal server error",
        ) from error

    if job_results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    return JobResultsResponse(
        id=job_results.id,
        status=job_results.status,
        total=job_results.total,
        results=[
            JobResultResponse(
                cnpj=item.cnpj,
                status=item.status,
                razao_social=item.razao_social,
                telefone=item.telefone,
                email=item.email,
            )
            for item in job_results.items
        ],
    )


@router.get("/{job_id}/export.xlsx")
def export_job_endpoint(job_id: uuid.UUID, session: Session = Depends(get_db)) -> StreamingResponse:
    try:
        job_results = get_job_results(session, job_id)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal server error",
        ) from error

    if job_results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job_results.status != ConsultaJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job is not completed",
        )

    filename = f"consulta-cnpj-{job_results.id}.xlsx"
    export_buffer = build_job_export(job_results)
    return StreamingResponse(
        export_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=BackgroundTask(export_buffer.close),
    )
