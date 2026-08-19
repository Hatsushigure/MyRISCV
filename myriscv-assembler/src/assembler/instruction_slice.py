from dataclasses import dataclass
from typing import Any, Self

from assembler.validation import Validation
from assembler.validation_error import ValidationError


@dataclass(frozen=True, slots=True, kw_only=True)
class InstructionSlice:
    source: str
    source_begin: int
    source_end: int

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: str = "") -> Self:
        source = Validation.require_string(data, "source", path=path)
        source_begin = Validation.require_integer(data, "source_begin", path=path)
        if source_begin < 0:
            raise ValidationError(
                Validation.field_path(path, "source_begin"), "must be non-negative"
            )

        source_end = Validation.require_integer(data, "source_end", path=path)
        if source_end <= source_begin:
            raise ValidationError(
                Validation.field_path(path, "source_end"),
                "must be greater than source_begin",
            )

        return cls(source=source, source_begin=source_begin, source_end=source_end)
