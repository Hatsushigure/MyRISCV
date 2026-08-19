from dataclasses import dataclass
from typing import Any, Self

from assembler.enums.instruction_argument_type import InstructionArgumentType
from assembler.validation import Validation
from assembler.validation_error import ValidationError


@dataclass(frozen=True, slots=True, kw_only=True)
class InstructionArgument:
    type: InstructionArgumentType
    bits: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: str = "") -> Self:
        type_str = Validation.require_string(data, "type", path=path)
        try:
            type = InstructionArgumentType(type_str)
        except ValueError as error:
            raise ValidationError(
                Validation.field_path(path, "type"),
                "must be 'register' or 'constant'",
            ) from error

        if type == InstructionArgumentType.REGISTER:
            return cls(type=type, bits=None)

        bits = Validation.require_positive_integer(data, "bits", path=path)
        return cls(type=type, bits=bits)
