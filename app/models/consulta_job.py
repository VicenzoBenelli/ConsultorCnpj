import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsultaJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"


class ConsultaJob(Base):
    __tablename__ = "consulta_jobs"
    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_consulta_jobs_total_nonnegative"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED')",
            name="ck_consulta_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConsultaJobStatus.PENDING.value, server_default=text("'PENDING'")
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    cnpjs: Mapped[list["ConsultaCnpj"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )

