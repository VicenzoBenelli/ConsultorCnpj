from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.jobs import get_job_status


TEMPLATES_DIRECTORY = Path(__file__).resolve().parent.parent / "templates"
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(TEMPLATES_DIRECTORY))


def render_page(
    request: Request,
    name: str,
    *,
    status_code: int = 200,
    **context: object,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code,
    )
    response.headers["Content-Security-Policy"] = CSP
    return response


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request) -> HTMLResponse:
    return render_page(request, "index.html")


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(
    request: Request,
    job_id: str,
    session: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        parsed_job_id = UUID(job_id)
    except ValueError:
        return render_page(request, "error.html", status_code=404)

    if get_job_status(session, parsed_job_id) is None:
        return render_page(request, "error.html", status_code=404)

    return render_page(request, "job.html", job_id=str(parsed_job_id))
