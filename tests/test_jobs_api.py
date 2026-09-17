from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.services.jobs import JobStatus


VALID_CNPJ = "12345678000195"


def fake_db():
    yield object()


def test_post_valid_batch_returns_201(monkeypatch) -> None:
    job = SimpleNamespace(id=uuid4(), status="PENDING", total=1, created_at=datetime.now(UTC))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.jobs.create_job", lambda session, cnpjs: job)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            response = client.post("/api/jobs", json={"cnpjs": VALID_CNPJ})
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 201
    assert response.json()["id"] == str(job.id)
    assert response.json()["total"] == 1


def test_post_empty_and_invalid_batches_return_422_without_service(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused")
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            empty = client.post("/api/jobs", json={"cnpjs": " ,; \n"})
            invalid = client.post("/api/jobs", json={"cnpjs": f"bad {VALID_CNPJ} 12345678000190"})
            malformed_payload = client.post("/api/jobs", json={})
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert empty.status_code == 422
    assert empty.json()["detail"]["errors"][0]["code"] == "EMPTY_BATCH"
    assert invalid.status_code == 422
    assert len(invalid.json()["detail"]["errors"]) == 2
    assert malformed_payload.status_code == 422


def test_get_job_returns_counts_or_404(monkeypatch) -> None:
    job_id = uuid4()
    job_status = JobStatus(
        id=job_id,
        status="PENDING",
        total=2,
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
        pending=2,
        processing=0,
        success=0,
        not_found=0,
        failed=0,
    )
    monkeypatch.setattr("app.api.jobs.get_job_status", lambda session, requested_id: job_status if requested_id == job_id else None)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            existing = client.get(f"/api/jobs/{job_id}")
            missing = client.get(f"/api/jobs/{uuid4()}")
            malformed = client.get("/api/jobs/not-a-uuid")
    finally:
        app.dependency_overrides.clear()

    assert existing.status_code == 200
    assert existing.json()["processed"] == 0
    assert missing.status_code == 404
    assert malformed.status_code == 422
