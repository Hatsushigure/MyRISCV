from typing import Any, Self

from assembler.enums.instruction_argument_type import InstructionArgumentType
from assembler.instruction_error import InstructionError
from assembler.instruction_pattern import InstructionPattern
from assembler.instruction_template import InstructionTemplate
from assembler.validation import Validation
from assembler.validation_error import ValidationError


class Instruction:
    _pattern: InstructionPattern
    _template: str
    _template_binds: dict[str, str]

    def __repr__(self) -> str:
        return f"{self.__dict__}"

    @property
    def template(self) -> str:
        return self._template

    @property
    def name(self) -> str:
        return self._pattern.name

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: str = "") -> Self:
        template = Validation.require_string(data, "template", path=path)
        pattern_path = Validation.field_path(path, "pattern")
        pattern = InstructionPattern(
            Validation.require_string(data, "pattern", path=path),
            path=pattern_path,
        )
        template_binds = Validation.require_mapping(
            data, "template_binds", path=path
        )
        template_binds_path = Validation.field_path(path, "template_binds")
        processed_template_binds: dict[str, str] = {}
        for arg_name, arg_source in template_binds.items():
            bind_path = Validation.field_path(template_binds_path, arg_name)
            processed_template_binds[arg_name] = Validation.require_string_value(
                arg_source, path=bind_path
            )

        result = cls()
        result._pattern = pattern
        result._template = template
        result._template_binds = processed_template_binds
        return result

    def validate_template(
        self, template: InstructionTemplate, *, path: str = ""
    ) -> None:
        binds_path = Validation.field_path(path, "template_binds")
        template_argument_bits = template.arguments
        template_arguments = set(template_argument_bits)
        bind_arguments = set(self._template_binds)
        missing = template_arguments - bind_arguments
        if missing:
            name = sorted(missing)[0]
            raise ValidationError(
                binds_path, f"does not bind template argument '{name}'"
            )
        redundant = bind_arguments - template_arguments
        if redundant:
            name = sorted(redundant)[0]
            raise ValidationError(
                Validation.field_path(binds_path, name),
                f"binds undefined template argument '{name}'",
            )

        pattern_arguments = self._pattern.arguments
        for name, source in self._template_binds.items():
            if source in pattern_arguments:
                argument = pattern_arguments[source]
                target_bits = template_argument_bits[name]
                if argument.bits is not None and argument.bits > target_bits:
                    raise ValidationError(
                        Validation.field_path(binds_path, name),
                        f"binds {argument.bits}-bit argument '{source}' to "
                        f"{target_bits}-bit template argument '{name}'",
                    )
                continue
            try:
                value = int(source, base=2)
            except ValueError as error:
                raise ValidationError(
                    Validation.field_path(binds_path, name),
                    "must reference an instruction argument or contain a "
                    f"binary integer, got '{source}'",
                ) from error
            bits = template_argument_bits[name]
            if value < 0 or value >= (1 << bits):
                raise ValidationError(
                    Validation.field_path(binds_path, name),
                    "binary integer is too large for template argument "
                    f"'{name}' ({bits} bits)",
                )

    def generate_instruction(
        self,
        register_mapping: dict[str, int],
        template: InstructionTemplate,
        source: str,
    ) -> bytes:
        arguments = self._pattern.arguments
        matched_args = self._pattern.match(source)
        processed_args: dict[str, int] = {}
        for arg_name, arg_definition in arguments.items():
            arg_str, source_offset = matched_args[arg_name]
            if arg_definition.type == InstructionArgumentType.REGISTER:
                arg_str = arg_str.lower()
                if arg_str not in register_mapping:
                    raise InstructionError(
                        f"Unknown register '{arg_str}'", source_offset=source_offset
                    )

                arg_val = register_mapping[arg_str]
                processed_args[arg_name] = arg_val
            else:
                arg_base = 10
                assert arg_definition.bits is not None
                unsigned_arg = arg_str.lower().lstrip("+-")
                if unsigned_arg.startswith("0b"):
                    arg_base = 2
                elif unsigned_arg.startswith("0x"):
                    arg_base = 16

                try:
                    arg_val = int(arg_str, base=arg_base)
                except (TypeError, ValueError):
                    raise InstructionError(
                        f"Instruction argument '{arg_name}' should be an "
                        f"integral, but got '{arg_str}'",
                        source_offset=source_offset,
                    )

                if arg_base == 10 and (
                    arg_val < -(1 << (arg_definition.bits - 1))
                    or arg_val > ((1 << (arg_definition.bits - 1)) - 1)
                ):
                    raise InstructionError(
                        f"{arg_val} out of range for instruction argument "
                        f"'{arg_name}' (max {arg_definition.bits} bits)",
                        source_offset=source_offset,
                    )
                elif arg_base in (2, 16) and (
                    arg_val < 0 or arg_val > ((1 << arg_definition.bits) - 1)
                ):
                    raise InstructionError(
                        f"0x{arg_val:X} out of range for instruction argument "
                        f"'{arg_name}' (max {arg_definition.bits} bits)",
                        source_offset=source_offset,
                    )

                arg_val = ((1 << arg_definition.bits) + arg_val) & (
                    (1 << arg_definition.bits) - 1
                )
                processed_args[arg_name] = arg_val

        template_args: dict[str, int] = {}
        for arg_name, arg_source in self._template_binds.items():
            arg_val: int = 0
            if arg_source not in processed_args:
                try:
                    arg_val = int(arg_source, base=2)
                except (TypeError, ValueError) as error:
                    raise InstructionError(
                        f"Template bind '{arg_name}' must be a binary integer, "
                        f"but got '{arg_source}'"
                    ) from error
            else:
                arg_val = processed_args[arg_source]
            template_args[arg_name] = arg_val

        return template.generate_instruction(template_args)
