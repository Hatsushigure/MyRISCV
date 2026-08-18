from dataclasses import dataclass
from typing import Any, Self, cast


@dataclass(frozen=True, slots=True, kw_only=True)
class InstructionSlice:
    source: str
    source_begin: int
    source_end: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        if "source" not in data:
            raise ValueError("Missing source in instruction slice")

        source = data["source"]
        if not isinstance(source, str):
            raise TypeError("Instruction slice source must be a string")

        source = cast(str, source)

        if "source_begin" not in data:
            raise ValueError("Missing source begin bit in instruction slice")

        source_begin = data["source_begin"]
        if not isinstance(source_begin, int) or source_begin < 0:
            raise TypeError(
                "Instruction slice source begin bit must be a non-negative integer"
            )

        source_begin = cast(int, source_begin)

        if "source_end" not in data:
            raise ValueError("Missing source end bit in instruction slice")

        source_end = data["source_end"]
        if not isinstance(source_end, int) or source_end - source_begin <= 0:
            raise TypeError(
                "Instruction slice source end bit must be a integer greater than begin bit"
            )

        source_end = cast(int, source_end)

        return cls(source=source, source_begin=source_begin, source_end=source_end)
