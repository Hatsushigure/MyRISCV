from dataclasses import dataclass
from typing import Any, Self, cast

from assembler.enums.instruction_argument_type import InstructionArgumentType


@dataclass(frozen=True, slots=True, kw_only=True)
class InstructionArgument:
    type: InstructionArgumentType
    bits: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        if "type" not in data:
            raise ValueError("Missing field 'type' for instruction argument")

        type_str = data["type"]
        type: InstructionArgumentType = InstructionArgumentType.REGISTER
        try:
            type = InstructionArgumentType(type_str)
        except ValueError:
            raise ValueError(
                "Instruction argument type must be 'register' or ''constant"
            )

        if type == InstructionArgumentType.REGISTER:
            return cls(type=type, bits=None)

        if "bits" not in data:
            raise ValueError(
                "Missing field 'bits' for constant type instruction argument"
            )

        bits = data["bits"]
        if not isinstance(bits, int) or bits <= 0:
            raise ValueError("Constant instruction argument must be a positive integer")

        bits = cast(int, bits)
        return cls(type=type, bits=bits)
