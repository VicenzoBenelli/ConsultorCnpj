from fastapi import FastAPI, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.jobs import router as jobs_router
from app.db.session import get_session_factory


app = FastAPI(title="Automacao de Consulta de CNPJ")
app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness() -> dict[str, str]:
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            session.execute(text("SELECT 1"))
    except (SQLAlchemyError, ValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from error
    return {"status": "ok"}
