from typing import Annotated

from pydantic import AfterValidator, JsonValue, StringConstraints


def validate_database_text(value: str) -> str:
    if "\x00" in value or any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("Text must not contain null characters or unpaired Unicode surrogates")
    return value


def validate_parameters(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            validate_database_text(item)
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value


ConfigurationIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    AfterValidator(validate_database_text),
]
ConfigurationParameters = Annotated[dict[str, JsonValue], AfterValidator(validate_parameters)]
