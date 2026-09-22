import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.jobs import router as jobs_router
from app.api.pages import router as pages_router
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.worker.embedded import EmbeddedWorker


LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    embedded_worker: EmbeddedWorker | None = None
    if get_settings().run_embedded_worker:
        embedded_worker = EmbeddedWorker()
        application.state.embedded_worker = embedded_worker
        if embedded_worker.start():
            LOGGER.info("Embedded worker enabled")

    try:
        yield
    finally:
        if embedded_worker is not None:
            LOGGER.info("Stopping embedded worker")
            embedded_worker.stop()
        application.state.embedded_worker = None


app = FastAPI(title="Automacao de Consulta de CNPJ", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(jobs_router)
app.include_router(pages_router)


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
