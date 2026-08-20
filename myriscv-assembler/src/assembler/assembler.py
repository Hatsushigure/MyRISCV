from pathlib import Path
from typing import TextIO

from assembler.assembly_error import AssemblyError
from assembler.instruction_error import InstructionError
from assembler.isa_processor import IsaProcessor


class Assembler:
    _isa_processor: IsaProcessor

    def __init__(self, isa_path: Path) -> None:
        self._isa_processor = IsaProcessor(isa_path)

    def assembly(self, code: TextIO) -> bytes:
        result: bytes = b""
        for line_number, line in enumerate(code, start=1):
            line = line.rstrip("\r\n")
            instruction_text = line.partition(";")[0]
            if not instruction_text.strip():
                continue
            try:
                result += self._isa_processor.generate_instruction(instruction_text)
            except InstructionError as error:
                column = len(instruction_text) - len(instruction_text.lstrip()) + 1
                if error.source_offset is not None:
                    column = error.source_offset + 1
                raise AssemblyError(
                    str(error), line=line_number, column=column
                ) from error

        return result
