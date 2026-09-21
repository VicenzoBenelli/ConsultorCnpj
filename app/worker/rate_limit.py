from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExternalApiControl


PROVIDER = "cnpjws_public"


@dataclass(frozen=True)
class RateGateResult:
    granted: bool
    available_at: datetime


def request_permission(session: Session, now: datetime, interval_seconds: int) -> RateGateResult:
    with session.begin():
        control = session.scalars(
            select(ExternalApiControl).where(ExternalApiControl.provider == PROVIDER).with_for_update()
        ).one()
        available_at = max(now, control.next_request_at or now, control.blocked_until or now)
        if available_at > now:
            return RateGateResult(granted=False, available_at=available_at)
        control.next_request_at = now + timedelta(seconds=interval_seconds)
        return RateGateResult(granted=True, available_at=now)


def block_provider(session: Session, now: datetime, cooldown_seconds: int, candidate_until: datetime | None = None) -> datetime:
    fallback_until = now + timedelta(seconds=cooldown_seconds)
    with session.begin():
        control = session.scalars(
            select(ExternalApiControl).where(ExternalApiControl.provider == PROVIDER).with_for_update()
        ).one()
        control.blocked_until = max(control.blocked_until or now, candidate_until or now, fallback_until)
        return control.blocked_until
