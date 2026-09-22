from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.services.jobs import JobStatus
from app.services.results import JobResultItem, JobResults


VALID_CNPJ = "12345678000195"


def fake_db():
    yield object()


def test_create_job_and_validation_contracts_remain_json(monkeypatch) -> None:
    job = SimpleNamespace(id=uuid4(), status="PENDING", total=1, created_at=datetime.now(UTC))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.jobs.create_job", lambda session, cnpjs: job)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            created = client.post("/api/jobs", json={"cnpjs": VALID_CNPJ})
            invalid_batch = client.post("/api/jobs", json={"cnpjs": "invalid"})
            invalid_payload = client.post("/api/jobs", json={})
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert created.status_code == 201
    assert created.headers["content-type"].startswith("application/json")
    assert "content-security-policy" not in created.headers
    assert created.json()["id"] == str(job.id)
    assert invalid_batch.status_code == 422
    assert invalid_batch.json()["detail"]["errors"][0]["code"] == "INVALID_FORMAT"
    assert invalid_payload.status_code == 422
    assert isinstance(invalid_payload.json()["detail"], list)


@pytest.mark.parametrize("job_state", ["PENDING", "RUNNING", "COMPLETED"])
def test_status_and_results_contracts_cover_job_and_item_states(monkeypatch, job_state: str) -> None:
    job_id = uuid4()
    job_status = JobStatus(
        id=job_id,
        status=job_state,
        total=5,
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
        pending=1,
        processing=1,
        success=1,
        not_found=1,
        failed=1,
    )
    results = JobResults(
        id=job_id,
        status=job_state,
        total=5,
        items=[
            JobResultItem("04252011000110", "PENDING", None, None, None),
            JobResultItem("12345678000195", "PROCESSING", None, None, None),
            JobResultItem("11444777000161", "SUCCESS", "Empresa", "01123456789", "a@example.com"),
            JobResultItem("19131243000197", "NOT_FOUND", None, None, None),
            JobResultItem("33000167000101", "FAILED", None, None, None),
        ],
    )
    monkeypatch.setattr("app.api.jobs.get_job_status", lambda session, requested_id: job_status)
    monkeypatch.setattr("app.api.jobs.get_job_results", lambda session, requested_id: results)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            status_response = client.get(f"/api/jobs/{job_id}")
            results_response = client.get(f"/api/jobs/{job_id}/results")
    finally:
        app.dependency_overrides.clear()

    assert status_response.status_code == 200
    assert status_response.headers["content-type"].startswith("application/json")
    assert status_response.json()["processed"] == 3
    assert results_response.status_code == 200
    assert [item["status"] for item in results_response.json()["results"]] == [
        "PENDING",
        "PROCESSING",
        "SUCCESS",
        "NOT_FOUND",
        "FAILED",
    ]
