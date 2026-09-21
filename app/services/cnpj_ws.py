import re
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

import httpx2


class CnpjWsError(Exception):
    pass


class CnpjWsTimeout(CnpjWsError):
    pass


class CnpjWsTransportError(CnpjWsError):
    pass


class CnpjWsInvalidResponse(CnpjWsError):
    def __init__(self, message: str, http_status: int | None = None) -> None:
        self.http_status = http_status
        super().__init__(message)


@dataclass(frozen=True)
class CnpjWsResponse:
    status_code: int
    payload: dict[str, Any] | None
    details: str | None = None


@dataclass(frozen=True)
class CompanyData:
    razao_social: str | None
    telefone: str | None
    email: str | None


class CnpjWsClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: int,
        *,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx2.Timeout(
            float(timeout_seconds),
            connect=float(timeout_seconds),
            read=float(timeout_seconds),
            write=float(timeout_seconds),
            pool=float(timeout_seconds),
        )
        self._client_factory = client_factory or self._create_client

    def close(self) -> None:
        pass

    def _create_client(self) -> httpx2.Client:
        return httpx2.Client(
            base_url=self._base_url,
            timeout=self._timeout,
        )

    def fetch(self, cnpj: str) -> CnpjWsResponse:
        client: Any | None = None
        try:
            client = self._client_factory()
            response = client.get(
                f"/cnpj/{cnpj}",
                headers={"Accept": "application/json"},
            )
        except httpx2.TimeoutException as error:
            raise CnpjWsTimeout("CNPJ.ws request timed out") from error
        except httpx2.RequestError as error:
            raise CnpjWsTransportError("CNPJ.ws transport failure") from error
        finally:
            if client is not None:
                client.close()

        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type.lower():
                raise CnpjWsInvalidResponse("Unexpected CNPJ.ws content type", 200)
            try:
                payload = response.json()
            except ValueError as error:
                raise CnpjWsInvalidResponse("Invalid CNPJ.ws JSON", 200) from error
            if not isinstance(payload, dict):
                raise CnpjWsInvalidResponse("Unexpected CNPJ.ws response structure", 200)
            return CnpjWsResponse(status_code=200, payload=payload)

        details = None
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict) and isinstance(error_payload.get("detalhes"), str):
                details = error_payload["detalhes"]
        except ValueError:
            pass
        return CnpjWsResponse(status_code=response.status_code, payload=None, details=details)


def extract_company_data(payload: dict[str, Any], queried_cnpj: str) -> CompanyData:
    establishment = payload.get("estabelecimento")
    if not isinstance(establishment, dict):
        raise CnpjWsInvalidResponse("Missing estabelecimento in CNPJ.ws response", 200)
    returned_cnpj = establishment.get("cnpj")
    if not isinstance(returned_cnpj, str) or returned_cnpj != queried_cnpj:
        raise CnpjWsInvalidResponse("CNPJ.ws returned a divergent CNPJ", 200)

    razao_social = _optional_text(payload.get("razao_social"), "razao_social")
    email = _optional_text(establishment.get("email"), "estabelecimento.email")
    telefone = _phone(establishment.get("ddd1"), establishment.get("telefone1"))
    if telefone is None:
        telefone = _phone(establishment.get("ddd2"), establishment.get("telefone2"))
    return CompanyData(razao_social=razao_social, telefone=telefone, email=email)


def _optional_text(value: Any, field: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise CnpjWsInvalidResponse(f"Unexpected {field} in CNPJ.ws response", 200)


def _phone(ddd: Any, number: Any) -> str | None:
    if ddd is None and number is None:
        return None
    if not isinstance(ddd, str) or not isinstance(number, str):
        raise CnpjWsInvalidResponse("Unexpected phone fields in CNPJ.ws response", 200)
    digits = re.sub(r"\D", "", ddd + number)
    return digits or None
