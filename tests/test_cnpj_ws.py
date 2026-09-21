import httpx2
import pytest

from app.services.cnpj_ws import (
    CnpjWsClient,
    CnpjWsInvalidResponse,
    CnpjWsTimeout,
    extract_company_data,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: object = None, content_type: str = "application/json") -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": content_type}

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeClient:
    def __init__(self, result: FakeResponse | Exception) -> None:
        self.result = result

    def get(self, path: str, headers: dict[str, str]) -> FakeResponse:
        assert path == "/cnpj/12345678000195"
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def close(self) -> None:
        pass


def client_with(result: FakeResponse | Exception) -> CnpjWsClient:
    return CnpjWsClient(
        "https://example.test",
        15,
        client_factory=lambda: FakeClient(result),
    )


def payload(**establishment: object) -> dict[str, object]:
    return {
        "razao_social": "Empresa Teste",
        "estabelecimento": {"cnpj": "12345678000195", **establishment},
    }


def test_fetches_200_and_extracts_primary_phone() -> None:
    response = client_with(FakeResponse(200, payload(ddd1="83", telefone1="3333-4444", email="a@example.com"))).fetch(
        "12345678000195"
    )
    company = extract_company_data(response.payload or {}, "12345678000195")

    assert company.telefone == "8333334444"
    assert company.email == "a@example.com"


def test_extracts_fallback_or_null_phone_and_email() -> None:
    fallback = extract_company_data(payload(ddd2="11", telefone2="99999-0000", email=None), "12345678000195")
    absent = extract_company_data(payload(email=None), "12345678000195")

    assert fallback.telefone == "11999990000"
    assert absent.telefone is None
    assert absent.email is None


def test_maps_non_success_statuses_and_429_details() -> None:
    response_404 = client_with(FakeResponse(404, {"detalhes": "not found"})).fetch("12345678000195")
    response_429 = client_with(FakeResponse(429, {"detalhes": "wait"})).fetch("12345678000195")
    response_500 = client_with(FakeResponse(500, {})).fetch("12345678000195")

    assert response_404.status_code == 404
    assert response_429.details == "wait"
    assert response_500.status_code == 500


@pytest.mark.parametrize(
    "result",
    [
        FakeResponse(200, {}, "text/html"),
        FakeResponse(200, ValueError("bad json")),
        FakeResponse(200, []),
    ],
)
def test_rejects_invalid_success_response(result: FakeResponse) -> None:
    with pytest.raises(CnpjWsInvalidResponse):
        client_with(result).fetch("12345678000195")


def test_rejects_invalid_structure_and_divergent_cnpj() -> None:
    with pytest.raises(CnpjWsInvalidResponse):
        extract_company_data({}, "12345678000195")
    with pytest.raises(CnpjWsInvalidResponse):
        extract_company_data(payload(cnpj="00000000000000"), "12345678000195")


def test_maps_timeout() -> None:
    with pytest.raises(CnpjWsTimeout):
        client_with(httpx2.TimeoutException("timeout")).fetch("12345678000195")
