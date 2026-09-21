import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    cnpjs: str


class CreateJobResponse(BaseModel):
    id: uuid.UUID
    status: str
    total: int
    created_at: datetime


class JobStatusResponse(CreateJobResponse):
    started_at: datetime | None
    finished_at: datetime | None
    pending: int
    processing: int
    success: int
    not_found: int
    failed: int
    processed: int


class JobResultResponse(BaseModel):
    cnpj: str
    status: str
    razao_social: str | None
    telefone: str | None
    email: str | None


class JobResultsResponse(BaseModel):
    id: uuid.UUID
    status: str
    total: int
    results: list[JobResultResponse]
