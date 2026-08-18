import json
from pathlib import Path
from typing import Any, cast

from assembler.instruction import Instruction
from assembler.instruction_template import InstructionTemplate


class ISAProcessor:
    _registers: dict[str, int]
    _templates: dict[str, InstructionTemplate]
    _instructions: dict[str, Instruction]

    def __init__(self, isa_path: Path) -> None:
        self._registers = {}
        self._templates = {}
        self._instructions = {}

        with isa_path.open() as f:
            self._process(json.load(f))

    def _process(self, data: dict[str, Any]):
        registers = data.get("registers", None)
        if not isinstance(registers, dict):
            raise TypeError("Field 'registers' must be a map")

        registers = cast(dict[str, Any], registers)
        for reg_name, reg_val_str in registers.items():
            reg_val: int = 0
            try:
                reg_val = int(reg_val_str, base=2)
            except (TypeError, ValueError):
                raise TypeError(
                    "Register value must be a string containing binary integer"
                )

            self._registers[reg_name] = reg_val

        templates = data.get("templates", None)
        if not isinstance(templates, dict):
            raise TypeError("Field 'templates' should be a map")

        templates = cast(dict[str, Any], templates)
        for temp_name, temp_data in templates.items():
            if not isinstance(temp_data, dict):
                raise TypeError("Template definition must be a map")

            temp_data = cast(dict[str, Any], temp_data)
            self._templates[temp_name] = InstructionTemplate.from_dict(temp_data)

        instructions = data.get("instructions", None)
        if not isinstance(instructions, dict):
            raise TypeError("Field 'instructions' should be a map")

        instructions = cast(dict[str, Any], instructions)
        for inst_name, inst_def in instructions.items():
            if not isinstance(inst_def, dict):
                raise TypeError("Instruction definition should be a map")

            inst_def = cast(dict[str, Any], inst_def)
            self._instructions[inst_name] = Instruction.from_dict(inst_def)

    def generate_instruction(self, name: str, args: list[str]) -> bytes:
        name = name.lower()
        if name not in self._instructions:
            raise ValueError(f"Undefined instruction '{name}'")

        instruction = self._instructions[name]
        if instruction.template not in self._templates:
            raise ValueError(f"Undefined template '{instruction.template}'")

        template = self._templates[instruction.template]
        return instruction.generate_instruction(self._registers, template, args)
