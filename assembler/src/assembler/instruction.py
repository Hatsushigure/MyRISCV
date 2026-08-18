from typing import Any, Self, cast

from assembler.enums.instruction_argument_type import InstructionArgumentType
from assembler.instruction_argument import InstructionArgument
from assembler.instruction_template import InstructionTemplate


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
    def from_dict(cls, data: dict[str, Any]) -> Self:
        arguments = data.get("arguments", None)
        if not isinstance(arguments, dict):
            raise TypeError("Field 'arguments' for instruction should be a map")

        arguments = cast(dict[str, Any], arguments)
        processed_arguments: dict[str, InstructionArgument] = {}
        for arg_name, arg_val in arguments.items():
            if not isinstance(arg_val, dict):
                raise TypeError("Instruction argument definition should be a map")

            arg_val = cast(dict[str, Any], arg_val)
            processed_arguments[arg_name] = InstructionArgument.from_dict(arg_val)

        template = data.get("template", None)
        if not isinstance(template, str):
            raise TypeError("Field 'template' for instruction should be a string")

        template = cast(str, template)

        template_binds = data.get("template_binds", None)
        if not isinstance(template_binds, dict):
            raise TypeError("Field 'template_binds' for instruction should be a map")

        template_binds = cast(dict[str, Any], template_binds)
        processed_template_binds: dict[str, str] = {}
        for arg_name, arg_source in template_binds.items():
            if not isinstance(arg_source, str):
                raise TypeError("Template bind source should be a string")

            arg_source = cast(str, arg_source)
            processed_template_binds[arg_name] = arg_source

        result = cls()
        result._arguments = processed_arguments
        result._template = template
        result._template_binds = template_binds
        return result

    def generate_instruction(
        self,
        register_mapping: dict[str, int],
        template: InstructionTemplate,
        args: list[str],
    ) -> bytes:
        if len(args) > len(self._arguments):
            raise ValueError(f"Redundent argument '{args[len(self._arguments)]}'")

        if len(args) < len(self._arguments):
            raise ValueError(
                f"Missing argument '{list(self._arguments.keys())[len(args)]}'"
            )

        processed_args: dict[str, int] = {}
        for (arg_name, arg_definition), arg_str in zip(self._arguments.items(), args):
            if arg_definition.type == InstructionArgumentType.REGISTER:
                arg_str = arg_str.lower()
                if arg_str not in register_mapping:
                    raise ValueError(f"Unknown register '{arg_str}'")

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
                    raise ValueError(
                        f"Instruction argument '{arg_name}' should be an integral, but got '{arg_str}'"
                    )

                if arg_base == 10 and (
                    arg_val < -(1 << (arg_definition.bits - 1))
                    or arg_val > ((1 << (arg_definition.bits - 1)) - 1)
                ):
                    raise ValueError(
                        f"{arg_val} out of range for instruction argument "
                        f"'{arg_name}' (max {arg_definition.bits} bits)"
                    )
                elif arg_base in (2, 16) and (
                    arg_val < 0 or arg_val > ((1 << arg_definition.bits) - 1)
                ):
                    raise ValueError(
                        f"0x{arg_val:X} out of range for instruction argument "
                        f"'{arg_name}' (max {arg_definition.bits} bits)"
                    )

                arg_val = ((1 << arg_definition.bits) + arg_val) & (
                    (1 << arg_definition.bits) - 1
                )
                processed_args[arg_name] = arg_val

        template_args: dict[str, int] = {}
        for arg_name, arg_source in self._template_binds.items():
            arg_val: int = 0
            if arg_source not in processed_args:
                arg_val = int(arg_source, base=2)
            else:
                arg_val = processed_args[arg_source]
            template_args[arg_name] = arg_val

        return template.generate_instruction(template_args)
