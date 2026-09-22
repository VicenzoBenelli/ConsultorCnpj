from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


CSP = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"


def fake_db():
    yield object()


def test_index_page_returns_html_with_form_and_csp() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-security-policy"] == CSP
    assert 'id="cnpjs"' in response.text
    assert 'id="create-job-button"' in response.text
    assert 'id="form-feedback"' in response.text


def test_existing_job_page_returns_html_with_data_attribute(monkeypatch) -> None:
    job_id = uuid4()
    monkeypatch.setattr(
        "app.api.pages.get_job_status",
        lambda session, requested_id: SimpleNamespace(id=job_id) if requested_id == job_id else None,
    )
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/jobs/{job_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-security-policy"] == CSP
    assert f'data-job-id="{job_id}"' in response.text
    assert 'id="job-status"' in response.text
    assert 'id="job-progress"' in response.text
    assert 'id="results-table-body"' in response.text
    assert 'id="download-link"' in response.text


def test_missing_or_invalid_html_job_returns_error_page(monkeypatch) -> None:
    monkeypatch.setattr("app.api.pages.get_job_status", lambda session, job_id: None)
    app.dependency_overrides[get_db] = fake_db

    try:
        with TestClient(app) as client:
            missing = client.get(f"/jobs/{uuid4()}")
            invalid = client.get("/jobs/valor-invalido")
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 404
    assert invalid.status_code == 404
    assert missing.headers["content-type"].startswith("text/html")
    assert invalid.headers["content-type"].startswith("text/html")
    assert "Job não encontrado" in missing.text
    assert "Job não encontrado" in invalid.text


def test_static_assets_are_served() -> None:
    with TestClient(app) as client:
        css = client.get("/static/css/app.css")
        api_js = client.get("/static/js/api.js")
        index_js = client.get("/static/js/index.js")
        job_js = client.get("/static/js/job.js")

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    for response in (api_js, index_js, job_js):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(("text/javascript", "application/javascript"))
