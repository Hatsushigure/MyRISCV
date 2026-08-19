from typing import Any, Self

from assembler.enums.instruction_argument_type import InstructionArgumentType
from assembler.instruction_argument import InstructionArgument
from assembler.instruction_error import InstructionError
from assembler.instruction_template import InstructionTemplate
from assembler.validation import Validation


class Instruction:
    _arguments: dict[str, InstructionArgument]
    _template: str
    _template_binds: dict[str, str]

    def __repr__(self) -> str:
        return f"{self.__dict__}"

    @property
    def template(self) -> str:
        return self._template

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: str = "") -> Self:
        arguments = Validation.require_mapping(data, "arguments", path=path)
        arguments_path = Validation.field_path(path, "arguments")
        processed_arguments: dict[str, InstructionArgument] = {}
        for arg_name, arg_val in arguments.items():
            arg_path = Validation.field_path(arguments_path, arg_name)
            arg_data = Validation.require_mapping_value(arg_val, path=arg_path)
            processed_arguments[arg_name] = InstructionArgument.from_dict(
                arg_data, path=arg_path
            )

        template = Validation.require_string(data, "template", path=path)
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
        result._arguments = processed_arguments
        result._template = template
        result._template_binds = processed_template_binds
        return result

    def generate_instruction(
        self,
        register_mapping: dict[str, int],
        template: InstructionTemplate,
        args: list[str],
    ) -> bytes:
        if len(args) > len(self._arguments):
            raise InstructionError(
                f"Redundant argument '{args[len(self._arguments)]}'",
                argument_index=len(self._arguments),
            )

        if len(args) < len(self._arguments):
            raise InstructionError(
                f"Missing argument '{list(self._arguments.keys())[len(args)]}'",
                argument_index=len(args),
            )

        processed_args: dict[str, int] = {}
        for (arg_name, arg_definition), arg_str in zip(self._arguments.items(), args):
            if arg_definition.type == InstructionArgumentType.REGISTER:
                arg_str = arg_str.lower()
                if arg_str not in register_mapping:
                    raise InstructionError(
                        f"Unknown register '{arg_str}'", argument_index=len(processed_args)
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
                        f"Instruction argument '{arg_name}' should be an integral, but got '{arg_str}'",
                        argument_index=len(processed_args),
                    )

                if arg_base == 10 and (
                    arg_val < -(1 << (arg_definition.bits - 1))
                    or arg_val > ((1 << (arg_definition.bits - 1)) - 1)
                ):
                    raise InstructionError(
                        f"{arg_val} out of range for instruction argument "
                        f"'{arg_name}' (max {arg_definition.bits} bits)",
                        argument_index=len(processed_args),
                    )
                elif arg_base in (2, 16) and (
                    arg_val < 0 or arg_val > ((1 << arg_definition.bits) - 1)
                ):
                    raise InstructionError(
                        f"0x{arg_val:X} out of range for instruction argument "
                        f"'{arg_name}' (max {arg_definition.bits} bits)",
                        argument_index=len(processed_args),
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
