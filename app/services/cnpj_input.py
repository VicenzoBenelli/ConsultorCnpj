import re
from dataclasses import dataclass


RAW_CNPJ_PATTERN = re.compile(r"^\d{14}$")
MASKED_CNPJ_PATTERN = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
SEPARATOR_PATTERN = re.compile(r"[,;\s]+")


@dataclass(frozen=True)
class BatchError:
    code: str
    message: str
    position: int | None = None
    value: str | None = None

    def as_dict(self) -> dict[str, str | int]:
        result: dict[str, str | int] = {"code": self.code, "message": self.message}
        if self.position is not None:
            result["position"] = self.position
        if self.value is not None:
            result["value"] = self.value
        return result


class CnpjBatchValidationError(ValueError):
    def __init__(self, errors: list[BatchError]) -> None:
        self.errors = errors
        super().__init__("Invalid CNPJ batch")


def is_valid_cnpj(cnpj: str) -> bool:
    if not RAW_CNPJ_PATTERN.fullmatch(cnpj) or len(set(cnpj)) == 1:
        return False

    first_weights = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    second_weights = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

    first_digit = _verification_digit(cnpj[:12], first_weights)
    second_digit = _verification_digit(cnpj[:12] + str(first_digit), second_weights)
    return cnpj[12:] == f"{first_digit}{second_digit}"


def parse_cnpj_batch(raw_cnpjs: str, max_cnpjs: int) -> list[str]:
    tokens = [token for token in SEPARATOR_PATTERN.split(raw_cnpjs.strip()) if token]
    if not tokens:
        raise CnpjBatchValidationError(
            [BatchError(code="EMPTY_BATCH", message="Provide at least one CNPJ.")]
        )

    normalized: list[str] = []
    errors: list[BatchError] = []
    for position, token in enumerate(tokens, start=1):
        cnpj = _normalize_token(token)
        if cnpj is None:
            errors.append(
                BatchError("INVALID_FORMAT", "CNPJ must have 14 digits or use the complete standard mask.", position, token)
            )
        elif not is_valid_cnpj(cnpj):
            errors.append(BatchError("INVALID_CHECK_DIGITS", "CNPJ check digits are invalid.", position, token))
        else:
            normalized.append(cnpj)

    if errors:
        raise CnpjBatchValidationError(errors)

    unique_cnpjs = list(dict.fromkeys(normalized))
    if len(unique_cnpjs) > max_cnpjs:
        raise CnpjBatchValidationError(
            [
                BatchError(
                    "MAX_CNPJS_EXCEEDED",
                    f"A job can contain at most {max_cnpjs} unique CNPJs.",
                )
            ]
        )
    return unique_cnpjs


def _normalize_token(token: str) -> str | None:
    if RAW_CNPJ_PATTERN.fullmatch(token):
        return token
    if MASKED_CNPJ_PATTERN.fullmatch(token):
        return token.replace(".", "").replace("/", "").replace("-", "")
    return None


def _verification_digit(value: str, weights: tuple[int, ...]) -> int:
    remainder = sum(int(digit) * weight for digit, weight in zip(value, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder
