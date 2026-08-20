import math
from typing import Any, Self

from assembler.instruction_slice import InstructionSlice
from assembler.instruction_error import InstructionError
from assembler.validation import Validation
from assembler.validation_error import ValidationError


class InstructionTemplate:
    _arguments: dict[str, int]
    _output_bits: int
    _slices: list[InstructionSlice]

    def __repr__(self) -> str:
        return f"{self.__dict__}"

    @property
    def arguments(self) -> dict[str, int]:
        return self._arguments.copy()

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
                raise InstructionError(
                    f"0b{slice_source:b} is too big for arg {slice.source} (max {source_max_bits} bits)"
                )

            int_result |= (
                self._int_slice(slice_source, slice.source_begin, slice.source_end)
                << current_bit
            )
            current_bit += slice.source_end - slice.source_begin

        return int_result.to_bytes(math.ceil(self._output_bits / 8), "little")

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: str = "") -> Self:
        arguments_data = Validation.require_mapping(data, "arguments", path=path)
        arguments_path = Validation.field_path(path, "arguments")
        arguments: dict[str, int] = {}
        for arg_name, arg_value in arguments_data.items():
            arg_path = Validation.field_path(arguments_path, arg_name)
            arguments[arg_name] = Validation.require_positive_integer_value(
                arg_value, path=arg_path
            )

        output = Validation.require_mapping(data, "output", path=path)
        output_path = Validation.field_path(path, "output")
        output_bits = Validation.require_positive_integer(
            output, "bits", path=output_path
        )
        slices = Validation.require_list(output, "slices", path=output_path)
        slices_path = Validation.field_path(output_path, "slices")

        slices_result: list[InstructionSlice] = []
        slice_total_bits = 0
        for index, slice_data in enumerate(slices):
            slice_path = Validation.field_path(slices_path, index)
            slice_mapping = Validation.require_mapping_value(
                slice_data, path=slice_path
            )
            slice_result = InstructionSlice.from_dict(
                slice_mapping, path=slice_path
            )
            if slice_result.source not in arguments:
                raise ValidationError(
                    Validation.field_path(slice_path, "source"),
                    f"references undefined argument '{slice_result.source}'",
                )

            if slice_result.source_end > arguments[slice_result.source]:
                raise ValidationError(
                    Validation.field_path(slice_path, "source_end"),
                    "is out of source range",
                )

            slice_total_bits += slice_result.source_end - slice_result.source_begin
            slices_result.append(slice_result)

        if slice_total_bits != output_bits:
            raise ValidationError(
                slices_path, "total length must match output.bits"
            )

        result = cls()
        result._arguments = arguments
        result._output_bits = output_bits
        result._slices = slices_result
        return result
