import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsultaCnpjStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


class ConsultaCnpj(Base):
    __tablename__ = "consulta_cnpjs"
    __table_args__ = (
        CheckConstraint("char_length(cnpj) = 14 AND cnpj ~ '^[0-9]{14}$'", name="ck_consulta_cnpjs_cnpj_digits"),
        CheckConstraint("input_order >= 0", name="ck_consulta_cnpjs_input_order_nonnegative"),
        CheckConstraint("attempt_count >= 0", name="ck_consulta_cnpjs_attempt_count_nonnegative"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'NOT_FOUND', 'FAILED')",
            name="ck_consulta_cnpjs_status",
        ),
        UniqueConstraint("job_id", "cnpj", name="uq_consulta_cnpjs_job_cnpj"),
        UniqueConstraint("job_id", "input_order", name="uq_consulta_cnpjs_job_input_order"),
        Index("ix_consulta_cnpjs_job_id", "job_id"),
        Index("ix_consulta_cnpjs_queue", "status", "next_attempt_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consulta_jobs.id", ondelete="CASCADE"), nullable=False
    )
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    input_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConsultaCnpjStatus.PENDING.value, server_default=text("'PENDING'")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    razao_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    job: Mapped["ConsultaJob"] = relationship(back_populates="cnpjs")

