import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import ConsultaCnpjStatus
from app.services.cnpj_ws import (
    CnpjWsClient,
    CnpjWsInvalidResponse,
    CnpjWsTimeout,
    CnpjWsTransportError,
    extract_company_data,
)
from app.worker.queue import (
    claim_next,
    complete_item,
    extend_lease,
    mark_request_started,
    recover_expired_leases,
    reschedule_after_rate_limit,
    schedule_retry,
)
from app.worker.rate_limit import block_provider, request_permission


LOGGER = logging.getLogger(__name__)
MARGIN_SECONDS = 5


class WorkerProcessor:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        client: CnpjWsClient,
        settings: Settings,
        *,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        should_stop: Callable[[], bool] = lambda: False,
    ) -> None:
        self._session_factory = session_factory
        self._client = client
        self._settings = settings
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._should_stop = should_stop

    def recover_leases(self) -> int:
        with self._session_factory() as session:
            recovered = recover_expired_leases(session, self._now())

        if recovered:
            LOGGER.info("Recovered %s expired leases", recovered)

        return recovered

    def process_one(self) -> bool:
        now = self._now()

        with self._session_factory() as session:
            item = claim_next(
                session,
                now,
                self._settings.worker_lease_seconds,
            )

        if item is None:
            return False

        LOGGER.info("Claimed CNPJ item %s", item.id)

        self._wait_for_rate_gate(item.id)

        return True

    def _wait_for_rate_gate(self, item_id: uuid.UUID) -> None:
        while not self._should_stop():
            now = self._now()

            with self._session_factory() as session:
                gate = request_permission(
                    session,
                    now,
                    self._settings.cnpjws_rate_limit_interval_seconds,
                )

            if gate.granted:
                self._call_and_persist(item_id)
                return

            lease_until = gate.available_at + timedelta(
                seconds=(
                    self._settings.cnpjws_timeout_seconds
                    + MARGIN_SECONDS
                )
            )

            with self._session_factory() as session:
                lease_extended = extend_lease(
                    session,
                    item_id,
                    lease_until,
                )

            if not lease_extended:
                LOGGER.warning(
                    "Unable to extend lease for item %s while waiting for rate gate",
                    item_id,
                )
                return

            delay = max(
                0.0,
                (gate.available_at - self._now()).total_seconds(),
            )

            LOGGER.info(
                "Waiting %.1fs for CNPJ.ws rate gate",
                delay,
            )

            self._sleep(delay)

    def _call_and_persist(self, item_id: uuid.UUID) -> None:
        now = self._now()

        lease_until = now + timedelta(
            seconds=(
                self._settings.cnpjws_timeout_seconds
                + MARGIN_SECONDS
            )
        )

        with self._session_factory() as session:
            lease_extended = extend_lease(
                session,
                item_id,
                lease_until,
            )

        if not lease_extended:
            LOGGER.warning(
                "Unable to extend lease before CNPJ.ws request for item %s",
                item_id,
            )
            return

        with self._session_factory() as session:
            cnpj = mark_request_started(
                session,
                item_id,
                now,
            )

        if cnpj is None:
            LOGGER.warning(
                "Item %s is no longer eligible for CNPJ.ws request",
                item_id,
            )
            return

        LOGGER.info(
            "Starting CNPJ.ws request for item %s",
            item_id,
        )

        try:
            response = self._client.fetch(cnpj)

        except CnpjWsTimeout as error:
            LOGGER.warning(
                "CNPJ.ws timeout for item %s: %r",
                item_id,
                error.__cause__,
            )

            self._recoverable_failure(
                item_id,
                self._now(),
                None,
                str(error),
            )
            return

        except CnpjWsTransportError as error:
            LOGGER.warning(
                "CNPJ.ws transport failure for item %s: %r",
                item_id,
                error.__cause__,
            )

            self._recoverable_failure(
                item_id,
                self._now(),
                None,
                str(error),
            )
            return

        except CnpjWsInvalidResponse as error:
            LOGGER.warning(
                "Invalid CNPJ.ws response for item %s: %s",
                item_id,
                str(error),
            )

            self._recoverable_failure(
                item_id,
                self._now(),
                error.http_status,
                str(error),
            )
            return

        except Exception:
            LOGGER.exception(
                "Unexpected CNPJ.ws client error for item %s",
                item_id,
            )

            self._fail_unrecoverable(
                item_id,
                self._now(),
                None,
                "Unexpected CNPJ.ws client error",
            )
            return

        LOGGER.info(
            "CNPJ.ws returned HTTP %s for item %s",
            response.status_code,
            item_id,
        )

        if response.status_code == 200:
            self._handle_success(
                item_id,
                cnpj,
                response.payload or {},
            )
            return

        if response.status_code == 404:
            with self._session_factory() as session:
                complete_item(
                    session,
                    item_id,
                    self._now(),
                    status=ConsultaCnpjStatus.NOT_FOUND.value,
                    http_status=404,
                )

            LOGGER.info(
                "CNPJ item %s marked as NOT_FOUND",
                item_id,
            )
            return

        if response.status_code == 429:
            self._handle_rate_limit(
                item_id,
                response.details,
            )
            return

        if response.status_code >= 500:
            self._recoverable_failure(
                item_id,
                self._now(),
                response.status_code,
                f"CNPJ.ws HTTP {response.status_code}",
            )
            return

        self._fail_unrecoverable(
            item_id,
            self._now(),
            response.status_code,
            f"Unexpected CNPJ.ws HTTP {response.status_code}",
        )

    def _handle_success(
        self,
        item_id: uuid.UUID,
        cnpj: str,
        payload: dict,
    ) -> None:
        try:
            company = extract_company_data(
                payload,
                cnpj,
            )

        except CnpjWsInvalidResponse as error:
            LOGGER.warning(
                "Invalid CNPJ.ws success payload for item %s: %s",
                item_id,
                str(error),
            )

            self._recoverable_failure(
                item_id,
                self._now(),
                error.http_status,
                str(error),
            )
            return

        with self._session_factory() as session:
            complete_item(
                session,
                item_id,
                self._now(),
                status=ConsultaCnpjStatus.SUCCESS.value,
                http_status=200,
                razao_social=company.razao_social,
                telefone=company.telefone,
                email=company.email,
            )

        LOGGER.info(
            "CNPJ item %s completed successfully",
            item_id,
        )

    def _handle_rate_limit(
        self,
        item_id: uuid.UUID,
        details: str | None,
    ) -> None:
        now = self._now()

        with self._session_factory() as session:
            blocked_until = block_provider(
                session,
                now,
                self._settings.cnpjws_429_cooldown_seconds,
            )

        with self._session_factory() as session:
            reschedule_after_rate_limit(
                session,
                item_id,
                blocked_until,
                details,
            )

        LOGGER.warning(
            "CNPJ.ws rate limit reached for item %s; blocked until %s",
            item_id,
            blocked_until,
        )

    def _recoverable_failure(
        self,
        item_id: uuid.UUID,
        now: datetime,
        http_status: int | None,
        message: str,
    ) -> None:
        with self._session_factory() as session:
            failed = schedule_retry(
                session,
                item_id,
                now,
                http_status=http_status,
                error_message=message[:1000],
                max_attempts=self._settings.cnpjws_max_attempts,
            )

        if failed:
            LOGGER.error(
                "Item %s failed permanently after retry budget was exhausted",
                item_id,
            )
        else:
            LOGGER.info(
                "Item %s retry scheduled",
                item_id,
            )

    def _fail_unrecoverable(
        self,
        item_id: uuid.UUID,
        now: datetime,
        http_status: int | None,
        message: str,
    ) -> None:
        with self._session_factory() as session:
            complete_item(
                session,
                item_id,
                now,
                status=ConsultaCnpjStatus.FAILED.value,
                http_status=http_status,
                error_message=message[:1000],
            )

        LOGGER.error(
            "Item %s failed with unrecoverable error",
            item_id,
        )
