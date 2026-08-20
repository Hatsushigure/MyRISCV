import json
import re
from pathlib import Path
from typing import Any

from assembler.instruction_error import InstructionError
from assembler.instruction import Instruction
from assembler.instruction_template import InstructionTemplate
from assembler.validation import Validation
from assembler.validation_error import ValidationError


class IsaProcessor:
    _registers: dict[str, int]
    _templates: dict[str, InstructionTemplate]
    _instructions: dict[str, Instruction]

    def __init__(self, isa_path: Path) -> None:
        self._registers = {}
        self._templates = {}
        self._instructions = {}

        with isa_path.open(encoding="utf-8") as f:
            self._process(json.load(f))

    def _process(self, data: Any) -> None:
        root = Validation.require_mapping_value(data, path="")
        registers = Validation.require_mapping(root, "registers", path="")
        for reg_name, reg_val_str in registers.items():
            reg_path = Validation.field_path("registers", reg_name)
            reg_val_text = Validation.require_string_value(
                reg_val_str, path=reg_path
            )
            try:
                reg_val = int(reg_val_text, base=2)
            except ValueError as error:
                raise ValidationError(
                    reg_path, "must contain a binary integer"
                ) from error

            self._registers[reg_name] = reg_val

        templates = Validation.require_mapping(root, "templates", path="")
        for temp_name, temp_data in templates.items():
            template_path = Validation.field_path("templates", temp_name)
            template_mapping = Validation.require_mapping_value(
                temp_data, path=template_path
            )
            self._templates[temp_name] = InstructionTemplate.from_dict(
                template_mapping, path=template_path
            )

        instructions = Validation.require_list(root, "instructions", path="")
        for index, inst_def in enumerate(instructions):
            instruction_path = Validation.field_path("instructions", index)
            instruction_mapping = Validation.require_mapping_value(
                inst_def, path=instruction_path
            )
            instruction = Instruction.from_dict(
                instruction_mapping, path=instruction_path
            )
            if instruction.template not in self._templates:
                raise ValidationError(
                    Validation.field_path(instruction_path, "template"),
                    f"references undefined template '{instruction.template}'",
                )
            instruction.validate_template(
                self._templates[instruction.template], path=instruction_path
            )
            if instruction.name in self._instructions:
                raise ValidationError(
                    Validation.field_path(instruction_path, "pattern"),
                    f"duplicates instruction name '{instruction.name}'",
                )
            self._instructions[instruction.name] = instruction

    def generate_instruction(self, source: str) -> bytes:
        match = re.match(r"\s*(\S+)", source)
        name = match.group(1).lower() if match is not None else ""
        if name not in self._instructions:
            raise InstructionError(f"Undefined instruction '{name}'")

        instruction = self._instructions[name]
        template = self._templates[instruction.template]
        return instruction.generate_instruction(self._registers, template, source)
