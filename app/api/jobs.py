import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.jobs import CreateJobRequest, CreateJobResponse, JobStatusResponse
from app.services.cnpj_input import CnpjBatchValidationError, parse_cnpj_batch
from app.services.jobs import create_job, get_job_status


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
