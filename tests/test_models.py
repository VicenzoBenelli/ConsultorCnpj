from app.models import ConsultaCnpj, ConsultaJob, ExternalApiControl


def test_models_import_without_database_initialization() -> None:
    assert ConsultaJob.__tablename__ == "consulta_jobs"
    assert ConsultaCnpj.__tablename__ == "consulta_cnpjs"
    assert ExternalApiControl.__tablename__ == "external_api_control"

