from dataclasses import dataclass
from typing import Self

from assembler.enums.instruction_argument_type import InstructionArgumentType
from assembler.validation_error import ValidationError


@dataclass(frozen=True, slots=True, kw_only=True)
class InstructionArgument:
    type: InstructionArgumentType
    bits: int | None

    @classmethod
    def from_spec(cls, spec: str, *, path: str = "") -> Self:
        if spec == "reg":
            return cls(type=InstructionArgumentType.REGISTER, bits=None)

        bits = int(spec, base=10)
        if bits <= 0:
            raise ValidationError(path, "argument bit width must be positive")
        return cls(type=InstructionArgumentType.CONSTANT, bits=bits)
