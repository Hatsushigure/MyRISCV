import math
from typing import Any, Self, cast

from assembler.instruction_slice import InstructionSlice


class InstructionTemplate:
    _arguments: dict[str, int]
    _output_bits: int
    _slices: list[InstructionSlice]

    def __repr__(self) -> str:
        return f"{self.__dict__}"

    def _int_slice(self, val: int, begin: int, end: int) -> int:
        return (val >> begin) & ((1 << (end - begin)) - 1)

    def generate_instruction(self, args: dict[str, int]) -> bytes:
        int_result: int = 0
        current_bit = 0

        for slice in self._slices:
            assert slice.source in args
            slice_source = args[slice.source]
            source_max_bits = self._arguments[slice.source]
            if slice_source >= (1 << source_max_bits):
                raise ValueError(
                    f"0b{slice_source:b} is too big for arg {slice.source} (max {source_max_bits} bits)"
                )

            int_result |= (
                self._int_slice(slice_source, slice.source_begin, slice.source_end)
                << current_bit
            )
            current_bit += slice.source_end - slice.source_begin

        return int_result.to_bytes(math.ceil(self._output_bits / 8), "little")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        if "arguments" not in data:
            raise ValueError("Missing arguments in instruction template")

        arguments = data["arguments"]
        if not isinstance(arguments, dict):
            raise TypeError("Instruction template arguments must be a map")

        arguments = cast(dict[str, Any], arguments)
        for arg_name, arg_val in arguments.items():
            if not isinstance(arg_val, int) or arg_val <= 0:
                raise TypeError(
                    "Instruction template argument length must be a positive integer"
                )

            arg_val = cast(int, arg_val)
            arguments[arg_name] = arg_val

        if "output" not in data:
            raise ValueError("Missing output definition in instruction template")

        output = data["output"]
        if not isinstance(output, dict):
            raise TypeError("Instruction template output definition must be a map")

        output = cast(dict[str, Any], output)
        if "bits" not in output:
            raise ValueError("Missing output length in instruction template")

        output_bits = output["bits"]
        if not isinstance(output_bits, int) or output_bits <= 0:
            raise TypeError(
                "Instruction template output length must be a positive integral"
            )

        output_bits = cast(int, output_bits)

        if "slices" not in output:
            raise ValueError("Missing slice list in instruction template")

        slices = output["slices"]
        if not isinstance(slices, list):
            raise TypeError("Instruction template slice list must be a list")

        slices = cast(list[Any], slices)
        slices_result: list[InstructionSlice] = []
        slice_total_bits: int = 0
        for s in slices:
            if not isinstance(s, dict):
                raise TypeError("Slice definition must be a map")

            s = cast(dict[str, Any], s)
            s_result = InstructionSlice.from_dict(s)
            if s_result.source not in arguments:
                raise ValueError(f"Undefined slice source '{s_result.source}")

            if s_result.source_end > arguments[s_result.source]:
                raise ValueError("Slice end bit out of source range")

            slice_total_bits += s_result.source_end - s_result.source_begin
            slices_result.append(s_result)
        if slice_total_bits != output_bits:
            raise ValueError(
                "Mismatched slice total length and output length in instruction template"
            )

        result = cls()
        result._arguments = arguments
        result._output_bits = output_bits
        result._slices = slices_result
        return result
