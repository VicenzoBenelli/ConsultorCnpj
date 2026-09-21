from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.results import JobResultItem, JobResults


def fake_db():
    yield object()


def job_results(status: str, items: list[JobResultItem] | None = None) -> JobResults:
    return JobResults(
        id=uuid4(),
        status=status,
        total=len(items or []),
        items=items or [],
    )


def test_results_returns_items_in_service_order_for_all_job_states(monkeypatch) -> None:
    items = [
        JobResultItem("04252011000110", "SUCCESS", "Empresa", "01123456789", "a@example.com"),
        JobResultItem("12345678000195", "NOT_FOUND", None, None, None),
        JobResultItem("11444777000161", "FAILED", None, None, None),
    ]
    app.dependency_overrides[get_db] = fake_db

    try:
        for job_status in ("PENDING", "RUNNING", "COMPLETED"):
            result = job_results(job_status, items)
            monkeypatch.setattr(
                "app.api.jobs.get_job_results",
                lambda session, requested_id, result=result: result if requested_id == result.id else None,
            )
            with TestClient(app) as client:
                response = client.get(f"/api/jobs/{result.id}/results")

            assert response.status_code == 200
            assert response.json()["status"] == job_status
            assert [item["cnpj"] for item in response.json()["results"]] == [
                "04252011000110",
                "12345678000195",
                "11444777000161",
            ]
            assert response.json()["results"][0]["razao_social"] == "Empresa"
            assert response.json()["results"][1]["status"] == "NOT_FOUND"
            assert response.json()["results"][2]["status"] == "FAILED"
            assert set(response.json()["results"][0]) == {
                "cnpj",
                "status",
                "razao_social",
                "telefone",
                "email",
            }
    finally:
        app.dependency_overrides.clear()


def test_results_returns_404_for_missing_job_and_422_for_invalid_uuid(monkeypatch) -> None:
    monkeypatch.setattr("app.api.jobs.get_job_results", lambda session, job_id: None)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            missing = client.get(f"/api/jobs/{uuid4()}/results")
            malformed = client.get("/api/jobs/not-a-uuid/results")
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 404
    assert malformed.status_code == 422


@pytest.mark.parametrize("job_status", ["PENDING", "RUNNING"])
def test_export_rejects_incomplete_jobs(monkeypatch, job_status: str) -> None:
    result = job_results(job_status)
    monkeypatch.setattr("app.api.jobs.get_job_results", lambda session, job_id: result)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/jobs/{result.id}/export.xlsx")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "job is not completed"


def test_export_returns_xlsx_headers_for_completed_job(monkeypatch) -> None:
    result = job_results(
        "COMPLETED",
        [JobResultItem("04252011000110", "SUCCESS", "Empresa", "01123456789", None)],
    )
    monkeypatch.setattr("app.api.jobs.get_job_results", lambda session, job_id: result)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/jobs/{result.id}/export.xlsx")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["content-disposition"] == f'attachment; filename="consulta-cnpj-{result.id}.xlsx"'
    assert response.content[:2] == b"PK"


def test_export_returns_404_for_missing_job(monkeypatch) -> None:
    monkeypatch.setattr("app.api.jobs.get_job_results", lambda session, job_id: None)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/jobs/{uuid4()}/export.xlsx")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
