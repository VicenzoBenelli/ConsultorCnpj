import pytest

from app.services.cnpj_input import CnpjBatchValidationError, is_valid_cnpj, parse_cnpj_batch


VALID_CNPJ = "12345678000195"
VALID_MASKED_CNPJ = "12.345.678/0001-95"
SECOND_VALID_CNPJ = "04252011000110"


def test_accepts_raw_and_masked_cnpj() -> None:
    assert parse_cnpj_batch(f"{VALID_CNPJ} {VALID_MASKED_CNPJ}", 500) == [VALID_CNPJ]


@pytest.mark.parametrize("value", ["123", "12.345.678/0001", "12.345.678/0001-9A", "abc12345678000195", "12.345.678/0001-95!"])
def test_rejects_malformed_tokens(value: str) -> None:
    with pytest.raises(CnpjBatchValidationError) as raised:
        parse_cnpj_batch(value, 500)

    assert raised.value.errors[0].code == "INVALID_FORMAT"
    assert raised.value.errors[0].position == 1


def test_rejects_space_inside_cnpj() -> None:
    with pytest.raises(CnpjBatchValidationError) as raised:
        parse_cnpj_batch("12345678 000195", 500)

    assert len(raised.value.errors) == 2


def test_validates_both_check_digits_and_repeated_sequences() -> None:
    assert is_valid_cnpj(VALID_CNPJ)
    assert not is_valid_cnpj("12345678000105")
    assert not is_valid_cnpj("12345678000190")
    assert not is_valid_cnpj("00000000000000")


def test_parses_all_supported_separators_and_ignores_empty_tokens() -> None:
    raw = f"\n{VALID_CNPJ},;\t{SECOND_VALID_CNPJ}  \n"

    assert parse_cnpj_batch(raw, 500) == [VALID_CNPJ, SECOND_VALID_CNPJ]


@pytest.mark.parametrize("value", ["", " \n,;\t "])
def test_rejects_empty_batch(value: str) -> None:
    with pytest.raises(CnpjBatchValidationError) as raised:
        parse_cnpj_batch(value, 500)

    assert raised.value.errors[0].code == "EMPTY_BATCH"


def test_reports_every_invalid_token_before_persisting() -> None:
    with pytest.raises(CnpjBatchValidationError) as raised:
        parse_cnpj_batch(f"invalid {VALID_CNPJ} 12345678000190", 500)

    assert [(error.code, error.position) for error in raised.value.errors] == [
        ("INVALID_FORMAT", 1),
        ("INVALID_CHECK_DIGITS", 3),
    ]


def test_deduplicates_after_validation_and_preserves_first_order() -> None:
    assert parse_cnpj_batch(f"{VALID_CNPJ} {SECOND_VALID_CNPJ} {VALID_MASKED_CNPJ}", 500) == [
        VALID_CNPJ,
        SECOND_VALID_CNPJ,
    ]


def test_applies_limit_after_deduplication() -> None:
    assert parse_cnpj_batch(VALID_CNPJ, 2) == [VALID_CNPJ]
    assert parse_cnpj_batch(f"{VALID_CNPJ} {SECOND_VALID_CNPJ}", 2) == [VALID_CNPJ, SECOND_VALID_CNPJ]
    assert parse_cnpj_batch(f"{VALID_CNPJ} {VALID_MASKED_CNPJ}", 1) == [VALID_CNPJ]

    with pytest.raises(CnpjBatchValidationError) as raised:
        parse_cnpj_batch(f"{VALID_CNPJ} {SECOND_VALID_CNPJ}", 1)

    assert raised.value.errors[0].code == "MAX_CNPJS_EXCEEDED"
